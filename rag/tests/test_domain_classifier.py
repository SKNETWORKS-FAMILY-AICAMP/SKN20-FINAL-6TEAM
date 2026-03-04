"""DomainClassifier 단위 테스트."""

from unittest.mock import Mock, patch

import pytest

from utils.domain_classifier import (
    DomainClassificationResult,
    DomainClassifier,
    get_domain_classifier,
    reset_domain_classifier,
)


class TestDomainClassificationResult:
    """DomainClassificationResult 데이터 클래스 테스트."""

    def test_result_fields_with_keyword_method(self) -> None:
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

    def test_result_fields_with_llm_method(self) -> None:
        """LLM 분류 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=["finance_tax", "hr_labor"],
            confidence=0.85,
            is_relevant=True,
            method="llm",
        )

        assert result.domains == ["finance_tax", "hr_labor"]
        assert result.confidence == 0.85
        assert result.is_relevant is True
        assert result.method == "llm"
        assert result.matched_keywords is None

    def test_result_fields_with_irrelevant(self) -> None:
        """비관련 질문 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=[],
            confidence=0.45,
            is_relevant=False,
            method="fallback_rejected",
        )

        assert result.domains == []
        assert result.confidence == 0.45
        assert result.is_relevant is False
        assert result.method == "fallback_rejected"

    def test_intent_default_none(self) -> None:
        """intent 필드 기본값 None 검증."""
        result = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.9,
            is_relevant=True,
            method="keyword",
        )
        assert result.intent is None

    def test_intent_document_generation(self) -> None:
        """intent=document_generation 설정 검증."""
        result = DomainClassificationResult(
            domains=["hr_labor"],
            confidence=0.95,
            is_relevant=True,
            method="llm",
            intent="document_generation",
        )
        assert result.intent == "document_generation"

    def test_intent_consultation(self) -> None:
        """intent=consultation 설정 검증."""
        result = DomainClassificationResult(
            domains=["law_common"],
            confidence=0.90,
            is_relevant=True,
            method="llm",
            intent="consultation",
        )
        assert result.intent == "consultation"


