"""상담 이력 서비스."""

from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import History
from apps.histories.batch_schemas import BatchHistoryCreate
from apps.histories.schemas import (
    HistoryCreate,
    HistoryResponse,
    HistoryThreadDetailResponse,
    HistoryThreadSummaryResponse,
)


class InvalidParentHistoryError(ValueError):
    """Raised when parent_history_id is invalid for current user."""


class _ThreadSummary(TypedDict):
    root_history_id: int
    last_history_id: int
    title: str
    message_count: int
    first_create_date: datetime | None
    last_create_date: datetime | None


class HistoryService:
    """상담 이력 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def _get_all_user_histories(self, user_id: int) -> list[History]:
        """사용자의 활성화된 전체 상담 이력을 시간순으로 반환합니다."""
        stmt = (
            select(History)
            .where(History.user_id == user_id, History.use_yn == True)
            .order_by(History.create_date.asc(), History.history_id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    @staticmethod
    def _build_thread_title(histories: list[History], root_id: int) -> str:
        """thread 제목(첫 user 질문 기반)을 생성합니다."""
        root = next((h for h in histories if h.history_id == root_id), None)
        title_source = (root.question if root and root.question else "").strip()
        if not title_source:
            first = histories[0]
            title_source = (first.question or "").strip() or "상담 세션"
        return title_source[:30] + ("..." if len(title_source) > 30 else "")

    def _build_thread_summaries(self, user_id: int) -> list[_ThreadSummary]:
        """사용자 이력을 parent_history_id 기준으로 thread summary로 그룹핑합니다."""
        histories = self._get_all_user_histories(user_id)
        if not histories:
            return []

        groups: dict[int, list[History]] = {}
        for history in histories:
            # root: parent_history_id == history_id (자기 참조)
            # non-root: parent_history_id == root_id
            # 미마이그레이션(NULL): history_id를 root로 취급
            root_id = int(history.parent_history_id or history.history_id)
            groups.setdefault(root_id, []).append(history)

        summaries: list[_ThreadSummary] = []
        for root_id, items in groups.items():
            items_sorted = sorted(
                items,
                key=lambda h: (
                    h.create_date or datetime.min,
                    h.history_id,
                ),
            )
            first_item = items_sorted[0]
            last_item = items_sorted[-1]
            summaries.append(
                {
                    "root_history_id": root_id,
                    "last_history_id": int(last_item.history_id),
                    "title": self._build_thread_title(items_sorted, root_id),
                    "message_count": len(items_sorted),
                    "first_create_date": first_item.create_date,  # type: ignore[typeddict-item]
                    "last_create_date": last_item.create_date,  # type: ignore[typeddict-item]
                }
            )

        summaries.sort(
            key=lambda s: (
                s["last_create_date"] or datetime.min,
                s["last_history_id"],
            ),
            reverse=True,
        )
        return summaries

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

    def get_history_threads(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[HistoryThreadSummaryResponse]:
        """상담 이력을 thread 단위로 요약해 반환합니다."""
        summaries = self._build_thread_summaries(user_id)
        window = summaries[offset: offset + limit]
        return [HistoryThreadSummaryResponse(**item) for item in window]

    def get_history_thread_detail(
        self,
        user_id: int,
        root_history_id: int,
    ) -> HistoryThreadDetailResponse | None:
        """특정 thread(root 기준)의 전체 이력을 반환합니다."""
        # parent_history_id == root_history_id 인 레코드가 해당 스레드 전체
        # (root 자신은 자기 참조, 나머지는 root를 직접 가리킴)
        stmt = (
            select(History)
            .where(
                History.user_id == user_id,
                History.parent_history_id == root_history_id,
                History.use_yn == True,
            )
            .order_by(History.create_date.asc(), History.history_id.asc())
        )
        thread_histories = list(self.db.execute(stmt).scalars().all())
        if not thread_histories:
            return None

        return HistoryThreadDetailResponse(
            root_history_id=root_history_id,
            last_history_id=int(thread_histories[-1].history_id),
            title=self._build_thread_title(thread_histories, root_history_id),
            message_count=len(thread_histories),
            first_create_date=thread_histories[0].create_date,  # type: ignore[arg-type]
            last_create_date=thread_histories[-1].create_date,  # type: ignore[arg-type]
            histories=[HistoryResponse.model_validate(h) for h in thread_histories],
        )

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

        parent_history_id가 None이면 첫 메시지(root)로 간주하여 자기 참조를 설정합니다.
        parent_history_id가 제공되면 해당 값이 root ID임을 가정하고 그대로 사용합니다.

        Args:
            data: 상담 이력 생성 요청 데이터
            user_id: 사용자 ID

        Returns:
            생성된 상담 이력 객체
        """
        if data.parent_history_id is not None:
            parent = self.get_history(data.parent_history_id, user_id)
            if parent is None:
                raise InvalidParentHistoryError("Invalid parent_history_id")

        history = History(
            user_id=user_id,
            agent_code=data.agent_code,
            question=data.question,
            answer=data.answer,
            parent_history_id=data.parent_history_id,
            evaluation_data=data.evaluation_data.model_dump() if data.evaluation_data else None,
        )
        self.db.add(history)

        if data.parent_history_id is None:
            # 첫 메시지: flush로 ID 확보 후 자기 참조 설정
            self.db.flush()
            history.parent_history_id = history.history_id

        self.db.commit()
        self.db.refresh(history)
        return history

    def update_evaluation_data(
        self, history_id: int, ragas_data: dict[str, Any]
    ) -> bool:
        """RAGAS 평가 결과를 기존 evaluation_data에 병합합니다.

        Args:
            history_id: 업데이트할 상담 이력 ID
            ragas_data: RAGAS 메트릭(faithfulness, answer_relevancy 등)

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

    def create_history_batch(
        self, data: BatchHistoryCreate,
    ) -> tuple[int, int, list[int]]:
        """배치로 히스토리를 저장합니다 (RAG 마이그레이션용).

        첫 턴은 자기 참조(root), 이후 턴은 모두 root_id를 직접 참조합니다.

        Args:
            data: 배치 저장 요청 (user_id, session_id, turns)

        Returns:
            (saved_count, skipped_count, history_ids) 튜플
        """
        saved_count = 0
        skipped_count = 0
        history_ids: list[int] = []
        root_id: int | None = None

        for turn in data.turns:
            # 멱등성: question + answer 앞 200자로 중복 체크
            answer_prefix = turn.answer[:200]
            dup_stmt = (
                select(History)
                .where(
                    History.user_id == data.user_id,
                    History.question == turn.question,
                    History.answer.startswith(answer_prefix),
                    History.use_yn == True,
                )
                .limit(1)
            )
            existing = self.db.execute(dup_stmt).scalar_one_or_none()
            if existing:
                history_ids.append(existing.history_id)
                skipped_count += 1
                if root_id is None:
                    root_id = int(existing.history_id)
                continue

            history = History(
                user_id=data.user_id,
                agent_code=turn.agent_code,
                question=turn.question,
                answer=turn.answer,
                parent_history_id=root_id,  # 첫 턴은 flush 후 자기 참조로 덮어씀
                evaluation_data=turn.evaluation_data,
            )
            self.db.add(history)
            self.db.flush()  # history_id 할당

            if root_id is None:
                # 첫 턴: 자기 참조 설정
                history.parent_history_id = history.history_id
                root_id = int(history.history_id)

            history_ids.append(history.history_id)
            saved_count += 1

        self.db.commit()
        return saved_count, skipped_count, history_ids

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
