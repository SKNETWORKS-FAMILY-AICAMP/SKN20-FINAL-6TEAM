"""RAG 서비스 환경설정 모듈.

Pydantic BaseSettings를 사용하여 환경변수를 관리합니다.
모든 설정값은 .env 파일 또는 환경변수에서 로드됩니다.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """RAG 서비스 설정 클래스.

    환경변수 또는 .env 파일에서 설정값을 로드합니다.

    Attributes:
        openai_api_key: OpenAI API 키 (필수)
        openai_model: 사용할 LLM 모델
        openai_temperature: LLM temperature
        embedding_model: 임베딩 모델명
        chroma_host: ChromaDB 호스트
        chroma_port: ChromaDB 포트
        bizinfo_api_key: 기업마당 API 키
        kstartup_api_key: K-Startup API 키
        evaluation_threshold: 평가 통과 임계값
        max_retry_count: 최대 재시도 횟수
        cors_origins: CORS 허용 오리진
    """

    model_config = SettingsConfigDict(
        env_file="../.env",  # 프로젝트 루트의 .env 파일
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MySQL 설정 (Backend와 동일한 DB 사용)
    mysql_host: str = Field(default="localhost", description="MySQL 호스트")
    mysql_port: int = Field(default=3306, description="MySQL 포트")
    mysql_database: str = Field(default="final_test", description="MySQL 데이터베이스명")
    mysql_user: str = Field(default="root", description="MySQL 사용자")
    mysql_password: str = Field(default="", description="MySQL 비밀번호")

    # OpenAI 설정
    openai_api_key: str = Field(default="", description="OpenAI API 키 (필수)")

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """OpenAI API 키 검증."""
        if not v or not v.strip():
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다. "
                "RAG 서비스를 실행하려면 유효한 OpenAI API 키가 필요합니다."
            )
        if not v.startswith("sk-"):
            logger.warning(
                "OPENAI_API_KEY 형식이 올바르지 않습니다. "
                "'sk-'로 시작해야 합니다."
            )
        return v
    openai_model: str = Field(default="gpt-4o-mini", description="LLM 모델")
    openai_temperature: float = Field(default=0.3, description="LLM temperature")

    # 임베딩 설정
    embedding_model: str = Field(
        default="BAAI/bge-m3", description="임베딩 모델"
    )

    # ChromaDB 설정
    chroma_host: str = Field(default="localhost", description="ChromaDB 호스트")
    chroma_port: int = Field(default=8002, description="ChromaDB 포트")

    # 외부 API 설정
    bizinfo_api_key: str = Field(default="", description="기업마당 API 키")
    kstartup_api_key: str = Field(default="", description="K-Startup API 키")

    # 평가 설정
    evaluation_threshold: int = Field(default=70, ge=0, le=100, description="평가 통과 임계값 (100점 만점)")
    max_retry_count: int = Field(default=2, ge=0, description="최대 재시도 횟수")
    enable_llm_evaluation: bool = Field(
        default=True, description="LLM 기반 답변 평가 활성화"
    )

    # 도메인 분류 설정
    domain_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="도메인 분류 신뢰도 임계값 (미만 시 도메인 외 질문으로 판단)"
    )
    enable_domain_rejection: bool = Field(
        default=True,
        description="도메인 외 질문 거부 기능 활성화"
    )

    # RAG 설정
    retrieval_k: int = Field(default=3, gt=0, description="도메인별 검색 결과 개수")
    retrieval_k_common: int = Field(default=2, gt=0, description="공통 법령 DB 검색 결과 개수")
    mmr_fetch_k_multiplier: int = Field(default=4, gt=0, description="MMR 검색 시 초기 후보 배수")
    mmr_lambda_mult: float = Field(default=0.6, ge=0.0, le=1.0, description="MMR 다양성 파라미터 (0=최대 다양성, 1=최대 유사도)")

    # 컨텍스트 길이 설정
    format_context_length: int = Field(default=500, description="컨텍스트 포맷팅 시 문서 내용 최대 길이")
    source_content_length: int = Field(default=300, description="SourceDocument 변환 시 내용 최대 길이")
    evaluator_context_length: int = Field(default=2000, description="평가 시 컨텍스트 최대 길이")

    # ===== RAG Feature Flags =====
    # 쿼리 처리
    enable_query_rewrite: bool = Field(default=True, description="쿼리 재작성 활성화")

    # 검색 설정
    enable_hybrid_search: bool = Field(default=True, description="Hybrid Search (BM25+Vector) 활성화")
    vector_search_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="벡터 검색 가중치 (0.0=BM25만, 1.0=벡터만)"
    )

    # 후처리 설정
    enable_reranking: bool = Field(default=True, description="Re-ranking 활성화")
    enable_context_compression: bool = Field(default=False, description="컨텍스트 압축 활성화")
    rerank_top_k: int = Field(default=5, description="Re-ranking 후 반환할 문서 수")

    # Reranker 설정
    reranker_type: str = Field(
        default="cross-encoder",
        description="Reranker 타입 (cross-encoder, llm)"
    )

    @field_validator("reranker_type")
    @classmethod
    def validate_reranker_type(cls, v: str) -> str:
        """Reranker 타입 검증."""
        allowed_types = {"cross-encoder", "llm"}
        if v not in allowed_types:
            raise ValueError(
                f"reranker_type은 {allowed_types} 중 하나여야 합니다 (입력: {v})"
            )
        return v

    cross_encoder_model: str = Field(
        default="BAAI/bge-reranker-base",
        description="Cross-Encoder 모델명"
    )

    # 캐싱 설정
    enable_response_cache: bool = Field(default=True, description="응답 캐싱 활성화")
    cache_max_size: int = Field(default=500, gt=0, description="캐시 최대 크기")
    cache_ttl: int = Field(default=3600, gt=0, description="캐시 TTL (초)")

    # Rate Limiting 설정
    enable_rate_limit: bool = Field(default=True, description="Rate Limiting 활성화")
    rate_limit_rate: float = Field(default=10.0, description="초당 토큰 충전 속도")
    rate_limit_capacity: float = Field(default=100.0, description="최대 토큰 수 (버스트)")

    # 관리자 인증 설정
    admin_api_key: str = Field(
        default="", description="관리자 API 키 (모니터링 엔드포인트 인증용, 비어있으면 인증 비활성화)"
    )

    # 타임아웃 설정
    llm_timeout: float = Field(default=30.0, gt=0, description="LLM 호출 타임아웃 (초)")
    search_timeout: float = Field(default=10.0, gt=0, description="검색 타임아웃 (초)")
    total_timeout: float = Field(default=60.0, gt=0, description="전체 요청 타임아웃 (초)")

    # Fallback 설정
    enable_fallback: bool = Field(default=True, description="Fallback 응답 활성화")
    fallback_message: str = Field(
        default="죄송합니다. 현재 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.",
        description="Fallback 메시지"
    )

    # RAGAS 평가 설정
    enable_ragas_evaluation: bool = Field(
        default=False, description="RAGAS 정량 평가 활성화"
    )
    ragas_log_file: str = Field(
        default="ragas.log", description="RAGAS 메트릭 로그 파일명"
    )

    # 도메인 분류 설정
    domain_classification_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="벡터 유사도 기반 도메인 분류 임계값"
    )
    enable_vector_domain_classification: bool = Field(
        default=True, description="벡터 유사도 기반 도메인 분류 활성화"
    )
    enable_llm_domain_classification: bool = Field(
        default=False,
        description="LLM 기반 도메인 분류 활성화 (벡터 분류와 비교용, 추가 비용 발생)"
    )

    # 검색 제한 설정
    max_retrieval_docs: int = Field(
        default=10, description="최대 검색 문서 수"
    )

    # 검색 평가 (규칙 기반) 설정
    min_retrieval_doc_count: int = Field(
        default=2, description="최소 검색 문서 수"
    )
    min_keyword_match_ratio: float = Field(
        default=0.3, ge=0.0, le=1.0, description="최소 키워드 매칭 비율"
    )
    min_avg_similarity_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="최소 평균 유사도 점수"
    )

    # Multi-Query 설정
    enable_multi_query: bool = Field(
        default=True, description="Multi-Query 재검색 활성화"
    )
    multi_query_count: int = Field(
        default=3, description="Multi-Query 생성 개수"
    )

    # 평가 후 재시도 설정
    enable_post_eval_retry: bool = Field(
        default=True, description="평가 실패 시 재시도 활성화 (비활성화 시 로깅만)"
    )

    # 통합 생성 에이전트 설정
    enable_integrated_generation: bool = Field(
        default=True,
        description="통합 생성 에이전트 활성화 (False이면 기존 방식 유지)"
    )
    enable_action_aware_generation: bool = Field(
        default=True,
        description="액션 인식 생성 활성화 (액션을 생성 전에 결정하여 답변에 반영)"
    )

    # 법률 보충 검색 설정
    enable_legal_supplement: bool = Field(
        default=True, description="법률 보충 검색 활성화 (주 도메인 검색 후 법률 키워드 발견 시 법률DB 추가 검색)"
    )
    legal_supplement_k: int = Field(
        default=3, gt=0, description="법률 보충 검색 시 가져올 문서 수"
    )

    # RetrievalAgent 설정
    enable_adaptive_search: bool = Field(
        default=True, description="검색 전략 자동 선택 (쿼리 특성 기반)"
    )
    enable_dynamic_k: bool = Field(
        default=True, description="동적 K값 (쿼리 특성에 따라 검색 문서 수 자동 조절)"
    )
    dynamic_k_min: int = Field(
        default=3, gt=0, description="동적 K 최소값"
    )
    dynamic_k_max: int = Field(
        default=8, gt=0, description="동적 K 최대값"
    )
    primary_domain_budget_ratio: float = Field(
        default=0.6, ge=0.0, le=1.0, description="복합 도메인 시 주 도메인 예산 비율"
    )
    enable_graduated_retry: bool = Field(
        default=True, description="단계적 재시도 활성화 (검색 평가 실패 시)"
    )
    max_retry_level: int = Field(
        default=2, ge=0, le=4, description="최대 재시도 단계 (0=없음, 1=파라미터 완화, 2=Multi-Query, 3=인접 도메인, 4=부분 답변)"
    )

    # CORS 설정
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS 허용 오리진",
    )

    # 서버 설정
    host: str = Field(default="0.0.0.0", description="서버 호스트")
    port: int = Field(default=8001, description="서버 포트")
    debug: bool = Field(default=False, description="디버그 모드")

    # 로그 레벨 설정
    log_level: str = Field(default="INFO", description="로그 레벨 (DEBUG, INFO, WARNING, ERROR)")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """로그 레벨 검증."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level은 {allowed} 중 하나여야 합니다 (입력: {v})")
        return upper

    # CLI에서 런타임 오버라이드 가능한 설정 키 (보안 관련 필드 제외)
    _ALLOWED_OVERRIDES: set[str] = {
        "enable_hybrid_search",
        "vector_search_weight",
        "enable_reranking",
        "enable_query_rewrite",
        "enable_context_compression",
        "enable_response_cache",
        "reranker_type",
        "enable_vector_domain_classification",
        "enable_llm_domain_classification",
        "enable_multi_query",
        "enable_ragas_evaluation",
        "enable_post_eval_retry",
        "enable_legal_supplement",
        "enable_adaptive_search",
        "enable_dynamic_k",
        "enable_graduated_retry",
        "max_retry_level",
        "primary_domain_budget_ratio",
        "enable_integrated_generation",
        "enable_action_aware_generation",
        "debug",
    }

    def override(self, **kwargs: Any) -> None:
        """런타임에 설정값을 오버라이드합니다 (CLI용).

        허용된 필드만 변경 가능하며, 타입 검증을 수행합니다.
        API 키, 호스트, 포트 등 보안/인프라 관련 필드는 변경 불가합니다.

        Args:
            **kwargs: 오버라이드할 설정 키-값 쌍
        """
        for key, value in kwargs.items():
            if key not in self._ALLOWED_OVERRIDES:
                logger.warning(f"오버라이드 불가능한 설정: {key}")
                continue

            field_info = self.model_fields.get(key)
            if field_info and field_info.annotation is not None:
                expected = field_info.annotation
                if not isinstance(value, expected):
                    logger.warning(
                        f"타입 불일치: {key}는 {expected.__name__}이어야 함 "
                        f"(입력: {type(value).__name__})"
                    )
                    continue

            object.__setattr__(self, key, value)
            logger.info(f"설정 오버라이드: {key} = {value}")

    @property
    def vectordb_dir(self) -> Path:
        """VectorDB 저장 디렉토리 경로."""
        return Path(__file__).parent.parent / "vectordb"

    def get_llm_config(self) -> dict[str, Any]:
        """LLM 설정을 딕셔너리로 반환합니다."""
        return {
            "model": self.openai_model,
            "temperature": self.openai_temperature,
            "api_key": self.openai_api_key,
        }


@lru_cache
def get_settings() -> Settings:
    """Settings 인스턴스를 반환합니다 (싱글톤).

    Returns:
        Settings 인스턴스
    """
    return Settings()
