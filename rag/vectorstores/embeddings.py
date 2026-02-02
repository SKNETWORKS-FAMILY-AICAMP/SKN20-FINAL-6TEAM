"""HuggingFace 임베딩 설정 모듈.

이 모듈은 VectorDB에서 사용할 HuggingFace 임베딩을 설정합니다.
BAAI/bge-m3 모델을 기본으로 사용하며, GPU를 자동 감지합니다.

Example:
    >>> from vectorstores.embeddings import get_embeddings
    >>> embeddings = get_embeddings()
    >>> vector = embeddings.embed_query("창업 지원금")
"""

import logging
from functools import lru_cache

import torch
from langchain_huggingface import HuggingFaceEmbeddings

from .config import VectorDBConfig

logger = logging.getLogger(__name__)


def get_device() -> str:
    """CUDA > MPS > CPU 우선순위로 디바이스 반환."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def get_embeddings(model: str | None = None) -> HuggingFaceEmbeddings:
    """HuggingFace 임베딩 인스턴스를 가져옵니다 (싱글톤).

    Args:
        model: 임베딩 모델 이름. None이면 설정값 사용 (기본: BAAI/bge-m3)

    Returns:
        HuggingFaceEmbeddings 인스턴스
    """
    config = VectorDBConfig()
    model_name = model or config.embedding_model
    device = get_device()

    logger.info(f"임베딩 모델 로딩: {model_name} (디바이스: {device})")

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
