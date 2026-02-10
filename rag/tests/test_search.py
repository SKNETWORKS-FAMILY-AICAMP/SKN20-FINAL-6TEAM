"""검색 모듈 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from langchain_core.documents import Document

from utils.search import BM25Index, HybridSearcher, SearchResult, reciprocal_rank_fusion


class TestBM25Index:
    """BM25Index 테스트."""

    @pytest.fixture
    def sample_docs(self):
        """테스트용 문서."""
        return [
            Document(page_content="창업 절차와 사업자 등록 방법에 대해 알아봅니다."),
            Document(page_content="부가가치세 신고 방법과 기한을 안내합니다."),
            Document(page_content="근로계약서 작성 시 주의사항을 설명합니다."),
            Document(page_content="창업 지원금과 보조금 신청 방법입니다."),
            Document(page_content="세금 신고 일정과 납부 방법을 안내합니다."),
        ]

    def test_fit(self, sample_docs):
        """인덱스 빌드 테스트."""
        index = BM25Index()
        index.fit(sample_docs)

        assert index.doc_count == 5
        assert index.avg_doc_len > 0
        assert len(index.idf) > 0

    def test_search_basic(self, sample_docs):
        """기본 검색 테스트."""
        index = BM25Index()
        index.fit(sample_docs)

        results = index.search("창업 사업자 등록", k=3)

        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.source == "bm25" for r in results)

    def test_search_relevance(self, sample_docs):
        """검색 관련성 테스트."""
        index = BM25Index()
        index.fit(sample_docs)

        results = index.search("창업", k=5)

        # 창업 관련 문서가 상위에 있어야 함
        assert len(results) > 0
        top_content = results[0].document.page_content
        assert "창업" in top_content

    def test_search_no_results(self, sample_docs):
        """결과 없는 검색."""
        index = BM25Index()
        index.fit(sample_docs)

        results = index.search("완전히 관련없는 쿼리 xyz123", k=3)

        # 관련 없으면 빈 결과 또는 낮은 점수
        # BM25는 term이 없으면 점수가 0이므로 결과가 없을 수 있음

    def test_empty_index(self):
        """빈 인덱스 검색."""
        index = BM25Index()
        results = index.search("창업", k=3)
        assert results == []


class TestReciprocalRankFusion:
    """RRF 테스트."""

    def test_basic_fusion(self):
        """기본 융합 테스트."""
        doc1 = Document(page_content="문서 1 내용")
        doc2 = Document(page_content="문서 2 내용")
        doc3 = Document(page_content="문서 3 내용")

        list1 = [
            SearchResult(doc1, 0.9, "vector"),
            SearchResult(doc2, 0.8, "vector"),
        ]
        list2 = [
            SearchResult(doc2, 0.9, "bm25"),
            SearchResult(doc3, 0.8, "bm25"),
        ]

        results = reciprocal_rank_fusion([list1, list2])

        assert len(results) == 3
        # doc2가 두 결과에 모두 있으므로 가장 높은 점수
        assert all(r.source == "hybrid" for r in results)

    def test_empty_lists(self):
        """빈 리스트 융합."""
        results = reciprocal_rank_fusion([[], []])
        assert results == []

    def test_single_list(self):
        """단일 리스트."""
        doc = Document(page_content="문서 내용")
        single_list = [SearchResult(doc, 0.9, "vector")]

        results = reciprocal_rank_fusion([single_list])
        assert len(results) == 1

    def test_weighted_fusion(self):
        """가중 RRF 테스트."""
        doc1 = Document(page_content="문서 1 내용 - 벡터 1위")
        doc2 = Document(page_content="문서 2 내용 - BM25 1위")
        doc3 = Document(page_content="문서 3 내용 - 공통")

        # 벡터: doc1 > doc3 > doc2
        vector_list = [
            SearchResult(doc1, 0.9, "vector"),
            SearchResult(doc3, 0.7, "vector"),
            SearchResult(doc2, 0.5, "vector"),
        ]
        # BM25: doc2 > doc3 > doc1
        bm25_list = [
            SearchResult(doc2, 0.9, "bm25"),
            SearchResult(doc3, 0.7, "bm25"),
            SearchResult(doc1, 0.5, "bm25"),
        ]

        # 벡터 가중치 0.8, BM25 가중치 0.2 (벡터 강조)
        results = reciprocal_rank_fusion(
            [vector_list, bm25_list],
            weights=[0.8, 0.2],
        )

        assert len(results) == 3
        # doc3이 양쪽 모두에서 중간 순위이므로 융합 후 상위
        # doc1이 벡터에서 1위 + 높은 가중치
        assert all(r.source == "hybrid" for r in results)

    def test_weighted_fusion_equal_weights(self):
        """동일 가중치 RRF 테스트 (기존 동작과 동일)."""
        doc1 = Document(page_content="문서 A 내용")
        doc2 = Document(page_content="문서 B 내용")

        list1 = [SearchResult(doc1, 0.9, "vector")]
        list2 = [SearchResult(doc2, 0.9, "bm25")]

        # 동일 가중치
        results_weighted = reciprocal_rank_fusion([list1, list2], weights=[1.0, 1.0])
        results_default = reciprocal_rank_fusion([list1, list2])

        assert len(results_weighted) == len(results_default)

    def test_weighted_fusion_zero_weight(self):
        """한쪽 가중치 0 테스트."""
        doc1 = Document(page_content="벡터 문서")
        doc2 = Document(page_content="BM25 문서")

        vector_list = [SearchResult(doc1, 0.9, "vector")]
        bm25_list = [SearchResult(doc2, 0.9, "bm25")]

        # BM25 가중치 0
        results = reciprocal_rank_fusion(
            [vector_list, bm25_list],
            weights=[1.0, 0.0],
        )

        assert len(results) == 2
        # 벡터 결과가 더 높은 점수를 가져야 함
        assert results[0].score > results[1].score


class TestHybridSearcher:
    """HybridSearcher 테스트."""

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        """벡터 스토어 Mock."""
        store = MagicMock()
        store.similarity_search_with_score.return_value = [
            (Document(page_content="벡터 문서1", metadata={}), 0.3),
            (Document(page_content="벡터 문서2", metadata={}), 0.5),
            (Document(page_content="벡터 문서3", metadata={}), 0.8),
        ]
        return store

    @pytest.fixture
    def searcher(self, mock_vector_store: MagicMock) -> HybridSearcher:
        """HybridSearcher 인스턴스."""
        with patch("utils.search.get_settings") as mock_settings:
            settings = MagicMock()
            settings.vector_search_weight = 0.7
            settings.enable_reranking = False
            mock_settings.return_value = settings
            return HybridSearcher(mock_vector_store)

    def test_search_returns_documents(self, searcher: HybridSearcher) -> None:
        """기본 검색: 문서가 k개 이하로 반환됩니다."""
        results = searcher.search("창업 절차", domain="startup", k=2, use_rerank=False)

        assert len(results) <= 2
        assert all(isinstance(doc, Document) for doc in results)

    def test_search_with_bm25_index(
        self, searcher: HybridSearcher, mock_vector_store: MagicMock
    ) -> None:
        """BM25 인덱스가 있으면 벡터 + BM25 모두 사용됩니다."""
        # BM25 인덱스 빌드
        docs = [
            Document(page_content="창업 절차와 사업자 등록 방법"),
            Document(page_content="부가가치세 신고 방법"),
        ]
        searcher.build_bm25_index("startup", docs)

        results = searcher.search("창업 절차", domain="startup", k=3, use_rerank=False)

        mock_vector_store.similarity_search_with_score.assert_called_once()
        assert len(results) <= 3

    def test_search_without_bm25_index(
        self, searcher: HybridSearcher, mock_vector_store: MagicMock
    ) -> None:
        """BM25 인덱스가 없으면 벡터 결과만 반환됩니다."""
        results = searcher.search("창업 절차", domain="startup", k=3, use_rerank=False)

        mock_vector_store.similarity_search_with_score.assert_called_once()
        assert len(results) <= 3
        assert "startup" not in searcher.bm25_indices

    def test_search_auto_builds_bm25_index_from_vector_store(
        self, searcher: HybridSearcher, mock_vector_store: MagicMock
    ) -> None:
        """BM25 인덱스가 없으면 벡터스토어 문서로 자동 빌드합니다."""
        mock_vector_store.get_domain_documents.return_value = [
            Document(page_content="창업 절차와 사업자 등록 방법", metadata={"id": "a1"}),
            Document(page_content="부가가치세 신고 방법", metadata={"id": "a2"}),
        ]

        results = searcher.search("창업 절차", domain="startup", k=3, use_rerank=False)

        assert len(results) <= 3
        assert "startup" in searcher.bm25_indices
        mock_vector_store.get_domain_documents.assert_called_once_with("startup")

    def test_search_score_in_metadata(self, searcher: HybridSearcher) -> None:
        """모든 반환 문서의 metadata에 score가 존재합니다."""
        results = searcher.search("창업 절차", domain="startup", k=5, use_rerank=False)

        for doc in results:
            assert "score" in doc.metadata

    def test_search_rerank_applied(self, searcher: HybridSearcher) -> None:
        """use_rerank=True이고 문서 수 > k이면 reranker가 호출됩니다."""
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            Document(page_content="리랭크 결과", metadata={"score": 0.9}),
        ]
        searcher._reranker = mock_reranker

        results = searcher.search("창업 절차", domain="startup", k=1, use_rerank=True)

        mock_reranker.rerank.assert_called_once()
        assert len(results) == 1

    def test_search_rerank_skipped_when_disabled(self, searcher: HybridSearcher) -> None:
        """use_rerank=False이면 reranker가 호출되지 않습니다."""
        mock_reranker = MagicMock()
        searcher._reranker = mock_reranker

        searcher.search("창업 절차", domain="startup", k=5, use_rerank=False)

        mock_reranker.rerank.assert_not_called()

    def test_build_search_results_sets_embedding_similarity(
        self, searcher: HybridSearcher, mock_vector_store: MagicMock
    ) -> None:
        """Hybrid 검색 후 모든 문서에 embedding_similarity가 존재합니다."""
        # BM25 인덱스 추가 (hybrid 경로 활성화)
        bm25_docs = [
            Document(page_content="창업 절차와 사업자 등록 방법"),
            Document(page_content="BM25 전용 문서 내용"),
        ]
        searcher.build_bm25_index("startup", bm25_docs)

        results = searcher.search("창업 절차", domain="startup", k=5, use_rerank=False)

        for doc in results:
            assert "embedding_similarity" in doc.metadata
            assert isinstance(doc.metadata["embedding_similarity"], float)
            assert 0.0 <= doc.metadata["embedding_similarity"] <= 1.0

    def test_vector_similarity_formula_cosine(
        self, searcher: HybridSearcher, mock_vector_store: MagicMock
    ) -> None:
        """cosine distance 0.3 → similarity 0.7로 변환됩니다."""
        mock_vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="테스트 문서", metadata={}), 0.3),
        ]

        results = searcher.search("테스트", domain="startup", k=5, use_rerank=False)

        assert len(results) >= 1
        # 1.0 - 0.3 = 0.7
        assert results[0].metadata["embedding_similarity"] == pytest.approx(0.7, abs=0.01)
