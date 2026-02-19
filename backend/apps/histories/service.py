"""상담 이력 서비스."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import History
from apps.histories.schemas import HistoryCreate


class HistoryService:
    """상담 이력 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def get_histories(
        self,
        user_id: int,
        agent_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[History]:
        """사용자의 상담 이력 목록을 조회합니다.

        Args:
            user_id: 사용자 ID
            agent_code: 에이전트 코드 필터 (선택)
            limit: 조회 개수
            offset: 오프셋

        Returns:
            상담 이력 목록
        """
        stmt = select(History).where(
            History.user_id == user_id,
            History.use_yn == True,
        )

        if agent_code:
            stmt = stmt.where(History.agent_code == agent_code)

        stmt = (
            stmt.order_by(History.create_date.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_history(self, history_id: int, user_id: int) -> History | None:
        """사용자의 특정 상담 이력을 조회합니다.

        Args:
            history_id: 상담 이력 ID
            user_id: 사용자 ID

        Returns:
            상담 이력 객체 또는 None
        """
        stmt = select(History).where(
            History.history_id == history_id,
            History.user_id == user_id,
            History.use_yn == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_history(self, data: HistoryCreate, user_id: int) -> History:
        """상담 이력을 저장합니다.

        Args:
            data: 상담 이력 생성 요청 데이터
            user_id: 사용자 ID

        Returns:
            생성된 상담 이력 객체
        """
        history = History(
            user_id=user_id,
            agent_code=data.agent_code,
            question=data.question,
            answer=data.answer,
            parent_history_id=data.parent_history_id,
            evaluation_data=data.evaluation_data.model_dump() if data.evaluation_data else None,
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def update_evaluation_data(
        self, history_id: int, ragas_data: dict[str, Any]
    ) -> bool:
        """RAGAS 평가 결과를 기존 evaluation_data에 머지합니다.

        Args:
            history_id: 업데이트할 상담 이력 ID
            ragas_data: RAGAS 메트릭 (faithfulness, answer_relevancy 등)

        Returns:
            업데이트 성공 여부
        """
        stmt = select(History).where(
            History.history_id == history_id,
            History.use_yn == True,
        )
        history = self.db.execute(stmt).scalar_one_or_none()
        if not history:
            return False

        existing = history.evaluation_data or {}
        history.evaluation_data = {**existing, **ragas_data}
        self.db.commit()
        return True

    def delete_history(self, history_id: int, user_id: int) -> bool:
        """상담 이력을 소프트 삭제합니다.

        Args:
            history_id: 상담 이력 ID
            user_id: 사용자 ID

        Returns:
            삭제 성공 여부
        """
        history = self.get_history(history_id, user_id)
        if not history:
            return False

        history.use_yn = False
        self.db.commit()
        return True
