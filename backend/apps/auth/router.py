from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt

from config.database import get_db
from config.settings import settings
from apps.common.models import User
from .schemas import TokenResponse, TestLoginResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


@router.get("/google")
async def login_google():
    """
    Google OAuth2 로그인 시작
    실제 구현 전까지는 테스트 로그인 사용 안내
    """
    return {
        "message": "Google OAuth2 is not implemented yet. Use /auth/test-login instead.",
        "test_login_url": "/auth/test-login"
    }


@router.post("/test-login", response_model=TestLoginResponse)
async def test_login(db: Session = Depends(get_db)):
    """
    테스트 로그인 - Google 로그인 구현 전까지 사용
    자동으로 test@bizmate.com 계정으로 로그인
    """
    test_email = "test@bizmate.com"
    test_username = "테스트 사용자"

    # 테스트 사용자 조회 또는 생성
    user = db.query(User).filter(User.google_email == test_email).first()
    if not user:
        user = User(
            google_email=test_email,
            username=test_username,
            type_code="U001",  # 예비창업자
            birth=datetime(1990, 1, 1)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": user.google_email})

    return TestLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            user_id=user.user_id,
            google_email=user.google_email,
            username=user.username,
            type_code=user.type_code
        )
    )


@router.post("/logout")
async def logout():
    """
    로그아웃 - 클라이언트에서 토큰 삭제 필요
    """
    return {"message": "Successfully logged out. Please delete the token on client side."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    db: Session = Depends(get_db)
):
    """
    토큰 갱신 (현재 미구현 - 새 로그인 필요)
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not implemented. Please login again."
    )
