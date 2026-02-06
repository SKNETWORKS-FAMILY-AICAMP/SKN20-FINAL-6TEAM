"""RAG 서비스 커스텀 예외 모듈.

구체적인 예외 타입을 정의하여 에러 핸들링을 개선합니다.
"""


class RAGError(Exception):
    """RAG 서비스 기본 예외.

    모든 RAG 관련 예외의 기본 클래스입니다.
    """

    pass


class VectorSearchError(RAGError):
    """벡터 검색 실패 예외.

    ChromaDB 연결 오류, 쿼리 실패 등 벡터 검색 관련 오류에 사용됩니다.
    """

    pass


class BM25SearchError(RAGError):
    """BM25 검색 실패 예외.

    BM25 인덱스 오류, 검색 실패 등에 사용됩니다.
    """

    pass


class RerankerError(RAGError):
    """Re-ranking 실패 예외.

    Cross-encoder 또는 LLM 기반 리랭킹 실패 시 사용됩니다.
    """

    pass


class DomainClassificationError(RAGError):
    """도메인 분류 실패 예외.

    키워드/벡터/LLM 기반 도메인 분류 실패 시 사용됩니다.
    """

    pass


class LLMInvocationError(RAGError):
    """LLM 호출 실패 예외.

    OpenAI API 호출 실패, 타임아웃, 토큰 한도 초과 등에 사용됩니다.
    """

    pass


class EmbeddingError(RAGError):
    """임베딩 생성 실패 예외.

    HuggingFace 임베딩 모델 로딩 실패, 임베딩 계산 오류 등에 사용됩니다.
    """

    pass


class CacheError(RAGError):
    """캐시 작업 실패 예외.

    캐시 읽기/쓰기 실패 시 사용됩니다.
    """

    pass
