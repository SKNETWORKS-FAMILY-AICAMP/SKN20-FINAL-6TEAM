from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievalEvaluationData(BaseModel):
    """Rule-based retrieval evaluation result."""

    status: str | None = Field(default=None, description="PASS/RETRY/FAIL")
    doc_count: int | None = Field(default=None, description="retrieved document count")
    keyword_match_ratio: float | None = Field(default=None, description="keyword match ratio")
    avg_similarity: float | None = Field(default=None, description="average similarity score")
    used_multi_query: bool = Field(default=False, description="whether multi-query was used")


class EvaluationData(BaseModel):
    """Evaluation payload stored in history.evaluation_data."""

    faithfulness: float | None = Field(default=None, description="Faithfulness score (0-1)")
    answer_relevancy: float | None = Field(default=None, description="Answer Relevancy score (0-1)")
    context_precision: float | None = Field(default=None, description="Context Precision score (0-1)")
    context_recall: float | None = Field(default=None, description="Context Recall score (0-1)")
    llm_score: int | None = Field(default=None, description="LLM score (0-100)")
    llm_passed: bool | None = Field(default=None, description="LLM pass/fail")
    contexts: list[str] = Field(default_factory=list, description="retrieved context snippets")
    domains: list[str] = Field(default_factory=list, description="detected domains")
    retrieval_evaluation: RetrievalEvaluationData | None = Field(
        default=None, description="rule-based retrieval evaluation"
    )
    response_time: float | None = Field(default=None, description="response time in seconds")
    query_rewrite_applied: bool | None = Field(default=None, description="query rewrite applied")
    query_rewrite_reason: str | None = Field(default=None, description="query rewrite reason")
    query_rewrite_time: float | None = Field(default=None, description="query rewrite elapsed (sec)")
    timeout_cause: str | None = Field(default=None, description="timeout cause")


class HistoryCreate(BaseModel):
    agent_code: str = Field(..., pattern=r"^A\d{7}$")
    question: str = Field(..., min_length=1, max_length=5000)
    answer: str = Field(..., min_length=1, max_length=50000)
    parent_history_id: int | None = None
    evaluation_data: EvaluationData | None = None


class HistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    user_id: int
    agent_code: str | None = None
    question: str | None = None
    answer: str | None = None
    parent_history_id: int | None = None
    evaluation_data: dict[str, Any] | None = None
    create_date: datetime | None = None


class HistoryDetailResponse(BaseModel):
    """Admin detail response with evaluation data."""

    model_config = ConfigDict(from_attributes=True)

    history_id: int
    user_id: int
    agent_code: str | None = None
    agent_name: str | None = Field(default=None, description="agent display name")
    question: str | None = None
    answer: str | None = None
    parent_history_id: int | None = None
    evaluation_data: EvaluationData | None = None
    create_date: datetime | None = None
    update_date: datetime | None = None

    user_email: str | None = None
    username: str | None = None


class HistoryThreadSummaryResponse(BaseModel):
    root_history_id: int
    last_history_id: int
    title: str
    message_count: int
    first_create_date: datetime | None = None
    last_create_date: datetime | None = None


class HistoryThreadDetailResponse(BaseModel):
    root_history_id: int
    last_history_id: int
    title: str
    message_count: int
    first_create_date: datetime | None = None
    last_create_date: datetime | None = None
    histories: list[HistoryResponse]
