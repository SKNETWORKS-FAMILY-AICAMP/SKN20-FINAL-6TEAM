"""도메인 분류 모듈.

LLM 기반 도메인 분류 + 키워드 가드레일로 오분류를 보정합니다.
원본 쿼리로 chitchat을 먼저 감지하고, 재작성된 쿼리로 도메인을 분류합니다.
LLM 결과를 강한 키워드 매칭으로 검증/보정하며, LLM 실패 시 키워드 폴백을 제공합니다.
실패 시 domain_classification_max_retries만큼 재시도합니다.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from utils.config import create_llm, get_settings
from utils.prompts import LLM_DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

VALID_DOMAINS = ("startup_funding", "finance_tax", "hr_labor", "law_common")


class DomainEvaluation(BaseModel):
    """개별 도메인에 대한 독립 평가."""

    domain: str = Field(description="도메인 이름")
    is_related: bool = Field(description="이 도메인과 관련 있는지")
    evidence: str = Field(description="판단 근거 (1문장)")


class LLMClassificationOutput(BaseModel):
    """LLM 도메인 분류 구조화 출력."""

    query_analysis: str = Field(description="질문의 핵심 의도와 주제 분석 (2~3문장)")
    is_relevant: bool = Field(description="Bizi 상담 범위 내 질문인지")
    domain_evaluations: list[DomainEvaluation] = Field(
        description="각 도메인에 대한 독립 평가"
    )
    confidence: float = Field(description="분류 정확성 확신도 (0.0~1.0)")
    intent: str = Field(default="consultation", description="의도 분류")
    reasoning: str = Field(description="최종 분류 요약")


# 강한 키워드 — 이 키워드가 쿼리에 포함되면 해당 도메인으로 간주
_STRONG_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "startup_funding": {
        "창업", "사업자등록", "법인설립", "지원사업", "보조금", "정책자금",
        "벤처기업", "스타트업", "소상공인", "사회적기업", "개업", "폐업",
        "프랜차이즈", "투자유치", "공동창업",
    },
    "finance_tax": {
        "부가가치세", "부가세", "법인세", "소득세", "종합소득세", "종소세",
        "양도세", "증여세", "상속세", "연말정산", "세금계산서", "원천징수",
        "세무조정", "간이과세", "가산세", "감가상각", "취득세", "재산세",
        "근로장려금",
    },
    "hr_labor": {
        "근로계약", "퇴직금", "연차", "4대보험", "최저임금", "주휴수당",
        "출산휴가", "육아휴직", "산재", "해고", "권고사직", "취업규칙",
        "수습", "야근", "초과근무", "징계", "노조",
    },
    "law_common": {
        "소송", "판례", "특허", "상표", "저작권", "손해배상",
        "고소", "고발", "민법", "상법", "공정거래", "NDA",
        "비밀유지계약", "주주간계약", "변호사", "법무사", "변리사",
        "개인정보보호", "정보보호",
    },
}


ClassificationMethod = Literal[
    "llm", "llm_retry", "llm_error", "llm_retry_failed",
    "followup_fallback", "keyword_override",
    "keyword_mismatch_merge", "keyword_augmented", "keyword_fallback",
]


@dataclass
class DomainClassificationResult:
    """도메인 분류 결과.

    Attributes:
        domains: 분류된 도메인 리스트
        confidence: 분류 신뢰도(0.0-1.0)
        is_relevant: 관련 질문 여부
        method: 분류 방식
        intent: 의도 분류 (consultation, document_generation, chitchat_* 등)
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: ClassificationMethod
    intent: str | None = None

    @classmethod
    def make_followup_fallback(
        cls,
        classification: "DomainClassificationResult",
        previous_domains: list[str],
    ) -> "DomainClassificationResult":
        """폴백 시 원본 intent 보존 (chitchat intent는 consultation으로 재설정)."""
        intent = classification.intent
        if intent and intent.startswith("chitchat"):
            intent = "consultation"
        return cls(
            domains=previous_domains,
            confidence=max(classification.confidence, 0.5),
            is_relevant=True,
            method="followup_fallback",
            intent=intent,
        )


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
        self._structured_chain = None

    def _llm_classify(self, query: str, original_query: str | None = None) -> DomainClassificationResult:
        """LLM 기반 도메인 분류 (Structured Output).

        프롬프트에 original_query와 query를 모두 전달합니다.
        with_structured_output으로 Pydantic 모델을 직접 반환받습니다.
        실패 시 method="llm_error"를 반환하여 caller가 재시도할 수 있습니다.

        Args:
            query: 분류 대상 쿼리 (재작성된 쿼리)
            original_query: 원본 쿼리 (chitchat 감지용, None이면 query와 동일)

        Returns:
            분류 결과 (실패 시 method="llm_error")
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate

            if self._structured_chain is None:
                llm = create_llm("domain_classification", temperature=0.0)
                structured_llm = llm.with_structured_output(
                    LLMClassificationOutput, method="json_schema"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("human", LLM_DOMAIN_CLASSIFICATION_PROMPT),
                ])
                self._structured_chain = prompt | structured_llm

            result: LLMClassificationOutput = self._structured_chain.invoke({
                "query": query,
                "original_query": original_query or query,
            })

            # domain_evaluations에서 is_related=True인 유효 도메인 추출
            domains = [
                e.domain for e in result.domain_evaluations
                if e.is_related and e.domain in VALID_DOMAINS
            ]

            return DomainClassificationResult(
                domains=domains,
                confidence=result.confidence,
                is_relevant=result.is_relevant,
                method="llm",
                intent=result.intent,
            )

        except Exception as e:
            logger.warning("[도메인 분류] LLM 분류 실패: %s", e)
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_error",
            )

    def _detect_keyword_domains(self, query: str) -> list[str]:
        """쿼리에서 강한 키워드 매칭으로 도메인 감지.

        Args:
            query: 분류 대상 쿼리

        Returns:
            매칭된 도메인 리스트 (없으면 빈 리스트)
        """
        detected = []
        for domain, keywords in _STRONG_DOMAIN_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                detected.append(domain)
        return detected

    def _apply_keyword_guardrail(
        self,
        llm_result: DomainClassificationResult,
        keyword_domains: list[str],
        query: str,
    ) -> DomainClassificationResult:
        """LLM 결과와 키워드 결과 비교, 불일치 시 보정.

        Args:
            llm_result: LLM 분류 결과
            keyword_domains: 키워드 매칭으로 감지된 도메인 리스트
            query: 원본 쿼리

        Returns:
            보정된 분류 결과
        """
        llm_domains = set(llm_result.domains)
        kw_domains = set(keyword_domains)

        # Case 1: LLM이 관련없다고 했지만 키워드는 매칭 → 키워드 우선
        if not llm_result.is_relevant and kw_domains:
            logger.warning(
                "[가드레일] LLM 거부 오버라이드: llm=%s → keyword=%s",
                llm_result.domains, keyword_domains,
            )
            return DomainClassificationResult(
                domains=keyword_domains,
                confidence=0.7,
                is_relevant=True,
                method="keyword_override",
                intent="consultation",
            )

        # Case 1.5: LLM 도메인과 키워드 도메인이 완전 불일치 → 키워드 도메인 병합
        # (LLM이 고신뢰도로 잘못된 도메인을 반환한 경우에도 키워드 도메인 추가)
        if kw_domains and not (kw_domains & llm_domains):
            merged = list(llm_domains | kw_domains)
            logger.warning(
                "[가드레일] 도메인 완전 불일치 병합: llm=%s + keyword=%s → %s",
                llm_result.domains, keyword_domains, merged,
            )
            return DomainClassificationResult(
                domains=merged,
                confidence=0.75,
                is_relevant=True,
                method="keyword_mismatch_merge",
                intent=llm_result.intent or "consultation",
            )

        # Case 2: LLM 도메인과 키워드 도메인 부분 불일치 → 키워드 도메인 병합
        missing = kw_domains - llm_domains
        if missing and llm_result.confidence < 0.9:
            merged = list(llm_domains | kw_domains)
            logger.info(
                "[가드레일] 도메인 보강: llm=%s + keyword=%s → %s",
                llm_result.domains, keyword_domains, merged,
            )
            return DomainClassificationResult(
                domains=merged,
                confidence=llm_result.confidence,
                is_relevant=True,
                method="keyword_augmented",
                intent=llm_result.intent,
            )

        # Case 3: 일치 또는 LLM 고신뢰 → LLM 결과 유지
        return llm_result

    def classify(self, query: str, original_query: str | None = None) -> DomainClassificationResult:
        """LLM 기반 도메인 분류 + 키워드 가드레일.

        original_query로 chitchat을 먼저 감지하고,
        query로 도메인을 분류합니다.
        LLM 성공 시 키워드 가드레일로 검증/보정하며,
        LLM 실패 시 키워드 폴백을 먼저 시도합니다.

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
            # 키워드 가드레일 — LLM 결과 검증/보정
            if self.settings.enable_keyword_guardrail:
                keyword_domains = self._detect_keyword_domains(query)
                if keyword_domains:
                    llm_result = self._apply_keyword_guardrail(llm_result, keyword_domains, query)
            return llm_result

        # LLM 실패 → 키워드 폴백 (재시도 전에 키워드로 시도)
        if self.settings.enable_keyword_guardrail:
            keyword_domains = self._detect_keyword_domains(query)
            if keyword_domains:
                logger.info(
                    "[도메인 분류] LLM 실패, 키워드 폴백: %s", keyword_domains,
                )
                return DomainClassificationResult(
                    domains=keyword_domains,
                    confidence=0.7,
                    is_relevant=True,
                    method="keyword_fallback",
                    intent="consultation",
                )

        # 키워드도 없으면 LLM 재시도
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