class TestDomainClassifier:
    """DomainClassifier 클래스 테스트."""

    @pytest.fixture
    def mock_settings_llm_enabled(self) -> Mock:
        """LLM 분류 활성화된 테스트용 설정."""
        mock_settings = Mock()
        mock_settings.enable_llm_domain_classification = True
        mock_settings.llm_max_retries = 1
        return mock_settings

    @pytest.fixture
    def mock_settings_llm_disabled(self) -> Mock:
        """LLM 분류 비활성화된 테스트용 설정."""
        mock_settings = Mock()
        mock_settings.enable_llm_domain_classification = False
        return mock_settings

    @pytest.fixture
    def classifier_llm_enabled(self, mock_settings_llm_enabled: Mock) -> DomainClassifier:
        """LLM 모드 DomainClassifier 인스턴스."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings_llm_enabled
            return DomainClassifier()

    @pytest.fixture
    def classifier_llm_disabled(self, mock_settings_llm_disabled: Mock) -> DomainClassifier:
        """키워드 전용 모드 DomainClassifier 인스턴스."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings_llm_disabled
            return DomainClassifier()

    # ========== _keyword_classify 테스트 ==========

    def test_keyword_classify_single_domain(self, classifier_llm_disabled: DomainClassifier) -> None:
        """단일 도메인 키워드 매칭."""
        query = "창업할 때 마케팅 전략이 궁금합니다"

        result = classifier_llm_disabled._keyword_classify(query)

        assert result is not None
        assert result.domains == ["startup_funding"]
        assert result.confidence >= 0.5
        assert result.is_relevant is True
        assert result.method == "keyword"
        assert "startup_funding" in result.matched_keywords
        assert "창업" in result.matched_keywords["startup_funding"]
        assert "마케팅" in result.matched_keywords["startup_funding"]

    def test_keyword_classify_multiple_domains(self, classifier_llm_disabled: DomainClassifier) -> None:
        """복수 도메인 키워드 매칭."""
        query = "창업할 때 세금 신고와 4대보험은 어떻게 하나요"

        result = classifier_llm_disabled._keyword_classify(query)

        assert result is not None
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert "hr_labor" in result.domains
        assert result.confidence >= 0.5
        assert result.is_relevant is True
        assert result.method == "keyword"

    def test_keyword_classify_no_match(self, classifier_llm_disabled: DomainClassifier) -> None:
        """키워드 매칭 실패."""
        query = "오늘 날씨가 어떤가요"

        result = classifier_llm_disabled._keyword_classify(query)

        assert result is None

    def test_keyword_classify_confidence_calculation(self, classifier_llm_disabled: DomainClassifier) -> None:
        """매칭된 키워드 수에 따른 신뢰도 계산."""
        # 1개 매칭: 0.5 + 0.1 = 0.6
        result_single = classifier_llm_disabled._keyword_classify("창업")
        assert result_single.confidence == pytest.approx(0.6)

        # 2개 매칭: 0.5 + 0.2 = 0.7
        result_multiple = classifier_llm_disabled._keyword_classify("창업 마케팅")
        assert result_multiple.confidence == pytest.approx(0.7)

        # 5개 이상 매칭: max 1.0
        result_many = classifier_llm_disabled._keyword_classify("창업 사업자등록 법인설립 지원사업 보조금 마케팅")
        assert result_many.confidence == 1.0

    def test_keyword_classify_law_common_domain(self, classifier_llm_disabled: DomainClassifier) -> None:
        """법률 도메인 키워드 매칭."""
        query = "특허 출원 절차와 소송 방법이 궁금합니다"

        result = classifier_llm_disabled._keyword_classify(query)

        assert result is not None
        assert "law_common" in result.domains
        assert result.is_relevant is True
        assert result.method == "keyword"
        assert "law_common" in result.matched_keywords

    # ========== classify 통합 테스트 (키워드 전용 모드) ==========

    def test_classify_keyword_only_match(self, classifier_llm_disabled: DomainClassifier) -> None:
        """키워드 전용 모드: 키워드 매칭 성공 → keyword 반환."""
        result = classifier_llm_disabled.classify("창업 절차가 궁금합니다")

        assert result.method == "keyword"
        assert "startup_funding" in result.domains
        assert result.is_relevant is True

    def test_classify_keyword_only_no_match_rejected(self, classifier_llm_disabled: DomainClassifier) -> None:
        """키워드 전용 모드: 키워드 미매칭 → fallback_rejected."""
        result = classifier_llm_disabled.classify("오늘 날씨가 어떤가요")

        assert result.method == "fallback_rejected"
        assert result.domains == []
        assert result.is_relevant is False

    # ========== classify 통합 테스트 (LLM 모드) ==========

    def test_classify_llm_result_accepted(self, classifier_llm_enabled: DomainClassifier) -> None:
        """LLM 분류 성공 → llm 결과 반환."""
        llm_success = DomainClassificationResult(
            domains=["finance_tax"],
            confidence=0.9,
            is_relevant=True,
            method="llm",
        )
        with patch.object(classifier_llm_enabled, "_llm_classify", return_value=llm_success):
            result = classifier_llm_enabled.classify("부가세 신고 방법")

        assert result.method == "llm"
        assert result.domains == ["finance_tax"]
        assert result.is_relevant is True

    def test_classify_llm_rejection_overridden_by_keyword(self, classifier_llm_enabled: DomainClassifier) -> None:
        """LLM 모드에서 keyword hit이 false out-of-scope 오버라이드."""
        with patch.object(
            classifier_llm_enabled,
            "_llm_classify",
            return_value=DomainClassificationResult(
                domains=[],
                confidence=0.9,
                is_relevant=False,
                method="llm",
            ),
        ):
            result = classifier_llm_enabled.classify("창업 사업자등록 절차 알려줘")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains
        assert result.method == "llm+keyword_override"

    def test_classify_llm_rejection_overridden_by_heuristic(self, classifier_llm_enabled: DomainClassifier) -> None:
        """keyword 분류 실패 시 heuristic fallback이 도메인 복구."""
        with patch.object(
            classifier_llm_enabled,
            "_llm_classify",
            return_value=DomainClassificationResult(
                domains=[],
                confidence=0.8,
                is_relevant=False,
                method="llm",
            ),
        ), patch.object(classifier_llm_enabled, "_keyword_classify", return_value=None):
            result = classifier_llm_enabled.classify("사업자등록 순서와 부가세 신고 주기 알려줘")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert result.method == "llm+heuristic_override"

    def test_classify_llm_retry_on_failure(self, mock_settings_llm_enabled: Mock) -> None:
        """LLM 실패 시 llm_max_retries 횟수만큼 재시도."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_settings_llm_enabled.llm_max_retries = 1
            mock_get_settings.return_value = mock_settings_llm_enabled
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        success_result = DomainClassificationResult(
            domains=["startup_funding"], confidence=0.9, is_relevant=True, method="llm"
        )
        with patch.object(classifier, "_llm_classify", side_effect=[error_result, success_result]):
            result = classifier.classify("창업 절차")

        assert result.method == "llm_retry"
        assert result.is_relevant is True

    def test_classify_llm_all_retries_fail_keyword_fallback(self, mock_settings_llm_enabled: Mock) -> None:
        """모든 LLM 재시도 실패 시 키워드 fallback."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_settings_llm_enabled.llm_max_retries = 1
            mock_get_settings.return_value = mock_settings_llm_enabled
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result):
            # "창업 절차" → 키워드 매칭 성공 예상
            result = classifier.classify("창업 절차")

        assert result.is_relevant is True
        assert "startup_funding" in result.domains

    def test_classify_llm_all_retries_fail_no_keyword_rejected(self, mock_settings_llm_enabled: Mock) -> None:
        """모든 LLM 재시도 실패 + 키워드 미매칭 → llm_retry_failed."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_settings_llm_enabled.llm_max_retries = 1
            mock_get_settings.return_value = mock_settings_llm_enabled
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result):
            result = classifier.classify("오늘 날씨")  # 키워드 미매칭

        assert result.method == "llm_retry_failed"
        assert result.is_relevant is False

    def test_classify_llm_zero_retries_on_failure(self, mock_settings_llm_enabled: Mock) -> None:
        """llm_max_retries=0 시 재시도 없이 즉시 키워드 fallback."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_settings_llm_enabled.llm_max_retries = 0
            mock_get_settings.return_value = mock_settings_llm_enabled
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result) as mock_llm:
            result = classifier.classify("오늘 날씨")

        # 초기 1회 호출만 (재시도 0회)
        assert mock_llm.call_count == 1
        assert result.method == "llm_retry_failed"


