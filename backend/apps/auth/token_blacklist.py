from datetime import datetime, timezone

from sqlalchemy import select, update

from config.database import SessionLocal
from apps.common.models import TokenBlacklist


def blacklist_token(jti: str, exp: datetime) -> None:
    """토큰을 블랙리스트에 등록합니다."""
    db = SessionLocal()
    try:
        stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        existing = db.execute(stmt).scalar_one_or_none()
        if not existing:
            entry = TokenBlacklist(jti=jti, expires_at=exp)
            db.add(entry)
            db.commit()
    finally:
        db.close()


def is_blacklisted(jti: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인합니다."""
    db = SessionLocal()
    try:
        stmt = select(TokenBlacklist).where(
            TokenBlacklist.jti == jti,
            TokenBlacklist.use_yn == True,
        )
        return db.execute(stmt).scalar_one_or_none() is not None
    finally:
        db.close()


def cleanup_expired() -> int:
    """만료된 블랙리스트 항목을 비활성화합니다."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        stmt = (
            update(TokenBlacklist)
            .where(TokenBlacklist.expires_at < now, TokenBlacklist.use_yn == True)
            .values(use_yn=False)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount
    finally:
        db.close()
