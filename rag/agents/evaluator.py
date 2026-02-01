"""평가 에이전트 모듈.

전문 에이전트의 답변 품질을 평가하고 재요청 여부를 판단합니다.
"""

import json
import logging
import re
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from schemas.response import EvaluationResult
from utils.config import get_settings
from utils.prompts import EVALUATOR_PROMPT

logger = logging.getLogger(__name__)

# JSON 파싱 재시도 최대 횟수
MAX_PARSE_RETRY = 2


class EvaluatorAgent:
    """평가 에이전트.

    전문 에이전트의 답변을 5가지 기준으로 평가합니다:
    - 검색 품질 (0-20점): 참고 컨텍스트가 질문과 관련 있는지
    - 정확성 (0-20점): 정보의 사실 부합 여부
    - 완성도 (0-20점): 질문에 대한 충분한 답변 여부
    - 관련성 (0-20점): 질문 의도와의 일치 여부
    - 출처 명시 (0-20점): 법령/규정 인용 시 출처 여부

    평가 임계값 (기본 70점) 미만 시 FAIL 처리하고 피드백을 제공합니다.

    Attributes:
        settings: 설정 객체
        llm: OpenAI LLM 인스턴스
        threshold: 평가 통과 임계값

    Example:
        >>> evaluator = EvaluatorAgent()
        >>> result = evaluator.evaluate(
        ...     question="퇴직금 계산 방법 알려주세요",
        ...     answer="퇴직금은 근로기준법 제34조에 따라...",
        ...     context="검색된 문서 내용..."
        ... )
        >>> print(result.passed)
        True
    """

    def __init__(self):
        """EvaluatorAgent를 초기화합니다."""
        self.settings = get_settings()
        # 평가용 경량 모델 (성능 최적화, 스킵 확률 낮춤으로 보완)
        self.llm = ChatOpenAI(
            model=self.settings.auxiliary_model,
            temperature=0.0,  # 평가는 일관성을 위해 낮은 temperature 사용
            api_key=self.settings.openai_api_key,
        )
        self.threshold = self.settings.evaluation_threshold

    def _parse_evaluation_response(self, response: str) -> tuple[dict[str, Any], bool]:
        """평가 응답을 파싱합니다.

        JSON 형식의 응답에서 평가 결과를 추출합니다.

        Args:
            response: LLM 응답 문자열

        Returns:
            (파싱된 평가 결과 딕셔너리, 파싱 성공 여부) 튜플
        """
        # JSON 블록 추출 시도 (```json ... ```)
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # { } 블록 직접 추출 시도
            brace_match = re.search(r"\{[\s\S]*\}", response)
            if brace_match:
                json_str = brace_match.group(0)
            else:
                json_str = response

        try:
            result = json.loads(json_str)
            # 필수 필드 검증
            if "scores" not in result or not isinstance(result.get("scores"), dict):
                logger.warning("평가 응답에 scores 필드가 없거나 형식이 잘못됨")
                return self._get_default_evaluation(needs_retry=True), False
            return result, True
        except json.JSONDecodeError as e:
            logger.warning(f"평가 응답 JSON 파싱 실패: {e}")
            return self._get_default_evaluation(needs_retry=True), False

    def _get_default_evaluation(self, needs_retry: bool = False) -> dict[str, Any]:
        """기본 평가 결과를 반환합니다.

        Args:
            needs_retry: 재시도가 필요한 경우 낮은 점수 반환

        Returns:
            기본 평가 결과 딕셔너리
        """
        if needs_retry:
            # 파싱 실패 시 낮은 점수로 재시도 유도
            return {
                "scores": {
                    "retrieval_quality": 10,
                    "accuracy": 10,
                    "completeness": 10,
                    "relevance": 10,
                    "citation": 10,
                },
                "total_score": 50,
                "passed": False,
                "feedback": "평가 응답 파싱 실패로 재시도가 필요합니다.",
            }
        # 정상적인 기본값
        return {
            "scores": {
                "retrieval_quality": 14,
                "accuracy": 14,
                "completeness": 14,
                "relevance": 14,
                "citation": 14,
            },
            "total_score": 70,
            "passed": True,
            "feedback": None,
        }

    def evaluate(
        self,
        question: str,
        answer: str,
        context: str = "",
    ) -> EvaluationResult:
        """답변을 평가합니다.

        Args:
            question: 사용자 질문
            answer: 에이전트 답변
            context: 검색된 컨텍스트 (참고용)

        Returns:
            평가 결과
        """
        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATOR_PROMPT),
            ("human", "위 기준에 따라 답변을 평가하세요."),
        ])

        # 체인 실행
        chain = prompt | self.llm | StrOutputParser()

        max_context_len = self.settings.evaluator_context_length
        response = chain.invoke({
            "question": question,
            "answer": answer,
            "context": context[:max_context_len] if context else "컨텍스트 없음",
        })

        # 응답 파싱 (tuple 언패킹: dict, success)
        parsed, parse_success = self._parse_evaluation_response(response)

        if not parse_success:
            logger.warning("평가 응답 파싱 실패 - 기본값 사용")

        # EvaluationResult 생성
        scores = parsed.get("scores", {})
        total_score = parsed.get("total_score", sum(scores.values()))
        passed = total_score >= self.threshold

        return EvaluationResult(
            scores=scores,
            total_score=total_score,
            passed=passed,
            feedback=parsed.get("feedback") if not passed else None,
        )

    async def aevaluate(
        self,
        question: str,
        answer: str,
        context: str = "",
    ) -> EvaluationResult:
        """답변을 비동기로 평가합니다.

        Args:
            question: 사용자 질문
            answer: 에이전트 답변
            context: 검색된 컨텍스트

        Returns:
            평가 결과
        """
        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATOR_PROMPT),
            ("human", "위 기준에 따라 답변을 평가하세요."),
        ])

        # 체인 실행
        chain = prompt | self.llm | StrOutputParser()

        max_context_len = self.settings.evaluator_context_length
        response = await chain.ainvoke({
            "question": question,
            "answer": answer,
            "context": context[:max_context_len] if context else "컨텍스트 없음",
        })

        # 응답 파싱 (tuple 언패킹: dict, success)
        parsed, parse_success = self._parse_evaluation_response(response)

        if not parse_success:
            logger.warning("비동기 평가 응답 파싱 실패 - 기본값 사용")

        # EvaluationResult 생성
        scores = parsed.get("scores", {})
        total_score = parsed.get("total_score", sum(scores.values()))
        passed = total_score >= self.threshold

        return EvaluationResult(
            scores=scores,
            total_score=total_score,
            passed=passed,
            feedback=parsed.get("feedback") if not passed else None,
        )

    def needs_retry(self, evaluation: EvaluationResult) -> bool:
        """재시도가 필요한지 판단합니다.

        Args:
            evaluation: 평가 결과

        Returns:
            재시도 필요 여부
        """
        return not evaluation.passed
