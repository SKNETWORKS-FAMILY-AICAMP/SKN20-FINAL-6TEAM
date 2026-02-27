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
    def _resolve_root_history_id(
        history_id: int,
        parent_map: dict[int, int | None],
        cache: dict[int, int],
    ) -> int:
        """parent 체인을 따라 root history_id를 찾습니다."""
        if history_id in cache:
            return cache[history_id]

        current = history_id
        visited: set[int] = set()
        while True:
            if current in cache:
                root_id = cache[current]
                break
            if current in visited:
                root_id = history_id
                break
            visited.add(current)

            parent_id = parent_map.get(current)
            if parent_id is None or parent_id not in parent_map:
                root_id = current
                break
            current = parent_id

        for hid in visited:
            cache[hid] = root_id
        return root_id

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
        """사용자 이력을 root chain 기준으로 thread summary로 그룹핑합니다."""
        histories = self._get_all_user_histories(user_id)
        if not histories:
            return []

        parent_map = {h.history_id: h.parent_history_id for h in histories}
        cache: dict[int, int] = {}
        groups: dict[int, list[History]] = {}

        for history in histories:
            root_id = self._resolve_root_history_id(history.history_id, parent_map, cache)
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
                    "last_history_id": last_item.history_id,
                    "title": self._build_thread_title(items_sorted, root_id),
                    "message_count": len(items_sorted),
                    "first_create_date": first_item.create_date,
                    "last_create_date": last_item.create_date,
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
        summaries = self._build_thread_summaries(user_id)
        target_summary = next(
            (item for item in summaries if item["root_history_id"] == root_history_id),
            None,
        )
        if target_summary is None:
            return None

        histories = self._get_all_user_histories(user_id)
        parent_map = {h.history_id: h.parent_history_id for h in histories}
        cache: dict[int, int] = {}
        thread_histories = [
            h
            for h in histories
            if self._resolve_root_history_id(h.history_id, parent_map, cache) == root_history_id
        ]
        thread_histories.sort(
            key=lambda h: (
                h.create_date or datetime.min,
                h.history_id,
            )
        )

        return HistoryThreadDetailResponse(
            root_history_id=target_summary["root_history_id"],
            last_history_id=target_summary["last_history_id"],
            title=target_summary["title"],
            message_count=target_summary["message_count"],
            first_create_date=target_summary["first_create_date"],
            last_create_date=target_summary["last_create_date"],
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

        Args:
            data: 배치 저장 요청 (user_id, session_id, turns)

        Returns:
            (saved_count, skipped_count, history_ids) 튜플
        """
        saved_count = 0
        skipped_count = 0
        history_ids: list[int] = []
        # 새 세션은 독립 스레드로 시작 (기존 스레드에 잘못 연결 방지)
        parent_id: int | None = None

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
                # 중복 발견 — skip하되 parent_id는 변경하지 않음
                # (다른 세션의 레코드와 교차 연결 방지)
                history_ids.append(existing.history_id)
                skipped_count += 1
                continue

            history = History(
                user_id=data.user_id,
                agent_code=turn.agent_code,
                question=turn.question,
                answer=turn.answer,
                parent_history_id=parent_id,
                evaluation_data=turn.evaluation_data,
            )
            self.db.add(history)
            self.db.flush()  # history_id 할당
            parent_id = history.history_id
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
