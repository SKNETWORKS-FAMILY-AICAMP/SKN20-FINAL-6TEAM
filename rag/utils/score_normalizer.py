"""점수 정규화 유틸리티 모듈.

BM25, 벡터, 크로스도메인 점수를 통일된 방식으로 Min-Max 정규화합니다.
"""

from langchain_core.documents import Document


class ScoreNormalizer:
    """검색 점수 정규화 유틸리티.

    BM25, 벡터, 크로스도메인 점수를 통일된 방식으로 정규화합니다.
    """

    @staticmethod
    def min_max_normalize(scores: list[tuple[int, float]]) -> list[tuple[int, float]]:
        """(index, score) 리스트를 Min-Max 정규화합니다.

        Args:
            scores: (인덱스, 점수) 튜플 리스트 (이미 정렬된 상태 가정)

        Returns:
            정규화된 (인덱스, 점수) 리스트
        """
        if not scores:
            return scores
        max_score = max(s for _, s in scores)
        min_score = min(s for _, s in scores)
        score_range = max_score - min_score
        if score_range > 0:
            return [(idx, (s - min_score) / score_range) for idx, s in scores]
        elif max_score > 0:
            return [(idx, 1.0) for idx, _ in scores]
        return scores

    @staticmethod
    def normalize_documents(documents: list[Document], score_key: str = "score") -> None:
        """문서 리스트의 metadata 점수를 Min-Max 정규화합니다 (in-place).

        Args:
            documents: Document 리스트
            score_key: metadata에서 점수를 읽을 키
        """
        if len(documents) < 2:
            return
        scores = [d.metadata.get(score_key, 0.0) for d in documents]
        min_s = min(scores)
        max_s = max(scores)
        score_range = max_s - min_s
        if score_range > 0:
            for d in documents:
                raw = d.metadata.get(score_key, 0.0)
                d.metadata[score_key] = (raw - min_s) / score_range
