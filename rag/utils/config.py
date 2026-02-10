"""RAG 서비스 환경설정 모듈.

Pydantic BaseSettings를 사용하여 환경변수를 관리합니다.
모든 설정값은 .env 파일 또는 환경변수에서 로드됩니다.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymysql
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 도메인 → 한글 라벨 매핑
DOMAIN_LABELS: dict[str, str] = {
    "startup_funding": "창업/지원",
    "finance_tax": "재무/세무",
    "hr_labor": "인사/노무",
    "law_common": "법률",
}

# 도메인 분류 키워드 (원형/lemma 기반)
# 명사: 그대로, 동사/형용사: "~다" 형태로 통일
# kiwipiepy 형태소 분석 후 매칭됨
_DEFAULT_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "startup_funding": [
        # 명사
        "창업", "사업자등록", "법인설립", "업종", "인허가",
        "지원사업", "보조금", "정책자금", "공고", "지원금",
        "마케팅", "광고", "홍보", "브랜딩", "스타트업",
        "개업", "가게", "매장", "점포", "프랜차이즈",
        "사업계획", "사업자", "폐업", "휴업", "업종변경",
        # 동사 (원형)
        "차리다",
    ],
    "finance_tax": [
        # 명사
        "세금", "부가세", "법인세", "소득세", "회계",
        "세무", "재무", "결산", "세무조정",
        "세액", "공제", "감면", "원천징수",
        "종소세", "종합소득", "양도세", "증여세", "상속세",
        "부가가치세", "세율", "세무사",
        "연말정산", "간이과세", "일반과세", "세금계산서",
        "장부", "복식부기", "간편장부", "사업소득",
        "가산세", "체납", "과태료", "세무조사",
        "매출", "매입", "경비", "비용처리",
        "감가상각", "자산", "부채", "자본",
        "현금영수증", "카드매출",
        "취득세", "재산세", "종합부동산세",
        # 동사 (원형)
        "신고하다", "납부하다", "절세하다",
    ],
    "hr_labor": [
        # 명사
        "근로", "채용", "해고", "급여", "퇴직금", "연차",
        "인사", "노무", "4대보험", "근로계약", "취업규칙",
        "권고사직", "정리해고",
        "월급", "임금", "최저임금", "수당", "주휴",
        "산재", "산업재해", "직장내괴롭힘", "괴롭힘", "육아휴직",
        "출산휴가", "파견", "비정규직", "정규직", "수습",
        "야근", "초과근무", "휴일근무", "교대근무",
        "징계", "감봉", "경고", "시말서",
        "단체협약", "노조", "노동조합",
        # 근무시간/근무제 관련
        "근무", "근무제", "근무시간", "근로시간", "연장근로",
        "위반", "처벌", "벌금", "과태료",
        "휴가", "휴직", "병가", "경조사",
        # 동사 (원형)
        "짜르다", "짤리다",
    ],
    "law_common": [
        # 법률 일반
        "법률", "법령", "조문", "판례", "법규", "규정",
        "상법", "민법", "행정법", "공정거래법",
        # 소송/분쟁
        "소장", "고소", "고발", "항소", "상고",
        "손해배상", "배상", "합의", "조정", "중재",
        # 지식재산권
        "지식재산", "출원", "등록", "침해",
        # 전문가
        "변호사", "법무사", "변리사",
        # 계약법
        "계약법", "약관", "이행", "채무불이행", "해제",
        # 소송/분쟁 (hr_labor에서 이전)
        "소송", "분쟁", "특허", "상표", "저작권",
        # 동사 (원형)
        "고소하다", "소송하다", "항소하다",
    ],
}

# 복합 키워드 규칙: lemma 집합 내 조합으로 도메인 판별
# 단독으로는 오탐 가능하지만, 조합 시 도메인 확정 가능한 패턴
# 각 규칙은 (도메인, 필수 키워드 집합) 형태
_DEFAULT_DOMAIN_COMPOUND_RULES: list[tuple[str, set[str]]] = [
    # "지원" + 기업/사업/기관/중소 → 지원사업
    ("startup_funding", {"지원", "기업"}),
    ("startup_funding", {"지원", "사업"}),
    ("startup_funding", {"지원", "중소"}),
    ("startup_funding", {"지원", "소상공인"}),
    ("startup_funding", {"지원", "벤처"}),
    # "등록" + 사업/법인 → 창업
    ("startup_funding", {"등록", "사업"}),
    ("startup_funding", {"등록", "법인"}),
    # 법률 복합 규칙
    ("law_common", {"법", "위반"}),
    ("law_common", {"법", "적용"}),
    ("law_common", {"법적", "절차"}),
    ("law_common", {"법적", "문제"}),
]


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
    min_doc_embedding_similarity: float = Field(
        default=0.2, ge=0.0, le=1.0, description="문서별 최소 임베딩 유사도 점수"
    )

    # Multi-Query 설정
    multi_query_count: int = Field(
        default=3, gt=0, description="Multi-Query 생성 개수"
    )

    # 평가 후 재시도 설정
    enable_post_eval_retry: bool = Field(
        default=True, description="평가 실패 시 재시도 활성화 (비활성화 시 로깅만)"
    )

    # 통합 생성 에이전트 설정
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
        "enable_context_compression",
        "enable_response_cache",
        "reranker_type",
        "enable_vector_domain_classification",
        "enable_llm_domain_classification",
        "multi_query_count",
        "enable_ragas_evaluation",
        "enable_post_eval_retry",
        "enable_legal_supplement",
        "enable_adaptive_search",
        "enable_dynamic_k",
        "enable_graduated_retry",
        "max_retry_level",
        "primary_domain_budget_ratio",
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


_settings: Settings | None = None


def get_settings() -> Settings:
    """Settings 인스턴스를 반환합니다 (싱글톤).

    Returns:
        Settings 인스턴스
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Settings 싱글톤을 리셋합니다 (테스트용)."""
    global _settings
    _settings = None


def create_llm(
    label: str,
    temperature: float | None = None,
    request_timeout: float | None = None,
) -> "ChatOpenAI":
    """ChatOpenAI 인스턴스를 생성합니다.

    Args:
        label: 토큰 트래킹 레이블 (예: "생성", "평가")
        temperature: None이면 settings.openai_temperature 사용
        request_timeout: None이면 설정하지 않음

    Returns:
        ChatOpenAI 인스턴스
    """
    from langchain_openai import ChatOpenAI
    from utils.token_tracker import TokenUsageCallbackHandler

    settings = get_settings()
    kwargs: dict = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": temperature if temperature is not None else settings.openai_temperature,
        "callbacks": [TokenUsageCallbackHandler(label)],
    }
    if request_timeout is not None:
        kwargs["request_timeout"] = request_timeout
    return ChatOpenAI(**kwargs)


# ===================================================================
# 도메인별 대표 쿼리 (임베딩 미리 계산)
# ===================================================================

DOMAIN_REPRESENTATIVE_QUERIES: dict[str, list[str]] = {
    "startup_funding": [
        "사업자등록 절차가 궁금합니다",
        "창업 지원사업 추천해주세요",
        "법인 설립 방법을 알려주세요",
        "정부 보조금 신청 방법",
        "마케팅 전략 조언",
        "스타트업 초기 자금 조달",
        "업종별 인허가 필요한가요",
        "창업 아이템 검증 방법",
        "예비창업자 지원 프로그램",
        "소상공인 지원정책",
        "가게 어떻게 차려요",
        "카페 창업 비용이 얼마나 드나요",
        "음식점 개업 절차 알려주세요",
        "프랜차이즈 가맹점 열고 싶어요",
        "헬스장 차리려면 뭐가 필요해요",
        "우리 지역에 기업 지원해주는 사업 있나요",
        "IT 기업 대상 정부 지원 프로그램 알려주세요",
    ],
    "finance_tax": [
        "부가세 신고 방법",
        "법인세 계산 방법",
        "세금 절세 방법",
        "회계 처리 방법",
        "재무제표 작성법",
        "원천징수 신고 절차",
        "세무조정 어떻게 하나요",
        "종합소득세 신고 기한",
        "매입세액 공제 조건",
        "결산 절차가 궁금합니다",
        "종소세 언제 내야 하나요",
        "부가세 납부 기한이 언제예요",
        "양도세 얼마나 나와요",
        "연말정산 어떻게 해요",
        "간이과세자 기준이 뭐예요",
    ],
    "hr_labor": [
        "퇴직금 계산 방법",
        "근로계약서 작성법",
        "4대보험 가입 방법",
        "연차 계산 방법",
        "해고 절차",
        "최저임금 적용 기준",
        "야근 수당 계산",
        "취업규칙 작성 방법",
        "근로시간 단축 제도",
        "채용 공고 작성법",
        "직원 짤랐는데 퇴직금 얼마 줘야 해요",
        "월급에서 세금 얼마나 떼나요",
        "주휴수당 계산법 알려주세요",
        "권고사직 시 절차가 어떻게 되나요",
        "알바 4대보험 가입해야 하나요",
        "주 52시간 근무제 위반 시 처벌이 어떻게 되나요",
        "연장근로 한도와 수당 계산법을 알려주세요",
        "육아휴직 신청 조건과 급여 기준",
        "직장내 괴롭힘 신고 방법이 궁금합니다",
        "출산휴가 기간과 급여는 어떻게 되나요",
    ],
    "law_common": [
        "소송 절차가 어떻게 되나요",
        "분쟁 해결 방법 알려주세요",
        "특허 출원 방법이 궁금합니다",
        "상표 등록 절차 안내해주세요",
        "저작권 침해 시 대응 방법",
        "상법에서 이사의 의무는 무엇인가요",
        "민법상 계약 해제 요건",
        "손해배상 청구 방법",
        "지식재산권 보호 방법",
        "법인 이사의 책임에 대해 알려주세요",
        "계약서 분쟁 시 어떻게 해야 하나요",
        "특허 침해 소송 절차가 궁금합니다",
        "회사 관련 법적 분쟁 해결",
    ],
}


# ===================================================================
# DomainConfig: MySQL 기반 도메인 설정 관리
# ===================================================================

@dataclass
class DomainConfig:
    """도메인 분류 설정 데이터.

    Attributes:
        keywords: 도메인별 키워드 리스트
        compound_rules: (도메인, 필수 lemma 집합) 튜플 리스트
        representative_queries: 도메인별 대표 쿼리 리스트
    """

    keywords: dict[str, list[str]] = field(default_factory=dict)
    compound_rules: list[tuple[str, set[str]]] = field(default_factory=list)
    representative_queries: dict[str, list[str]] = field(default_factory=dict)


# 모듈 레벨 캐시
_domain_config: DomainConfig | None = None


def _get_default_config() -> DomainConfig:
    """하드코딩된 기본 설정을 반환합니다 (fallback용).

    Returns:
        기본 DomainConfig
    """
    return DomainConfig(
        keywords=dict(_DEFAULT_DOMAIN_KEYWORDS),
        compound_rules=list(_DEFAULT_DOMAIN_COMPOUND_RULES),
        representative_queries=dict(DOMAIN_REPRESENTATIVE_QUERIES),
    )


def _get_connection() -> pymysql.Connection:
    """MySQL 연결을 생성합니다.

    Returns:
        pymysql Connection 객체
    """
    settings = get_settings()
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _tables_exist(conn: pymysql.Connection) -> bool:
    """도메인 설정 테이블이 존재하는지 확인합니다."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'domain'"
        )
        result = cursor.fetchone()
        return result["cnt"] > 0


