"""OpenAI 임베딩 설정 모듈.

이 모듈은 VectorDB에서 사용할 OpenAI 임베딩을 설정합니다.
text-embedding-3-small 모델을 기본으로 사용합니다.

Example:
    >>> from vectorstores.embeddings import get_embeddings
    >>> embeddings = get_embeddings()
    >>> vector = embeddings.embed_query("창업 지원금")
"""

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from .config import VectorDBConfig


@lru_cache(maxsize=1)
def get_embeddings(model: str | None = None) -> OpenAIEmbeddings:
    """OpenAI 임베딩 인스턴스를 가져옵니다.

    싱글톤 패턴으로 하나의 인스턴스만 생성하여 재사용합니다.

    Args:
        model: 임베딩 모델 이름. None이면 설정값 사용 (기본: text-embedding-3-small)

    Returns:
        OpenAIEmbeddings 인스턴스
    """
    config = VectorDBConfig()
    model_name = model or config.embedding_model

    return OpenAIEmbeddings(
        model=model_name,
        openai_api_key=config.openai_api_key,
    )
