"""Bizi RAG 시스템의 VectorStores 모듈.

이 모듈은 ChromaDB 기반의 벡터 스토리지를 제공합니다.
하나의 ChromaDB 인스턴스에 여러 컬렉션(도메인)을 저장합니다.

구조:
    vectordb/
    └── chroma.sqlite3  # 모든 컬렉션이 하나의 DB에 저장됨
        ├── startup_funding_db (컬렉션)
        ├── finance_tax_db (컬렉션)
        ├── hr_labor_db (컬렉션)
        └── law_common_db (컬렉션)

Example:
    >>> from vectorstores import ChromaVectorStore, COLLECTION_NAMES
    >>> store = ChromaVectorStore()
    >>> store.build_all_vectordbs()
    >>> results = store.similarity_search("창업 지원금", "startup_funding", k=5)
"""

from .config import VectorDBConfig, ChunkingConfig, COLLECTION_NAMES
from .embeddings import get_embeddings
from .chroma import ChromaVectorStore
from .loader import DataLoader

__all__ = [
    "VectorDBConfig",
    "ChunkingConfig",
    "COLLECTION_NAMES",
    "get_embeddings",
    "ChromaVectorStore",
    "DataLoader",
]
