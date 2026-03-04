"""도메인 분류 모듈.

LLM 기반 1차 분류 + 키워드 fallback을 지원합니다:
1. LLM 모드 (ENABLE_LLM_DOMAIN_CLASSIFICATION=true):
   LLM이 1차 분류기. LLM 호출 실패 시에만 키워드 방식으로 fallback합니다.
2. 기본 모드 (ENABLE_LLM_DOMAIN_CLASSIFICATION=false):
   키워드 매칭만 사용합니다.

키워드 매칭은 kiwipiepy 형태소 분석기를 사용하여 원형(lemma) 기반으로 수행합니다.

DB 관리 기능(DomainConfig, init_db, load_domain_config 등)은 utils.config에 위치하며,
후방 호환을 위해 이 모듈에서 re-export합니다.
"""

import json
import logging
import re
from dataclasses import dataclass

from kiwipiepy import Kiwi

from utils.config import (
    DOMAIN_REPRESENTATIVE_QUERIES,
    DomainConfig,
    _get_connection,
    _get_default_config,
    create_llm,
    get_domain_config,
    get_settings,
    init_db,
    load_domain_config,
    reload_domain_config,
    reset_domain_config,
)
from utils.prompts import LLM_DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# Re-exports (backward compatibility):
# DOMAIN_REPRESENTATIVE_QUERIES, DomainConfig, _get_connection,
# _get_default_config, init_db, load_domain_config, get_domain_config,
# reload_domain_config, reset_domain_config


# ===================================================================
# 도메인 분류 결과 및 형태소 분석
# ===================================================================

@dataclass
class DomainClassificationResult:
    """도메인 분류 결과.

    Attributes:
        domains: 분류된 도메인 리스트
        confidence: 분류 신뢰도(0.0-1.0)
        is_relevant: 관련 질문 여부
        method: 분류 방식('keyword', 'llm', 'fallback')
        matched_keywords: 키워드 매칭 시 매칭된 키워드들
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: str
    matched_keywords: dict[str, list[str]] | None = None
    intent: str | None = None


_kiwi: Kiwi | None = None


def _get_kiwi() -> Kiwi:
    """Kiwi 형태소 분석기 싱글톤."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def extract_lemmas(query: str) -> set[str]:
    """쿼리에서 명사와 동사/형용사 원형을 추출합니다.

    Args:
        query: 사용자 질문

    Returns:
        추출된 lemma 집합 (명사 원형 + 동사/형용사 '~다' 형태)
    """
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(query)
    lemmas: set[str] = set()

    for token in tokens:
        if token.tag.startswith("NN") or token.tag == "SL":
            # 명사, 외래어 → 그대로
            lemmas.add(token.form)
        elif token.tag.startswith("VV") or token.tag.startswith("VA"):
            # 동사/형용사 -> 원형 + "다"
            lemmas.add(token.form + "다")

    return lemmas


# ===================================================================
# DomainClassifier
# ===================================================================

