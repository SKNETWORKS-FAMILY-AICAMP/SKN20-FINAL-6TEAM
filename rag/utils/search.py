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
from utils.score_normalizer import ScoreNormalizer

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

    def __init__(self, k1: float = 1.5, b: float = 0.75, use_kiwi: bool = True):
        """BM25Index를 초기화합니다.

        Args:
            k1: term frequency saturation 파라미터
            b: document length normalization 파라미터
            use_kiwi: kiwipiepy 형태소 분석기 사용 여부
        """
        self.k1 = k1
        self.b = b
        self._use_kiwi = use_kiwi
        self._kiwi = None
        self.documents: list[Document] = []
        self.doc_freqs: list[Counter] = []
        self.idf: dict[str, float] = {}
        self.avg_doc_len: float = 0
        self.doc_count: int = 0

    def _get_kiwi(self):
        """Kiwi 인스턴스를 지연 로딩합니다."""
        if self._kiwi is None:
            try:
                from kiwipiepy import Kiwi
                self._kiwi = Kiwi()
            except ImportError:
                logger.warning("[BM25] kiwipiepy 미설치, 정규식 토크나이저로 fallback")
                self._use_kiwi = False
        return self._kiwi

    def _tokenize(self, text: str) -> list[str]:
        """텍스트를 토큰화합니다."""
        if self._use_kiwi:
            kiwi = self._get_kiwi()
            if kiwi:
                tokens = kiwi.tokenize(text)
                result = []
                for token in tokens:
                    if token.tag.startswith("NN") or token.tag == "SL":
                        result.append(token.form)
                    elif token.tag.startswith("VV") or token.tag.startswith("VA"):
                        result.append(token.form + "다")
                return [t for t in result if len(t) >= 2]
        # fallback: 기존 정규식
        tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', text.lower())
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

        # Min-Max 정규화 (0~1 범위로 변환)
        scores = ScoreNormalizer.min_max_normalize(scores)

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
    weights: list[float] | None = None,
    k: int | None = None,
) -> list[SearchResult]:
    """가중치를 적용한 Reciprocal Rank Fusion으로 여러 검색 결과를 융합합니다.

    Args:
        results_list: 여러 검색 결과 리스트
        weights: 각 결과 리스트의 가중치 (예: [vector_weight, bm25_weight])
        k: RRF 파라미터 (None이면 settings.rrf_k 사용)

    Returns:
        융합된 검색 결과
    """
    if k is None:
        k = get_settings().rrf_k

    if weights is None:
        weights = [1.0] * len(results_list)

    # 가중치 정규화
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # 문서별 RRF 점수 계산
    doc_scores: dict[int, float] = {}
    doc_map: dict[int, Document] = {}

    for results, weight in zip(results_list, weights):
        for rank, result in enumerate(results):
            # 문서 ID 생성 (content hash)
            doc_id = hash(result.document.page_content[:200])

            # 가중 RRF 점수 누적
            rrf_score = weight * (1 / (k + rank + 1))
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


