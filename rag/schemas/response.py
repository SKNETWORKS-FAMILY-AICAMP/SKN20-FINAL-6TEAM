"""Response schemas for RAG service."""

from typing import Any

from pydantic import BaseModel, Field


class AgentTimingMetrics(BaseModel):
    domain: str = Field(description="agent domain")
    retrieve_time: float = Field(default=0.0, description="retrieve time in seconds")
    generate_time: float = Field(default=0.0, description="generate time in seconds")
    total_time: float = Field(default=0.0, description="total agent time in seconds")


class TimingMetrics(BaseModel):
    classify_time: float = Field(default=0.0, description="classify time in seconds")
    agents: list[AgentTimingMetrics] = Field(default_factory=list, description="per-agent timings")
    integrate_time: float = Field(default=0.0, description="integrate time in seconds")
    evaluate_time: float = Field(default=0.0, description="evaluate time in seconds")
    total_time: float = Field(default=0.0, description="total pipeline time in seconds")


class ActionSuggestion(BaseModel):
    type: str = Field(description="action type")
    label: str = Field(description="action label")
    description: str | None = Field(default=None, description="action description")
    params: dict[str, Any] = Field(default_factory=dict, description="action params")


class EvaluationResult(BaseModel):
    scores: dict[str, int] = Field(default_factory=dict, description="category scores")
    total_score: int = Field(description="total score")
    passed: bool = Field(description="pass/fail")
    feedback: str | None = Field(default=None, description="feedback message")


class SourceDocument(BaseModel):
    title: str | None = Field(default=None, description="document title")
    content: str = Field(description="document content")
    source: str | None = Field(default=None, description="source name")
    url: str = Field(default="https://law.go.kr/", description="source url")
    metadata: dict[str, Any] = Field(default_factory=dict, description="metadata")


class RetrievalEvaluationData(BaseModel):
    status: str | None = Field(default=None, description="PASS/RETRY/FAIL")
    doc_count: int | None = Field(default=None, description="retrieved document count")
    keyword_match_ratio: float | None = Field(default=None, description="keyword match ratio")
    avg_similarity: float | None = Field(default=None, description="average similarity")
    used_multi_query: bool = Field(default=False, description="whether multi-query was used")


class EvaluationDataForDB(BaseModel):
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
    query_rewrite_applied: bool | None = Field(default=None, description="query rewrite applied")
    query_rewrite_reason: str | None = Field(default=None, description="query rewrite reason")
    query_rewrite_time: float | None = Field(default=None, description="query rewrite elapsed (sec)")
    timeout_cause: str | None = Field(default=None, description="timeout cause")
    response_time: float | None = Field(default=None, description="response time in seconds")


class ChatResponse(BaseModel):
    content: str = Field(description="response content")
    domain: str = Field(description="primary domain")
    domains: list[str] = Field(default_factory=list, description="all detected domains")
    sources: list[SourceDocument] = Field(default_factory=list, description="source documents")
    actions: list[ActionSuggestion] = Field(default_factory=list, description="recommended actions")
    evaluation: EvaluationResult | None = Field(default=None, description="LLM evaluation result")
    session_id: str | None = Field(default=None, description="session id")
    retry_count: int = Field(default=0, description="retry count")
    ragas_metrics: dict[str, Any] | None = Field(default=None, description="ragas metrics")
    timing_metrics: TimingMetrics | None = Field(default=None, description="pipeline timing metrics")
    evaluation_data: EvaluationDataForDB | None = Field(default=None, description="db evaluation payload")


class DocumentResponse(BaseModel):
    success: bool = Field(description="success flag")
    document_type: str = Field(description="document type")
    file_path: str | None = Field(default=None, description="server file path", exclude=True)
    file_name: str | None = Field(default=None, description="file name")
    file_content: str | None = Field(default=None, description="file content base64")
    message: str | None = Field(default=None, description="message")


class StreamResponse(BaseModel):
    type: str = Field(description="chunk type")
    content: str | None = Field(default=None, description="chunk content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="chunk metadata")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="service status")
    version: str = Field(default="1.0.0", description="service version")
    vectordb_status: dict[str, Any] = Field(default_factory=dict, description="vectordb status")
    openai_status: dict[str, Any] = Field(default_factory=dict, description="openai status")
    rag_config: dict[str, Any] = Field(default_factory=dict, description="rag feature flags")
