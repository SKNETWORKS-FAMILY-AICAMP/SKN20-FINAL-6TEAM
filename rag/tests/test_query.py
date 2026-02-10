"""쿼리 처리 모듈 테스트."""

import pytest
from langchain_core.documents import Document
from unittest.mock import MagicMock, patch

from utils.query import MultiQueryRetriever, QueryProcessor


class TestQueryProcessor:
    """QueryProcessor 테스트."""

    def test_generate_cache_key(self):
        """캐시 키 생성 테스트."""
        key1 = QueryProcessor.generate_cache_key("창업 절차 알려주세요")
        key2 = QueryProcessor.generate_cache_key("창업 절차  알려주세요")  # 공백 다름
        key3 = QueryProcessor.generate_cache_key("창업 절차 알려주세요", domain="startup")

        # 정규화로 인해 공백 차이는 무시
        assert key1 == key2
        # 도메인이 다르면 다른 키
        assert key1 != key3

    def test_generate_cache_key_case_insensitive(self):
        """캐시 키 대소문자 무시 테스트."""
        key1 = QueryProcessor.generate_cache_key("Hello World")
        key2 = QueryProcessor.generate_cache_key("hello world")

        assert key1 == key2

    def test_extract_keywords(self):
        """키워드 추출 테스트."""
        query = "창업할 때 세금 신고는 어떻게 하나요?"
        keywords = QueryProcessor.extract_keywords(query)

        # 정규식이 완전한 단어를 추출하므로 "창업할", "신고는" 등이 추출됨
        assert "창업할" in keywords or "창업" in keywords
        assert "세금" in keywords
        assert "신고는" in keywords or "신고" in keywords

        # 불용어는 제외
        assert "어떻게" not in keywords
        assert "하나요" not in keywords

    def test_extract_keywords_empty(self):
        """빈 쿼리 키워드 추출."""
        keywords = QueryProcessor.extract_keywords("")
        assert keywords == []

    def test_extract_keywords_only_stopwords(self):
        """불용어만 있는 쿼리."""
        query = "어떻게 하나요?"
        keywords = QueryProcessor.extract_keywords(query)
        # 모두 불용어이므로 빈 리스트 또는 짧은 단어 제외
        # "어떻게", "하나요"는 불용어이므로 제외됨

    def test_extract_keywords_mixed(self):
        """한글/영어 혼합 쿼리."""
        query = "startup 창업 funding 지원금"
        keywords = QueryProcessor.extract_keywords(query)

        assert "startup" in keywords
        assert "창업" in keywords
        assert "funding" in keywords
        assert "지원금" in keywords


class TestQueryProcessorIntegration:
    """QueryProcessor 통합 테스트 (API 호출 필요)."""

    @pytest.fixture
    def processor(self):
        """테스트용 프로세서."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        try:
            return QueryProcessor()
        except Exception:
            pytest.skip("OpenAI API 키가 설정되지 않음")

    @pytest.mark.skip(reason="실제 API 호출 필요")
    def test_compress_context(self, processor):
        """컨텍스트 압축 테스트 (실제 API 호출)."""
        query = "부가세 신고 기한"
        document = """
        부가가치세 신고는 매 분기별로 해야 합니다.
        일반과세자의 경우 1월, 4월, 7월, 10월에 신고합니다.
        오늘 날씨가 좋습니다. 이것은 관련 없는 내용입니다.
        신고 기한은 각 분기 종료 후 25일 이내입니다.
        """

        compressed = processor.compress_context(query, document)

        # 압축된 내용은 원본보다 짧거나 관련 내용만 포함
        assert isinstance(compressed, str)
        assert len(compressed) > 0


class TestMultiQueryRetriever:
    """MultiQueryRetriever 점수 분리/필터링 테스트."""

    @pytest.fixture
    def retriever(self):
        """테스트용 MultiQueryRetriever."""
        with patch("utils.query.create_llm"), patch("utils.query.get_settings") as mock_get_settings:
            settings = MagicMock()
            settings.multi_query_count = 3
            settings.retrieval_k = 3
            settings.retrieval_k_common = 2
            settings.max_retrieval_docs = 10
            settings.enable_reranking = False
            settings.min_doc_embedding_similarity = 0.2
            mock_get_settings.return_value = settings

            rag_chain = MagicMock()
            rag_chain.reranker = None
            rag_chain.vector_store = MagicMock()
            return MultiQueryRetriever(rag_chain)

    def test_rrf_keeps_legacy_score_and_sets_separate_rank_fields(self, retriever):
        """RRF가 metadata['score']를 덮어쓰지 않고 별도 필드를 기록하는지 검증."""
        doc_a = Document(page_content="A 문서", metadata={"score": 0.11, "title": "A"})
        doc_b = Document(page_content="B 문서", metadata={"score": 0.22, "title": "B"})

        fused = retriever._reciprocal_rank_fusion([[doc_a, doc_b], [doc_a]])

        assert fused
        assert "rrf_score" in doc_a.metadata
        assert "ranking_score" in doc_a.metadata
        assert doc_a.metadata["ranking_score"] == doc_a.metadata["rrf_score"]
        assert doc_a.metadata["score"] == 0.11

    def test_embedding_filter_applies_threshold(self, retriever):
        """embedding similarity 임계값 필터가 동작하는지 검증."""
        retriever.settings.min_doc_embedding_similarity = 0.5

        doc_high = Document(page_content="높은 유사도 문서", metadata={"title": "high"})
        doc_low = Document(page_content="낮은 유사도 문서", metadata={"title": "low"})
        fused_docs = [doc_high, doc_low]

        similarity_map = {
            retriever._make_doc_key(doc_high): 0.8,
            retriever._make_doc_key(doc_low): 0.1,
        }

        with patch.object(retriever, "_collect_embedding_similarity_map", return_value=similarity_map):
            filtered_docs, used_fallback = retriever._apply_embedding_similarity_filter(
                query="테스트",
                domain="finance_tax",
                fused_docs=fused_docs,
                include_common=True,
            )

        assert used_fallback is False
        assert len(filtered_docs) == 1
        assert filtered_docs[0].page_content == "높은 유사도 문서"
        assert filtered_docs[0].metadata["embedding_similarity"] == 0.8
        assert doc_low.metadata["embedding_similarity"] == 0.1

    def test_embedding_filter_keeps_rrf_top1_when_all_filtered(self, retriever):
        """모든 후보 탈락 시 RRF Top1 fallback이 적용되는지 검증."""
        retriever.settings.min_doc_embedding_similarity = 0.7

        doc_top1 = Document(
            page_content="RRF 1위 문서",
            metadata={"title": "top1", "rrf_score": 0.03},
        )
        doc_top2 = Document(
            page_content="RRF 2위 문서",
            metadata={"title": "top2", "rrf_score": 0.02},
        )

        with patch.object(retriever, "_collect_embedding_similarity_map", return_value={}):
            filtered_docs, used_fallback = retriever._apply_embedding_similarity_filter(
                query="테스트",
                domain="finance_tax",
                fused_docs=[doc_top1, doc_top2],
                include_common=False,
            )

        assert used_fallback is True
        assert len(filtered_docs) == 1
        assert filtered_docs[0].page_content == "RRF 1위 문서"
        assert filtered_docs[0].metadata["embedding_similarity"] == 0.0
