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
_ragas_llm_factory = None
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from datasets import Dataset

    # ── 한국어 프롬프트 커스터마이징 (ragas 버전별 분기) ──
    try:
        # ragas >= 0.2.x API
        from ragas.metrics._answer_relevance import (
            ResponseRelevanceInput,
            ResponseRelevanceOutput,
            ResponseRelevancePrompt,
        )
        from ragas.metrics._faithfulness import (
            NLIStatementInput,
            NLIStatementOutput,
            NLIStatementPrompt,
            StatementFaithfulnessAnswer,
            StatementGeneratorInput,
            StatementGeneratorOutput,
            StatementGeneratorPrompt,
        )

        class KoreanResponseRelevancePrompt(ResponseRelevancePrompt):
            instruction = (
                "주어진 답변에 대한 질문을 반드시 한국어로 생성하세요. "
                "또한 답변이 비확정적(noncommittal)인지 판단하세요. "
                "답변이 모호하거나 회피적이면 noncommittal을 1로, "
                "확정적이고 구체적이면 0으로 설정하세요. "
                '"잘 모르겠습니다", "확실하지 않습니다" 등이 비확정적 답변의 예입니다.'
            )
            examples = [
                (
                    ResponseRelevanceInput(
                        response="근로기준법 제34조에 따르면, 사용자는 근로자가 "
                        "퇴직한 경우에 1년 이상 계속 근로한 근로자에게 퇴직금을 "
                        "지급해야 합니다.",
                    ),
                    ResponseRelevanceOutput(
                        question="퇴직금 계산 방법은 어떻게 되나요?",
                        noncommittal=0,
                    ),
                ),
            ]

        class KoreanStatementGeneratorPrompt(StatementGeneratorPrompt):
            instruction = (
                "질문과 답변이 주어지면, 답변의 각 문장을 분석하여 "
                "독립적으로 이해 가능한 진술문(statement)으로 분해하세요. "
                "반드시 한국어로 작성하세요."
            )
            examples = [
                (
                    StatementGeneratorInput(
                        question="퇴직금 지급 기준은 무엇인가요?",
                        answer="근로기준법에 따르면 1년 이상 계속 근로한 근로자에게 퇴직금을 지급해야 합니다.",
                    ),
                    StatementGeneratorOutput(
                        statements=["근로기준법에 따르면 1년 이상 계속 근로한 근로자에게 퇴직금을 지급해야 한다."]
                    ),
                )
            ]

        class KoreanNLIStatementPrompt(NLIStatementPrompt):
            instruction = (
                "주어진 컨텍스트를 기반으로 각 진술문의 사실 일관성을 판단하세요. "
                "진술문이 컨텍스트에서 직접 추론 가능하면 verdict를 1로, "
                "추론할 수 없으면 0으로 설정하세요."
            )
            examples = [
                (
                    NLIStatementInput(
                        context="근로기준법 제34조에 따르면 사용자는 계속근로기간 1년에 대하여 "
                        "30일분 이상의 평균임금을 퇴직금으로 지급해야 한다.",
                        statements=["퇴직금은 1년 이상 근로한 근로자에게 지급된다."],
                    ),
                    NLIStatementOutput(
                        statements=[
                            StatementFaithfulnessAnswer(
                                statement="퇴직금은 1년 이상 근로한 근로자에게 지급된다.",
                                reason="컨텍스트에서 명시되어 있다.",
                                verdict=1,
                            ),
                        ]
                    ),
                ),
            ]

        answer_relevancy.question_generation = KoreanResponseRelevancePrompt()
        # gpt-4o-mini는 n>1 지원 → RAGAS 기본값 strictness=3 사용
        # strictness=3: 질문 3개 생성 → cosine 평균 → AR 점수 안정성 향상
        answer_relevancy.strictness = 3
        faithfulness.statement_generator_prompt = KoreanStatementGeneratorPrompt()
        faithfulness.nli_statements_prompt = KoreanNLIStatementPrompt()
        logger.info("[RAGAS] 한국어 프롬프트 커스터마이징 적용 완료 (strictness=3)")
    except ImportError:
        logger.info("[RAGAS] 한국어 프롬프트 커스터마이징 미지원 (기본 프롬프트 사용)")

    # LLM factory (ragas 버전별 분기)
    try:
        from ragas.llms import llm_factory as _ragas_llm_factory
    except ImportError:
        logger.info("[RAGAS] llm_factory 미지원 (기본 LLM 사용)")

    _RAGAS_AVAILABLE = True
except ImportError:
    logger.warning(
        "RAGAS 라이브러리가 설치되지 않았습니다. "
        "RAGAS 평가 기능이 비활성화됩니다. "
        "설치: pip install ragas datasets"
    )


def _get_langchain_embeddings():
    """answer_relevancy 호환용 langchain embeddings를 lazy 생성합니다.

    ragas 0.4.3의 answer_relevancy 메트릭은 embed_query()/embed_documents()
    인터페이스(legacy)를 사용하지만, ragas 자동 생성 OpenAIEmbeddings는
    embed_text()/embed_texts()(modern)만 지원합니다.
    langchain_openai.OpenAIEmbeddings를 명시적으로 전달하여 호환성을 해결합니다.
    """
    if not hasattr(_get_langchain_embeddings, "_instance"):
        try:
            from langchain_openai import OpenAIEmbeddings as LangchainOpenAIEmbeddings
            from utils.config import get_settings
            _get_langchain_embeddings._instance = LangchainOpenAIEmbeddings(
                model=get_settings().ragas_embedding_model
            )
        except Exception:
            logger.warning("langchain_openai OpenAIEmbeddings 초기화 실패")
            _get_langchain_embeddings._instance = None
    return _get_langchain_embeddings._instance


def _get_ragas_llm():
    """faithfulness NLI 판정용 max_tokens 확장 LLM을 lazy 생성합니다.

    RAGAS InstructorModelArgs의 기본 max_tokens=1024로는 한국어 답변의
    NLI 진술문 판정 JSON이 잘릴 수 있습니다 (finish_reason='length').
    max_tokens=8192로 확장하여 긴 답변도 정상 평가되도록 합니다.
    기본 모델: gpt-4o-mini (비용 효율 + 적절한 엄격도 + n>1 지원)
    """
    if not hasattr(_get_ragas_llm, "_instance"):
        if not _RAGAS_AVAILABLE or _ragas_llm_factory is None:
            _get_ragas_llm._instance = None
            return None
        try:
            from openai import OpenAI
            from utils.config import get_settings

            settings = get_settings()
            client = OpenAI(api_key=settings.openai_api_key)
            _get_ragas_llm._instance = _ragas_llm_factory(
                settings.ragas_llm_model,
                client=client,
                max_tokens=settings.ragas_max_tokens,
            )
            logger.info("[RAGAS] 커스텀 LLM 생성 완료 (model=%s, max_tokens=%d)",
                        settings.ragas_llm_model, settings.ragas_max_tokens)
        except Exception as e:
            logger.warning(f"RAGAS 커스텀 LLM 생성 실패: {e}")
            _get_ragas_llm._instance = None
    return _get_ragas_llm._instance


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
                llm=_get_ragas_llm(),
                embeddings=_get_langchain_embeddings(),
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
                llm=_get_ragas_llm(),
                embeddings=_get_langchain_embeddings(),
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
                llm=_get_ragas_llm(),
                embeddings=_get_langchain_embeddings(),
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
                llm=_get_ragas_llm(),
                embeddings=_get_langchain_embeddings(),
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