def reciprocal_rank_fusion_docs(
    doc_lists: list[list[Document]],
    k: int | None = None,
) -> list[Document]:
    """Document 리스트 기반 RRF 융합 (Multi-Query용).

    Args:
        doc_lists: 각 쿼리별 검색 결과 Document 리스트
        k: RRF 상수 (None이면 settings.rrf_k 사용)

    Returns:
        RRF 점수로 정렬된 Document 리스트 (메타데이터에 rrf_score/score 포함)
    """
    if k is None:
        k = get_settings().rrf_k
    fused_scores: dict[int, float] = {}
    doc_map: dict[int, Document] = {}

    for doc_list in doc_lists:
        for rank, doc in enumerate(doc_list):
            doc_id = hash(doc.page_content[:500])
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
                fused_scores[doc_id] = 0.0
            fused_scores[doc_id] += 1 / (rank + k)

    sorted_doc_ids = sorted(
        fused_scores.keys(),
        key=lambda x: fused_scores[x],
        reverse=True,
    )

    result_docs = []
    for doc_id in sorted_doc_ids:
        doc = doc_map[doc_id]
        doc.metadata["rrf_score"] = fused_scores[doc_id]
        doc.metadata["score"] = fused_scores[doc_id]
        result_docs.append(doc)

    return result_docs


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
        self._bm25_init_attempted: set[str] = set()
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
        if not documents:
            logger.warning(f"BM25 인덱스 빌드 스킵: {domain} (문서 없음)")
            return

        try:
            index = BM25Index()
            index.fit(documents)
            self.bm25_indices[domain] = index
            logger.info(f"BM25 인덱스 빌드 완료: {domain} ({len(documents)}개 문서)")
        except Exception as e:
            logger.error(f"BM25 인덱스 빌드 실패: {domain} - {e}")

    def _ensure_bm25_index(self, domain: str) -> None:
        """도메인 BM25 인덱스를 필요 시 지연 초기화합니다.

        런타임 경로에서 `build_bm25_index`가 호출되지 않아 BM25가 비활성처럼
        동작하는 문제를 방지하기 위해, 최초 검색 시 1회 자동 빌드를 시도합니다.
        """
        if domain in self.bm25_indices:
            return
        if domain in self._bm25_init_attempted:
            return

        self._bm25_init_attempted.add(domain)

        load_documents = getattr(self.vector_store, "get_domain_documents", None)
        if not callable(load_documents):
            logger.warning("[하이브리드] BM25 인덱스 자동 빌드 불가: get_domain_documents 미지원 (%s)", domain)
            return

        try:
            documents = load_documents(domain)
        except Exception as e:
            logger.warning("[하이브리드] BM25 인덱스 자동 빌드 실패 (%s): %s", domain, e)
            return

        if not isinstance(documents, list):
            logger.warning("[하이브리드] BM25 인덱스 자동 빌드 실패: 문서 포맷 오류 (%s)", domain)
            return

        valid_documents = [
            doc for doc in documents
            if isinstance(doc, Document)
            and isinstance(doc.page_content, str)
            and doc.page_content.strip()
        ]
        if not valid_documents:
            logger.warning("[하이브리드] BM25 인덱스 자동 빌드 스킵: 유효 문서 없음 (%s)", domain)
            return

        self.build_bm25_index(domain, valid_documents)

    def _build_search_results(
        self,
        query: str,
        domain: str,
        k: int,
        vector_weight: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """벡터+BM25 검색 후 가중치 RRF 융합한 문서 리스트를 반환합니다.

        Args:
            query: 검색 쿼리
            domain: 도메인
            k: 반환할 후보 문서 수 (reranking 전)
            vector_weight: 벡터 가중치 (None이면 설정값 사용)
            filter: ChromaDB 메타데이터 필터 (선택)

        Returns:
            융합된 문서 리스트
        """
        if vector_weight is None:
            vector_weight = self.settings.vector_search_weight
        vector_weight = min(1.0, max(0.0, vector_weight))
        bm25_weight = 1.0 - vector_weight

        fetch_k = k * 3

        logger.info(
            "[하이브리드] 검색 시작: 도메인=%s, k=%d, 벡터가중치=%.2f, BM25가중치=%.2f",
            domain, k, vector_weight, bm25_weight,
        )

        # 1. 벡터 검색
        vector_results: list[SearchResult] = []
        try:
            raw_results = self.vector_store.similarity_search_with_score(
                query=query, domain=domain, k=fetch_k, filter=filter,
            )
            vector_results = [
                SearchResult(doc, max(0.0, min(1.0, 1.0 - distance)), "vector")
                for doc, distance in raw_results
            ]
        except Exception as e:
            logger.warning("[하이브리드] 벡터 검색 실패: %s", e)
        logger.info("[하이브리드] 벡터 검색: %d건", len(vector_results))

        # 벡터 검색 원본 유사도 보존 (RRF 전)
        vector_similarity_map: dict[int, float] = {}
        for r in vector_results:
            doc_id = hash(r.document.page_content[:200])
            vector_similarity_map[doc_id] = r.score

        # 2. BM25 검색
        self._ensure_bm25_index(domain)
        bm25_results: list[SearchResult] = []
        if domain in self.bm25_indices:
            bm25_results = self.bm25_indices[domain].search(query, k=fetch_k)
        logger.info("[하이브리드] BM25 검색: %d건", len(bm25_results))

        # 3. 가중 RRF 융합
        if bm25_results:
            combined = reciprocal_rank_fusion(
                [vector_results, bm25_results],
                weights=[vector_weight, bm25_weight],
            )
        else:
            combined = vector_results
        logger.info("[하이브리드] RRF 융합 완료: %d건", len(combined))

        # 4. 문서 추출 (score + embedding_similarity를 metadata에 주입)
        documents: list[Document] = []
        for r in combined[:fetch_k]:
            r.document.metadata["score"] = r.score
            doc_id = hash(r.document.page_content[:200])
            r.document.metadata["embedding_similarity"] = vector_similarity_map.get(doc_id, 0.0)
            documents.append(r.document)

        return documents

    def search(
        self,
        query: str,
        domain: str,
        k: int = 5,
        use_rerank: bool = True,
        vector_weight: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Hybrid 검색을 수행합니다.

        Args:
            query: 검색 쿼리
            domain: 도메인
            k: 반환할 결과 수
            use_rerank: Re-ranking 사용 여부
            vector_weight: 벡터 검색 가중치 (0.0-1.0, None이면 설정값 사용)
            filter: ChromaDB 메타데이터 필터 (선택)

        Returns:
            검색된 문서 리스트
        """
        documents = self._build_search_results(query, domain, k, vector_weight, filter=filter)

        if use_rerank and self.reranker and len(documents) > k:
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
        vector_weight: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Hybrid 검색을 비동기로 수행합니다.

        Args:
            query: 검색 쿼리
            domain: 도메인
            k: 반환할 결과 수
            use_rerank: Re-ranking 사용 여부
            vector_weight: 벡터 검색 가중치 (0.0-1.0, None이면 설정값 사용)
            filter: ChromaDB 메타데이터 필터 (선택)

        Returns:
            검색된 문서 리스트
        """
        documents = await asyncio.to_thread(
            self._build_search_results, query, domain, k, vector_weight, filter=filter,
        )

        if use_rerank and self.reranker and len(documents) > k:
            documents = await self.reranker.arerank(query, documents, top_k=k)
        else:
            documents = documents[:k]

        return documents


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


def reset_hybrid_searcher() -> None:
    """HybridSearcher 싱글톤을 리셋합니다 (테스트용)."""
    global _hybrid_searcher
    _hybrid_searcher = None
    logger.debug("[하이브리드] 싱글톤 리셋")