class DomainClassifier:
    """도메인 분류기.

    ENABLE_LLM_DOMAIN_CLASSIFICATION 설정에 따라 두 가지 모드로 동작:
    - false (기본): 키워드 매칭만 사용.
    - true: LLM 분류를 1차 분류기로 사용. LLM 실패 시 키워드로 fallback.

    Example:
        >>> classifier = DomainClassifier()
        >>> result = classifier.classify("사업자등록 절차가 궁금합니다")
        >>> print(result.domains)  # ['startup_funding']
    """

    def __init__(self) -> None:
        """DomainClassifier를 초기화합니다."""
        self.settings = get_settings()
        # LLM 분류용 인스턴스 캐시 (호출마다 재생성 방지)
        self._llm_instance = None

    def _keyword_classify(self, query: str) -> DomainClassificationResult | None:
        """형태소 분석 + 키워드 기반 도메인 분류.

        kiwipiepy로 쿼리를 형태소 분석하여 원형(lemma)을 추출하고
        DOMAIN_KEYWORDS의 원형 키워드와 매칭합니다.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과 (키워드 매칭 실패 시 None)
        """
        lemmas = extract_lemmas(query)
        detected_domains: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        config = get_domain_config()

        for domain, keywords in config.keywords.items():
            # lemma 집합과 키워드 집합의 교집합
            keyword_set = set(keywords)
            hits = list(lemmas & keyword_set)
            # 원문 부분 문자열 매칭도 보조 (복합명사 대응: "사업자등록" in query)
            for kw in keywords:
                if len(kw) >= 2 and kw in query and kw not in hits:
                    hits.append(kw)
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        # 복합 키워드 규칙 체크 (단일 키워드로 못 잡는 패턴)
        if not detected_domains:
            for domain, required_lemmas in config.compound_rules:
                if required_lemmas.issubset(lemmas):
                    if domain not in detected_domains:
                        detected_domains.append(domain)
                    matched_keywords.setdefault(domain, []).append(
                        "+".join(sorted(required_lemmas))
                    )
                    break  # 첫 매칭 규칙만 적용

        if detected_domains:
            total_matches = sum(len(kws) for kws in matched_keywords.values())
            confidence = min(1.0, 0.5 + (total_matches * 0.1))

            return DomainClassificationResult(
                domains=detected_domains,
                confidence=confidence,
                is_relevant=True,
                method="keyword",
                matched_keywords=matched_keywords,
            )

        return None

    def _llm_classify(self, query: str) -> DomainClassificationResult:
        """LLM 기반 도메인 분류.

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true 시 1차 분류기로 사용됩니다.
        실패 시 method="llm_error"를 반환하여 caller가 fallback할 수 있습니다.

        Args:
            query: 사용자 질문

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

            response = chain.invoke({"query": query})

            # JSON 파싱
            # 코드 블록 제거
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # 첫 줄 (```json) 과 마지막 줄 (```) 제거
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            # Robust JSON parse:
            # 1) direct parse
            # 2) fenced ```json ... ``` block extraction
            # 3) first object-like {...} extraction
            try:
                result = json.loads(cleaned)
            except Exception:
                block_match = re.search(r"```json\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
                if block_match:
                    result = json.loads(block_match.group(1))
                else:
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

    def _heuristic_domain_fallback(self, query: str) -> list[str]:
        """Fast keyword heuristic used when LLM returns out-of-scope."""
        text = (query or "").lower()
        domain_patterns = {
            "startup_funding": [
                r"창업", r"사업자등록", r"사업자", r"법인설립", r"지원사업", r"개업",
                r"startup", r"business registration", r"incorporat",
            ],
            "finance_tax": [
                r"세금", r"부가세", r"법인세", r"소득세", r"회계", r"세무",
                r"vat", r"tax", r"corporate tax", r"filing",
            ],
            "hr_labor": [
                r"근로", r"노무", r"급여", r"4대보험", r"채용", r"퇴직금",
                r"employment", r"labor", r"payroll", r"contract",
            ],
            "law_common": [
                r"법률", r"법적", r"소송", r"상표", r"특허", r"계약", r"분쟁",
                r"legal", r"lawsuit", r"trademark", r"patent",
            ],
        }
        matched: list[str] = []
        for domain, patterns in domain_patterns.items():
            if any(re.search(pattern, text) for pattern in patterns):
                matched.append(domain)
        return matched

    def classify(self, query: str) -> DomainClassificationResult:
        """질문을 분류하여 관련 도메인과 신뢰도를 반환합니다.

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true 시 LLM 분류를 1차 분류기로 사용합니다.
        LLM 실패 시 settings.llm_max_retries 횟수만큼 재시도 후 키워드 fallback합니다.

        Args:
            query: 사용자 질문

        Returns:
            도메인 분류 결과
        """
        # 0. LLM 분류 모드
        if self.settings.enable_llm_domain_classification:
            llm_result = self._llm_classify(query)
            if llm_result.method != "llm_error":
                # Guardrail: avoid false rejection in LLM-only mode.
                keyword_result = self._keyword_classify(query)
                if keyword_result and keyword_result.is_relevant:
                    if (not llm_result.is_relevant) or (not llm_result.domains):
                        logger.warning(
                            "[domain classification] override llm out-of-scope by keyword: llm=%s/%s -> keyword=%s",
                            llm_result.is_relevant,
                            llm_result.domains,
                            keyword_result.domains,
                        )
                        return DomainClassificationResult(
                            domains=keyword_result.domains,
                            confidence=max(llm_result.confidence, keyword_result.confidence),
                            is_relevant=True,
                            method="llm+keyword_override",
                            matched_keywords=keyword_result.matched_keywords,
                        )
                if (not llm_result.is_relevant) or (not llm_result.domains):
                    heuristic_domains = self._heuristic_domain_fallback(query)
                    if heuristic_domains:
                        logger.warning(
                            "[domain classification] override llm result by heuristic fallback: %s",
                            heuristic_domains,
                        )
                        return DomainClassificationResult(
                            domains=heuristic_domains,
                            confidence=max(llm_result.confidence, 0.7),
                            is_relevant=True,
                            method="llm+heuristic_override",
                        )
                logger.info(
                    "[domain classification] llm result accepted: %s (confidence: %.2f)",
                    llm_result.domains,
                    llm_result.confidence,
                )
                return llm_result

            # LLM 실패 → settings.llm_max_retries 횟수만큼 재시도
            for attempt in range(self.settings.llm_max_retries):
                logger.warning(
                    "[domain classification] LLM classification failed, retrying (%d/%d)",
                    attempt + 1,
                    self.settings.llm_max_retries,
                )
                retry_result = self._llm_classify(query)
                if retry_result.method != "llm_error":
                    logger.info(
                        "[도메인 분류] LLM 재시도 성공: %s (신뢰도: %.2f)",
                        retry_result.domains,
                        retry_result.confidence,
                    )
                    retry_result.method = "llm_retry"
                    return retry_result

            # 모든 재시도 실패 → 키워드 fallback
            logger.error("[도메인 분류] LLM 분류 재시도 실패, 키워드 분류로 fallback")
            keyword_result = self._keyword_classify(query)
            if keyword_result:
                return keyword_result
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_retry_failed",
            )

        # 1. 키워드 분류 (LLM 모드 비활성화)
        keyword_result = self._keyword_classify(query)
        if keyword_result:
            logger.info(
                "[도메인 분류] 키워드 매칭: %s (신뢰도: %.2f)",
                keyword_result.domains,
                keyword_result.confidence,
            )
            return keyword_result

        # fallback: 분류 불가 → 도메인 외 질문으로 처리
        logger.warning("[도메인 분류] 분류 실패, 도메인 외 질문으로 거부")
        return DomainClassificationResult(
            domains=[],
            confidence=0.0,
            is_relevant=False,
            method="fallback_rejected",
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