def _has_data(conn: pymysql.Connection) -> bool:
    """도메인 테이블에 데이터가 있는지 확인합니다."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS cnt FROM domain")
        result = cursor.fetchone()
        return result["cnt"] > 0


def init_db() -> None:
    """MySQL에 도메인 설정 테이블을 생성하고 시드 데이터를 삽입합니다.

    테이블이 이미 존재하고 데이터가 있으면 건너뜁니다.
    """
    try:
        conn = _get_connection()
    except Exception:
        logger.warning("[도메인 설정 DB] MySQL 연결 실패, 하드코딩 기본값 사용")
        return

    try:
        if _tables_exist(conn) and _has_data(conn):
            logger.info("[도메인 설정 DB] 기존 테이블/데이터 사용")
            return

        if not _tables_exist(conn):
            _create_tables(conn)

        if not _has_data(conn):
            _seed_data(conn)
            conn.commit()
            logger.info("[도메인 설정 DB] 시드 데이터 삽입 완료")
    finally:
        conn.close()


def _create_tables(conn: pymysql.Connection) -> None:
    """테이블을 생성합니다."""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain` (
                `domain_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_key` VARCHAR(50) NOT NULL UNIQUE,
                `name` VARCHAR(100) NOT NULL,
                `sort_order` INT DEFAULT 0,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_keyword` (
                `keyword_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `keyword` VARCHAR(100) NOT NULL,
                `keyword_type` VARCHAR(20) DEFAULT 'noun',
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE,
                UNIQUE KEY `uq_domain_keyword` (`domain_id`, `keyword`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_compound_rule` (
                `rule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `required_lemmas` JSON NOT NULL,
                `description` VARCHAR(255) DEFAULT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_representative_query` (
                `query_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `query_text` VARCHAR(500) NOT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()
    logger.info("[도메인 설정 DB] 테이블 생성 완료")


def _seed_data(conn: pymysql.Connection) -> None:
    """현재 하드코딩 값으로 시드 데이터를 삽입합니다."""
    default = _get_default_config()

    domain_names = {
        "startup_funding": "창업/지원사업",
        "finance_tax": "재무/세무",
        "hr_labor": "인사/노무",
        "law_common": "법률",
    }

    domain_ids: dict[str, int] = {}

    with conn.cursor() as cursor:
        # 도메인 삽입
        for i, domain_key in enumerate(["startup_funding", "finance_tax", "hr_labor", "law_common"]):
            name = domain_names[domain_key]
            cursor.execute(
                "INSERT INTO domain (domain_key, name, sort_order) VALUES (%s, %s, %s)",
                (domain_key, name, i),
            )
            domain_ids[domain_key] = cursor.lastrowid

        # 키워드 삽입
        for domain_key, keywords in default.keywords.items():
            domain_id = domain_ids[domain_key]
            for kw in keywords:
                kw_type = "verb" if kw.endswith("다") else "noun"
                cursor.execute(
                    "INSERT INTO domain_keyword (domain_id, keyword, keyword_type) "
                    "VALUES (%s, %s, %s)",
                    (domain_id, kw, kw_type),
                )

        # 복합 규칙 삽입
        for domain_key, required_lemmas in default.compound_rules:
            domain_id = domain_ids[domain_key]
            lemmas_json = json.dumps(sorted(required_lemmas), ensure_ascii=False)
            desc = "+".join(sorted(required_lemmas)) + " → " + domain_key
            cursor.execute(
                "INSERT INTO domain_compound_rule (domain_id, required_lemmas, description) "
                "VALUES (%s, %s, %s)",
                (domain_id, lemmas_json, desc),
            )

        # 대표 쿼리 삽입
        for domain_key, queries in default.representative_queries.items():
            domain_id = domain_ids[domain_key]
            for query_text in queries:
                cursor.execute(
                    "INSERT INTO domain_representative_query (domain_id, query_text) "
                    "VALUES (%s, %s)",
                    (domain_id, query_text),
                )


def load_domain_config() -> DomainConfig:
    """MySQL에서 도메인 설정을 로드합니다.

    DB 연결 실패 시 하드코딩 기본값을 반환합니다.

    Returns:
        DomainConfig 인스턴스
    """
    try:
        conn = _get_connection()
    except Exception:
        logger.warning("[도메인 설정 DB] MySQL 연결 실패, 하드코딩 기본값 사용")
        return _get_default_config()

    try:
        if not _tables_exist(conn) or not _has_data(conn):
            logger.warning("[도메인 설정 DB] 테이블/데이터 없음, 하드코딩 기본값 사용")
            return _get_default_config()

        config = DomainConfig()

        with conn.cursor() as cursor:
            # 활성 도메인 조회
            cursor.execute(
                "SELECT domain_id, domain_key FROM domain "
                "WHERE use_yn = 1 ORDER BY sort_order"
            )
            domains = cursor.fetchall()

            domain_map: dict[int, str] = {
                row["domain_id"]: row["domain_key"] for row in domains
            }

            # 키워드 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT keyword FROM domain_keyword "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                config.keywords[domain_key] = [
                    row["keyword"] for row in cursor.fetchall()
                ]

            # 복합 규칙 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT required_lemmas FROM domain_compound_rule "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                for row in cursor.fetchall():
                    lemmas_raw = row["required_lemmas"]
                    # MySQL JSON 컬럼은 이미 파싱된 리스트로 반환될 수 있음
                    if isinstance(lemmas_raw, str):
                        lemmas = set(json.loads(lemmas_raw))
                    else:
                        lemmas = set(lemmas_raw)
                    config.compound_rules.append((domain_key, lemmas))

            # 대표 쿼리 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT query_text FROM domain_representative_query "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                config.representative_queries[domain_key] = [
                    row["query_text"] for row in cursor.fetchall()
                ]

        logger.info(
            "[도메인 설정 DB] 로드 완료: 키워드 %d개, 규칙 %d개, 쿼리 %d개",
            sum(len(kws) for kws in config.keywords.values()),
            len(config.compound_rules),
            sum(len(qs) for qs in config.representative_queries.values()),
        )
        return config

    finally:
        conn.close()


def get_domain_config() -> DomainConfig:
    """캐시된 DomainConfig 싱글톤을 반환합니다.

    Returns:
        DomainConfig 인스턴스
    """
    global _domain_config
    if _domain_config is None:
        _domain_config = load_domain_config()
    return _domain_config


def reload_domain_config() -> DomainConfig:
    """도메인 설정을 다시 로드합니다.

    Returns:
        새로 로드된 DomainConfig
    """
    global _domain_config
    _domain_config = load_domain_config()
    logger.info("[도메인 설정 DB] 설정 리로드 완료")
    return _domain_config


def reset_domain_config() -> None:
    """캐시된 DomainConfig를 초기화합니다 (테스트용)."""
    global _domain_config
    _domain_config = None
