"""커스텀 예외 테스트."""

import pytest

from utils.exceptions import (
    RAGError,
    VectorSearchError,
    BM25SearchError,
    RerankerError,
    DomainClassificationError,
    LLMInvocationError,
    EmbeddingError,
    CacheError,
)


class TestRAGError:
    """RAGError 기본 예외 테스트."""

    def test_raise_rag_error(self):
        """RAGError 발생."""
        with pytest.raises(RAGError) as exc_info:
            raise RAGError("테스트 에러")

        assert "테스트 에러" in str(exc_info.value)

    def test_rag_error_inheritance(self):
        """RAGError가 Exception 상속."""
        assert issubclass(RAGError, Exception)


class TestVectorSearchError:
    """VectorSearchError 테스트."""

    def test_raise_vector_search_error(self):
        """VectorSearchError 발생."""
        with pytest.raises(VectorSearchError):
            raise VectorSearchError("ChromaDB 연결 실패")

    def test_vector_search_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(VectorSearchError, RAGError)

    def test_catch_as_rag_error(self):
        """RAGError로 잡기."""
        with pytest.raises(RAGError):
            raise VectorSearchError("벡터 검색 실패")


class TestBM25SearchError:
    """BM25SearchError 테스트."""

    def test_raise_bm25_search_error(self):
        """BM25SearchError 발생."""
        with pytest.raises(BM25SearchError):
            raise BM25SearchError("BM25 인덱스 없음")

    def test_bm25_search_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(BM25SearchError, RAGError)


class TestRerankerError:
    """RerankerError 테스트."""

    def test_raise_reranker_error(self):
        """RerankerError 발생."""
        with pytest.raises(RerankerError):
            raise RerankerError("리랭킹 모델 로드 실패")

    def test_reranker_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(RerankerError, RAGError)


class TestDomainClassificationError:
    """DomainClassificationError 테스트."""

    def test_raise_domain_classification_error(self):
        """DomainClassificationError 발생."""
        with pytest.raises(DomainClassificationError):
            raise DomainClassificationError("도메인 분류 실패")

    def test_domain_classification_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(DomainClassificationError, RAGError)


class TestLLMInvocationError:
    """LLMInvocationError 테스트."""

    def test_raise_llm_invocation_error(self):
        """LLMInvocationError 발생."""
        with pytest.raises(LLMInvocationError):
            raise LLMInvocationError("OpenAI API 호출 실패")

    def test_llm_invocation_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(LLMInvocationError, RAGError)

    def test_llm_error_with_cause(self):
        """원인 예외 체이닝."""
        original = ValueError("잘못된 API 키")
        with pytest.raises(LLMInvocationError) as exc_info:
            try:
                raise original
            except ValueError as e:
                raise LLMInvocationError("LLM 호출 실패") from e

        assert exc_info.value.__cause__ == original


class TestEmbeddingError:
    """EmbeddingError 테스트."""

    def test_raise_embedding_error(self):
        """EmbeddingError 발생."""
        with pytest.raises(EmbeddingError):
            raise EmbeddingError("임베딩 모델 로드 실패")

    def test_embedding_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(EmbeddingError, RAGError)


class TestCacheError:
    """CacheError 테스트."""

    def test_raise_cache_error(self):
        """CacheError 발생."""
        with pytest.raises(CacheError):
            raise CacheError("캐시 쓰기 실패")

    def test_cache_error_inheritance(self):
        """RAGError 상속 확인."""
        assert issubclass(CacheError, RAGError)


class TestExceptionHierarchy:
    """예외 계층 구조 테스트."""

    def test_all_errors_inherit_from_rag_error(self):
        """모든 커스텀 예외가 RAGError 상속."""
        error_classes = [
            VectorSearchError,
            BM25SearchError,
            RerankerError,
            DomainClassificationError,
            LLMInvocationError,
            EmbeddingError,
            CacheError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, RAGError), f"{error_class.__name__} should inherit from RAGError"

    def test_catch_all_with_rag_error(self):
        """RAGError로 모든 커스텀 예외 catch."""
        errors_to_test = [
            VectorSearchError("test"),
            BM25SearchError("test"),
            RerankerError("test"),
            DomainClassificationError("test"),
            LLMInvocationError("test"),
            EmbeddingError("test"),
            CacheError("test"),
        ]

        for error in errors_to_test:
            try:
                raise error
            except RAGError:
                pass  # 성공적으로 catch
            except Exception:
                pytest.fail(f"{type(error).__name__} was not caught by RAGError")