class TestLLMIntentParsing:
    """LLM 분류 시 intent 필드 파싱 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        mock_settings = Mock()
        mock_settings.enable_llm_domain_classification = True
        mock_settings.llm_max_retries = 1

        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            return DomainClassifier()

    def test_llm_returns_document_generation_intent(self, classifier: DomainClassifier) -> None:
        """LLM이 document_generation intent 반환 시 파싱."""
        with patch.object(classifier, "_llm_classify") as mock_llm:
            mock_llm.return_value = DomainClassificationResult(
                domains=["hr_labor"],
                confidence=0.95,
                is_relevant=True,
                method="llm",
                intent="document_generation",
            )
            result = classifier.classify("근로계약서 만들어줘")

        assert result.intent == "document_generation"
        assert result.is_relevant is True
        assert "hr_labor" in result.domains

    def test_llm_returns_consultation_intent(self, classifier: DomainClassifier) -> None:
        """LLM이 consultation intent 반환 시 파싱."""
        with patch.object(classifier, "_llm_classify") as mock_llm:
            mock_llm.return_value = DomainClassificationResult(
                domains=["law_common"],
                confidence=0.90,
                is_relevant=True,
                method="llm",
                intent="consultation",
            )
            result = classifier.classify("계약서 작성할 때 주의사항")

        assert result.intent == "consultation"
        assert result.is_relevant is True
        assert "law_common" in result.domains

    def test_llm_missing_intent_defaults_consultation(self, classifier: DomainClassifier) -> None:
        """LLM 응답에 intent 없으면 consultation 기본값."""
        with patch.object(classifier, "_llm_classify") as mock_llm:
            mock_llm.return_value = DomainClassificationResult(
                domains=["startup_funding"],
                confidence=0.85,
                is_relevant=True,
                method="llm",
                intent="consultation",
            )
            result = classifier.classify("사업자등록 절차")

        assert result.intent == "consultation"


class TestGetDomainClassifier:
    """get_domain_classifier 싱글톤 함수 테스트."""

    def test_singleton_returns_same_instance(self) -> None:
        """싱글톤 패턴 검증 - 같은 인스턴스 반환."""
        reset_domain_classifier()

        instance1 = get_domain_classifier()
        instance2 = get_domain_classifier()

        assert instance1 is instance2

    def test_reset_clears_singleton(self) -> None:
        """reset_domain_classifier가 싱글톤을 초기화."""
        instance1 = get_domain_classifier()
        reset_domain_classifier()
        instance2 = get_domain_classifier()

        assert instance1 is not instance2

    def test_returns_domain_classifier_instance(self) -> None:
        """get_domain_classifier가 DomainClassifier 인스턴스 반환."""
        reset_domain_classifier()
        classifier = get_domain_classifier()

        assert isinstance(classifier, DomainClassifier)
