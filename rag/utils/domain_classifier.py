"""벡터 유사도 기반 도메인 분류 및 MySQL 설정 관리 모듈.

LLM 호출 없이 임베딩 유사도로 도메인을 분류합니다.
키워드 매칭과 벡터 유사도를 둘 다 실행하여 벡터가 최종 결정권을 가집니다.
키워드 매칭은 신뢰도 보정용으로만 사용됩니다.

키워드 매칭은 kiwipiepy 형태소 분석기를 사용하여 원형(lemma) 기반으로 수행합니다.

도메인 키워드, 복합 규칙, 대표 쿼리를 MySQL DB에서 관리합니다.
DB 연결 실패 시 기존 하드코딩 값으로 자동 fallback합니다.
"""

import json
import logging
import time as _time
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pymysql
from kiwipiepy import Kiwi
from langchain_huggingface import HuggingFaceEmbeddings

from utils.config import create_llm, get_settings
from utils.prompts import (
    LLM_DOMAIN_CLASSIFICATION_PROMPT,
    _DEFAULT_DOMAIN_COMPOUND_RULES,
    _DEFAULT_DOMAIN_KEYWORDS,
)

logger = logging.getLogger(__name__)


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


# ===================================================================
# 도메인 분류 결과 및 형태소 분석
# ===================================================================

