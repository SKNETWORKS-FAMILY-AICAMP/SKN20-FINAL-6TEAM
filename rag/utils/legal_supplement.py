"""법률 보충 검색 필요성 판단 모듈.

3개 주 도메인 에이전트(창업/지원, 재무/세무, 인사/노무)가 문서 검색 후,
법률 정보가 필요하다고 판단되면 법률 에이전트가 보충 검색을 수행합니다.

LLM 호출 없이 순수 키워드 매칭으로 동작합니다 (추가 비용/지연 없음).

키워드를 2계층으로 분리하여 과민 트리거를 방지합니다:
- 강한 키워드 (1개만 있어도 트리거): 핵심 법률 용어
- 약한 키워드 (2개 이상 있어야 트리거): 범용/맥락 의존 용어

추가로 ~법 패턴(예: 산업안전보건법)을 자동 감지하여 최우선 트리거합니다.
"""

import logging
import re

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# 강한 법률 키워드 (쿼리에 1개만 있어도 트리거)
STRONG_LEGAL_KEYWORDS: set[str] = {
    "법률", "법령", "판례", "소송", "분쟁", "손해배상",
    "특허", "상표", "저작권", "변호사", "법무사",
}

# 약한 법률 키워드 (쿼리에 2개 이상 있어야 트리거)
WEAK_LEGAL_KEYWORDS: set[str] = {
    "규정", "법적", "조문", "상법", "민법", "근로기준법",
    "세법", "공정거래법", "개인정보보호법", "산업안전보건법",
    "건설산업기본법", "고소", "소장", "판결",
    "지식재산", "위약금", "계약해지", "해제", "위반",
    "처벌", "벌금", "과태료", "의무", "자격요건",
}

# 하위호환: 전체 키워드 합집합 (retrieval_agent.py 등에서 참조)
LEGAL_SUPPLEMENT_KEYWORDS: set[str] = STRONG_LEGAL_KEYWORDS | WEAK_LEGAL_KEYWORDS

# ~법 패턴으로 한국 법률명 자동 감지 (예: 산업안전보건법, 건설근로자퇴직공제법)
_LAW_NAME_PATTERN = re.compile(r"[가-힣]{2,}법")
# 법률명이 아닌 일반 단어 제외
_LAW_NAME_EXCLUSIONS: set[str] = {
    "방법", "기법", "문법", "용법", "처방", "비법", "수법",
    "서법", "선법", "주법", "화법", "작법", "어법", "심법",
}

# 쿼리 약한 키워드 매칭 최소 수 (2개 이상)
_QUERY_WEAK_KEYWORD_THRESHOLD = 2

# 문서 키워드 매칭 최소 수 (2개 이상)
_DOC_KEYWORD_THRESHOLD = 2

# 문서 검사 시 상위 N건만 확인
_DOC_CHECK_LIMIT = 8

# 문서당 검사 최대 글자수
_DOC_CONTENT_LIMIT = 800


def needs_legal_supplement(
    query: str,
    documents: list[Document],
    classified_domains: list[str],
) -> bool:
    """법률 보충 검색이 필요한지 판단합니다.

    Args:
        query: 사용자 질문
        documents: 도메인 에이전트가 검색한 문서 리스트
        classified_domains: 분류된 도메인 리스트

    Returns:
        법률 보충 검색이 필요하면 True
    """
    # law_common이 주 도메인이면 보충 불필요 (단독 처리)
    if "law_common" in classified_domains:
        logger.debug("[법률 보충] law_common이 주 도메인 → 보충 불필요")
        return False

    # ~법 패턴 매칭 (산업안전보건법, 건설산업기본법 등 구체적 법률명)
    law_names = _LAW_NAME_PATTERN.findall(query)
    actual_laws = [name for name in law_names if name not in _LAW_NAME_EXCLUSIONS]
    if actual_laws:
        logger.info(
            "[법률 보충] 법률명 감지: %s → 보충 필요",
            ", ".join(actual_laws),
        )
        return True

    # 쿼리 강한 키워드 매칭 (1개만 있어도 트리거)
    strong_matches = sum(1 for kw in STRONG_LEGAL_KEYWORDS if kw in query)
    if strong_matches >= 1:
        logger.info(
            "[법률 보충] 쿼리 강한 키워드 %d개 매칭 → 보충 필요",
            strong_matches,
        )
        return True

    # 쿼리 약한 키워드 매칭 (2개 이상이어야 트리거)
    weak_matches = sum(1 for kw in WEAK_LEGAL_KEYWORDS if kw in query)
    if weak_matches >= _QUERY_WEAK_KEYWORD_THRESHOLD:
        logger.info(
            "[법률 보충] 쿼리 약한 키워드 %d개 매칭 → 보충 필요",
            weak_matches,
        )
        return True

    # 문서 키워드 매칭 (전체 키워드 사용, 상위 N건, 각 M자까지)
    doc_matches = 0
    matched_keywords: set[str] = set()
    for doc in documents[:_DOC_CHECK_LIMIT]:
        content = doc.page_content[:_DOC_CONTENT_LIMIT]
        for kw in LEGAL_SUPPLEMENT_KEYWORDS:
            if kw in content and kw not in matched_keywords:
                matched_keywords.add(kw)
                doc_matches += 1

    if doc_matches >= _DOC_KEYWORD_THRESHOLD:
        logger.info(
            "[법률 보충] 문서 키워드 %d개 매칭 (%s) → 보충 필요",
            doc_matches,
            ", ".join(sorted(matched_keywords)),
        )
        return True

    logger.debug(
        "[법률 보충] 키워드 미달 (강한=%d, 약한=%d, 문서=%d) → 보충 불필요",
        strong_matches, weak_matches, doc_matches,
    )
    return False
