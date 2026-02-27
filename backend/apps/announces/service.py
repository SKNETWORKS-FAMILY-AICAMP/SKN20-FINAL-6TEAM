"""공지 서비스."""

from datetime import datetime

from sqlalchemy import func, inspect, select, update
from sqlalchemy.orm import Session

from apps.announces.schemas import (
    AnnounceSyncItem,
    AnnounceSyncResponse,
    AnnounceSyncTrigger,
)
from apps.common.models import Announce, Company, User

SYNC_ITEM_LINK = "/company"
SYNC_ITEM_TITLE = "신규 공고"
SYNC_ITEM_TYPE = "info"
FALLBACK_COMPANY_NAME_PREFIX = "기업 #"
FALLBACK_REPRESENTATIVE_NAME = "신규 공고"


class AnnounceService:
    """공지 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def get_announces_by_biz_code(
        self, biz_code: str | None = None, limit: int = 5
    ) -> list[Announce]:
        """업종코드 대분류 prefix 기준으로 공고 목록을 조회합니다."""
        stmt = select(Announce).where(Announce.use_yn == True)

        if biz_code:
            prefix = biz_code[:2]
            stmt = stmt.where(Announce.biz_code.like(f"{prefix}%"))

        stmt = stmt.order_by(Announce.create_date.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def sync_announces_for_user(
        self, user: User, trigger: AnnounceSyncTrigger
    ) -> AnnounceSyncResponse:
        """사용자별 신규 공고 요약 알림을 동기화합니다."""
        if not self._has_last_announce_checked_at_column():
            now = datetime.now()
            return AnnounceSyncResponse(
                trigger=trigger,
                cursor_from=None,
                cursor_to=now,
                synced_at=now,
                items=[],
            )

        cursor_from = user.last_announce_checked_at
        cursor_to = datetime.now()

        # 신규/기존 사용자의 첫 동기화는 커서만 초기화합니다.
        if cursor_from is None:
            self._update_cursor_safely(user_id=user.user_id, cursor_to=cursor_to)
            self.db.commit()
            return AnnounceSyncResponse(
                trigger=trigger,
                cursor_from=None,
                cursor_to=cursor_to,
                synced_at=cursor_to,
                items=[],
            )

        companies = self._get_active_companies(user.user_id)
        items: list[AnnounceSyncItem] = []

        for company in companies:
            item = self._build_company_sync_item(
                company=company,
                cursor_from=cursor_from,
                cursor_to=cursor_to,
            )
            if item is not None:
                items.append(item)

        self._update_cursor_safely(user_id=user.user_id, cursor_to=cursor_to)
        self.db.commit()

        return AnnounceSyncResponse(
            trigger=trigger,
            cursor_from=cursor_from,
            cursor_to=cursor_to,
            synced_at=cursor_to,
            items=items,
        )

    def _get_active_companies(self, user_id: int) -> list[Company]:
        stmt = (
            select(Company)
            .where(
                Company.user_id == user_id,
                Company.use_yn == True,
            )
            .order_by(Company.company_id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _has_last_announce_checked_at_column(self) -> bool:
        bind = self.db.get_bind()
        if bind is None:
            return False

        inspector = inspect(bind)
        user_columns = inspector.get_columns("user")
        return any(column.get("name") == "last_announce_checked_at" for column in user_columns)

    def _update_cursor_safely(self, user_id: int, cursor_to: datetime) -> None:
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(
                last_announce_checked_at=func.greatest(
                    func.coalesce(User.last_announce_checked_at, cursor_to),
                    cursor_to,
                )
            )
        )
        self.db.execute(stmt)

    def _build_company_sync_item(
        self,
        company: Company,
        cursor_from: datetime,
        cursor_to: datetime,
    ) -> AnnounceSyncItem | None:
        biz_code = company.biz_code or ""
        biz_prefix = biz_code[:2]
        if len(biz_prefix) < 2:
            return None

        new_announces = self._get_new_announces_by_prefix(
            biz_prefix=biz_prefix,
            cursor_from=cursor_from,
            cursor_to=cursor_to,
        )
        if not new_announces:
            return None

        representative = new_announces[0]
        new_count = len(new_announces)
        company_name = (
            company.com_name
            if company.com_name
            else f"{FALLBACK_COMPANY_NAME_PREFIX}{company.company_id}"
        )

        if new_count == 1:
            message = f"{company_name} 신규 공고 1건"
        else:
            representative_name = (
                representative.ann_name.strip()
                if representative.ann_name
                else FALLBACK_REPRESENTATIVE_NAME
            )
            if not representative_name:
                representative_name = FALLBACK_REPRESENTATIVE_NAME
            message = f"{company_name} {representative_name} 외 {new_count - 1}건"

        created_at = representative.create_date or cursor_to
        return AnnounceSyncItem(
            id=f"announce-company-{company.company_id}-rep-{representative.announce_id}",
            title=SYNC_ITEM_TITLE,
            message=message,
            company_label=company_name,
            type=SYNC_ITEM_TYPE,
            created_at=created_at,
            link=SYNC_ITEM_LINK,
        )

    def _get_new_announces_by_prefix(
        self,
        biz_prefix: str,
        cursor_from: datetime,
        cursor_to: datetime,
    ) -> list[Announce]:
        stmt = (
            select(Announce)
            .where(
                Announce.use_yn == True,
                Announce.biz_code.like(f"{biz_prefix}%"),
                Announce.create_date > cursor_from,
                Announce.create_date <= cursor_to,
            )
            .order_by(Announce.create_date.desc(), Announce.announce_id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
