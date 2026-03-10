"""DomainClassifier 단위 테스트."""

from unittest.mock import Mock, patch

import pytest

from utils.domain_classifier import (
    DomainClassificationResult,
    DomainClassifier,
    DomainEvaluation,
    LLMClassificationOutput,
    VALID_DOMAINS,
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
        mock_settings.enable_keyword_guardrail = False
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
        mock_settings.enable_keyword_guardrail = False

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


class TestKeywordGuardrail:
    """키워드 가드레일 테스트."""

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """테스트용 설정."""
        mock_settings = Mock()
        mock_settings.domain_classification_max_retries = 2
        mock_settings.enable_keyword_guardrail = True
        return mock_settings

    @pytest.fixture
    def classifier(self, mock_settings: Mock) -> DomainClassifier:
        """DomainClassifier 인스턴스."""
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            return DomainClassifier()

    # ========== _detect_keyword_domains 테스트 ==========

    def test_detect_startup_keywords(self, classifier: DomainClassifier) -> None:
        """창업 도메인 키워드 감지."""
        result = classifier._detect_keyword_domains("소상공인 정책자금 지원 조건")
        assert "startup_funding" in result

    def test_detect_finance_keywords(self, classifier: DomainClassifier) -> None:
        """세무 도메인 키워드 감지."""
        result = classifier._detect_keyword_domains("부가가치세 신고 기한")
        assert "finance_tax" in result

    def test_detect_hr_keywords(self, classifier: DomainClassifier) -> None:
        """인사노무 도메인 키워드 감지."""
        result = classifier._detect_keyword_domains("출산휴가 기간과 급여")
        assert "hr_labor" in result

    def test_detect_law_keywords(self, classifier: DomainClassifier) -> None:
        """법률 도메인 키워드 감지."""
        result = classifier._detect_keyword_domains("손해배상 소송 절차")
        assert "law_common" in result

    def test_detect_multiple_domains(self, classifier: DomainClassifier) -> None:
        """복수 도메인 키워드 감지."""
        result = classifier._detect_keyword_domains("법인설립 후 법인세 신고")
        assert "startup_funding" in result
        assert "finance_tax" in result

    def test_detect_no_keywords(self, classifier: DomainClassifier) -> None:
        """키워드 미매칭 시 빈 리스트."""
        result = classifier._detect_keyword_domains("오늘 날씨 어때요")
        assert result == []

    # ========== _apply_keyword_guardrail 테스트 ==========

    def test_guardrail_override_llm_rejection(self, classifier: DomainClassifier) -> None:
        """LLM 거부 + 키워드 매칭 → 키워드 오버라이드."""
        llm_result = DomainClassificationResult(
            domains=[], confidence=0.9, is_relevant=False, method="llm",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["startup_funding"], "소상공인 정책자금"
        )
        assert result.method == "keyword_override"
        assert result.domains == ["startup_funding"]
        assert result.is_relevant is True

    def test_guardrail_mismatch_merge(self, classifier: DomainClassifier) -> None:
        """LLM 도메인과 키워드 도메인 완전 불일치 → 병합 (Case 1.5)."""
        llm_result = DomainClassificationResult(
            domains=["finance_tax"], confidence=0.9, is_relevant=True, method="llm",
            intent="consultation",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["startup_funding"], "소상공인 정책자금"
        )
        assert result.method == "keyword_mismatch_merge"
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert result.confidence == 0.75

    def test_guardrail_mismatch_merge_multi_domain(self, classifier: DomainClassifier) -> None:
        """복합 도메인: LLM 도메인과 키워드 완전 불일치 → 모두 병합."""
        llm_result = DomainClassificationResult(
            domains=["hr_labor", "law_common"], confidence=0.85, is_relevant=True, method="llm",
            intent="consultation",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["startup_funding"], "소상공인 창업 관련 해고 분쟁"
        )
        assert result.method == "keyword_mismatch_merge"
        assert "startup_funding" in result.domains
        assert "hr_labor" in result.domains
        assert "law_common" in result.domains

    def test_guardrail_augment_partial_mismatch(self, classifier: DomainClassifier) -> None:
        """LLM 도메인과 키워드 부분 일치 + 저신뢰 → 누락 도메인 병합 (Case 2)."""
        llm_result = DomainClassificationResult(
            domains=["finance_tax"], confidence=0.6, is_relevant=True, method="llm",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["finance_tax", "startup_funding"], "법인설립 후 법인세"
        )
        assert result.method == "keyword_augmented"
        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains

    def test_guardrail_no_change_high_confidence_partial_match(self, classifier: DomainClassifier) -> None:
        """LLM 고신뢰 + 부분 일치 → LLM 결과 유지 (Case 3)."""
        llm_result = DomainClassificationResult(
            domains=["finance_tax", "startup_funding"], confidence=0.95, is_relevant=True, method="llm",
            intent="consultation",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["startup_funding"], "정책자금"
        )
        assert result.method == "llm"
        assert result.domains == ["finance_tax", "startup_funding"]

    def test_guardrail_no_change_matching_domains(self, classifier: DomainClassifier) -> None:
        """LLM 도메인과 키워드 도메인 일치 → 변경 없음."""
        llm_result = DomainClassificationResult(
            domains=["finance_tax"], confidence=0.7, is_relevant=True, method="llm",
            intent="consultation",
        )
        result = classifier._apply_keyword_guardrail(
            llm_result, ["finance_tax"], "부가가치세 신고"
        )
        assert result.method == "llm"

    # ========== classify + 가드레일 통합 테스트 ==========

    def test_classify_with_guardrail_mismatch_merge(self, classifier: DomainClassifier) -> None:
        """classify: LLM 오분류(완전 불일치) → 키워드 병합."""
        llm_wrong = DomainClassificationResult(
            domains=["finance_tax"], confidence=0.85, is_relevant=True, method="llm",
            intent="consultation",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_wrong):
            result = classifier.classify("소상공인 정책자금 지원 조건")

        assert "startup_funding" in result.domains
        assert "finance_tax" in result.domains
        assert result.method == "keyword_mismatch_merge"

    def test_classify_keyword_fallback_on_llm_error(self, classifier: DomainClassifier) -> None:
        """classify: LLM 실패 → 키워드 폴백."""
        llm_error = DomainClassificationResult(
            domains=[], confidence=0.0, is_relevant=False, method="llm_error",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_error):
            result = classifier.classify("부가가치세 신고 기한")

        assert result.method == "keyword_fallback"
        assert result.domains == ["finance_tax"]
        assert result.is_relevant is True

    def test_classify_guardrail_disabled(self, mock_settings: Mock) -> None:
        """enable_keyword_guardrail=False 시 가드레일 비활성화."""
        mock_settings.enable_keyword_guardrail = False
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            classifier = DomainClassifier()

        llm_wrong = DomainClassificationResult(
            domains=["finance_tax"], confidence=0.6, is_relevant=True, method="llm",
            intent="consultation",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_wrong):
            result = classifier.classify("소상공인 정책자금 지원 조건")

        # 가드레일 비활성화 → LLM 결과 그대로
        assert result.method == "llm"
        assert result.domains == ["finance_tax"]


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


class TestLLMClassificationOutput:
    """LLMClassificationOutput Pydantic 모델 테스트."""

    def test_output_model_creation(self) -> None:
        """LLMClassificationOutput 모델 정상 생성."""
        output = LLMClassificationOutput(
            query_analysis="세금 관련 질문",
            is_relevant=True,
            domain_evaluations=[
                DomainEvaluation(domain="finance_tax", is_related=True, evidence="세금 관련"),
                DomainEvaluation(domain="hr_labor", is_related=False, evidence="노무 무관"),
            ],
            confidence=0.9,
            intent="consultation",
            reasoning="세무 도메인 질문",
        )
        assert output.is_relevant is True
        assert len(output.domain_evaluations) == 2
        assert output.domain_evaluations[0].is_related is True

    def test_output_extracts_related_domains(self) -> None:
        """domain_evaluations에서 is_related=True 도메인만 추출."""
        output = LLMClassificationOutput(
            query_analysis="복합 질문",
            is_relevant=True,
            domain_evaluations=[
                DomainEvaluation(domain="startup_funding", is_related=False, evidence="무관"),
                DomainEvaluation(domain="finance_tax", is_related=True, evidence="세금"),
                DomainEvaluation(domain="hr_labor", is_related=True, evidence="퇴직금"),
                DomainEvaluation(domain="law_common", is_related=False, evidence="무관"),
            ],
            confidence=0.85,
            intent="consultation",
            reasoning="세무+노무 복합",
        )
        domains = [e.domain for e in output.domain_evaluations if e.is_related]
        assert domains == ["finance_tax", "hr_labor"]

    def test_valid_domains_constant(self) -> None:
        """VALID_DOMAINS 상수 검증."""
        assert set(VALID_DOMAINS) == {"startup_funding", "finance_tax", "hr_labor", "law_common"}


class TestStructuredOutputIntegration:
    """Structured Output을 사용하는 _llm_classify 통합 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        mock_settings = Mock()
        mock_settings.domain_classification_max_retries = 2
        mock_settings.enable_keyword_guardrail = False
        with patch("utils.domain_classifier.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            return DomainClassifier()

    def test_structured_output_single_domain(self, classifier: DomainClassifier) -> None:
        """Structured output으로 단일 도메인 분류."""
        mock_output = LLMClassificationOutput(
            query_analysis="부가세 신고 관련 질문",
            is_relevant=True,
            domain_evaluations=[
                DomainEvaluation(domain="startup_funding", is_related=False, evidence="창업 무관"),
                DomainEvaluation(domain="finance_tax", is_related=True, evidence="부가세 신고"),
                DomainEvaluation(domain="hr_labor", is_related=False, evidence="노무 무관"),
                DomainEvaluation(domain="law_common", is_related=False, evidence="법률 무관"),
            ],
            confidence=0.9,
            intent="consultation",
            reasoning="세무 도메인",
        )
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_output

        with patch("utils.domain_classifier.create_llm") as mock_create_llm, \
             patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_llm = Mock()
            mock_llm.with_structured_output.return_value = Mock()
            mock_create_llm.return_value = mock_llm
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)

            result = classifier._llm_classify("부가세 신고 방법")

        assert result.domains == ["finance_tax"]
        assert result.confidence == 0.9
        assert result.is_relevant is True
        assert result.method == "llm"

    def test_structured_output_multi_domain(self, classifier: DomainClassifier) -> None:
        """Structured output으로 복합 도메인 분류."""
        mock_output = LLMClassificationOutput(
            query_analysis="해고 절차와 손해배상",
            is_relevant=True,
            domain_evaluations=[
                DomainEvaluation(domain="startup_funding", is_related=False, evidence="무관"),
                DomainEvaluation(domain="finance_tax", is_related=False, evidence="무관"),
                DomainEvaluation(domain="hr_labor", is_related=True, evidence="해고 절차"),
                DomainEvaluation(domain="law_common", is_related=True, evidence="손해배상"),
            ],
            confidence=0.85,
            intent="consultation",
            reasoning="노무+법률 복합",
        )
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_output

        with patch("utils.domain_classifier.create_llm") as mock_create_llm, \
             patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_llm = Mock()
            mock_llm.with_structured_output.return_value = Mock()
            mock_create_llm.return_value = mock_llm
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)

            result = classifier._llm_classify("직원 해고 후 손해배상")

        assert set(result.domains) == {"hr_labor", "law_common"}
        assert result.confidence == 0.85

    def test_structured_output_filters_invalid_domains(self, classifier: DomainClassifier) -> None:
        """유효하지 않은 도메인 이름은 필터링."""
        mock_output = LLMClassificationOutput(
            query_analysis="테스트",
            is_relevant=True,
            domain_evaluations=[
                DomainEvaluation(domain="finance_tax", is_related=True, evidence="세금"),
                DomainEvaluation(domain="invalid_domain", is_related=True, evidence="잘못된"),
            ],
            confidence=0.8,
            intent="consultation",
            reasoning="테스트",
        )
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_output

        with patch("utils.domain_classifier.create_llm") as mock_create_llm, \
             patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_llm = Mock()
            mock_llm.with_structured_output.return_value = Mock()
            mock_create_llm.return_value = mock_llm
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)

            result = classifier._llm_classify("세금 관련")

        assert result.domains == ["finance_tax"]

    def test_structured_output_error_fallback(self, classifier: DomainClassifier) -> None:
        """Structured output 실패 시 llm_error 반환."""
        with patch("utils.domain_classifier.create_llm") as mock_create_llm:
            mock_llm = Mock()
            mock_llm.with_structured_output.side_effect = Exception("structured output failed")
            mock_create_llm.return_value = mock_llm

            result = classifier._llm_classify("테스트 쿼리")

        assert result.method == "llm_error"
        assert result.domains == []
        assert result.is_relevant is False
