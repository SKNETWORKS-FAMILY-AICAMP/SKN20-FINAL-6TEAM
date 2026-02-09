"""RAG 평가 모듈.

RAGAS 기반 정량 평가와 5단계 검색 품질 평가 시스템을 제공합니다.

- RagasEvaluator: RAGAS 메트릭 (Faithfulness, Answer Relevancy, Context Precision)
- SearchQualityEvaluator: 5단계 통합 검색 품질 평가
"""

from evaluation.ragas_evaluator import RagasEvaluator, RagasMetrics


def __getattr__(name: str):
    """SearchQualityEvaluator를 lazy import합니다."""
    if name == "SearchQualityEvaluator":
        from evaluation.search_quality_eval import SearchQualityEvaluator
        return SearchQualityEvaluator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RagasEvaluator", "RagasMetrics", "SearchQualityEvaluator"]
