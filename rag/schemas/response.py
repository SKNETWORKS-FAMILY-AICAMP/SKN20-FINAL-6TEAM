"""응답 스키마 모듈.

API 응답에 사용되는 Pydantic 모델을 정의합니다.
"""

from typing import Any

from pydantic import BaseModel, Field


class AgentTimingMetrics(BaseModel):
    """에이전트별 타이밍 메트릭.

    Attributes:
        domain: 에이전트 도메인
        retrieve_time: 검색 시간 (초)
        generate_time: 생성 시간 (초)
        total_time: 에이전트 총 시간 (초)
    """

    domain: str = Field(description="에이전트 도메인")
    retrieve_time: float = Field(default=0.0, description="검색 시간 (초)")
    generate_time: float = Field(default=0.0, description="생성 시간 (초)")
    total_time: float = Field(default=0.0, description="에이전트 총 시간 (초)")


class TimingMetrics(BaseModel):
    """RAG 처리 단계별 타이밍 메트릭.

    Attributes:
        classify_time: 분류 시간 (초)
        agents: 에이전트별 타이밍
        integrate_time: 통합 시간 (초)
        evaluate_time: 평가 시간 (초)
        total_time: 총 응답 시간 (초)
    """

    classify_time: float = Field(default=0.0, description="분류 시간 (초)")
    agents: list[AgentTimingMetrics] = Field(
        default_factory=list, description="에이전트별 타이밍"
    )
    integrate_time: float = Field(default=0.0, description="통합 시간 (초)")
    evaluate_time: float = Field(default=0.0, description="평가 시간 (초)")
    total_time: float = Field(default=0.0, description="총 응답 시간 (초)")


class ActionSuggestion(BaseModel):
    """추천 액션.

    Attributes:
        type: 액션 유형 (document_generation, funding_search, calculation, etc.)
        label: 액션 라벨 (UI에 표시)
        description: 액션 설명
        params: 액션 파라미터
    """

    type: str = Field(description="액션 유형")
    label: str = Field(description="액션 라벨")
    description: str | None = Field(default=None, description="액션 설명")
    params: dict[str, Any] = Field(default_factory=dict, description="액션 파라미터")


class EvaluationResult(BaseModel):
    """평가 결과.

    Attributes:
        scores: 항목별 점수
        total_score: 총점
        passed: 통과 여부
        feedback: 피드백 (미통과 시)
    """

    scores: dict[str, int] = Field(
        default_factory=dict,
        description="항목별 점수 (accuracy, completeness, relevance, citation)",
    )
    total_score: int = Field(description="총점 (100점 만점)")
    passed: bool = Field(description="통과 여부")
    feedback: str | None = Field(default=None, description="개선 피드백")


class SourceDocument(BaseModel):
    """출처 문서.

    Attributes:
        title: 문서 제목
        content: 문서 내용 (발췌)
        source: 출처
        metadata: 메타데이터
    """

    title: str | None = Field(default=None, description="문서 제목")
    content: str = Field(description="문서 내용")
    source: str | None = Field(default=None, description="출처")
    metadata: dict[str, Any] = Field(default_factory=dict, description="메타데이터")


class ChatResponse(BaseModel):
    """채팅 응답 스키마.

    Attributes:
        content: 응답 내용
        domain: 처리 도메인
        domains: 복합 질문 시 관련 도메인 목록
        sources: 참고 출처
        actions: 추천 액션
        evaluation: 평가 결과
        session_id: 세션 ID
    """

    content: str = Field(description="응답 내용")
    domain: str = Field(description="주요 처리 도메인")
    domains: list[str] = Field(default_factory=list, description="관련 도메인 목록")
    sources: list[SourceDocument] = Field(default_factory=list, description="참고 출처")
    actions: list[ActionSuggestion] = Field(default_factory=list, description="추천 액션")
    evaluation: EvaluationResult | None = Field(default=None, description="평가 결과")
    session_id: str | None = Field(default=None, description="세션 ID")
    retry_count: int = Field(default=0, description="재시도 횟수")
    ragas_metrics: dict[str, Any] | None = Field(
        default=None, description="RAGAS 정량 평가 메트릭"
    )
    timing_metrics: TimingMetrics | None = Field(
        default=None, description="단계별 처리 시간 메트릭"
    )


class DocumentResponse(BaseModel):
    """문서 생성 응답 스키마.

    Attributes:
        success: 성공 여부
        document_type: 문서 유형
        file_path: 파일 경로
        file_name: 파일명
        file_content: 파일 내용 (base64 인코딩)
        message: 메시지
    """

    success: bool = Field(description="성공 여부")
    document_type: str = Field(description="문서 유형")
    file_path: str | None = Field(default=None, description="파일 경로")
    file_name: str | None = Field(default=None, description="파일명")
    file_content: str | None = Field(default=None, description="파일 내용 (base64)")
    message: str | None = Field(default=None, description="메시지")


class StreamResponse(BaseModel):
    """스트리밍 응답 청크.

    Attributes:
        type: 청크 유형 (token, source, action, done, error)
        content: 내용
        metadata: 메타데이터
    """

    type: str = Field(description="청크 유형")
    content: str | None = Field(default=None, description="내용")
    metadata: dict[str, Any] = Field(default_factory=dict, description="메타데이터")


class HealthResponse(BaseModel):
    """헬스체크 응답.

    Attributes:
        status: 상태 (healthy, degraded, unhealthy)
        version: 버전
        vectordb_status: VectorDB 상태
        openai_status: OpenAI API 연결 상태
    """

    status: str = Field(default="healthy", description="서비스 상태")
    version: str = Field(default="1.0.0", description="서비스 버전")
    vectordb_status: dict[str, Any] = Field(
        default_factory=dict, description="VectorDB 상태"
    )
    openai_status: dict[str, Any] = Field(
        default_factory=dict, description="OpenAI API 연결 상태"
    )
