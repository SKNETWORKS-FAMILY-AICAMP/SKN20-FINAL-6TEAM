"""RAG 체인 테스트."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from langchain_core.documents import Document


class TestRAGChainRetrieve:
    """RAGChain retrieve 메서드 테스트."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock VectorStore fixture."""
        store = MagicMock()
        store.max_marginal_relevance_search.return_value = [
            Document(
                page_content="테스트 문서 1",
                metadata={"title": "문서1", "source": "출처1"},
            ),
            Document(
                page_content="테스트 문서 2",
                metadata={"title": "문서2", "source": "출처2"},
            ),
        ]
        store.similarity_search.return_value = [
            Document(
                page_content="테스트 문서 1",
                metadata={"title": "문서1", "source": "출처1"},
            ),
        ]
        return store

    @pytest.fixture
    def rag_chain(self, mock_vector_store):
        """RAGChain fixture."""
        with patch("chains.rag_chain.create_llm"):
            from chains.rag_chain import RAGChain
            chain = RAGChain(vector_store=mock_vector_store)
            chain._reranker = None  # Re-ranking 비활성화
            return chain

    def test_retrieve_default(self, rag_chain, mock_vector_store):
        """기본 검색 테스트."""
        with patch("utils.query.get_multi_query_retriever") as mock_mq_fn:
            mock_mq = MagicMock()
            mock_mq.retrieve.return_value = (
                [Document(page_content="MQ 결과", metadata={"score": 0.9})],
                "확장 쿼리 1 | 확장 쿼리 2",
                ["테스트 쿼리", "확장 쿼리 1", "확장 쿼리 2"],
            )
            mock_mq_fn.return_value = mock_mq

            docs = rag_chain.retrieve(
                query="테스트 쿼리",
                domain="finance_tax",
            )

        assert len(docs) > 0
        mock_mq.retrieve.assert_called_once()
        call_kwargs = mock_mq.retrieve.call_args.kwargs
        assert "vector_weight" not in call_kwargs

    def test_retrieve_with_search_strategy(self, rag_chain, mock_vector_store):
        """검색 전략 적용 테스트."""
        from utils.feedback import SearchStrategy

        strategy = SearchStrategy(
            k=5,
            k_common=3,
            use_rerank=False,
            use_mmr=True,
            mmr_lambda=0.7,
        )

        # settings에서 hybrid search 비활성화
        rag_chain.settings.enable_hybrid_search = False

        docs = rag_chain._retrieve_documents(
            query="테스트 쿼리",
            domain="finance_tax",
            search_strategy=strategy,
            use_hybrid=False,  # Hybrid Search 비활성화하여 직접 벡터 검색
        )

        # 검색 전략의 k 값이 적용되었는지 확인 (첫 번째 호출 = 도메인 검색)
        calls = mock_vector_store.max_marginal_relevance_search.call_args_list
        domain_call = calls[0]  # 첫 번째 호출이 도메인 검색
        assert domain_call[1]["k"] == 5
        assert domain_call[1]["lambda_mult"] == 0.7

    def test_retrieve_no_mmr(self, rag_chain, mock_vector_store):
        """MMR 비활성화 검색 테스트."""
        docs = rag_chain._retrieve_documents(
            query="테스트 쿼리",
            domain="finance_tax",
            use_mmr=False,
            use_hybrid=False,  # Hybrid Search 비활성화하여 similarity_search 호출
        )

        mock_vector_store.similarity_search.assert_called()

    def test_retrieve_include_common(self, rag_chain, mock_vector_store):
        """공통 법령 DB 포함 검색 테스트."""
        docs = rag_chain._retrieve_documents(
            query="테스트 쿼리",
            domain="finance_tax",
            include_common=True,
        )

        # finance_tax와 law_common 두 번 호출
        calls = mock_vector_store.max_marginal_relevance_search.call_args_list
        domains = [call[1]["domain"] for call in calls]
        assert "finance_tax" in domains
        assert "law_common" in domains


class TestRAGChainFormatContext:
    """RAGChain format_context 메서드 테스트."""

    @pytest.fixture
    def rag_chain(self):
        """RAGChain fixture."""
        with patch("chains.rag_chain.create_llm"), \
             patch("chains.rag_chain.ChromaVectorStore"):
            from chains.rag_chain import RAGChain
            return RAGChain()

    def test_format_context_empty(self, rag_chain):
        """빈 문서 리스트 포맷팅 테스트."""
        context = rag_chain.format_context([])
        assert "관련 참고 자료가 없습니다" in context

    def test_format_context_with_title(self, rag_chain):
        """제목이 있는 문서 포맷팅 테스트."""
        docs = [
            Document(
                page_content="문서 내용입니다.",
                metadata={"title": "문서 제목", "source_name": "출처"},
            ),
        ]
        context = rag_chain.format_context(docs)

        assert "문서 제목" in context
        assert "출처" in context
        assert "문서 내용" in context

    def test_format_context_without_title(self, rag_chain):
        """제목이 없는 문서 포맷팅 테스트."""
        docs = [
            Document(
                page_content="문서 내용입니다.",
                metadata={"source_file": "파일.pdf"},
            ),
        ]
        context = rag_chain.format_context(docs)

        assert "파일.pdf" in context


class TestRAGChainDocumentsToSources:
    """RAGChain documents_to_sources 메서드 테스트."""

    @pytest.fixture
    def rag_chain(self):
        """RAGChain fixture."""
        with patch("chains.rag_chain.create_llm"), \
             patch("chains.rag_chain.ChromaVectorStore"):
            from chains.rag_chain import RAGChain
            return RAGChain()

    def test_documents_to_sources(self, rag_chain):
        """SourceDocument 변환 테스트."""
        docs = [
            Document(
                page_content="문서 내용입니다. " * 100,  # 긴 내용
                metadata={
                    "title": "문서 제목",
                    "source_name": "출처명",
                    "extra": "추가 정보",
                },
            ),
        ]
        sources = rag_chain.documents_to_sources(docs)

        assert len(sources) == 1
        assert sources[0].title == "문서 제목"
        assert sources[0].source == "출처명"
        assert len(sources[0].content) <= rag_chain.settings.source_content_length


