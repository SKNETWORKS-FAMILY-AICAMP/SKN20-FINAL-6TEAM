from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any


class RetrievalEvaluationData(BaseModel):
    """규칙 기반 검색 평가 결과."""

    status: str | None = Field(default=None, description="PASS/RETRY/FAIL")
    doc_count: int | None = Field(default=None, description="검색된 문서 수")
    keyword_match_ratio: float | None = Field(default=None, description="키워드 매칭 비율")
    avg_similarity: float | None = Field(default=None, description="평균 유사도 점수")
    used_multi_query: bool = Field(default=False, description="Multi-Query 사용 여부")


class EvaluationData(BaseModel):
    """RAGAS 및 평가 결과."""

    faithfulness: float | None = Field(default=None, description="Faithfulness 점수 (0-1)")
    answer_relevancy: float | None = Field(default=None, description="Answer Relevancy 점수 (0-1)")
    context_precision: float | None = Field(default=None, description="Context Precision 점수 (0-1)")
    llm_score: int | None = Field(default=None, description="LLM 평가 점수 (0-100)")
    llm_passed: bool | None = Field(default=None, description="LLM 평가 통과 여부")
    contexts: list[str] = Field(default_factory=list, description="검색된 문서 내용 (발췌)")
    domains: list[str] = Field(default_factory=list, description="질문 도메인")
    retrieval_evaluation: RetrievalEvaluationData | None = Field(
        default=None, description="규칙 기반 검색 평가 결과"
    )
    response_time: float | None = Field(default=None, description="응답 시간 (초)")


class HistoryCreate(BaseModel):
    agent_code: str
    question: str
    answer: str
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
    """관리자용 상세 응답 (evaluation_data 포함)."""

    model_config = ConfigDict(from_attributes=True)

    history_id: int
    user_id: int
    agent_code: str | None = None
    question: str | None = None
    answer: str | None = None
    parent_history_id: int | None = None
    evaluation_data: EvaluationData | None = None
    create_date: datetime | None = None
    update_date: datetime | None = None

    # 사용자 정보 (조인)
    user_email: str | None = None
    username: str | None = None
