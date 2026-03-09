"""도메인 분류 모듈.

LLM 기반 단일 경로로 도메인을 분류합니다.
원본 쿼리로 chitchat을 먼저 감지하고, 재작성된 쿼리로 도메인을 분류합니다.
실패 시 domain_classification_max_retries만큼 재시도합니다.
"""

import json
import logging
import re
from dataclasses import dataclass

from utils.config import create_llm, get_settings
from utils.prompts import LLM_DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class DomainClassificationResult:
    """도메인 분류 결과.

    Attributes:
        domains: 분류된 도메인 리스트
        confidence: 분류 신뢰도(0.0-1.0)
        is_relevant: 관련 질문 여부
        method: 분류 방식('llm', 'llm_retry', 'llm_error', 'llm_retry_failed')
        intent: 의도 분류 (consultation, document_generation, chitchat_* 등)
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: str
    intent: str | None = None


class DomainClassifier:
    """LLM 기반 도메인 분류기.

    원본 쿼리(original_query)로 chitchat을 감지하고,
    재작성된 쿼리(query)로 도메인을 분류합니다.

    Example:
        >>> classifier = DomainClassifier()
        >>> result = classifier.classify("사업자등록 절차가 궁금합니다")
        >>> print(result.domains)  # ['startup_funding']
    """

    def __init__(self) -> None:
        """DomainClassifier를 초기화합니다."""
        self.settings = get_settings()
        self._llm_instance = None

    def _llm_classify(self, query: str, original_query: str | None = None) -> DomainClassificationResult:
        """LLM 기반 도메인 분류.

        프롬프트에 original_query와 query를 모두 전달합니다.
        실패 시 method="llm_error"를 반환하여 caller가 재시도할 수 있습니다.

        Args:
            query: 분류 대상 쿼리 (재작성된 쿼리)
            original_query: 원본 쿼리 (chitchat 감지용, None이면 query와 동일)

        Returns:
            분류 결과 (실패 시 method="llm_error")
        """
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            if self._llm_instance is None:
                self._llm_instance = create_llm("domain_classification", temperature=0.0)
            llm = self._llm_instance
            prompt = ChatPromptTemplate.from_messages([
                ("human", LLM_DOMAIN_CLASSIFICATION_PROMPT),
            ])
            chain = prompt | llm | StrOutputParser()

            response = chain.invoke({
                "query": query,
                "original_query": original_query or query,
            })

            # JSON 파싱 — 코드 블록 제거
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)

            # Robust JSON parse
            try:
                result = json.loads(cleaned)
            except Exception:
                obj_match = re.search(r"\{[\s\S]*\}", cleaned)
                if not obj_match:
                    raise
                result = json.loads(obj_match.group(0))

            return DomainClassificationResult(
                domains=result.get("domains", []),
                confidence=float(result.get("confidence", 0.5)),
                is_relevant=result.get("is_relevant", True),
                method="llm",
                intent=result.get("intent", "consultation"),
            )

        except Exception as e:
            logger.warning("[도메인 분류] LLM 분류 실패: %s", e)
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_error",
            )

    def classify(self, query: str, original_query: str | None = None) -> DomainClassificationResult:
        """LLM 기반 도메인 분류.

        original_query로 chitchat을 먼저 감지하고,
        query로 도메인을 분류합니다.
        실패 시 domain_classification_max_retries만큼 재시도합니다.

        Args:
            query: 분류 대상 쿼리 (재작성된 쿼리)
            original_query: 원본 쿼리 (chitchat 감지용, None이면 query와 동일)

        Returns:
            도메인 분류 결과
        """
        llm_result = self._llm_classify(query, original_query)
        if llm_result.method != "llm_error":
            logger.info(
                "[도메인 분류] LLM 결과: %s (신뢰도: %.2f, intent: %s)",
                llm_result.domains,
                llm_result.confidence,
                llm_result.intent,
            )
            return llm_result

        # LLM 실패 → 재시도
        for attempt in range(self.settings.domain_classification_max_retries):
            logger.warning(
                "[도메인 분류] LLM 분류 실패, 재시도 (%d/%d)",
                attempt + 1,
                self.settings.domain_classification_max_retries,
            )
            retry_result = self._llm_classify(query, original_query)
            if retry_result.method != "llm_error":
                logger.info(
                    "[도메인 분류] LLM 재시도 성공: %s (신뢰도: %.2f)",
                    retry_result.domains,
                    retry_result.confidence,
                )
                retry_result.method = "llm_retry"
                return retry_result

        # 모든 재시도 실패
        logger.error("[도메인 분류] LLM 분류 재시도 모두 실패")
        return DomainClassificationResult(
            domains=[],
            confidence=0.0,
            is_relevant=False,
            method="llm_retry_failed",
        )


_domain_classifier: DomainClassifier | None = None


def get_domain_classifier() -> DomainClassifier:
    """DomainClassifier 싱글톤 인스턴스를 반환합니다.

    Returns:
        DomainClassifier 인스턴스
    """
    global _domain_classifier
    if _domain_classifier is None:
        _domain_classifier = DomainClassifier()
    return _domain_classifier


def reset_domain_classifier() -> None:
    """DomainClassifier 싱글톤을 리셋합니다(테스트용)."""
    global _domain_classifier
    _domain_classifier = None
