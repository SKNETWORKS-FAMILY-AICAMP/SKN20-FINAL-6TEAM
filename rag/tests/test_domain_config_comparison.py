"""하드코딩 vs MySQL DB 도메인 분류 비교 테스트.

단일 도메인(각 2개), 복합 도메인(3개), 거부(3개) 총 12개 케이스에 대해
두 방식의 분류 결과가 동일한지 검증합니다.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from utils.domain_classifier import (
    VectorDomainClassifier,
    DomainClassificationResult,
    extract_lemmas,
)
from utils.config import (
    DomainConfig,
    _get_default_config,
    load_domain_config,
    reload_domain_config,
    reset_domain_config,
)


# === 단일 도메인 케이스 (도메인별 2개) ===
SINGLE_DOMAIN_CASES = [
    # startup_funding
    (
        "프랜차이즈 가맹점 개업 절차가 궁금합니다",
        ["startup_funding"],
        "프랜차이즈개업-startup",
    ),
    (
        "소상공인 정책자금 대출 조건이 어떻게 되나요",
        ["startup_funding"],
        "정책자금-startup",
    ),
    # finance_tax
    (
        "부가가치세 간이과세자 기준이 뭔가요",
        ["finance_tax"],
        "부가가치세-finance",
    ),
    (
        "법인세 결산 방법 알려주세요",
        ["finance_tax"],
        "법인세결산-finance",
    ),
    # hr_labor
    (
        "주휴수당 계산법이 어떻게 되나요",
        ["hr_labor"],
        "주휴수당-hr",
    ),
    (
        "직원을 권고사직 시키려면 절차가 어떻게 되나요",
        ["hr_labor"],
        "권고사직-hr",
    ),
]

# === 복합 도메인 케이스 (3개) ===
MULTI_DOMAIN_CASES = [
    (
        "창업하면서 직원 채용할 때 4대보험 어떻게 하나요",
        ["startup_funding", "hr_labor"],
        "창업+채용-startup+hr",
    ),
    (
        "법인설립 후 법인세 신고 절차가 궁금해요",
        ["startup_funding", "finance_tax"],
        "법인설립+법인세-startup+finance",
    ),
    (
        "프랜차이즈 개업하면 직원 급여에서 원천징수 어떻게 하나요",
        ["startup_funding", "finance_tax", "hr_labor"],
        "개업+급여+원천징수-all",
    ),
]

# === 거부 케이스 (3개) ===
REJECTION_CASES = [
    ("오늘 서울 날씨 어때요", [], "날씨-거부"),
    ("피자 맛있는 집 추천해주세요", [], "맛집-거부"),
    ("챗GPT가 뭐야", [], "챗GPT-거부"),
]

# 전체 합산
ALL_CASES = SINGLE_DOMAIN_CASES + MULTI_DOMAIN_CASES + REJECTION_CASES
ALL_IDS = [c[2] for c in ALL_CASES]


@pytest.fixture(autouse=True)
def _reset():
    """각 테스트 전후로 캐시 초기화."""
    reset_domain_config()
    yield
    reset_domain_config()


@pytest.fixture
def mock_settings():
    """Mock 설정."""
    settings = MagicMock()
    settings.domain_classification_threshold = 0.6
    settings.enable_vector_domain_classification = True
    settings.enable_llm_domain_classification = False
    settings.openai_api_key = "test-key"
    return settings


def _make_mock_conn_for_config(config: DomainConfig):
    """DomainConfig 데이터로 mock MySQL 연결을 생성합니다."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # tables_exist + has_data
    cursor.fetchone.side_effect = [{"cnt": 1}, {"cnt": 3}]

    # 도메인 목록
    domain_keys = ["startup_funding", "finance_tax", "hr_labor", "law_common"]
    domains = [
        {"domain_id": i + 1, "domain_key": dk}
        for i, dk in enumerate(domain_keys)
    ]
    fetchall_results = [domains]

    # 키워드
    for dk in domain_keys:
        fetchall_results.append(
            [{"keyword": kw} for kw in config.keywords.get(dk, [])]
        )

    # 복합 규칙
    rules_by_domain: dict[str, list] = {}
    for dk, lemmas in config.compound_rules:
        rules_by_domain.setdefault(dk, []).append(
            {"required_lemmas": json.dumps(sorted(lemmas), ensure_ascii=False)}
        )
    for dk in domain_keys:
        fetchall_results.append(rules_by_domain.get(dk, []))

    # 대표 쿼리
    for dk in domain_keys:
        fetchall_results.append(
            [{"query_text": q} for q in config.representative_queries.get(dk, [])]
        )

    cursor.fetchall.side_effect = fetchall_results
    return conn


