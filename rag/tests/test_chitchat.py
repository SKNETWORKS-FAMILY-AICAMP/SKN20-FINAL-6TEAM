"""Chitchat(일상 대화) 감지 및 응답 기능 테스트."""

from unittest.mock import MagicMock, patch

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


class TestLLMChitchat:
    """LLM 모드 chitchat 처리 테스트."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        with patch("utils.domain_classifier.get_settings") as mock_settings:
            settings = MagicMock()
            settings.domain_classification_max_retries = 2
            mock_settings.return_value = settings
            return DomainClassifier()

    def test_chitchat_detected(self, classifier: DomainClassifier) -> None:
        """LLM chitchat intent 감지."""
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

    def test_non_chitchat_rejection(self, classifier: DomainClassifier) -> None:
        """chitchat이 아닌 거부 결과 반환."""
        llm_result = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="llm",
            intent="consultation",
        )
        with patch.object(classifier, "_llm_classify", return_value=llm_result):
            result = classifier.classify("날씨 어때요")
        assert result.is_relevant is False
        assert result.intent == "consultation"


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
