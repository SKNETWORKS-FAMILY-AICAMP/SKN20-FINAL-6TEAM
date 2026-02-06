"""검색 유틸리티 모듈.

Hybrid Search, Re-ranking 등 고급 검색 기능을 제공합니다.
"""

import asyncio
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from utils.config import get_settings
from utils.reranker import get_reranker

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """검색 결과."""

    document: Document
    score: float
    source: str = "vector"  # vector, bm25, hybrid


class BM25Index:
    """BM25 키워드 검색 인덱스.

    문서 컬렉션에 대한 BM25 스코어링을 제공합니다.

    Attributes:
        k1: BM25 파라미터 (기본 1.5)
        b: BM25 파라미터 (기본 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """BM25Index를 초기화합니다.

        Args:
            k1: term frequency saturation 파라미터
            b: document length normalization 파라미터
        """
        self.k1 = k1
        self.b = b
        self.documents: list[Document] = []
        self.doc_freqs: list[Counter] = []
        self.idf: dict[str, float] = {}
        self.avg_doc_len: float = 0
        self.doc_count: int = 0

    def _tokenize(self, text: str) -> list[str]:
        """텍스트를 토큰화합니다."""
        # 한글, 영문, 숫자 추출
        tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', text.lower())
        # 2글자 이상만
        return [t for t in tokens if len(t) >= 2]

    def fit(self, documents: list[Document]) -> None:
        """문서 컬렉션으로 인덱스를 빌드합니다.

        Args:
            documents: 문서 리스트
        """
        self.documents = documents
        self.doc_count = len(documents)

        # 문서별 term frequency 계산
        self.doc_freqs = []
        total_len = 0

        for doc in documents:
            tokens = self._tokenize(doc.page_content)
            self.doc_freqs.append(Counter(tokens))
            total_len += len(tokens)

        self.avg_doc_len = total_len / self.doc_count if self.doc_count > 0 else 0

        # IDF 계산
        df = Counter()  # document frequency
        for freq in self.doc_freqs:
            for term in freq.keys():
                df[term] += 1

        for term, doc_freq in df.items():
            # IDF with smoothing
            self.idf[term] = math.log(
                (self.doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1
            )

    def search(self, query: str, k: int = 10) -> list[SearchResult]:
        """BM25 검색을 수행합니다.

        Args:
            query: 검색 쿼리
            k: 반환할 결과 수

        Returns:
            검색 결과 리스트
        """
        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []

        for idx, doc_freq in enumerate(self.doc_freqs):
            doc_len = sum(doc_freq.values())
            score = 0.0

            for term in query_tokens:
                if term not in doc_freq:
                    continue

                tf = doc_freq[term]
                idf = self.idf.get(term, 0)

                # BM25 score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * (doc_len / self.avg_doc_len)
                )
                score += idf * (numerator / denominator)

            if score > 0:
                scores.append((idx, score))

        # 점수로 정렬
        scores.sort(key=lambda x: x[1], reverse=True)

        # 상위 k개 반환
        results = []
        for idx, score in scores[:k]:
            results.append(SearchResult(
                document=self.documents[idx],
                score=score,
                source="bm25",
            ))

        return results


def reciprocal_rank_fusion(
    results_list: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """Reciprocal Rank Fusion으로 여러 검색 결과를 융합합니다.

    Args:
        results_list: 여러 검색 결과 리스트
        k: RRF 파라미터 (기본 60)

    Returns:
        융합된 검색 결과
    """
    # 문서별 RRF 점수 계산
    doc_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for results in results_list:
        for rank, result in enumerate(results):
            # 문서 ID 생성 (content hash)
            doc_id = hash(result.document.page_content[:200])

            # RRF 점수 누적
            rrf_score = 1 / (k + rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            doc_map[doc_id] = result.document

    # 점수로 정렬
    sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)

    # 결과 생성
    results = []
    for doc_id in sorted_ids:
        results.append(SearchResult(
            document=doc_map[doc_id],
            score=doc_scores[doc_id],
            source="hybrid",
        ))

    return results


class HybridSearcher:
    """Hybrid Search 구현.

    BM25 키워드 검색과 벡터 검색을 결합합니다.
    """

    def __init__(self, vector_store: Any):
        """HybridSearcher를 초기화합니다.

        Args:
            vector_store: ChromaVectorStore 인스턴스
        """
        self.vector_store = vector_store
        self.bm25_indices: dict[str, BM25Index] = {}
        self._reranker = None  # 지연 로딩
        self.settings = get_settings()

    @property
    def reranker(self):
        """Reranker 인스턴스 (지연 로딩)."""
        if self._reranker is None and self.settings.enable_reranking:
            self._reranker = get_reranker()
        return self._reranker

    def build_bm25_index(self, domain: str, documents: list[Document]) -> None:
        """도메인별 BM25 인덱스를 빌드합니다.

        Args:
            domain: 도메인 키
            documents: 문서 리스트
        """
        index = BM25Index()
        index.fit(documents)
        self.bm25_indices[domain] = index
        logger.info(f"BM25 인덱스 빌드 완료: {domain} ({len(documents)}개 문서)")

    def search(
        self,
        query: str,
        domain: str,
        k: int = 5,
        use_rerank: bool = True,
        vector_weight: float = 0.5,
    ) -> list[Document]:
        """Hybrid 검색을 수행합니다.

        Args:
            query: 검색 쿼리
            domain: 도메인
            k: 반환할 결과 수
            use_rerank: Re-ranking 사용 여부
            vector_weight: 벡터 검색 가중치 (0-1)

        Returns:
            검색된 문서 리스트
        """
        logger.info("[하이브리드] 검색 시작: 도메인=%s, k=%d", domain, k)

        fetch_k = k * 3  # 더 많이 가져와서 융합

        # 벡터 검색
        vector_results = []
        try:
            vector_docs = self.vector_store.max_marginal_relevance_search(
                query=query,
                domain=domain,
                k=fetch_k,
                fetch_k=fetch_k * 2,
                lambda_mult=self.settings.mmr_lambda_mult,
            )
            vector_results = [
                SearchResult(doc, 1.0 - (i / fetch_k), "vector")
                for i, doc in enumerate(vector_docs)
            ]
        except Exception as e:
            logger.warning(f"벡터 검색 실패: {e}")
        logger.info("[하이브리드] 벡터 검색: %d건", len(vector_results))

        # BM25 검색 (인덱스가 있는 경우)
        bm25_results = []
        if domain in self.bm25_indices:
            bm25_results = self.bm25_indices[domain].search(query, k=fetch_k)
        logger.info("[하이브리드] BM25 검색: %d건", len(bm25_results))

        # 결과 융합
        if bm25_results:
            combined = reciprocal_rank_fusion([vector_results, bm25_results])
        else:
            combined = vector_results
        logger.info("[하이브리드] RRF 융합 완료: %d건", len(combined))

        # 상위 결과 추출
        documents = [r.document for r in combined[:fetch_k]]

        # Re-ranking (선택적)
        if use_rerank and len(documents) > k:
            documents = self.reranker.rerank(query, documents, top_k=k)
        else:
            documents = documents[:k]

        return documents

    async def asearch(
        self,
        query: str,
        domain: str,
        k: int = 5,
        use_rerank: bool = True,
    ) -> list[Document]:
        """Hybrid 검색을 비동기로 수행합니다.

        Args:
            query: 검색 쿼리
            domain: 도메인
            k: 반환할 결과 수
            use_rerank: Re-ranking 사용 여부

        Returns:
            검색된 문서 리스트
        """
        logger.info("[하이브리드] 검색 시작: 도메인=%s, k=%d", domain, k)

        fetch_k = k * 3

        # 벡터 검색 (동기 -> 스레드)
        vector_results = await asyncio.to_thread(
            self._vector_search, query, domain, fetch_k
        )
        logger.info("[하이브리드] 벡터 검색: %d건", len(vector_results))

        # BM25 검색
        bm25_results = []
        if domain in self.bm25_indices:
            bm25_results = self.bm25_indices[domain].search(query, k=fetch_k)
        logger.info("[하이브리드] BM25 검색: %d건", len(bm25_results))

        # 결과 융합
        if bm25_results:
            combined = reciprocal_rank_fusion([vector_results, bm25_results])
        else:
            combined = vector_results
        logger.info("[하이브리드] RRF 융합 완료: %d건", len(combined))

        documents = [r.document for r in combined[:fetch_k]]

        # Re-ranking (비동기)
        if use_rerank and len(documents) > k:
            documents = await self.reranker.arerank(query, documents, top_k=k)
        else:
            documents = documents[:k]

        return documents

    def _vector_search(
        self,
        query: str,
        domain: str,
        k: int,
    ) -> list[SearchResult]:
        """벡터 검색을 수행합니다."""
        try:
            docs = self.vector_store.max_marginal_relevance_search(
                query=query,
                domain=domain,
                k=k,
                fetch_k=k * 2,
                lambda_mult=self.settings.mmr_lambda_mult,
            )
            return [
                SearchResult(doc, 1.0 - (i / k), "vector")
                for i, doc in enumerate(docs)
            ]
        except Exception as e:
            logger.warning(f"벡터 검색 실패: {e}")
            return []


# 싱글톤 인스턴스
_hybrid_searcher: HybridSearcher | None = None


def get_hybrid_searcher(vector_store: Any) -> HybridSearcher:
    """HybridSearcher 인스턴스를 반환합니다.

    Args:
        vector_store: ChromaVectorStore 인스턴스

    Returns:
        HybridSearcher 인스턴스
    """
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher(vector_store)
    return _hybrid_searcher
