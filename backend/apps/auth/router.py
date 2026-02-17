import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger("auth")
limiter = Limiter(key_func=get_remote_address)

from config.database import get_db
from config.settings import settings
from apps.common.models import User
from apps.common.deps import get_current_user
from .services import verify_google_token
from .schemas import LoginResponse, TestLoginRequest, UserInfo, GoogleLoginRequest
from .token_blacklist import blacklist_token, is_blacklisted

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        "access_token", path="/",
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
    )
    response.delete_cookie(
        "refresh_token", path="/auth",
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
    )


def _build_user_info(user: User) -> UserInfo:
    return UserInfo(
        user_id=user.user_id,
        google_email=user.google_email,
        username=user.username,
        type_code=user.type_code,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/google", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login_google(
    request: Request,
    body: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Google OAuth2 로그인 — HttpOnly 쿠키로 토큰 발급"""
    id_info = verify_google_token(body.id_token)
    email = id_info.get("email")
    name = id_info.get("name", "Google User")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google 토큰에서 이메일을 찾을 수 없습니다",
        )

    if not id_info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google에서 이메일 인증이 완료되지 않았습니다",
        )

    user = db.execute(select(User).where(User.google_email == email)).scalar_one_or_none()
    if user and not user.use_yn:
        logger.warning("LOGIN_BLOCKED email=%s reason=deactivated", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )
    if not user:
        user = User(
            google_email=email,
            username=name,
            type_code="U0000002",
            birth=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(data={"sub": user.google_email})
    refresh_token = create_refresh_token(data={"sub": user.google_email})
    set_auth_cookies(response, access_token, refresh_token)

    logger.info("LOGIN_SUCCESS email=%s user_id=%d", user.google_email, user.user_id)
    return LoginResponse(user=_build_user_info(user))


@router.post("/test-login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def test_login(
    request: Request,
    response: Response,
    body: TestLoginRequest | None = None,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """테스트 로그인 — ENABLE_TEST_LOGIN=true일 때만 동작"""
    if not settings.ENABLE_TEST_LOGIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    test_email = body.email if body and body.email else "test@bizi.com"
    test_username = body.username if body and body.username else "테스트 사용자"
    test_type_code = body.type_code if body and body.type_code else "U0000002"

    user = db.execute(select(User).where(User.google_email == test_email)).scalar_one_or_none()
    if not user:
        user = User(
            google_email=test_email,
            username=test_username,
            type_code=test_type_code,
            birth=datetime(1990, 1, 1),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(data={"sub": user.google_email})
    refresh_token = create_refresh_token(data={"sub": user.google_email})
    set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(user=_build_user_info(user))


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """로그아웃 — 토큰 블랙리스트 등록 + 쿠키 삭제"""
    # access_token 블랙리스트 등록
    access_raw = request.cookies.get("access_token")
    if access_raw:
        try:
            payload = jwt.decode(access_raw, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            jti = payload.get("jti")
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            if jti:
                blacklist_token(jti, exp, db)
        except InvalidTokenError:
            pass

    # refresh_token 블랙리스트 등록
    refresh_raw = request.cookies.get("refresh_token")
    if refresh_raw:
        try:
            payload = jwt.decode(refresh_raw, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            jti = payload.get("jti")
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            if jti:
                blacklist_token(jti, exp, db)
        except InvalidTokenError:
            pass

    clear_auth_cookies(response)
    logger.info("LOGOUT user_id=%d", current_user.user_id)
    return {"message": "로그아웃되었습니다"}


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Refresh Token으로 새 토큰 쌍 발급 (Token Rotation)"""
    refresh_raw = request.cookies.get("refresh_token")
    if not refresh_raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="리프레시 토큰이 없습니다")

    try:
        payload = jwt.decode(refresh_raw, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 리프레시 토큰입니다")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰 유형입니다")

    jti = payload.get("jti")
    if jti and is_blacklisted(jti, db):
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다")

    email: str | None = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰 정보입니다")

    user = db.execute(select(User).where(User.google_email == email, User.use_yn == True)).scalar_one_or_none()
    if not user:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다")

    # 기존 refresh token 블랙리스트 등록 (rotation)
    if jti:
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        blacklist_token(jti, exp, db)

    new_access = create_access_token(data={"sub": email})
    new_refresh = create_refresh_token(data={"sub": email})
    set_auth_cookies(response, new_access, new_refresh)

    logger.info("TOKEN_REFRESH email=%s", email)
    return {"message": "토큰이 갱신되었습니다"}


@router.get("/me", response_model=LoginResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> LoginResponse:
    """현재 인증된 사용자 정보 반환 (페이지 새로고침 시 인증 복원용)"""
    return LoginResponse(user=_build_user_info(current_user))
