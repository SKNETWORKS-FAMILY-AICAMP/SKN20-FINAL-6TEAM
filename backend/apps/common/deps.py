from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only
import jwt
from jwt.exceptions import InvalidTokenError
from config.database import get_db
from config.settings import settings
from apps.auth.token_blacklist import is_blacklisted
from .models import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        jti = payload.get("jti")
        if jti and is_blacklisted(jti, db):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

        user_email: str | None = payload.get("sub")
        if user_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    stmt = (
        select(User)
        .options(
            load_only(
                User.user_id,
                User.google_email,
                User.username,
                User.type_code,
                User.use_yn,
            )
        )
        .where(User.google_email == user_email, User.use_yn == True)
    )
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """인증된 사용자를 반환하거나 게스트이면 None을 반환합니다."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        jti = payload.get("jti")
        if jti and is_blacklisted(jti, db):
            return None
        user_email = payload.get("sub")
        if not user_email:
            return None
        stmt = (
            select(User)
            .options(
                load_only(
                    User.user_id,
                    User.google_email,
                    User.username,
                    User.type_code,
                    User.use_yn,
                )
            )
            .where(User.google_email == user_email, User.use_yn == True)
        )
        return db.execute(stmt).scalar_one_or_none()
    except InvalidTokenError:
        return None
