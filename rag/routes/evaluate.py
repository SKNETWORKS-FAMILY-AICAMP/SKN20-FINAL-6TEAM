"""RAGAS 평가 전용 엔드포인트 (Backend BackgroundTask 전용, Docker 내부 호출)."""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Evaluate"])


class EvaluateRequest(BaseModel):
    """단건 RAGAS 평가 요청."""

    question: str = Field(..., description="사용자 질문")
    answer: str = Field(..., description="생성된 답변")
    contexts: list[str] = Field(..., description="검색된 컨텍스트 목록")


class BatchEvaluateRequest(BaseModel):
    """배치 RAGAS 평가 요청."""

    items: list[EvaluateRequest] = Field(
        ..., description="평가할 항목 리스트", max_length=50
    )


class BatchEvaluateResult(BaseModel):
    """배치 평가 개별 결과."""

    index: int
    question: str
    metrics: dict[str, Any] = {}
    error: str | None = None


@router.post("/api/evaluate")
async def evaluate_answer(request: EvaluateRequest) -> dict[str, Any]:
    """RAGAS 기반 답변 품질 평가를 수행합니다.

    Backend의 BackgroundTask에서 호출됩니다.
    enable_ragas_evaluation이 false면 빈 dict를 반환합니다.

    Returns:
        RAGAS 메트릭 dict (faithfulness, answer_relevancy, context_precision, context_recall)
        또는 빈 dict (평가 비활성화 또는 실패 시)
    """
    settings = get_settings()
    if not settings.enable_ragas_evaluation:
        return {}

    try:
        from evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        result = await evaluator.aevaluate_answer_quality(
            question=request.question,
            answer=request.answer,
            contexts=request.contexts,
        )
        # None 값과 error 키 제거 — evaluator 비활성 시 모든 값이 None
        return {k: v for k, v in (result or {}).items() if v is not None and k != "error"}
    except Exception as e:
        logger.warning("[RAGAS 평가 엔드포인트] 실패: %s", e)
        return {}


@router.post("/api/evaluate/ragas/batch")
async def evaluate_batch(
    request: BatchEvaluateRequest,
) -> list[BatchEvaluateResult]:
    """RAGAS 배치 평가를 수행합니다.

    최대 50건의 질문-답변 쌍에 대해 일괄 평가를 수행합니다.
    각 항목은 독립적으로 평가되며, 개별 실패는 다른 항목에 영향을 주지 않습니다.

    Args:
        request: 배치 평가 요청 (최대 50건)

    Returns:
        항목별 평가 결과 리스트
    """
    settings = get_settings()
    if not settings.enable_ragas_evaluation:
        return [
            BatchEvaluateResult(
                index=i, question=item.question, error="RAGAS 평가 비활성화"
            )
            for i, item in enumerate(request.items)
        ]

    try:
        from evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
    except Exception as e:
        return [
            BatchEvaluateResult(
                index=i,
                question=item.question,
                error=f"RagasEvaluator 초기화 실패: {e}",
            )
            for i, item in enumerate(request.items)
        ]

    results: list[BatchEvaluateResult] = []
    for i, item in enumerate(request.items):
        try:
            result = await evaluator.aevaluate_answer_quality(
                question=item.question,
                answer=item.answer,
                contexts=item.contexts,
            )
            metrics = {
                k: v
                for k, v in (result or {}).items()
                if v is not None and k != "error"
            }
            results.append(
                BatchEvaluateResult(index=i, question=item.question, metrics=metrics)
            )
        except Exception as e:
            logger.warning("[RAGAS 배치 평가] 항목 %d 실패: %s", i, e)
            results.append(
                BatchEvaluateResult(index=i, question=item.question, error=str(e))
            )

    return results
