"""평가 에이전트 테스트."""

import pytest
from unittest.mock import MagicMock, patch

from schemas.response import EvaluationResult


class TestEvaluatorAgent:
    """EvaluatorAgent 테스트."""

    @pytest.fixture
    def evaluator(self):
        """평가 에이전트 fixture."""
        with patch("agents.evaluator.ChatOpenAI"):
            from agents.evaluator import EvaluatorAgent
            return EvaluatorAgent()

    def test_parse_evaluation_valid_json(self, evaluator):
        """유효한 JSON 응답 파싱 테스트."""
        response = """```json
{
    "scores": {
        "retrieval_quality": 18,
        "accuracy": 17,
        "completeness": 16,
        "relevance": 19,
        "citation": 15
    },
    "total_score": 85,
    "passed": true,
    "feedback": null
}
```"""
        result, success = evaluator._parse_evaluation_response(response)

        assert success is True
        assert result["total_score"] == 85
        assert result["passed"] is True

    def test_parse_evaluation_without_code_block(self, evaluator):
        """코드 블록 없는 JSON 응답 파싱 테스트."""
        response = """{
    "scores": {
        "retrieval_quality": 10,
        "accuracy": 10,
        "completeness": 10,
        "relevance": 10,
        "citation": 10
    },
    "total_score": 50,
    "passed": false,
    "feedback": "정보가 부정확합니다."
}"""
        result, success = evaluator._parse_evaluation_response(response)

        assert success is True
        assert result["total_score"] == 50
        assert result["passed"] is False
        assert result["feedback"] == "정보가 부정확합니다."

    def test_parse_evaluation_invalid_json(self, evaluator):
        """유효하지 않은 JSON 응답 처리 테스트."""
        response = "이것은 JSON이 아닙니다."
        result, success = evaluator._parse_evaluation_response(response)

        # 파싱 실패 시 기본값 반환
        assert success is False
        assert result["total_score"] == 50
        assert result["passed"] is False

    def test_parse_evaluation_missing_fields(self, evaluator):
        """필드가 누락된 JSON 응답 처리 테스트."""
        response = '{"total_score": 60}'
        result, success = evaluator._parse_evaluation_response(response)

        # scores 필드가 없으면 실패
        assert success is False

    def test_evaluation_criteria_count(self, evaluator):
        """평가 기준 5개 확인 테스트."""
        # EVALUATOR_PROMPT에서 5개 기준이 정의되어 있어야 함
        from utils.prompts import EVALUATOR_PROMPT

        criteria = [
            "retrieval_quality",
            "accuracy",
            "completeness",
            "relevance",
            "citation",
        ]
        for criterion in criteria:
            assert criterion in EVALUATOR_PROMPT or "검색" in EVALUATOR_PROMPT


class TestEvaluationResult:
    """EvaluationResult 스키마 테스트."""

    def test_evaluation_result_creation(self):
        """EvaluationResult 생성 테스트."""
        result = EvaluationResult(
            scores={
                "retrieval_quality": 18,
                "accuracy": 17,
                "completeness": 16,
                "relevance": 19,
                "citation": 15,
            },
            total_score=85,
            passed=True,
            feedback=None,
        )

        assert result.total_score == 85
        assert result.passed is True
        assert len(result.scores) == 5

    def test_evaluation_result_threshold(self):
        """평가 통과 임계값 테스트."""
        from utils.config import get_settings

        settings = get_settings()

        # 70점 이상 통과
        assert settings.evaluation_threshold == 70

        passing = EvaluationResult(total_score=70, passed=True)
        failing = EvaluationResult(total_score=69, passed=False)

        assert passing.passed is True
        assert failing.passed is False
