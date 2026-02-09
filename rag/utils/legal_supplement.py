"""법률 보충 검색 필요성 판단 모듈.

3개 주 도메인 에이전트(창업/지원, 재무/세무, 인사/노무)가 문서 검색 후,
법률 정보가 필요하다고 판단되면 법률 에이전트가 보충 검색을 수행합니다.

LLM 호출 없이 순수 키워드 매칭으로 동작합니다 (추가 비용/지연 없음).
"""

import logging

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# 법률 보충 검색 트리거 키워드
LEGAL_SUPPLEMENT_KEYWORDS: set[str] = {
    # 일반 법률
    "법률", "법령", "조문", "판례", "규정", "법적",
    # 주요 법률
    "상법", "민법", "근로기준법", "세법", "공정거래법",
    # 소송/분쟁
    "소송", "분쟁", "손해배상", "고소", "소장", "판결",
    # 지식재산
    "특허", "상표", "저작권", "지식재산",
    # 전문가
    "변호사", "법무사",
    # 계약/책임
    "위약금", "계약해지", "해제", "위반", "처벌", "벌금", "과태료",
}

# 쿼리 키워드 매칭 최소 수 (1개 이상)
_QUERY_KEYWORD_THRESHOLD = 1

# 문서 키워드 매칭 최소 수 (2개 이상)
_DOC_KEYWORD_THRESHOLD = 2

# 문서 검사 시 상위 N건만 확인
_DOC_CHECK_LIMIT = 5

# 문서당 검사 최대 글자수
_DOC_CONTENT_LIMIT = 500


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

    # 쿼리 키워드 매칭
    query_matches = sum(1 for kw in LEGAL_SUPPLEMENT_KEYWORDS if kw in query)
    if query_matches >= _QUERY_KEYWORD_THRESHOLD:
        logger.info(
            "[법률 보충] 쿼리 키워드 %d개 매칭 → 보충 필요",
            query_matches,
        )
        return True

    # 문서 키워드 매칭 (상위 N건, 각 M자까지)
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

    logger.debug("[법률 보충] 키워드 미달 (쿼리=%d, 문서=%d) → 보충 불필요", query_matches, doc_matches)
    return False
