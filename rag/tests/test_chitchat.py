"""Chitchat(일상 대화) 감지 및 응답 기능 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.domain_classifier import DomainClassificationResult, DomainClassifier
from utils.prompts import CHITCHAT_RESPONSES


class TestChitchatResponses:
    """CHITCHAT_RESPONSES 상수 테스트."""

    def test_all_intents_have_responses(self) -> None:
        """모든 chitchat intent에 대한 응답이 존재."""
        expected_intents = [
            "chitchat_greeting",
            "chitchat_farewell",
            "chitchat_thanks",
            "chitchat_bot_identity",
            "chitchat_affirmative",
            "chitchat_emotional",
        ]
        for intent in expected_intents:
            assert intent in CHITCHAT_RESPONSES
            assert len(CHITCHAT_RESPONSES[intent]) > 0


class TestKeywordChitchat:
    """키워드 모드 chitchat 감지 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        with patch("utils.domain_classifier.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_llm_domain_classification = False
            mock_settings.return_value = settings
            return DomainClassifier()

    def test_greeting_detected(self, classifier: DomainClassifier) -> None:
        """인사말 chitchat 감지."""
        result = classifier._keyword_classify("안녕하세요")
        assert result is not None
        assert result.is_relevant is False
        assert result.domains == []
        assert result.intent == "chitchat_greeting"

    def test_thanks_detected(self, classifier: DomainClassifier) -> None:
        """감사 chitchat 감지."""
        result = classifier._keyword_classify("감사합니다")
        assert result is not None
        assert result.is_relevant is False
        assert result.domains == []
        assert result.intent == "chitchat_greeting"  # keyword mode default

    def test_greeting_plus_domain_not_chitchat(self, classifier: DomainClassifier) -> None:
        """인사 + 도메인 질문 → 도메인으로 분류 (chitchat 아님)."""
        result = classifier._keyword_classify("안녕하세요 세무 질문인데요")
        assert result is not None
        assert result.is_relevant is True
        assert "chitchat" not in result.domains

    def test_pure_domain_unaffected(self, classifier: DomainClassifier) -> None:
        """순수 도메인 질문은 변경 없음."""
        result = classifier._keyword_classify("사업자등록 절차")
        assert result is not None
        assert result.is_relevant is True
        assert "startup_funding" in result.domains


class TestLLMChitchat:
    """LLM 모드 chitchat 처리 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        with patch("utils.domain_classifier.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_llm_domain_classification = True
            settings.llm_max_retries = 1
            mock_settings.return_value = settings
            return DomainClassifier()

    def test_chitchat_skips_guardrail(self, classifier: DomainClassifier) -> None:
        """LLM chitchat intent는 keyword guardrail을 건너뜀."""
        llm_result = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="llm",
            intent="chitchat_greeting",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_result):
            result = classifier.classify("안녕하세요")
        assert result.intent == "chitchat_greeting"
        assert result.is_relevant is False
        assert result.method == "llm"

    def test_non_chitchat_reject_still_uses_guardrail(self, classifier: DomainClassifier) -> None:
        """chitchat이 아닌 거부는 keyword guardrail이 작동."""
        llm_result = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="llm",
            intent="consultation",
        )
        keyword_result = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.7,
            is_relevant=True,
            method="keyword",
            matched_keywords={"startup_funding": ["창업"]},
        )
        with (
            patch.object(classifier, "_llm_classify", return_value=llm_result),
            patch.object(classifier, "_keyword_classify", return_value=keyword_result),
        ):
            result = classifier.classify("창업 절차")
        # keyword guardrail이 override
        assert result.is_relevant is True
        assert "startup_funding" in result.domains


class TestRouterChitchat:
    """라우터 chitchat 노드/엣지 테스트."""

    def test_should_continue_returns_chitchat(self) -> None:
        """chitchat intent일 때 'chitchat' 반환."""
        from agents.router import MainRouter

        with patch.object(MainRouter, "__init__", lambda self, **kw: None):
            router = MainRouter.__new__(MainRouter)
            state = {
                "classification_result": DomainClassificationResult(
                    domains=[],
                    confidence=0.95,
                    is_relevant=False,
                    method="llm",
                    intent="chitchat_greeting",
                ),
                "actions": [],
            }
            result = router._should_continue_after_classify(state)
            assert result == "chitchat"

    def test_should_continue_returns_reject_for_non_chitchat(self) -> None:
        """chitchat이 아닌 거부는 'reject' 반환."""
        from agents.router import MainRouter

        with patch.object(MainRouter, "__init__", lambda self, **kw: None):
            router = MainRouter.__new__(MainRouter)
            state = {
                "classification_result": DomainClassificationResult(
                    domains=[],
                    confidence=0.95,
                    is_relevant=False,
                    method="llm",
                    intent="consultation",
                ),
                "actions": [],
            }
            result = router._should_continue_after_classify(state)
            assert result == "reject"


class TestPreviousDomainsSkipEmpty:
    """previous_domains 역순 탐색 테스트."""

    def test_skip_empty_domains_turn(self) -> None:
        """빈 도메인 턴을 건너뛰고 마지막 유효 도메인을 찾는다."""
        turns = [
            {"domains": ["startup_funding"], "question": "사업자등록"},
            {"domains": [], "question": "고마워"},  # chitchat
            {"domains": [], "question": "안녕"},     # chitchat
        ]
        previous_domains = None
        for turn in reversed(turns):
            prev = turn.get("domains")
            if prev:
                previous_domains = prev
                break
        assert previous_domains == ["startup_funding"]

    def test_all_empty_returns_none(self) -> None:
        """모든 턴의 도메인이 비어있으면 None."""
        turns = [
            {"domains": [], "question": "안녕"},
            {"domains": [], "question": "고마워"},
        ]
        previous_domains = None
        for turn in reversed(turns):
            prev = turn.get("domains")
            if prev:
                previous_domains = prev
                break
        assert previous_domains is None

    def test_latest_non_empty_wins(self) -> None:
        """여러 유효 도메인 중 가장 최근 것을 반환."""
        turns = [
            {"domains": ["startup_funding"], "question": "창업"},
            {"domains": ["finance_tax"], "question": "세금"},
            {"domains": [], "question": "고마워"},
        ]
        previous_domains = None
        for turn in reversed(turns):
            prev = turn.get("domains")
            if prev:
                previous_domains = prev
                break
        assert previous_domains == ["finance_tax"]

    def test_no_turns(self) -> None:
        """턴이 없으면 None."""
        turns: list[dict] = []
        previous_domains = None
        for turn in reversed(turns):
            prev = turn.get("domains")
            if prev:
                previous_domains = prev
                break
        assert previous_domains is None
