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

    def test_result_fields_with_irrelevant(self) -> None:
        """비관련 질문 결과 필드 검증."""
        result = DomainClassificationResult(
            domains=[],
            confidence=0.45,
            is_relevant=False,
            method="llm",
        )

        assert result.domains == []
        assert result.confidence == 0.45
        assert result.is_relevant is False

    def test_intent_default_none(self) -> None:
        """intent 필드 기본값 None 검증."""
        result = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.9,
            is_relevant=True,
            method="llm",
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
    def mock_settings(self) -> Mock:
        """테스트용 설정."""
        mock_settings = Mock()
        mock_settings.domain_classification_max_retries = 2
        return mock_settings

    @pytest.fixture
    def classifier(self, mock_settings: Mock) -> DomainClassifier:
        """DomainClassifier 인스턴스."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            return DomainClassifier()

    # ========== classify 테스트 ==========

    def test_classify_llm_success(self, classifier: DomainClassifier) -> None:
        """LLM 분류 성공 → llm 결과 반환."""
        llm_success = DomainClassificationResult(
            domains=["finance_tax"],
            confidence=0.9,
            is_relevant=True,
            method="llm",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_success):
            result = classifier.classify("부가세 신고 방법")

        assert result.method == "llm"
        assert result.domains == ["finance_tax"]
        assert result.is_relevant is True

    def test_classify_passes_original_query(self, classifier: DomainClassifier) -> None:
        """classify가 original_query를 _llm_classify에 전달."""
        llm_success = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.9,
            is_relevant=True,
            method="llm",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_success) as mock_llm:
            classifier.classify("사업자등록 관련 절차를 알려주세요", original_query="안녕")

        mock_llm.assert_called_once_with("사업자등록 관련 절차를 알려주세요", "안녕")

    def test_classify_original_query_none(self, classifier: DomainClassifier) -> None:
        """original_query가 None이면 그대로 전달."""
        llm_success = DomainClassificationResult(
            domains=["finance_tax"],
            confidence=0.9,
            is_relevant=True,
            method="llm",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_success) as mock_llm:
            classifier.classify("세금 신고")

        mock_llm.assert_called_once_with("세금 신고", None)

    def test_classify_retry_on_failure(self, mock_settings: Mock) -> None:
        """LLM 실패 시 domain_classification_max_retries만큼 재시도."""
        mock_settings.domain_classification_max_retries = 2
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
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

    def test_classify_all_retries_fail(self, mock_settings: Mock) -> None:
        """모든 LLM 재시도 실패 → llm_retry_failed."""
        mock_settings.domain_classification_max_retries = 1
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result):
            result = classifier.classify("오늘 날씨")

        assert result.method == "llm_retry_failed"
        assert result.is_relevant is False

    def test_classify_zero_retries(self, mock_settings: Mock) -> None:
        """domain_classification_max_retries=0 시 재시도 없이 즉시 실패."""
        mock_settings.domain_classification_max_retries = 0
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result) as mock_llm:
            result = classifier.classify("오늘 날씨")

        # 초기 1회 호출만 (재시도 0회)
        assert mock_llm.call_count == 1
        assert result.method == "llm_retry_failed"

    def test_classify_retry_call_count(self, mock_settings: Mock) -> None:
        """재시도 횟수가 정확한지 확인 (초기 1회 + 재시도 N회)."""
        mock_settings.domain_classification_max_retries = 3
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = DomainClassifier()

        error_result = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error"
        )
        with patch.object(classifier, "_llm_classify", return_value=error_result) as mock_llm:
            result = classifier.classify("테스트 쿼리")

        # 초기 1회 + 재시도 3회 = 4회
        assert mock_llm.call_count == 4
        assert result.method == "llm_retry_failed"

    def test_classify_chitchat_intent(self, classifier: DomainClassifier) -> None:
        """Chitchat intent가 정상 반환되는지 확인."""
        chitchat_result = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="llm",
            intent="chitchat_greeting",
        )
        with patch.object(classifier, "_llm_classify", return_value=chitchat_result):
            result = classifier.classify("안녕하세요")

        assert result.intent == "chitchat_greeting"
        assert result.is_relevant is False
        assert result.domains == []


class TestLLMIntentParsing:
    """LLM 분류 시 intent 필드 파싱 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        mock_settings = Mock()
        mock_settings.domain_classification_max_retries = 2

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
