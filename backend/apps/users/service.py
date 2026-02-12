"""사용자 서비스."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import User, Code
from apps.users.schemas import UserUpdate, UserTypeUpdate

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
        if data.birth is not None:
            user.birth = data.birth

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
            ValueError: 유효하지 않은 유형 코드인 경우
        """
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
