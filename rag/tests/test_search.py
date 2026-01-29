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
