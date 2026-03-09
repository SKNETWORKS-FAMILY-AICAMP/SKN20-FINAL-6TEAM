"""배치 히스토리 저장 스키마 (RAG → Backend 내부 통신용)."""

from typing import Any

from pydantic import BaseModel, Field


class BatchTurn(BaseModel):
    """배치 저장 시 개별 턴 데이터."""

    agent_code: str = Field(..., pattern=r"^A\d{7}$")
    question: str = Field(..., min_length=1, max_length=5000)
    answer: str = Field(..., min_length=1, max_length=50000)
    evaluation_data: dict[str, Any] | None = None
    timestamp: str | None = None


class BatchHistoryCreate(BaseModel):
    """배치 히스토리 저장 요청."""

    user_id: int
    session_id: str
    turns: list[BatchTurn] = Field(..., min_length=1, max_length=100)


class BatchHistoryResponse(BaseModel):
    """배치 히스토리 저장 응답."""

    saved_count: int
    skipped_count: int
    history_ids: list[int]
