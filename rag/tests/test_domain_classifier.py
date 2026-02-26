"""VectorDomainClassifier 단위 테스트."""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from utils.domain_classifier import (
    DOMAIN_REPRESENTATIVE_QUERIES,
    DomainClassificationResult,
    VectorDomainClassifier,
    get_domain_classifier,
    reset_domain_classifier,
)


class TestDomainClassificationResult:
    """DomainClassificationResult 데이터 클래스 테스트."""

    def test_result_fields_with_keyword_method(self):
        """키워드 매칭 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.7,
            is_relevant=True,
            method="keyword",
            matched_keywords={"startup_funding": ["창업", "사업자등록"]},
        )

        assert result.domains == ["startup_funding"]
        assert result.confidence == 0.7
        assert result.is_relevant is True
        assert result.method == "keyword"
        assert result.matched_keywords == {"startup_funding": ["창업", "사업자등록"]}

    def test_result_fields_with_vector_method(self):
        """벡터 유사도 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=["finance_tax", "hr_labor"],
            confidence=0.85,
            is_relevant=True,
            method="vector",
        )

        assert result.domains == ["finance_tax", "hr_labor"]
        assert result.confidence == 0.85
        assert result.is_relevant is True
        assert result.method == "vector"
        assert result.matched_keywords is None

    def test_result_fields_with_irrelevant(self):
        """비관련 질문 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=[],
            confidence=0.45,
            is_relevant=False,
            method="vector",
        )

        assert result.domains == []
        assert result.confidence == 0.45
        assert result.is_relevant is False
        assert result.method == "vector"


class TestVectorDomainClassifier:
    """VectorDomainClassifier 클래스 테스트."""

    @pytest.fixture(autouse=True)
    def _clear_vector_cache(self):
        """테스트 간 클래스 레벨 벡터 캐시를 초기화합니다."""
        VectorDomainClassifier._DOMAIN_VECTORS_CACHE = None
        yield
        VectorDomainClassifier._DOMAIN_VECTORS_CACHE = None

    @pytest.fixture
    def mock_embeddings(self):
        """Mock HuggingFaceEmbeddings."""
        mock = Mock()
        # embed_documents 반환값: 10개 쿼리 x 1024 차원
        mock.embed_documents.return_value = [
            np.random.randn(1024).tolist() for _ in range(10)
        ]
        # embed_query 반환값: 1024 차원 벡터
        mock.embed_query.return_value = np.random.randn(1024).tolist()
        return mock

    @pytest.fixture
    def mock_settings_with_vector_enabled(self):
        """벡터 분류 활성화된 테스트용 설정."""
        mock_settings = Mock()
        mock_settings.domain_classification_threshold = 0.6
        mock_settings.enable_vector_domain_classification = True
        mock_settings.enable_llm_domain_classification = False
        mock_settings.multi_domain_gap_threshold = 0.15
        return mock_settings

    @pytest.fixture
    def classifier(self, mock_embeddings, mock_settings_with_vector_enabled):
        """VectorDomainClassifier 인스턴스."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings_with_vector_enabled
            return VectorDomainClassifier(mock_embeddings)

    # ========== _keyword_classify 테스트 ==========

    def test_keyword_classify_single_domain(self, classifier):
        """단일 도메인 키워드 매칭."""
        query = "창업할 때 마케팅 전략이 궁금합니다"

        result = classifier._keyword_classify(query)

        assert result is not None
        assert result.domains == ["startup_funding"]
        assert result.confidence >= 0.5
        assert result.is_relevant is True
        assert result.method == "keyword"
        assert "startup_funding" in result.matched_keywords
        assert "창업" in result.matched_keywords["startup_funding"]
        assert "마케팅" in result.matched_keywords["startup_funding"]

    def test_keyword_classify_multiple_domains(self, classifier):
        """복수 도메인 키워드 매칭."""
        query = "창업할 때 세금 신고와 4대보험은 어떻게 하나요"

        result = classifier._keyword_classify(query)

        assert result is not None
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert "hr_labor" in result.domains
        assert result.confidence >= 0.5
        assert result.is_relevant is True
        assert result.method == "keyword"

    def test_keyword_classify_no_match(self, classifier):
        """키워드 매칭 실패."""
        query = "오늘 날씨가 어떤가요"

        result = classifier._keyword_classify(query)

        assert result is None

    def test_keyword_classify_confidence_calculation(self, classifier):
        """매칭된 키워드 수에 따른 신뢰도 계산."""
        # 1개 매칭: 0.5 + 0.1 = 0.6
        query_single = "창업"
        result_single = classifier._keyword_classify(query_single)
        assert result_single.confidence == pytest.approx(0.6)

        # 2개 매칭: 0.5 + 0.2 = 0.7
        query_multiple = "창업 마케팅"
        result_multiple = classifier._keyword_classify(query_multiple)
        assert result_multiple.confidence == pytest.approx(0.7)

        # 5개 이상 매칭: max 1.0
        query_many = "창업 사업자등록 법인설립 지원사업 보조금 마케팅"
        result_many = classifier._keyword_classify(query_many)
        assert result_many.confidence == 1.0

    # ========== _precompute_vectors 테스트 ==========

    def test_precompute_vectors_calculates_all_domains(self, classifier):
        """모든 도메인의 벡터를 미리 계산."""
        domain_vectors = classifier._precompute_vectors()

        assert len(domain_vectors) == len(DOMAIN_REPRESENTATIVE_QUERIES)
        assert "startup_funding" in domain_vectors
        assert "finance_tax" in domain_vectors
        assert "hr_labor" in domain_vectors
        assert "law_common" in domain_vectors

        # 각 도메인 벡터가 1024 차원인지 확인
        for domain, vector in domain_vectors.items():
            assert isinstance(vector, np.ndarray)
            assert vector.shape == (1024,)

    def test_precompute_vectors_caches_result(self, classifier, mock_embeddings):
        """벡터 계산 결과를 캐싱."""
        # 첫 호출
        result1 = classifier._precompute_vectors()
        call_count_first = mock_embeddings.embed_documents.call_count

        # 두 번째 호출 (캐시 사용)
        result2 = classifier._precompute_vectors()
        call_count_second = mock_embeddings.embed_documents.call_count

        # 같은 객체 반환
        assert result1 is result2
        # embed_documents 추가 호출 없음
        assert call_count_first == call_count_second

    def test_precompute_vectors_averages_query_embeddings(
        self, classifier, mock_embeddings
    ):
        """대표 쿼리 임베딩의 평균 벡터 계산."""
        # Mock 데이터 준비
        mock_vectors = [np.array([1.0, 2.0, 3.0]) for _ in range(10)]
        mock_embeddings.embed_documents.return_value = mock_vectors

        # _domain_vectors 초기화 (캐시 무효화)
        classifier._domain_vectors = None

        domain_vectors = classifier._precompute_vectors()

        # 평균 벡터 검증 (모든 벡터가 동일하므로 평균도 동일)
        for domain, vector in domain_vectors.items():
            assert np.allclose(vector, [1.0, 2.0, 3.0])

    # ========== _vector_classify 테스트 ==========

    def test_keyword_classify_law_common_domain(self, classifier):
        """법률 도메인 키워드 매칭."""
        query = "특허 출원 절차와 소송 방법이 궁금합니다"

        result = classifier._keyword_classify(query)

        assert result is not None
        assert "law_common" in result.domains
        assert result.is_relevant is True
        assert result.method == "keyword"
        assert "law_common" in result.matched_keywords

    def test_vector_classify_above_threshold(
        self, classifier, mock_embeddings, mock_settings_with_vector_enabled
    ):
        """임계값 이상 - 관련 질문."""
        # 정규화된 단위 벡터 사용 (dot product = cosine similarity)
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0  # 단위 벡터

        # startup_funding: 높은 유사도 (cos ≈ 0.9)
        domain_vec_high = np.zeros(1024)
        domain_vec_high[0] = 0.9
        domain_vec_high[1] = 0.4359  # sqrt(1 - 0.81) ≈ 0.4359
        domain_vec_high = domain_vec_high / np.linalg.norm(domain_vec_high)

        # 낮은 유사도 (cos ≈ 0.3)
        domain_vec_low = np.zeros(1024)
        domain_vec_low[0] = 0.3
        domain_vec_low[2] = 0.9539  # sqrt(1 - 0.09) ≈ 0.9539
        domain_vec_low = domain_vec_low / np.linalg.norm(domain_vec_low)

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": domain_vec_high,
            "finance_tax": domain_vec_low,
            "hr_labor": domain_vec_low,
            "law_common": domain_vec_low,
        }

        result = classifier._vector_classify("사업자등록 방법")

        assert result.is_relevant is True
        assert result.domains == ["startup_funding"]
        assert result.confidence >= mock_settings_with_vector_enabled.domain_classification_threshold
        assert result.method == "vector"

    def test_vector_classify_below_threshold(
        self, classifier, mock_embeddings, mock_settings_with_vector_enabled
    ):
        """임계값 미만 - 비관련 질문."""
        # Mock 설정: 코사인 유사도가 임계값(0.6) 미만이 되도록
        # 직교에 가까운 벡터 사용 (같은 방향의 스칼라 배수는 유사도 1.0)
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0  # 첫 번째 축 방향

        domain_vec_low = np.zeros(1024)
        domain_vec_low[1] = 1.0  # 두 번째 축 방향 (직교 → 유사도 ≈ 0)

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": domain_vec_low,
            "finance_tax": domain_vec_low,
            "hr_labor": domain_vec_low,
            "law_common": domain_vec_low,
        }

        result = classifier._vector_classify("오늘 날씨가 어떤가요")

        assert result.is_relevant is False
        assert result.domains == []
        assert result.confidence < mock_settings_with_vector_enabled.domain_classification_threshold
        assert result.method == "vector"

    def test_vector_classify_multiple_domains_within_threshold(
        self, classifier, mock_embeddings
    ):
        """복수 도메인 탐지: 최고 점수와 0.1 이내 차이."""
        # 정규화된 단위 벡터 사용 (dot product = cosine similarity)
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0  # 단위 벡터

        # startup_funding: cos ≈ 0.9
        vec_sf = np.zeros(1024)
        vec_sf[0] = 0.9
        vec_sf[1] = np.sqrt(1 - 0.81)
        vec_sf = vec_sf / np.linalg.norm(vec_sf)

        # finance_tax: cos ≈ 0.85 (차이 0.05 < 0.1)
        vec_ft = np.zeros(1024)
        vec_ft[0] = 0.85
        vec_ft[2] = np.sqrt(1 - 0.7225)
        vec_ft = vec_ft / np.linalg.norm(vec_ft)

        # hr_labor: cos ≈ 0.5 (차이 0.4 > 0.1)
        vec_hl = np.zeros(1024)
        vec_hl[0] = 0.5
        vec_hl[3] = np.sqrt(1 - 0.25)
        vec_hl = vec_hl / np.linalg.norm(vec_hl)

        # law_common: cos ≈ 0.5 (차이 0.4 > 0.1)
        vec_lc = np.zeros(1024)
        vec_lc[0] = 0.5
        vec_lc[4] = np.sqrt(1 - 0.25)
        vec_lc = vec_lc / np.linalg.norm(vec_lc)

        classifier._domain_vectors = {
            "startup_funding": vec_sf,
            "finance_tax": vec_ft,
            "hr_labor": vec_hl,
            "law_common": vec_lc,
        }

        mock_embeddings.embed_query.return_value = query_vec

        result = classifier._vector_classify("창업과 세무")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert "hr_labor" not in result.domains

    # ========== classify 통합 테스트 ==========

    def _setup_high_similarity_vectors(self, classifier, mock_embeddings):
        """높은 벡터 유사도 설정 헬퍼."""
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0

        # startup_funding: 높은 유사도 (cos ≈ 0.9)
        vec_high = np.zeros(1024)
        vec_high[0] = 0.9
        vec_high[1] = np.sqrt(1 - 0.81)
        vec_high = vec_high / np.linalg.norm(vec_high)

        # 나머지: 낮은 유사도 (cos ≈ 0.3)
        vec_low = np.zeros(1024)
        vec_low[0] = 0.3
        vec_low[2] = np.sqrt(1 - 0.09)
        vec_low = vec_low / np.linalg.norm(vec_low)

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": vec_high,
            "finance_tax": vec_low,
            "hr_labor": vec_low,
            "law_common": vec_low,
        }

    def _setup_low_similarity_vectors(self, classifier, mock_embeddings):
        """낮은 벡터 유사도(직교) 설정 헬퍼."""
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0

        domain_vec_1 = np.zeros(1024)
        domain_vec_1[1] = 1.0
        domain_vec_2 = np.zeros(1024)
        domain_vec_2[2] = 1.0
        domain_vec_3 = np.zeros(1024)
        domain_vec_3[3] = 1.0
        domain_vec_4 = np.zeros(1024)
        domain_vec_4[4] = 1.0

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": domain_vec_1,
            "finance_tax": domain_vec_2,
            "hr_labor": domain_vec_3,
            "law_common": domain_vec_4,
        }

    def test_classify_keyword_and_vector_both_pass(self, classifier, mock_embeddings):
        """키워드+벡터 모두 통과 → keyword+vector 확정, 신뢰도 +0.1 보정."""
        query = "창업 절차가 궁금합니다"
        self._setup_high_similarity_vectors(classifier, mock_embeddings)

        result = classifier.classify(query)

        assert result.method == "keyword+vector"
        assert "startup_funding" in result.domains
        assert result.is_relevant is True
        assert result.matched_keywords is not None
        # 벡터 신뢰도 + 0.1 보정 확인
        assert result.confidence > 0.6
        mock_embeddings.embed_query.assert_called_once()

    def test_classify_keyword_pass_vector_fail_rejected(
        self, classifier, mock_embeddings
    ):
        """키워드 매칭 성공 + 벡터 미통과 → 거부 (키워드에 낚임 방지)."""
        query = "이번에 새로 창업한 가게에서 두쫀쿠 판대~"
        self._setup_low_similarity_vectors(classifier, mock_embeddings)

        result = classifier.classify(query)

        assert result.is_relevant is False
        assert result.domains == []
        # 벡터가 최종 결정권: 키워드 매칭됐더라도 거부
        assert result.method == "vector"

    def test_classify_no_keyword_vector_pass(self, classifier, mock_embeddings):
        """키워드 미매칭 + 벡터 통과 → vector 확정."""
        query = "법인 설립 시 필요한 서류"
        self._setup_high_similarity_vectors(classifier, mock_embeddings)

        result = classifier.classify(query)

        assert result.method == "vector"
        assert result.domains == ["startup_funding"]
        assert result.is_relevant is True
        mock_embeddings.embed_query.assert_called_once()

    def test_classify_no_keyword_vector_fail_rejected(
        self, classifier, mock_embeddings
    ):
        """키워드 미매칭 + 벡터 미통과 → 거부."""
        query = "오늘 날씨가 어떤가요"
        self._setup_low_similarity_vectors(classifier, mock_embeddings)

        result = classifier.classify(query)

        assert result.method == "vector"
        assert result.is_relevant is False
        assert result.domains == []

    def test_classify_keyword_vector_confidence_boost_capped_at_1(
        self, classifier, mock_embeddings
    ):
        """신뢰도 보정이 1.0을 초과하지 않는지 확인."""
        query = "창업 사업자등록 법인설립 지원사업 보조금 마케팅"

        # 매우 높은 벡터 유사도 설정 (0.95+)
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0

        vec_very_high = np.zeros(1024)
        vec_very_high[0] = 0.98
        vec_very_high[1] = np.sqrt(1 - 0.9604)
        vec_very_high = vec_very_high / np.linalg.norm(vec_very_high)

        vec_low = np.zeros(1024)
        vec_low[1] = 1.0

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": vec_very_high,
            "finance_tax": vec_low,
            "hr_labor": vec_low,
            "law_common": vec_low,
        }

        result = classifier.classify(query)

        assert result.confidence <= 1.0
        assert result.method == "keyword+vector"

    def test_classify_vector_always_called_even_with_keyword_match(
        self, classifier, mock_embeddings
    ):
        """키워드 매칭되더라도 벡터 분류가 항상 호출되는지 확인."""
        query = "창업 절차가 궁금합니다"
        self._setup_high_similarity_vectors(classifier, mock_embeddings)

        classifier.classify(query)

        # 벡터 분류가 항상 호출됨
        mock_embeddings.embed_query.assert_called_once()

    # ========== 키워드 보정 threshold 인접 회귀 테스트 ==========

    def _setup_specific_similarity_vectors(
        self,
        classifier: VectorDomainClassifier,
        mock_embeddings: Mock,
        target_similarity: float,
    ) -> None:
        """특정 코사인 유사도를 가지는 벡터를 설정하는 헬퍼.

        Args:
            classifier: VectorDomainClassifier 인스턴스
            mock_embeddings: Mock 임베딩
            target_similarity: startup_funding에 설정할 코사인 유사도
        """
        query_vec = np.zeros(1024)
        query_vec[0] = 1.0

        # startup_funding: target_similarity
        vec_target = np.zeros(1024)
        vec_target[0] = target_similarity
        vec_target[1] = np.sqrt(1 - target_similarity ** 2)
        vec_target = vec_target / np.linalg.norm(vec_target)

        # 나머지: 낮은 유사도 (cos ≈ 0.0, 직교)
        vec_low_1 = np.zeros(1024)
        vec_low_1[2] = 1.0
        vec_low_2 = np.zeros(1024)
        vec_low_2[3] = 1.0
        vec_low_3 = np.zeros(1024)
        vec_low_3[4] = 1.0

        mock_embeddings.embed_query.return_value = query_vec
        classifier._domain_vectors = {
            "startup_funding": vec_target,
            "finance_tax": vec_low_1,
            "hr_labor": vec_low_2,
            "law_common": vec_low_3,
        }

    def test_classify_keyword_boost_crosses_threshold(
        self, classifier: VectorDomainClassifier, mock_embeddings: Mock
    ) -> None:
        """벡터 0.56 + 키워드 보정 → 0.66으로 threshold(0.6) 통과."""
        query = "창업 절차가 궁금합니다"
        self._setup_specific_similarity_vectors(classifier, mock_embeddings, 0.56)

        result = classifier.classify(query)

        assert result.is_relevant is True
        assert result.method == "keyword+vector"
        assert result.confidence == pytest.approx(0.66, abs=0.01)
        assert "startup_funding" in result.domains

    def test_classify_keyword_boost_still_below_threshold(
        self, classifier: VectorDomainClassifier, mock_embeddings: Mock
    ) -> None:
        """벡터 0.45 + 키워드 보정 → 0.55로 여전히 threshold(0.6) 미만."""
        query = "창업 절차가 궁금합니다"
        self._setup_specific_similarity_vectors(classifier, mock_embeddings, 0.45)

        result = classifier.classify(query)

        assert result.is_relevant is False
        assert result.method == "vector"

    def test_classify_keyword_boost_at_exact_threshold(
        self, classifier: VectorDomainClassifier, mock_embeddings: Mock
    ) -> None:
        """벡터 0.50 + 키워드 보정 → 0.60 = threshold 정확히 일치 (>= 통과)."""
        query = "창업 절차가 궁금합니다"
        self._setup_specific_similarity_vectors(classifier, mock_embeddings, 0.50)

        result = classifier.classify(query)

        assert result.is_relevant is True
        assert result.method == "keyword+vector"
        assert result.confidence == pytest.approx(0.60, abs=0.01)

    def test_classify_fallback_to_keyword_when_vector_disabled(
        self, mock_embeddings
    ):
        """벡터 분류 비활성화 시 키워드 결과 사용."""
        mock_settings = Mock()
        mock_settings.enable_vector_domain_classification = False
        mock_settings.enable_llm_domain_classification = False

        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = VectorDomainClassifier(mock_embeddings)

            query = "창업 절차가 궁금합니다"
            result = classifier.classify(query)

            assert result.method == "keyword"
            assert result.domains == ["startup_funding"]
            assert result.is_relevant is True
            mock_embeddings.embed_query.assert_not_called()

    def test_classify_fallback_to_rejection_when_vector_disabled_no_keyword(
        self, mock_embeddings
    ):
        """벡터 분류 비활성화 + 키워드 미매칭 시 도메인 외 질문으로 거부."""
        mock_settings = Mock()
        mock_settings.enable_vector_domain_classification = False
        mock_settings.enable_llm_domain_classification = False

        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = VectorDomainClassifier(mock_embeddings)

            query = "알 수 없는 질문"
            result = classifier.classify(query)

            assert result.method == "fallback_rejected"
            assert result.domains == []
            assert result.confidence == 0.0
            assert result.is_relevant is False


    def test_classify_llm_rejection_overridden_by_keyword(self, mock_embeddings):
        """In LLM-only mode, keyword hit should override false out-of-scope."""
        mock_settings = Mock()
        mock_settings.enable_vector_domain_classification = False
        mock_settings.enable_llm_domain_classification = True

        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = VectorDomainClassifier(mock_embeddings)

        with patch.object(
            classifier,
            "_llm_classify",
            return_value=DomainClassificationResult(
                domains=[],
                confidence=0.9,
                is_relevant=False,
                method="llm",
            ),
        ):
            result = classifier.classify("창업 사업자등록 절차 알려줘")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains
        assert result.method == "llm+keyword_override"

    def test_classify_llm_rejection_overridden_by_heuristic(self, mock_embeddings):
        """If keyword classifier misses, heuristic fallback should still recover domain."""
        mock_settings = Mock()
        mock_settings.enable_vector_domain_classification = False
        mock_settings.enable_llm_domain_classification = True

        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = VectorDomainClassifier(mock_embeddings)

        with patch.object(
            classifier,
            "_llm_classify",
            return_value=DomainClassificationResult(
                domains=[],
                confidence=0.8,
                is_relevant=False,
                method="llm",
            ),
        ), patch.object(classifier, "_keyword_classify", return_value=None):
            result = classifier.classify("사업자등록 순서와 부가세 신고 주기 알려줘")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert result.method == "llm+heuristic_override"


class TestGetDomainClassifier:
    """get_domain_classifier 싱글톤 함수 테스트."""

    def test_singleton_returns_same_instance(self):
        """싱글톤 패턴 검증 - 같은 인스턴스 반환."""
        with patch("vectorstores.embeddings.get_embeddings") as mock_get_embeddings:
            mock_embeddings = Mock()
            mock_get_embeddings.return_value = mock_embeddings

            # lru_cache 초기화
            reset_domain_classifier()

            instance1 = get_domain_classifier()
            instance2 = get_domain_classifier()

            assert instance1 is instance2
            # get_embeddings는 한 번만 호출 (싱글톤)
            mock_get_embeddings.assert_called_once()

    def test_singleton_calls_get_embeddings(self):
        """get_embeddings 호출 확인."""
        with patch("vectorstores.embeddings.get_embeddings") as mock_get_embeddings:
            mock_embeddings = Mock()
            mock_get_embeddings.return_value = mock_embeddings

            reset_domain_classifier()
            classifier = get_domain_classifier()

            assert isinstance(classifier, VectorDomainClassifier)
            mock_get_embeddings.assert_called_once()
