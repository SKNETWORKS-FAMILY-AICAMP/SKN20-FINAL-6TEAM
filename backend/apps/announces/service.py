"""공고 서비스."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import Announce


class AnnounceService:
    """공고 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def get_announces_by_biz_code(
        self, biz_code: str | None = None, limit: int = 5
    ) -> list[Announce]:
        """업종코드 대분류 prefix 기준으로 공고 목록을 조회합니다.

        Args:
            biz_code: 업종코드 (앞 2자리로 대분류 prefix 매칭)
            limit: 최대 결과 수

        Returns:
            공고 목록
        """
        stmt = select(Announce).where(Announce.use_yn == True)

        if biz_code:
            prefix = biz_code[:2]
            stmt = stmt.where(Announce.biz_code.like(f"{prefix}%"))

        stmt = stmt.order_by(Announce.create_date.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
