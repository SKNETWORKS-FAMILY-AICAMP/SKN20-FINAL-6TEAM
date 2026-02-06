"""RAGAS 정량 평가 모듈.

RAGAS 라이브러리를 사용하여 RAG 시스템의 정량적 평가를 수행합니다.

메트릭:
    - Faithfulness: 답변이 검색된 컨텍스트와 사실적으로 일관되는지
    - Answer Relevancy: 답변이 질문에 관련 있는지
    - Context Precision: 검색된 컨텍스트가 정밀한지 (관련 문서 상위 랭킹)
    - Context Recall: 검색된 컨텍스트가 정답을 충분히 커버하는지 (ground_truth 필요)
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# RAGAS 가용 여부 확인 (선택적 의존성)
_RAGAS_AVAILABLE = False
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from datasets import Dataset

    _RAGAS_AVAILABLE = True
except ImportError:
    logger.warning(
        "RAGAS 라이브러리가 설치되지 않았습니다. "
        "RAGAS 평가 기능이 비활성화됩니다. "
        "설치: pip install ragas datasets"
    )


@dataclass
class RagasMetrics:
    """RAGAS 평가 메트릭 결과.

    Attributes:
        faithfulness: 사실 일관성 점수 (0-1)
        answer_relevancy: 답변 관련성 점수 (0-1)
        context_precision: 컨텍스트 정밀도 점수 (0-1)
        context_recall: 컨텍스트 재현율 점수 (0-1, ground_truth 필요)
        error: 평가 중 발생한 오류 메시지
    """

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """유효한 메트릭만 딕셔너리로 변환합니다."""
        result: dict[str, Any] = {}
        if self.faithfulness is not None:
            result["faithfulness"] = round(self.faithfulness, 4)
        if self.answer_relevancy is not None:
            result["answer_relevancy"] = round(self.answer_relevancy, 4)
        if self.context_precision is not None:
            result["context_precision"] = round(self.context_precision, 4)
        if self.context_recall is not None:
            result["context_recall"] = round(self.context_recall, 4)
        if self.error:
            result["error"] = self.error
        return result

    @property
    def available(self) -> bool:
        """유효한 메트릭이 하나라도 있는지 확인합니다."""
        return any(
            v is not None
            for v in [
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
                self.context_recall,
            ]
        )


class RagasEvaluator:
    """RAGAS 기반 정량 평가기.

    RAG 파이프라인의 정량적 평가를 수행합니다.
    RAGAS 라이브러리가 설치되지 않았거나 설정에서 비활성화된 경우
    graceful하게 비활성화됩니다.
    """

    def __init__(self) -> None:
        from utils.config import get_settings

        self._settings = get_settings()
        self._enabled = _RAGAS_AVAILABLE and self._settings.enable_ragas_evaluation

    @property
    def is_available(self) -> bool:
        """RAGAS 평가가 사용 가능한지 확인합니다."""
        return self._enabled

    def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> RagasMetrics:
        """단일 쿼리에 대한 RAGAS 평가를 수행합니다.

        Args:
            question: 사용자 질문
            answer: 생성된 답변
            contexts: 검색된 컨텍스트 문자열 리스트
            ground_truth: 정답 (선택, 없으면 Context Recall 미측정)

        Returns:
            RAGAS 메트릭 결과
        """
        if not self._enabled:
            return RagasMetrics(error="RAGAS 평가가 비활성화되어 있습니다")

        try:
            data: dict[str, list[Any]] = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            }

            metrics_list = [faithfulness, answer_relevancy, context_precision]

            if ground_truth:
                data["ground_truth"] = [ground_truth]
                metrics_list.append(context_recall)

            dataset = Dataset.from_dict(data)

            result = ragas_evaluate(
                dataset=dataset,
                metrics=metrics_list,
            )

            scores = result.to_pandas().iloc[0]

            return RagasMetrics(
                faithfulness=self._safe_float(scores.get("faithfulness")),
                answer_relevancy=self._safe_float(scores.get("answer_relevancy")),
                context_precision=self._safe_float(scores.get("context_precision")),
                context_recall=(
                    self._safe_float(scores.get("context_recall"))
                    if ground_truth
                    else None
                ),
            )

        except Exception as e:
            logger.error(f"RAGAS 평가 실패: {e}", exc_info=True)
            return RagasMetrics(error=str(e))

    def evaluate_batch(
        self,
        questions: list[str],
        answers: list[str],
        contexts_list: list[list[str]],
        ground_truths: list[str] | None = None,
    ) -> list[RagasMetrics]:
        """배치 쿼리에 대한 RAGAS 평가를 수행합니다.

        테스트 데이터셋 기반 배치 평가에 사용합니다.

        Args:
            questions: 질문 리스트
            answers: 답변 리스트
            contexts_list: 컨텍스트 리스트의 리스트
            ground_truths: 정답 리스트 (선택)

        Returns:
            질문별 RAGAS 메트릭 리스트
        """
        if not self._enabled:
            return [
                RagasMetrics(error="RAGAS 평가가 비활성화되어 있습니다")
            ] * len(questions)

        try:
            data: dict[str, list[Any]] = {
                "question": questions,
                "answer": answers,
                "contexts": contexts_list,
            }

            metrics_list = [faithfulness, answer_relevancy, context_precision]

            if ground_truths:
                data["ground_truth"] = ground_truths
                metrics_list.append(context_recall)

            dataset = Dataset.from_dict(data)

            result = ragas_evaluate(
                dataset=dataset,
                metrics=metrics_list,
            )

            df = result.to_pandas()
            results: list[RagasMetrics] = []
            for _, row in df.iterrows():
                results.append(
                    RagasMetrics(
                        faithfulness=self._safe_float(row.get("faithfulness")),
                        answer_relevancy=self._safe_float(
                            row.get("answer_relevancy")
                        ),
                        context_precision=self._safe_float(
                            row.get("context_precision")
                        ),
                        context_recall=(
                            self._safe_float(row.get("context_recall"))
                            if ground_truths
                            else None
                        ),
                    )
                )

            return results

        except Exception as e:
            logger.error(f"RAGAS 배치 평가 실패: {e}", exc_info=True)
            return [RagasMetrics(error=str(e))] * len(questions)

    def evaluate_context_precision(
        self,
        question: str,
        contexts: list[str],
    ) -> float | None:
        """문서 평가용 - Context Precision만 측정합니다.

        검색된 문서가 질문과 얼마나 관련있는지 평가합니다.
        RAGAS가 비활성화되어 있거나 오류 발생 시 None을 반환합니다.

        Args:
            question: 사용자 질문
            contexts: 검색된 컨텍스트 문자열 리스트

        Returns:
            Context Precision 점수 (0-1) 또는 None
        """
        if not self._enabled:
            return None

        try:
            data = {
                "question": [question],
                "contexts": [contexts],
                # context_precision은 answer 없이도 동작 가능
                "answer": [""],  # 빈 답변
            }

            dataset = Dataset.from_dict(data)
            result = ragas_evaluate(
                dataset=dataset,
                metrics=[context_precision],
            )

            scores = result.to_pandas().iloc[0]
            return self._safe_float(scores.get("context_precision"))

        except Exception as e:
            logger.error(f"Context Precision 평가 실패: {e}", exc_info=True)
            return None

    def evaluate_answer_quality(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> dict[str, float | None]:
        """답변 평가용 - Faithfulness + Answer Relevancy를 측정합니다.

        Args:
            question: 사용자 질문
            answer: 생성된 답변
            contexts: 검색된 컨텍스트 문자열 리스트

        Returns:
            {"faithfulness": float, "answer_relevancy": float} 또는 None 값 포함
        """
        if not self._enabled:
            return {"faithfulness": None, "answer_relevancy": None}

        try:
            data = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            }

            dataset = Dataset.from_dict(data)
            result = ragas_evaluate(
                dataset=dataset,
                metrics=[faithfulness, answer_relevancy],
            )

            scores = result.to_pandas().iloc[0]
            return {
                "faithfulness": self._safe_float(scores.get("faithfulness")),
                "answer_relevancy": self._safe_float(scores.get("answer_relevancy")),
            }

        except Exception as e:
            logger.error(f"Answer Quality 평가 실패: {e}", exc_info=True)
            return {"faithfulness": None, "answer_relevancy": None, "error": str(e)}

    async def aevaluate_answer_quality(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> dict[str, float | None]:
        """답변 평가를 비동기로 수행합니다.

        Args:
            question: 사용자 질문
            answer: 생성된 답변
            contexts: 검색된 컨텍스트 문자열 리스트

        Returns:
            {"faithfulness": float, "answer_relevancy": float}
        """
        import asyncio

        return await asyncio.to_thread(
            self.evaluate_answer_quality,
            question,
            answer,
            contexts,
        )

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """값을 안전하게 float로 변환합니다."""
        if value is None:
            return None
        try:
            result = float(value)
            # NaN 처리
            if result != result:  # noqa: PLR0124
                return None
            return result
        except (ValueError, TypeError):
            return None
