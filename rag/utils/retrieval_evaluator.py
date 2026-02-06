"""규칙 기반 검색 품질 평가 모듈.

검색된 문서의 품질을 규칙 기반으로 1차 평가합니다.
LLM 호출 없이 빠르게 검색 품질을 판단합니다.
"""

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document

from utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievalEvaluationResult:
    """검색 평가 결과.

    Attributes:
        passed: 평가 통과 여부
        doc_count: 검색된 문서 수
        keyword_match_ratio: 키워드 매칭 비율 (0.0-1.0)
        avg_similarity_score: 평균 유사도 점수 (0.0-1.0)
        reason: 평가 실패 이유 (실패 시)
        details: 상세 평가 정보
    """

    passed: bool
    doc_count: int
    keyword_match_ratio: float
    avg_similarity_score: float
    reason: str | None = None
    details: dict | None = None


class RuleBasedRetrievalEvaluator:
    """규칙 기반 검색 품질 평가기.

    검색 결과를 다음 기준으로 평가합니다:
    1. 문서 수: 최소 N개 이상
    2. 키워드 매칭률: 쿼리 키워드가 문서에 포함된 비율
    3. 유사도 점수: 평균 유사도가 임계값 이상

    Attributes:
        min_doc_count: 최소 문서 수
        min_keyword_match_ratio: 최소 키워드 매칭 비율
        min_avg_similarity: 최소 평균 유사도 점수
    """

    def __init__(self):
        """RuleBasedRetrievalEvaluator를 초기화합니다."""
        settings = get_settings()
        self.min_doc_count = settings.min_retrieval_doc_count
        self.min_keyword_match_ratio = settings.min_keyword_match_ratio
        self.min_avg_similarity = settings.min_avg_similarity_score

    def _extract_keywords(self, query: str) -> list[str]:
        """쿼리에서 키워드를 추출합니다.

        Args:
            query: 사용자 질문

        Returns:
            키워드 리스트
        """
        # 한글, 영문 단어 추출 (2글자 이상)
        words = re.findall(r"[가-힣a-zA-Z]{2,}", query)
        # 불용어 제거
        stopwords = {
            "것", "수", "등", "때", "위해", "대해", "관해",
            "어떻게", "무엇", "언제", "어디", "왜", "어떤",
            "하는", "되는", "있는", "없는", "같은",
        }
        return [w for w in words if w not in stopwords]

    def _calculate_keyword_match_ratio(
        self,
        query: str,
        documents: list[Document],
    ) -> tuple[float, list[str], list[str]]:
        """키워드 매칭 비율을 계산합니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트

        Returns:
            (매칭 비율, 매칭된 키워드, 전체 키워드)
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return 1.0, [], []  # 키워드 없으면 통과

        # 모든 문서 내용 합치기
        all_content = " ".join(doc.page_content for doc in documents)
        all_content_lower = all_content.lower()

        matched_keywords = []
        for kw in keywords:
            if kw.lower() in all_content_lower:
                matched_keywords.append(kw)

        ratio = len(matched_keywords) / len(keywords) if keywords else 1.0
        return ratio, matched_keywords, keywords

    def evaluate(
        self,
        query: str,
        documents: list[Document],
        scores: list[float] | None = None,
    ) -> RetrievalEvaluationResult:
        """검색 결과를 평가합니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            scores: 유사도 점수 리스트 (없으면 메타데이터에서 추출)

        Returns:
            검색 평가 결과
        """
        doc_count = len(documents)
        reasons = []

        # 1. 문서 수 체크
        if doc_count < self.min_doc_count:
            reasons.append(f"문서 수 부족 ({doc_count} < {self.min_doc_count})")

        # 2. 키워드 매칭률 체크
        keyword_ratio, matched, all_keywords = self._calculate_keyword_match_ratio(
            query, documents
        )
        if keyword_ratio < self.min_keyword_match_ratio:
            reasons.append(
                f"키워드 매칭 부족 ({keyword_ratio:.1%} < {self.min_keyword_match_ratio:.1%})"
            )

        # 3. 유사도 점수 체크
        if scores is None:
            scores = [doc.metadata.get("score", 0.0) for doc in documents]

        # 점수가 없거나 0인 경우 기본값 사용
        valid_scores = [s for s in scores if s > 0]
        avg_similarity = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

        # 점수가 거리 기반(낮을수록 좋음)인 경우 변환
        # ChromaDB는 거리를 반환하므로 1 - distance로 변환
        if avg_similarity > 1.0:
            # 거리 기반인 경우 (예: L2 distance)
            avg_similarity = max(0, 1 - avg_similarity / 2)

        if avg_similarity < self.min_avg_similarity:
            reasons.append(
                f"유사도 점수 낮음 ({avg_similarity:.2f} < {self.min_avg_similarity})"
            )

        passed = len(reasons) == 0
        reason = "; ".join(reasons) if reasons else None

        result = RetrievalEvaluationResult(
            passed=passed,
            doc_count=doc_count,
            keyword_match_ratio=keyword_ratio,
            avg_similarity_score=avg_similarity,
            reason=reason,
            details={
                "matched_keywords": matched,
                "all_keywords": all_keywords,
                "valid_scores": valid_scores,
            },
        )

        log_level = logging.INFO if passed else logging.WARNING
        logger.log(
            log_level,
            "[검색 평가] %s: doc=%d, keyword=%.1f%%, similarity=%.2f",
            "PASS" if passed else "FAIL",
            doc_count,
            keyword_ratio * 100,
            avg_similarity,
        )
        if reason:
            logger.log(log_level, "[검색 평가] 이유: %s", reason)

        return result


@lru_cache(maxsize=1)
def get_retrieval_evaluator() -> RuleBasedRetrievalEvaluator:
    """RuleBasedRetrievalEvaluator 싱글톤 인스턴스를 반환합니다."""
    return RuleBasedRetrievalEvaluator()
