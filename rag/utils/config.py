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

    # OpenAI 설정
    openai_api_key: str = Field(default="", description="OpenAI API 키 (필수)")

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """OpenAI API 키 검증."""
        if not v or not v.strip():
            logger.warning(
                "OPENAI_API_KEY가 설정되지 않았습니다. "
                "RAG 서비스가 정상 작동하지 않을 수 있습니다."
            )
            return v
        if not v.startswith("sk-"):
            logger.warning(
                "OPENAI_API_KEY 형식이 올바르지 않습니다. "
                "'sk-'로 시작해야 합니다."
            )
        return v
    openai_model: str = Field(default="gpt-4o-mini", description="메인 LLM 모델 (답변 생성)")
    auxiliary_model: str = Field(
        default="gpt-3.5-turbo",
        description="보조 LLM 모델 (분류, 평가, Multi-query 등 경량 작업)"
    )
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

    # 평가 설정 (품질-성능 균형)
    evaluation_threshold: int = Field(default=68, description="평가 통과 임계값 (품질 유지)")
    max_retry_count: int = Field(default=1, description="최대 재시도 횟수 (성능 위해 1회)")
    skip_evaluation_for_cached: bool = Field(default=True, description="캐시 히트 시 평가 스킵")
    skip_evaluation_for_short_query: bool = Field(default=True, description="짧은 질문 평가 스킵")
    short_query_threshold: int = Field(default=8, description="짧은 질문 기준 글자 수")
    skip_evaluation_probability: float = Field(default=0.15, description="일반 질문 평가 스킵 확률 (15%)")

    # RAG 설정 (성능 최적화)
    retrieval_k: int = Field(default=3, description="도메인별 검색 결과 개수")
    retrieval_k_common: int = Field(default=2, description="공통 법령 DB 검색 결과 개수")
    mmr_fetch_k_multiplier: int = Field(default=3, description="MMR 검색 시 초기 후보 배수 (4→3 최적화)")
    mmr_lambda_mult: float = Field(default=0.7, description="MMR 다양성 파라미터 (0.6→0.7 유사도 우선)")

    # 컨텍스트 길이 설정
    format_context_length: int = Field(default=500, description="컨텍스트 포맷팅 시 문서 내용 최대 길이")
    source_content_length: int = Field(default=300, description="SourceDocument 변환 시 내용 최대 길이")
    evaluator_context_length: int = Field(default=2000, description="평가 시 컨텍스트 최대 길이")

    # 고급 검색 설정 (성능 최적화)
    enable_query_rewrite: bool = Field(default=False, description="쿼리 재작성 비활성화 (Multi-query로 대체)")
    enable_multi_query: bool = Field(default=True, description="Multi-query Retrieval 활성화")
    multi_query_count: int = Field(default=2, description="Multi-query 생성 시 쿼리 개수 (2개로 최적화)")
    enable_hybrid_search: bool = Field(default=True, description="Hybrid Search (BM25+Vector) 활성화")
    enable_reranking: bool = Field(default=True, description="Re-ranking 활성화")
    enable_context_compression: bool = Field(default=False, description="컨텍스트 압축 비활성화 (성능)")
    rerank_top_k: int = Field(default=4, description="Re-ranking 후 반환할 문서 수 (5→4 최적화)")
    rerank_batch_size: int = Field(default=4, description="Re-ranking 배치 크기 (6→4 최적화)")

    # 캐싱 설정 (성능 최적화)
    enable_response_cache: bool = Field(default=True, description="응답 캐싱 활성화")
    cache_max_size: int = Field(default=500, description="캐시 최대 크기")
    cache_ttl: int = Field(default=7200, description="캐시 TTL (초) - 2시간으로 연장")
    enable_domain_cache: bool = Field(default=True, description="도메인 분류 캐싱 활성화")
    domain_cache_size: int = Field(default=200, description="도메인 분류 캐시 크기")

    # Rate Limiting 설정
    enable_rate_limit: bool = Field(default=True, description="Rate Limiting 활성화")
    rate_limit_rate: float = Field(default=10.0, description="초당 토큰 충전 속도")
    rate_limit_capacity: float = Field(default=100.0, description="최대 토큰 수 (버스트)")

    # 타임아웃 설정 (성능 최적화)
    llm_timeout: float = Field(default=20.0, description="LLM 호출 타임아웃 (30→20초)")
    search_timeout: float = Field(default=8.0, description="검색 타임아웃 (10→8초)")
    total_timeout: float = Field(default=45.0, description="전체 요청 타임아웃 (60→45초)")

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

    # CORS 설정
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS 허용 오리진",
    )

    # 서버 설정
    host: str = Field(default="0.0.0.0", description="서버 호스트")
    port: int = Field(default=8001, description="서버 포트")
    debug: bool = Field(default=False, description="디버그 모드")

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
