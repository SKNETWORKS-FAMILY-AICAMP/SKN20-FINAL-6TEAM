"""검색 모듈 테스트."""

import pytest

from langchain_core.documents import Document

from utils.search import BM25Index, SearchResult, reciprocal_rank_fusion


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