@dataclass
class DomainClassificationResult:
    """도메인 분류 결과.

    Attributes:
        domains: 분류된 도메인 리스트
        confidence: 분류 신뢰도 (0.0-1.0)
        is_relevant: 관련 질문 여부
        method: 분류 방법 ('keyword', 'vector', 'fallback')
        matched_keywords: 키워드 매칭 시 매칭된 키워드들
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: str
    matched_keywords: dict[str, list[str]] | None = None


@lru_cache(maxsize=1)
def _get_kiwi() -> Kiwi:
    """Kiwi 형태소 분석기 싱글톤."""
    return Kiwi()


def extract_lemmas(query: str) -> set[str]:
    """쿼리에서 명사와 동사/형용사 원형을 추출합니다.

    Args:
        query: 사용자 질문

    Returns:
        추출된 lemma 집합 (명사 원형 + 동사/형용사 '~다' 형태)
    """
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(query)
    lemmas: set[str] = set()

    for token in tokens:
        if token.tag.startswith("NN") or token.tag == "SL":
            # 명사, 외래어 → 그대로
            lemmas.add(token.form)
        elif token.tag.startswith("VV") or token.tag.startswith("VA"):
            # 동사/형용사 → 원형 + "다"
            lemmas.add(token.form + "다")

    return lemmas


# ===================================================================
# VectorDomainClassifier
# ===================================================================

class VectorDomainClassifier:
    """벡터 유사도 기반 도메인 분류기 (LLM 미사용).

    키워드 매칭 + 벡터 유사도를 둘 다 실행하여 벡터가 최종 결정권을 가집니다.
    키워드 매칭은 신뢰도 보정(+0.1)용으로만 사용됩니다.

    Attributes:
        embeddings: HuggingFace 임베딩 모델
        settings: RAG 설정
        _domain_vectors: 도메인별 대표 쿼리 임베딩 벡터

    Example:
        >>> from vectorstores.embeddings import get_embeddings
        >>> classifier = VectorDomainClassifier(get_embeddings())
        >>> result = classifier.classify("사업자등록 절차가 궁금합니다")
        >>> print(result.domains)  # ['startup_funding']
    """

    # 클래스 레벨 벡터 캐시 (모든 인스턴스에서 공유)
    _DOMAIN_VECTORS_CACHE: dict[str, np.ndarray] | None = None

    def __init__(self, embeddings: HuggingFaceEmbeddings):
        """VectorDomainClassifier를 초기화합니다.

        Args:
            embeddings: HuggingFace 임베딩 인스턴스
        """
        self.embeddings = embeddings
        self.settings = get_settings()
        self._domain_vectors: dict[str, np.ndarray] | None = None

    def _precompute_vectors(self) -> dict[str, np.ndarray]:
        """도메인별 대표 쿼리 벡터를 미리 계산합니다.

        클래스 레벨 캐시를 사용하여 인스턴스 간 중복 계산을 방지합니다.

        Returns:
            도메인별 평균 임베딩 벡터
        """
        # 1. 클래스 레벨 캐시 확인
        if VectorDomainClassifier._DOMAIN_VECTORS_CACHE is not None:
            return VectorDomainClassifier._DOMAIN_VECTORS_CACHE

        # 2. 인스턴스 레벨 캐시 확인
        if self._domain_vectors is not None:
            return self._domain_vectors

        logger.info("[도메인 분류] 대표 쿼리 벡터 계산 중... (첫 요청 시 지연 발생 가능)")
        precompute_start = _time.time()
        domain_vectors: dict[str, np.ndarray] = {}

        config = get_domain_config()
        for domain, queries in config.representative_queries.items():
            # 각 도메인의 대표 쿼리들 임베딩
            vectors = self.embeddings.embed_documents(queries)
            # 평균 벡터 계산 (centroid)
            domain_vectors[domain] = np.mean(vectors, axis=0)
            logger.debug(
                "[도메인 분류] %s: %d개 쿼리 임베딩 완료",
                domain,
                len(queries),
            )

        # 클래스 레벨 캐시에 저장
        VectorDomainClassifier._DOMAIN_VECTORS_CACHE = domain_vectors
        self._domain_vectors = domain_vectors
        elapsed = _time.time() - precompute_start
        logger.info("[도메인 분류] 대표 쿼리 벡터 계산 완료 (%.2f초)", elapsed)
        return domain_vectors

    def _keyword_classify(self, query: str) -> DomainClassificationResult | None:
        """형태소 분석 + 키워드 기반 도메인 분류.

        kiwipiepy로 쿼리를 형태소 분석하여 원형(lemma)을 추출한 뒤,
        DOMAIN_KEYWORDS의 원형 키워드와 매칭합니다.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과 (키워드 매칭 실패 시 None)
        """
        lemmas = extract_lemmas(query)
        detected_domains: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        config = get_domain_config()

        for domain, keywords in config.keywords.items():
            # lemma 집합과 키워드 집합의 교집합
            keyword_set = set(keywords)
            hits = list(lemmas & keyword_set)
            # 원문 부분 문자열 매칭도 보조 (복합명사 대응: "사업자등록" in query)
            for kw in keywords:
                if len(kw) >= 2 and kw in query and kw not in hits:
                    hits.append(kw)
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        # 복합 키워드 규칙 체크 (단일 키워드로 못 잡는 패턴)
        if not detected_domains:
            for domain, required_lemmas in config.compound_rules:
                if required_lemmas.issubset(lemmas):
                    if domain not in detected_domains:
                        detected_domains.append(domain)
                    matched_keywords.setdefault(domain, []).append(
                        "+".join(sorted(required_lemmas))
                    )
                    break  # 첫 매칭 규칙만 적용

        if detected_domains:
            total_matches = sum(len(kws) for kws in matched_keywords.values())
            confidence = min(1.0, 0.5 + (total_matches * 0.1))

            return DomainClassificationResult(
                domains=detected_domains,
                confidence=confidence,
                is_relevant=True,
                method="keyword",
                matched_keywords=matched_keywords,
            )

        return None

    def _vector_classify(self, query: str) -> DomainClassificationResult:
        """벡터 유사도 기반 도메인 분류.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과
        """
        domain_vectors = self._precompute_vectors()

        # 쿼리 임베딩
        query_vector = np.array(self.embeddings.embed_query(query))

        # 각 도메인과의 코사인 유사도 계산
        similarities: dict[str, float] = {}
        for domain, domain_vec in domain_vectors.items():
            # 코사인 유사도 (이미 정규화된 벡터)
            similarity = float(np.dot(query_vector, domain_vec))
            similarities[domain] = similarity

        # 유사도 내림차순 정렬
        sorted_domains = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        logger.debug("[도메인 분류] 벡터 유사도: %s", sorted_domains)

        threshold = self.settings.domain_classification_threshold
        best_domain, best_score = sorted_domains[0]

        # 임계값 미만이면 도메인 외 질문으로 판단
        if best_score < threshold:
            return DomainClassificationResult(
                domains=[],
                confidence=best_score,
                is_relevant=False,
                method="vector",
            )

        # 복수 도메인 탐지: 최고 점수와 0.1 이내 차이인 도메인 포함
        detected_domains = [best_domain]
        for domain, score in sorted_domains[1:]:
            if best_score - score < 0.1 and score >= threshold:
                detected_domains.append(domain)

        return DomainClassificationResult(
            domains=detected_domains,
            confidence=best_score,
            is_relevant=True,
            method="vector",
        )

    def _llm_classify(self, query: str) -> DomainClassificationResult:
        """LLM 기반 도메인 분류.

        벡터 분류와 비교하기 위한 참조 분류입니다.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과
        """
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            llm = create_llm("도메인분류", temperature=0.0)
            prompt = ChatPromptTemplate.from_messages([
                ("human", LLM_DOMAIN_CLASSIFICATION_PROMPT),
            ])
            chain = prompt | llm | StrOutputParser()

            response = chain.invoke({"query": query})

            # JSON 파싱
            # 코드 블록 제거
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # 첫 줄 (```json) 과 마지막 줄 (```) 제거
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)

            return DomainClassificationResult(
                domains=result.get("domains", []),
                confidence=float(result.get("confidence", 0.5)),
                is_relevant=result.get("is_relevant", True),
                method="llm",
            )

        except Exception as e:
            logger.warning("[도메인 분류] LLM 분류 실패: %s", e)
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_error",
            )

    def _log_classification_comparison(
        self,
        primary_result: DomainClassificationResult,
        llm_result: DomainClassificationResult,
    ) -> None:
        """벡터 vs LLM 분류 비교 로깅.

        Args:
            primary_result: 1차 분류 결과 (키워드 또는 벡터)
            llm_result: LLM 분류 결과
        """
        primary_domains = set(primary_result.domains)
        llm_domains = set(llm_result.domains)
        match = primary_domains == llm_domains

        logger.info(
            "[도메인 비교] %s=%s (%.2f) | LLM=%s (%.2f) | 일치=%s",
            primary_result.method.upper(),
            list(primary_result.domains),
            primary_result.confidence,
            list(llm_result.domains),
            llm_result.confidence,
            "YES" if match else "NO",
        )

        if not match:
            logger.debug(
                "[도메인 비교] 불일치 상세 - 1차만: %s, LLM만: %s",
                list(primary_domains - llm_domains),
                list(llm_domains - primary_domains),
            )

    def classify(self, query: str) -> DomainClassificationResult:
        """질문을 분류하여 관련 도메인과 신뢰도를 반환합니다.

        키워드 매칭과 벡터 유사도를 둘 다 실행하여 벡터가 최종 결정권을 가집니다.
        키워드 매칭은 신뢰도 보정(+0.1)용으로만 사용됩니다.

        Args:
            query: 사용자 질문

        Returns:
            도메인 분류 결과
        """
        # 1. 키워드 매칭 (0ms, 즉시)
        keyword_result = self._keyword_classify(query)

        # 2. 벡터 유사도 분류 (항상 실행)
        if self.settings.enable_vector_domain_classification:
            vector_result = self._vector_classify(query)
        else:
            vector_result = None

        # 3. 결과 조합: 벡터 + 키워드 보정 후 최종 판정
        if vector_result:
            threshold = self.settings.domain_classification_threshold

            # 키워드 매칭 시 벡터 유사도에 보정 적용 (threshold 판정 전)
            if keyword_result:
                boosted_confidence = min(1.0, vector_result.confidence + 0.1)

                # 벡터가 이미 통과했거나, 키워드 보정(+0.1) 후 threshold 이상이면
                # keyword+vector 확정으로 재판정
                if vector_result.is_relevant or boosted_confidence >= threshold:
                    # 보정된 신뢰도로 재판정
                    if boosted_confidence >= threshold:
                        # 키워드 도메인 기준으로 결과 생성
                        final_domains = keyword_result.domains if not vector_result.is_relevant else vector_result.domains
                        vector_result.domains = final_domains
                        vector_result.confidence = boosted_confidence
                        vector_result.is_relevant = True
                        vector_result.method = "keyword+vector"
                        vector_result.matched_keywords = keyword_result.matched_keywords
                        logger.info(
                            "[도메인 분류] 키워드+벡터 확정: %s (신뢰도: %.2f, 키워드: %s)",
                            vector_result.domains,
                            vector_result.confidence,
                            keyword_result.matched_keywords,
                        )
                        return vector_result

            if vector_result.is_relevant:
                logger.info(
                    "[도메인 분류] 벡터 유사도 확정: %s (신뢰도: %.2f)",
                    vector_result.domains,
                    vector_result.confidence,
                )
                return vector_result

            # 벡터 미통과 + 키워드 보정 없음 → 거부
            if keyword_result:
                logger.info(
                    "[도메인 분류] 키워드 '%s' 매칭됐으나 벡터 유사도 %.2f로 거부",
                    keyword_result.matched_keywords,
                    vector_result.confidence,
                )
            return vector_result

        # 벡터 분류 비활성화 시 키워드 결과 또는 fallback
        if keyword_result:
            logger.info(
                "[도메인 분류] 벡터 비활성화, 키워드 매칭: %s (신뢰도: %.2f)",
                keyword_result.domains,
                keyword_result.confidence,
            )
            return keyword_result

        # fallback: 분류 불가 → 도메인 외 질문으로 처리
        logger.warning("[도메인 분류] 분류 실패, 도메인 외 질문으로 거부")
        return DomainClassificationResult(
            domains=[],
            confidence=0.0,
            is_relevant=False,
            method="fallback_rejected",
        )


@lru_cache(maxsize=1)
def get_domain_classifier() -> VectorDomainClassifier:
    """VectorDomainClassifier 싱글톤 인스턴스를 반환합니다.

    Returns:
        VectorDomainClassifier 인스턴스
    """
    from vectorstores.embeddings import get_embeddings

    return VectorDomainClassifier(get_embeddings())
