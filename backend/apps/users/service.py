"""사용자 서비스."""

from datetime import datetime

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from apps.common.models import User, Code
from apps.common.notification_settings import (
    DEFAULT_NOTIFICATION_SETTINGS,
    decode_notification_settings,
    encode_notification_settings,
)
from apps.users.schemas import NotificationSettingsUpdate, UserUpdate, UserTypeUpdate

ADMIN_TYPE_CODE = "U0000001"


class UserService:
    """사용자 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int) -> User | None:
        """사용자를 ID로 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 객체 또는 None
        """
        return self.db.get(User, user_id)

    def update_user(self, user: User, data: UserUpdate) -> User:
        """사용자 정보를 수정합니다.

        Args:
            user: 현재 사용자 객체
            data: 수정 요청 데이터

        Returns:
            수정된 사용자 객체
        """
        if data.username is not None:
            user.username = data.username

        has_age_column = self._has_age_column()

        if "birth" in data.model_fields_set:
            user.birth = data.birth
            if has_age_column:
                user.age = (
                    self._calculate_age_from_birth(data.birth)
                    if data.birth is not None
                    else None
                )
        elif "age" in data.model_fields_set and has_age_column:
            user.age = data.age

        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_type(self, user: User, data: UserTypeUpdate) -> User:
        """사용자 유형을 변경합니다.

        Args:
            user: 현재 사용자 객체
            data: 유형 변경 요청 데이터

        Returns:
            수정된 사용자 객체

        Raises:
            ValueError: 유효하지 않은 유형 코드이거나 관리자 계정인 경우
        """
        if user.type_code == ADMIN_TYPE_CODE:
            raise ValueError("관리자 계정의 유형은 변경할 수 없습니다.")

        valid_codes = self._get_allowed_type_codes()
        if data.type_code not in valid_codes:
            raise ValueError(
                f"Invalid type_code. Must be one of: {', '.join(valid_codes)}"
            )

        user.type_code = data.type_code
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user: User) -> None:
        """사용자를 소프트 삭제합니다 (회원 탈퇴).

        Args:
            user: 삭제할 사용자 객체
        """
        user.use_yn = False
        self.db.commit()

    def get_notification_settings(self, user: User) -> dict[str, bool]:
        """사용자 알림 설정을 조회합니다."""
        if not self._has_notification_settings_column():
            return dict(DEFAULT_NOTIFICATION_SETTINGS)

        return decode_notification_settings(user.notification_settings)

    def update_notification_settings(
        self, user: User, data: NotificationSettingsUpdate
    ) -> dict[str, bool]:
        """사용자 알림 설정을 갱신합니다."""
        normalized = decode_notification_settings(data.model_dump())
        if not self._has_notification_settings_column():
            return normalized

        user.notification_settings = encode_notification_settings(normalized)
        self.db.commit()
        self.db.refresh(user)
        return decode_notification_settings(user.notification_settings)

    def _get_allowed_type_codes(self) -> list[str]:
        """관리자를 제외한 허용된 사용자 유형 코드 목록을 조회합니다.

        Returns:
            허용된 유형 코드 목록
        """
        stmt = select(Code.code).where(
            Code.main_code == "U",
            Code.use_yn == True,
        )
        all_codes = list(self.db.execute(stmt).scalars().all())
        return [c for c in all_codes if c != ADMIN_TYPE_CODE]

    def _has_notification_settings_column(self) -> bool:
        bind = self.db.get_bind()
        if bind is None:
            return False

        inspector = inspect(bind)
        user_columns = inspector.get_columns("user")
        return any(column.get("name") == "notification_settings" for column in user_columns)

    def _has_age_column(self) -> bool:
        bind = self.db.get_bind()
        if bind is None:
            return False

        inspector = inspect(bind)
        user_columns = inspector.get_columns("user")
        return any(column.get("name") == "age" for column in user_columns)

    def to_user_response(self, user: User) -> dict[str, object]:
        payload: dict[str, object] = {
            "user_id": user.user_id,
            "google_email": user.google_email,
            "username": user.username,
            "type_code": user.type_code,
            "birth": user.birth,
            "create_date": user.create_date,
            "age": None,
        }

        if self._has_age_column():
            payload["age"] = user.age

        return payload

    def _calculate_age_from_birth(self, birth: datetime) -> int:
        today = datetime.now().date()
        birth_date = birth.date()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return max(age, 0)
