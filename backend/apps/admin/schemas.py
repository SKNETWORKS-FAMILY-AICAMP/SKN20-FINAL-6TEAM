"""관리자 API 스키마."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Any


class ServiceStatus(BaseModel):
    """개별 서비스 상태."""

    name: str = Field(description="서비스 이름 (backend/rag/database)")
    status: str = Field(description="healthy/degraded/unhealthy")
    response_time_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ServerStatusResponse(BaseModel):
    """서버 상태 응답."""

    overall_status: str = Field(description="전체 상태 (healthy/degraded/unhealthy)")
    services: list[ServiceStatus]
    uptime_seconds: float
    checked_at: datetime


class HistoryListItem(BaseModel):
    """관리자용 상담 이력 목록 항목."""

    model_config = ConfigDict(from_attributes=True)

    history_id: int
    user_id: int
    agent_code: str | None = None
    agent_name: str | None = Field(default=None, description="에이전트 이름 (Code 테이블 JOIN)")
    question: str | None = None
    answer_preview: str | None = Field(default=None, description="답변 미리보기 (처음 200자)")
    create_date: datetime | None = None

    # 평가 요약
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    llm_score: int | None = Field(default=None, ge=0, le=100)
    llm_passed: bool | None = None
    response_time: float | None = None
    domains: list[str] = Field(default_factory=list)

    # 사용자 정보
    user_email: str | None = None
    username: str | None = None


class HistoryListResponse(BaseModel):
    """관리자용 상담 이력 목록 응답."""

    items: list[HistoryListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class EvaluationStats(BaseModel):
    """평가 통계."""

    total_count: int = Field(description="전체 상담 수")
    evaluated_count: int = Field(description="평가된 상담 수")
    passed_count: int = Field(description="LLM 평가 통과 수")
    failed_count: int = Field(description="LLM 평가 실패 수")

    avg_faithfulness: float | None = Field(default=None, description="평균 Faithfulness")
    avg_answer_relevancy: float | None = Field(default=None, description="평균 Answer Relevancy")
    avg_llm_score: float | None = Field(default=None, description="평균 LLM 점수")

    # 도메인별 통계
    domain_counts: dict[str, int] = Field(default_factory=dict, description="도메인별 상담 수")


class HistoryFilterParams(BaseModel):
    """상담 이력 필터 파라미터."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    domain: str | None = Field(None, pattern=r"^[a-zA-Z가-힣_]+$", max_length=50)
    agent_code: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)
    max_score: int | None = Field(default=None, ge=0, le=100)
    passed_only: bool | None = None
    user_id: int | None = None


# ─── 모니터링 스키마 ───────────────────────────────────────────


class MetricsResponse(BaseModel):
    """서버 리소스 현황 응답."""

    cpu_percent: float = Field(description="CPU 사용률 (%)")
    memory_percent: float = Field(description="메모리 사용률 (%)")
    disk_percent: float = Field(description="디스크 사용률 (%)")
    memory_total_gb: float = Field(description="전체 메모리 (GB)")
    memory_used_gb: float = Field(description="사용 중 메모리 (GB)")
    disk_total_gb: float = Field(description="전체 디스크 (GB)")
    disk_used_gb: float = Field(description="사용 중 디스크 (GB)")
    timestamp: datetime = Field(description="측정 시각")


class JobLogResponse(BaseModel):
    """스케줄러 작업 실행 이력 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_name: str = Field(description="작업 이름")
    status: str = Field(description="started | success | failed")
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, description="실행 시간(ms)")
    record_count: int | None = Field(default=None, description="처리 레코드 수")
    error_msg: str | None = Field(default=None, description="실패 시 오류 메시지")


class LogPageResponse(BaseModel):
    """로그 파일 페이지 응답."""

    total_lines: int = Field(description="전체 로그 줄 수")
    page: int
    page_size: int
    lines: list[str] = Field(description="최신 순으로 정렬된 로그 라인 목록")
    file: str = Field(description="로그 파일 이름 (backend | rag)")