def _keyword_classify_with_config(
    query: str,
    config: DomainConfig,
) -> DomainClassificationResult | None:
    """주어진 DomainConfig로 키워드 분류를 수행합니다."""
    lemmas = extract_lemmas(query)
    detected_domains: list[str] = []
    matched_keywords: dict[str, list[str]] = {}

    for domain, keywords in config.keywords.items():
        keyword_set = set(keywords)
        hits = list(lemmas & keyword_set)
        for kw in keywords:
            if len(kw) >= 2 and kw in query and kw not in hits:
                hits.append(kw)
        if hits:
            detected_domains.append(domain)
            matched_keywords[domain] = hits

    if not detected_domains:
        for domain, required_lemmas in config.compound_rules:
            if required_lemmas.issubset(lemmas):
                if domain not in detected_domains:
                    detected_domains.append(domain)
                matched_keywords.setdefault(domain, []).append(
                    "+".join(sorted(required_lemmas))
                )
                break

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


# ===================================================================
# 1. 하드코딩 단독 테스트
# ===================================================================


class TestHardcodedSingleDomain:
    """하드코딩 기반 단일 도메인 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        SINGLE_DOMAIN_CASES,
        ids=[c[2] for c in SINGLE_DOMAIN_CASES],
    )
    def test_single_domain(self, query, expected_domains, test_id):
        config = _get_default_config()
        result = _keyword_classify_with_config(query, config)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains), (
            f"도메인 불일치: 예상={expected_domains}, 실제={result.domains}"
        )


class TestHardcodedMultiDomain:
    """하드코딩 기반 복합 도메인 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        MULTI_DOMAIN_CASES,
        ids=[c[2] for c in MULTI_DOMAIN_CASES],
    )
    def test_multi_domain(self, query, expected_domains, test_id):
        config = _get_default_config()
        result = _keyword_classify_with_config(query, config)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains), (
            f"도메인 불일치: 예상={expected_domains}, 실제={result.domains}"
        )


class TestHardcodedRejection:
    """하드코딩 기반 거부 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        REJECTION_CASES,
        ids=[c[2] for c in REJECTION_CASES],
    )
    def test_rejection(self, query, expected_domains, test_id):
        config = _get_default_config()
        result = _keyword_classify_with_config(query, config)
        assert result is None, f"거부 예상했으나 매칭됨: {result.domains}"


# ===================================================================
# 2. MySQL (mock) 단독 테스트
# ===================================================================


class TestMySQLSingleDomain:
    """MySQL (mock) 기반 단일 도메인 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        SINGLE_DOMAIN_CASES,
        ids=[c[2] for c in SINGLE_DOMAIN_CASES],
    )
    @patch("utils.config._get_connection")
    def test_single_domain(self, mock_get_conn, query, expected_domains, test_id):
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        config = load_domain_config()
        result = _keyword_classify_with_config(query, config)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains), (
            f"도메인 불일치: 예상={expected_domains}, 실제={result.domains}"
        )


class TestMySQLMultiDomain:
    """MySQL (mock) 기반 복합 도메인 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        MULTI_DOMAIN_CASES,
        ids=[c[2] for c in MULTI_DOMAIN_CASES],
    )
    @patch("utils.config._get_connection")
    def test_multi_domain(self, mock_get_conn, query, expected_domains, test_id):
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        config = load_domain_config()
        result = _keyword_classify_with_config(query, config)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains), (
            f"도메인 불일치: 예상={expected_domains}, 실제={result.domains}"
        )


class TestMySQLRejection:
    """MySQL (mock) 기반 거부 분류 테스트."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        REJECTION_CASES,
        ids=[c[2] for c in REJECTION_CASES],
    )
    @patch("utils.config._get_connection")
    def test_rejection(self, mock_get_conn, query, expected_domains, test_id):
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        config = load_domain_config()
        result = _keyword_classify_with_config(query, config)
        assert result is None, f"거부 예상했으나 매칭됨: {result.domains}"


# ===================================================================
# 3. 하드코딩 vs MySQL 동일성 비교 (핵심)
# ===================================================================


