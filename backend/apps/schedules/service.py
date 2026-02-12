"""일정 관리 서비스."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import Company, Schedule
from apps.schedules.schemas import ScheduleCreate, ScheduleUpdate


class ScheduleService:
    """일정 관리 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def _get_user_company_ids(self, user_id: int) -> list[int]:
        """사용자가 소유한 기업 ID 목록을 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            기업 ID 목록
        """
        stmt = select(Company.company_id).where(
            Company.user_id == user_id,
            Company.use_yn == True,
        )
        return list(self.db.execute(stmt).scalars().all())

    def check_company_ownership(self, company_id: int, user_id: int) -> Company | None:
        """사용자의 기업인지 확인합니다.

        Args:
            company_id: 기업 ID
            user_id: 사용자 ID

        Returns:
            기업 객체 또는 None
        """
        stmt = select(Company).where(
            Company.company_id == company_id,
            Company.user_id == user_id,
            Company.use_yn == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_schedules(
        self,
        user_id: int,
        company_id: int | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
    ) -> list[Schedule]:
        """사용자의 일정 목록을 조회합니다.

        Args:
            user_id: 사용자 ID
            company_id: 기업 ID 필터 (선택)
            start_from: 시작일 이후 필터 (선택)
            start_to: 시작일 이전 필터 (선택)

        Returns:
            일정 목록

        Raises:
            PermissionError: 접근 권한이 없는 기업의 일정 조회 시
        """
        user_company_ids = self._get_user_company_ids(user_id)

        if not user_company_ids:
            return []

        stmt = select(Schedule).where(
            Schedule.company_id.in_(user_company_ids),
            Schedule.use_yn == True,
        )

        if company_id:
            if company_id not in user_company_ids:
                raise PermissionError("Access denied to this company")
            stmt = stmt.where(Schedule.company_id == company_id)

        if start_from:
            stmt = stmt.where(Schedule.start_date >= start_from)
        if start_to:
            stmt = stmt.where(Schedule.start_date <= start_to)

        stmt = stmt.order_by(Schedule.start_date.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_schedule(self, schedule_id: int, user_id: int) -> Schedule | None:
        """사용자의 특정 일정을 조회합니다.

        Args:
            schedule_id: 일정 ID
            user_id: 사용자 ID

        Returns:
            일정 객체 또는 None
        """
        user_company_ids = self._get_user_company_ids(user_id)

        if not user_company_ids:
            return None

        stmt = select(Schedule).where(
            Schedule.schedule_id == schedule_id,
            Schedule.company_id.in_(user_company_ids),
            Schedule.use_yn == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_schedule(self, data: ScheduleCreate, user_id: int) -> Schedule | None:
        """일정을 등록합니다.

        Args:
            data: 일정 생성 요청 데이터
            user_id: 사용자 ID

        Returns:
            생성된 일정 객체 또는 None (기업 소유 확인 실패 시)
        """
        company = self.check_company_ownership(data.company_id, user_id)
        if not company:
            return None

        schedule = Schedule(
            company_id=data.company_id,
            schedule_name=data.schedule_name,
            start_date=data.start_date,
            end_date=data.end_date,
            memo=data.memo,
            announce_id=data.announce_id,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update_schedule(
        self, schedule_id: int, data: ScheduleUpdate, user_id: int
    ) -> Schedule | None:
        """일정을 수정합니다.

        Args:
            schedule_id: 일정 ID
            data: 일정 수정 요청 데이터
            user_id: 사용자 ID

        Returns:
            수정된 일정 객체 또는 None
        """
        schedule = self.get_schedule(schedule_id, user_id)
        if not schedule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(schedule, key, value)

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete_schedule(self, schedule_id: int, user_id: int) -> bool:
        """일정을 소프트 삭제합니다.

        Args:
            schedule_id: 일정 ID
            user_id: 사용자 ID

        Returns:
            삭제 성공 여부
        """
        schedule = self.get_schedule(schedule_id, user_id)
        if not schedule:
            return False

        schedule.use_yn = False
        self.db.commit()
        return True
