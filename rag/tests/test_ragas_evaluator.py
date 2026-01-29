"""RAGAS 평가 모듈 테스트."""

import pytest
from unittest.mock import patch

from evaluation.ragas_evaluator import RagasMetrics, RagasEvaluator


class TestRagasMetrics:
    """RagasMetrics 데이터 클래스 테스트."""

    def test_metrics_creation_with_values(self):
        """유효한 값으로 메트릭 생성."""
        metrics = RagasMetrics(
            faithfulness=0.85,
            answer_relevancy=0.90,
            context_precision=0.75,
        )
        assert metrics.faithfulness == 0.85
        assert metrics.answer_relevancy == 0.90
        assert metrics.context_precision == 0.75
        assert metrics.context_recall is None
        assert metrics.error is None

    def test_metrics_creation_all_four(self):
        """4개 메트릭 모두 포함하여 생성."""
        metrics = RagasMetrics(
            faithfulness=0.85,
            answer_relevancy=0.90,
            context_precision=0.75,
            context_recall=0.80,
        )
        assert metrics.context_recall == 0.80

    def test_metrics_available_with_values(self):
        """유효한 메트릭이 있으면 available=True."""
        metrics = RagasMetrics(faithfulness=0.85)
        assert metrics.available is True

    def test_metrics_available_empty(self):
        """메트릭이 없으면 available=False."""
        metrics = RagasMetrics()
        assert metrics.available is False

    def test_metrics_available_with_error_only(self):
        """에러만 있으면 available=False."""
        metrics = RagasMetrics(error="평가 실패")
        assert metrics.available is False
        assert metrics.error == "평가 실패"

    def test_to_dict_includes_valid_values(self):
        """to_dict는 유효한 값만 포함."""
        metrics = RagasMetrics(
            faithfulness=0.85123,
            answer_relevancy=0.90456,
        )
        d = metrics.to_dict()
        assert d["faithfulness"] == 0.8512
        assert d["answer_relevancy"] == 0.9046
        assert "context_precision" not in d
        assert "context_recall" not in d

    def test_to_dict_with_error(self):
        """to_dict는 에러 메시지도 포함."""
        metrics = RagasMetrics(error="RAGAS 비활성화")
        d = metrics.to_dict()
        assert d["error"] == "RAGAS 비활성화"

    def test_to_dict_rounds_values(self):
        """to_dict는 소수점 4자리로 반올림."""
        metrics = RagasMetrics(faithfulness=0.123456789)
        d = metrics.to_dict()
        assert d["faithfulness"] == 0.1235

    def test_to_dict_empty(self):
        """빈 메트릭의 to_dict는 빈 딕셔너리."""
        metrics = RagasMetrics()
        d = metrics.to_dict()
        assert d == {}


class TestRagasEvaluator:
    """RagasEvaluator 테스트."""

    def test_evaluator_disabled_when_ragas_not_available(self):
        """RAGAS 미설치 시 비활성화."""
        with patch("evaluation.ragas_evaluator._RAGAS_AVAILABLE", False):
            evaluator = RagasEvaluator()
            assert evaluator.is_available is False

    def test_evaluate_single_returns_error_when_disabled(self):
        """비활성화 시 에러 메트릭 반환."""
        with patch("evaluation.ragas_evaluator._RAGAS_AVAILABLE", False):
            evaluator = RagasEvaluator()
            result = evaluator.evaluate_single(
                question="테스트 질문",
                answer="테스트 답변",
                contexts=["컨텍스트"],
            )
            assert result.error is not None
            assert result.available is False

    def test_evaluate_batch_returns_errors_when_disabled(self):
        """비활성화 시 배치도 에러 리스트 반환."""
        with patch("evaluation.ragas_evaluator._RAGAS_AVAILABLE", False):
            evaluator = RagasEvaluator()
            results = evaluator.evaluate_batch(
                questions=["질문1", "질문2"],
                answers=["답변1", "답변2"],
                contexts_list=[["ctx1"], ["ctx2"]],
            )
            assert len(results) == 2
            assert all(not m.available for m in results)
            assert all(m.error is not None for m in results)

    def test_evaluator_disabled_when_config_disabled(self):
        """설정에서 비활성화 시 is_available=False."""
        with patch("evaluation.ragas_evaluator._RAGAS_AVAILABLE", True):
            with patch(
                "evaluation.ragas_evaluator.get_settings"
            ) as mock_settings:
                mock_settings.return_value.enable_ragas_evaluation = False
                evaluator = RagasEvaluator()
                assert evaluator.is_available is False

    def test_safe_float_with_valid_value(self):
        """_safe_float: 유효한 값."""
        assert RagasEvaluator._safe_float(0.85) == 0.85
        assert RagasEvaluator._safe_float(1) == 1.0
        assert RagasEvaluator._safe_float("0.5") == 0.5

    def test_safe_float_with_none(self):
        """_safe_float: None."""
        assert RagasEvaluator._safe_float(None) is None

    def test_safe_float_with_nan(self):
        """_safe_float: NaN."""
        assert RagasEvaluator._safe_float(float("nan")) is None

    def test_safe_float_with_invalid(self):
        """_safe_float: 변환 불가 값."""
        assert RagasEvaluator._safe_float("invalid") is None