class TestHardcodedVsMySQLComparison:
    """하드코딩 vs MySQL 결과 동일성 비교 (12개 전 케이스)."""

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        ALL_CASES,
        ids=ALL_IDS,
    )
    @patch("utils.config._get_connection")
    def test_domains_match(self, mock_get_conn, query, expected_domains, test_id):
        """두 방식의 도메인 분류 결과가 동일합니다."""
        h_config = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(h_config)
        s_config = load_domain_config()

        h_result = _keyword_classify_with_config(query, h_config)
        s_result = _keyword_classify_with_config(query, s_config)

        if h_result is None:
            assert s_result is None, (
                f"불일치: 하드코딩=None, MySQL={s_result.domains}"
            )
        else:
            assert s_result is not None, (
                f"불일치: 하드코딩={h_result.domains}, MySQL=None"
            )
            assert set(h_result.domains) == set(s_result.domains), (
                f"도메인 불일치: 하드코딩={h_result.domains}, "
                f"MySQL={s_result.domains}"
            )

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        ALL_CASES,
        ids=ALL_IDS,
    )
    @patch("utils.config._get_connection")
    def test_confidence_match(self, mock_get_conn, query, expected_domains, test_id):
        """두 방식의 신뢰도가 동일합니다."""
        h_config = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(h_config)
        s_config = load_domain_config()

        h_result = _keyword_classify_with_config(query, h_config)
        s_result = _keyword_classify_with_config(query, s_config)

        if h_result is None:
            return  # 거부 케이스는 신뢰도 비교 불필요

        assert h_result.confidence == s_result.confidence, (
            f"신뢰도 불일치: 하드코딩={h_result.confidence}, "
            f"MySQL={s_result.confidence}"
        )

    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        ALL_CASES,
        ids=ALL_IDS,
    )
    @patch("utils.config._get_connection")
    def test_matched_keywords_match(self, mock_get_conn, query, expected_domains, test_id):
        """두 방식의 매칭 키워드가 동일합니다."""
        h_config = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(h_config)
        s_config = load_domain_config()

        h_result = _keyword_classify_with_config(query, h_config)
        s_result = _keyword_classify_with_config(query, s_config)

        if h_result is None:
            return

        for domain in h_result.matched_keywords:
            h_kws = set(h_result.matched_keywords[domain])
            s_kws = set(s_result.matched_keywords[domain])
            assert h_kws == s_kws, (
                f"[{domain}] 키워드 불일치: 하드코딩={h_kws}, MySQL={s_kws}"
            )


# ===================================================================
# 4. VectorDomainClassifier 통합 테스트 (12개 전 케이스)
# ===================================================================


class TestClassifierIntegration:
    """VectorDomainClassifier._keyword_classify() 통합 테스트."""

    @pytest.fixture
    def classifier(self, mock_settings):
        """테스트용 분류기."""
        mock_embeddings = MagicMock()
        with patch(
            "utils.domain_classifier.get_settings",
            return_value=mock_settings,
        ):
            clf = VectorDomainClassifier(mock_embeddings)
            clf.settings = mock_settings
            return clf

    # --- 단일 도메인 ---
    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        SINGLE_DOMAIN_CASES,
        ids=[c[2] for c in SINGLE_DOMAIN_CASES],
    )
    @patch("utils.config._get_connection")
    def test_single_domain(self, mock_get_conn, classifier, query, expected_domains, test_id):
        """단일 도메인 키워드 매칭."""
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        reload_domain_config()
        result = classifier._keyword_classify(query)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains)

    # --- 복합 도메인 ---
    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        MULTI_DOMAIN_CASES,
        ids=[c[2] for c in MULTI_DOMAIN_CASES],
    )
    @patch("utils.config._get_connection")
    def test_multi_domain(self, mock_get_conn, classifier, query, expected_domains, test_id):
        """복합 도메인 키워드 매칭."""
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        reload_domain_config()
        result = classifier._keyword_classify(query)
        assert result is not None, f"키워드 매칭 실패: {query}"
        assert set(result.domains) == set(expected_domains), (
            f"도메인 불일치: 예상={expected_domains}, 실제={result.domains}"
        )

    # --- 거부 ---
    @pytest.mark.parametrize(
        "query, expected_domains, test_id",
        REJECTION_CASES,
        ids=[c[2] for c in REJECTION_CASES],
    )
    @patch("utils.config._get_connection")
    def test_rejection(self, mock_get_conn, classifier, query, expected_domains, test_id):
        """도메인 외 질문은 None 반환."""
        default = _get_default_config()
        mock_get_conn.return_value = _make_mock_conn_for_config(default)
        reload_domain_config()
        result = classifier._keyword_classify(query)
        assert result is None, f"거부 예상했으나 매칭됨: {result.domains}"
