"""피드백 분석 및 검색 전략 모듈.

평가 피드백을 분석하여 검색 전략을 동적으로 조정합니다.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """피드백 유형."""

    RETRIEVAL_QUALITY = "retrieval_quality"  # 검색 품질 문제
    ACCURACY = "accuracy"  # 정확성 문제
    COMPLETENESS = "completeness"  # 완성도 문제
    RELEVANCE = "relevance"  # 관련성 문제
    CITATION = "citation"  # 출처 명시 문제
    UNKNOWN = "unknown"


@dataclass
class SearchStrategy:
    """검색 전략."""

    # 기본 검색 파라미터
    k: int = 3
    k_common: int = 2

    # 고급 검색 옵션
    use_mmr: bool = True
    use_rerank: bool = False
    use_hybrid: bool = False

    # MMR 파라미터
    mmr_lambda: float = 0.6
    fetch_k_multiplier: int = 4

    # 추가 검색 키워드
    additional_keywords: list[str] = field(default_factory=list)

    # 검색 범위 확장
    expand_search: bool = False


class FeedbackAnalyzer:
    """피드백 분석기.

    평가 피드백을 분석하여 문제 유형을 식별하고
    적절한 검색 전략을 제안합니다.
    """

    # 피드백 패턴 매핑
    RETRIEVAL_PATTERNS = [
        r"검색.*부족",
        r"검색.*결과.*부족",
        r"관련.*문서.*부족",
        r"참고.*자료.*부족",
        r"검색.*품질",
        r"관련.*없는.*문서",
        r"검색.*실패",
    ]

    ACCURACY_PATTERNS = [
        r"정확.*부족",
        r"부정확",
        r"오류",
        r"잘못된.*정보",
        r"근거.*없",
        r"추론",
        r"추측",
        r"확인.*필요",
    ]

    COMPLETENESS_PATTERNS = [
        r"불완전",
        r"부족.*설명",
        r"누락",
        r"더.*자세",
        r"추가.*설명.*필요",
        r"구체적.*부족",
    ]

    RELEVANCE_PATTERNS = [
        r"관련.*없",
        r"관련성.*부족",
        r"질문.*맞지",
        r"벗어난",
        r"동떨어진",
    ]

    CITATION_PATTERNS = [
        r"출처.*없",
        r"출처.*부족",
        r"인용.*없",
        r"근거.*제시.*없",
        r"참고.*명시.*없",
    ]

    def analyze(self, feedback: str | None) -> list[FeedbackType]:
        """피드백을 분석하여 문제 유형을 식별합니다.

        Args:
            feedback: 평가 피드백 문자열

        Returns:
            식별된 피드백 유형 리스트
        """
        if not feedback:
            return [FeedbackType.UNKNOWN]

        feedback_lower = feedback.lower()
        identified_types = []

        # 패턴 매칭
        if self._match_patterns(feedback_lower, self.RETRIEVAL_PATTERNS):
            identified_types.append(FeedbackType.RETRIEVAL_QUALITY)

        if self._match_patterns(feedback_lower, self.ACCURACY_PATTERNS):
            identified_types.append(FeedbackType.ACCURACY)

        if self._match_patterns(feedback_lower, self.COMPLETENESS_PATTERNS):
            identified_types.append(FeedbackType.COMPLETENESS)

        if self._match_patterns(feedback_lower, self.RELEVANCE_PATTERNS):
            identified_types.append(FeedbackType.RELEVANCE)

        if self._match_patterns(feedback_lower, self.CITATION_PATTERNS):
            identified_types.append(FeedbackType.CITATION)

        if not identified_types:
            identified_types.append(FeedbackType.UNKNOWN)

        return identified_types

    def _match_patterns(self, text: str, patterns: list[str]) -> bool:
        """패턴 매칭을 수행합니다."""
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    def suggest_strategy(
        self,
        feedback: str | None,
        current_strategy: SearchStrategy | None = None,
        retry_count: int = 0,
    ) -> SearchStrategy:
        """피드백에 기반한 검색 전략을 제안합니다.

        Args:
            feedback: 평가 피드백
            current_strategy: 현재 검색 전략
            retry_count: 재시도 횟수

        Returns:
            조정된 검색 전략
        """
        strategy = current_strategy or SearchStrategy()
        feedback_types = self.analyze(feedback)

        logger.debug(f"피드백 분석 결과: {feedback_types}")

        for ftype in feedback_types:
            if ftype == FeedbackType.RETRIEVAL_QUALITY:
                # 검색 품질 문제: 더 많이 검색하고 다양성 높임
                strategy.k = min(strategy.k + 2, 10)
                strategy.k_common = min(strategy.k_common + 1, 5)
                strategy.use_rerank = True
                strategy.use_hybrid = True
                strategy.mmr_lambda = max(0.4, strategy.mmr_lambda - 0.1)
                strategy.expand_search = True
                logger.info("검색 전략 조정: 검색 범위 확장, Re-ranking 활성화")

            elif ftype == FeedbackType.ACCURACY:
                # 정확성 문제: Re-ranking 강화
                strategy.use_rerank = True
                strategy.fetch_k_multiplier = min(6, strategy.fetch_k_multiplier + 1)
                logger.info("검색 전략 조정: Re-ranking 강화")

            elif ftype == FeedbackType.COMPLETENESS:
                # 완성도 문제: 더 많은 문서 검색
                strategy.k = min(strategy.k + 2, 10)
                strategy.expand_search = True
                logger.info("검색 전략 조정: 검색 결과 수 증가")

            elif ftype == FeedbackType.RELEVANCE:
                # 관련성 문제: 다양성 감소
                strategy.mmr_lambda = min(0.8, strategy.mmr_lambda + 0.1)
                logger.info("검색 전략 조정: 유사도 중시")

            elif ftype == FeedbackType.CITATION:
                # 출처 문제: 법령 DB 검색 강화
                strategy.k_common = min(strategy.k_common + 2, 5)
                logger.info("검색 전략 조정: 법령 DB 검색 강화")

        # 재시도 횟수에 따른 추가 조정
        if retry_count >= 1:
            strategy.use_rerank = True
            strategy.use_hybrid = True
            logger.info(f"재시도 {retry_count}회: 고급 검색 기능 활성화")

        return strategy

    def extract_suggestions(self, feedback: str | None) -> list[str]:
        """피드백에서 구체적인 제안사항을 추출합니다.

        Args:
            feedback: 평가 피드백

        Returns:
            제안사항 리스트
        """
        if not feedback:
            return []

        suggestions = []

        # 구체적인 키워드 추출 시도
        keyword_patterns = [
            r"['\"](.*?)['\"]",  # 따옴표 안의 내용
            r"「(.+?)」",  # 한국어 꺾쇠 안의 내용
        ]

        for pattern in keyword_patterns:
            matches = re.findall(pattern, feedback)
            suggestions.extend(matches)

        return suggestions


# 싱글톤 인스턴스
_feedback_analyzer: FeedbackAnalyzer | None = None


def get_feedback_analyzer() -> FeedbackAnalyzer:
    """FeedbackAnalyzer 싱글톤 인스턴스를 반환합니다.

    Returns:
        FeedbackAnalyzer 인스턴스
    """
    global _feedback_analyzer
    if _feedback_analyzer is None:
        _feedback_analyzer = FeedbackAnalyzer()
    return _feedback_analyzer
