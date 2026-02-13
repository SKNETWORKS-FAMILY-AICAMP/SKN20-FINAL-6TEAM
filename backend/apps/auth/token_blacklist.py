from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.common.models import TokenBlacklist


def blacklist_token(jti: str, exp: datetime, db: Session) -> None:
    """토큰을 블랙리스트에 등록합니다."""
    stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
    existing = db.execute(stmt).scalar_one_or_none()
    if not existing:
        entry = TokenBlacklist(jti=jti, expires_at=exp)
        db.add(entry)
        db.commit()


def is_blacklisted(jti: str, db: Session) -> bool:
    """토큰이 블랙리스트에 있는지 확인합니다."""
    stmt = select(TokenBlacklist).where(
        TokenBlacklist.jti == jti,
        TokenBlacklist.use_yn == True,
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def cleanup_expired(db: Session) -> int:
    """만료된 블랙리스트 항목을 비활성화합니다."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(TokenBlacklist)
        .where(TokenBlacklist.expires_at < now, TokenBlacklist.use_yn == True)
        .values(use_yn=False)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
