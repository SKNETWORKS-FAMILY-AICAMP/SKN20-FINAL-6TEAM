"""ChromaDB 벡터 스토어 구현 모듈.

이 모듈은 Bizi RAG 시스템의 벡터 데이터베이스를 관리합니다.
하나의 ChromaDB 인스턴스에 여러 컬렉션(테이블)을 저장합니다.

구조:
    vectordb/
    └── chroma.sqlite3  # 모든 컬렉션이 하나의 DB에 저장됨
        ├── startup_funding_db (컬렉션)
        ├── finance_tax_db (컬렉션)
        ├── hr_labor_db (컬렉션)
        └── law_common_db (컬렉션)
"""

import logging
import threading
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from tqdm import tqdm

from .config import COLLECTION_NAMES, VectorDBConfig
from .embeddings import get_embeddings
from .loader import DataLoader

# 캐시 최대 크기 (도메인 개수보다 크게 설정)
MAX_STORE_CACHE_SIZE = 10


class ChromaVectorStore:
    """ChromaDB 기반 벡터 스토어 클래스.

    하나의 persist_directory에 여러 컬렉션(테이블)을 저장하고 관리합니다.
    각 도메인(창업/세무/노무/법령)별로 별도의 컬렉션을 사용합니다.

    Attributes:
        config: VectorDB 설정 객체
        embeddings: OpenAI 임베딩 인스턴스
        loader: 데이터 로더 인스턴스
        _client: ChromaDB 클라이언트 (싱글톤)
        _stores: 컬렉션별 Chroma 인스턴스 캐시

    Example:
        >>> store = ChromaVectorStore()
        >>> store.build_vectordb("startup_funding")
        >>> results = store.similarity_search("창업 지원금", "startup_funding", k=5)
    """

    def __init__(self, config: VectorDBConfig | None = None):
        """ChromaVectorStore를 초기화합니다.

        Args:
            config: VectorDB 설정 객체. None이면 기본 설정 사용.
        """
        self.config = config or VectorDBConfig()
        self.embeddings = get_embeddings(self.config.embedding_model)
        self.loader = DataLoader()
        self._client: chromadb.PersistentClient | None = None
        # LRU 캐시 방식의 OrderedDict 사용
        self._stores: OrderedDict[str, Chroma] = OrderedDict()
        self._store_lock = threading.Lock()

        # 저장 디렉토리 생성
        self.config.persist_directory.mkdir(parents=True, exist_ok=True)

    def _get_client(self) -> chromadb.PersistentClient:
        """ChromaDB 클라이언트를 가져옵니다 (싱글톤).

        하나의 persist_directory를 사용하여 모든 컬렉션을 관리합니다.

        Returns:
            ChromaDB PersistentClient 인스턴스
        """
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self.config.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
        return self._client

    def _get_collection_name(self, domain: str) -> str:
        """도메인에 해당하는 컬렉션 이름을 반환합니다.

        Args:
            domain: 도메인 키 (startup_funding, finance_tax, hr_labor, law_common)

        Returns:
            컬렉션 이름 문자열
        """
        return COLLECTION_NAMES.get(domain, domain)

    def get_or_create_store(self, domain: str) -> Chroma:
        """도메인에 해당하는 Chroma 벡터 스토어를 가져오거나 생성합니다.

        LRU 캐시 방식으로 관리하여 메모리 누수를 방지합니다.

        Args:
            domain: 도메인 키

        Returns:
            Chroma 벡터 스토어 인스턴스
        """
        with self._store_lock:
            if domain in self._stores:
                # 기존 항목을 맨 뒤로 이동 (최근 사용)
                self._stores.move_to_end(domain)
                return self._stores[domain]

            collection_name = self._get_collection_name(domain)
            client = self._get_client()

            store = Chroma(
                client=client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
                collection_metadata=self.config.collection_metadata,
            )

            # 캐시 크기 초과 시 가장 오래된 항목 제거
            while len(self._stores) >= MAX_STORE_CACHE_SIZE:
                removed_domain, _ = self._stores.popitem(last=False)
                logger.debug(f"캐시에서 제거됨: {removed_domain}")

            self._stores[domain] = store
            return store

    def build_vectordb(
        self,
        domain: str,
        force_rebuild: bool = False,
    ) -> int:
        """특정 도메인의 벡터 데이터베이스를 빌드합니다.

        전처리된 데이터를 로드하여 임베딩을 생성하고 ChromaDB에 저장합니다.

        Args:
            domain: 빌드할 도메인 키
            force_rebuild: True이면 기존 데이터를 삭제하고 재빌드

        Returns:
            추가된 문서 수
        """
        collection_name = self._get_collection_name(domain)
        client = self._get_client()

        # 기존 컬렉션 확인
        existing_collections = [c.name for c in client.list_collections()]

        if collection_name in existing_collections and not force_rebuild:
            store = self.get_or_create_store(domain)
            existing_count = store._collection.count()
            if existing_count > 0:
                logger.info(f"컬렉션 {collection_name}이(가) 이미 존재합니다 ({existing_count}개 문서).")
                logger.info("재빌드하려면 force_rebuild=True를 사용하세요.")
                return existing_count

        # 강제 재빌드 시 기존 컬렉션 삭제
        if force_rebuild and collection_name in existing_collections:
            client.delete_collection(collection_name)
            if domain in self._stores:
                del self._stores[domain]
            logger.info(f"기존 컬렉션 {collection_name} 삭제됨")

        store = self.get_or_create_store(domain)

        # 문서 로드
        documents: list[Document] = []
        for doc in self.loader.load_db_documents(domain):
            documents.append(doc)

        if not documents:
            logger.warning(f"{domain}에 대한 문서를 찾을 수 없습니다")
            return 0

        logger.info(f"{len(documents)}개 문서를 {collection_name}에 추가 중...")

        # 배치로 문서 추가
        batch_size = self.config.batch_size
        total_added = 0

        for i in tqdm(range(0, len(documents), batch_size), desc=f"{domain} 빌드"):
            batch = documents[i:i + batch_size]

            texts = [doc.page_content for doc in batch]
            metadatas = [doc.metadata for doc in batch]
            ids = [doc.metadata.get("id", f"doc_{i + j}") for j, doc in enumerate(batch)]

            store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids,
            )
            total_added += len(batch)

        logger.info(f"{total_added}개 문서가 {collection_name}에 성공적으로 추가됨")
        return total_added

    def build_all_vectordbs(self, force_rebuild: bool = False) -> dict[str, int]:
        """모든 도메인의 벡터 데이터베이스를 빌드합니다.

        Args:
            force_rebuild: True이면 기존 데이터를 삭제하고 재빌드

        Returns:
            도메인별 추가된 문서 수 딕셔너리
        """
        results = {}
        for domain in COLLECTION_NAMES.keys():
            logger.info(f"{'='*50}")
            logger.info(f"{domain} 빌드 중...")
            logger.info(f"{'='*50}")
            count = self.build_vectordb(domain, force_rebuild=force_rebuild)
            results[domain] = count

        return results

    def similarity_search(
        self,
        query: str,
        domain: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """유사도 검색을 수행합니다.

        Args:
            query: 검색 쿼리 텍스트
            domain: 검색할 도메인 키
            k: 반환할 결과 수
            filter: 메타데이터 필터 (선택)

        Returns:
            유사한 문서 리스트
        """
        store = self.get_or_create_store(domain)
        collection_name = self._get_collection_name(domain)
        logger.info("[벡터검색] similarity_search: 컬렉션=%s, k=%d", collection_name, k)
        results = store.similarity_search(query, k=k, filter=filter)
        logger.info("[벡터검색] similarity_search 결과: %d건", len(results))
        titles = [r.metadata.get("title", "제목없음") for r in results]
        logger.info("[벡터검색] 검색 문서: %s", titles)
        return results

    def similarity_search_with_score(
        self,
        query: str,
        domain: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """유사도 점수와 함께 검색을 수행합니다.

        Args:
            query: 검색 쿼리 텍스트
            domain: 검색할 도메인 키
            k: 반환할 결과 수
            filter: 메타데이터 필터 (선택)

        Returns:
            (문서, 유사도 점수) 튜플 리스트
        """
        store = self.get_or_create_store(domain)
        collection_name = self._get_collection_name(domain)
        logger.info("[벡터검색] similarity_search_with_score: 컬렉션=%s, k=%d", collection_name, k)
        results = store.similarity_search_with_score(query, k=k, filter=filter)
        logger.info("[벡터검색] similarity_search_with_score 결과: %d건", len(results))
        titles = [doc.metadata.get("title", "제목없음") for doc, _ in results]
        logger.info("[벡터검색] 검색 문서: %s", titles)
        return results

    def max_marginal_relevance_search(
        self,
        query: str,
        domain: str,
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """MMR(Maximal Marginal Relevance) 검색을 수행합니다.

        유사도와 다양성을 균형있게 고려하여 검색 결과를 반환합니다.
        중복되거나 비슷한 내용의 문서를 줄이고 다양한 정보를 제공합니다.

        Args:
            query: 검색 쿼리 텍스트
            domain: 검색할 도메인 키
            k: 반환할 결과 수
            fetch_k: MMR 알고리즘에 전달할 초기 후보 수
            lambda_mult: 다양성 파라미터 (0=최대 다양성, 1=최대 유사도)
            filter: 메타데이터 필터 (선택)

        Returns:
            다양성이 고려된 문서 리스트
        """
        store = self.get_or_create_store(domain)
        collection_name = self._get_collection_name(domain)
        logger.info("[벡터검색] MMR: 컬렉션=%s, k=%d, fetch_k=%d", collection_name, k, fetch_k)
        results = store.max_marginal_relevance_search(
            query=query,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
        )
        logger.info("[벡터검색] MMR 결과: %d건", len(results))
        titles = [r.metadata.get("title", "제목없음") for r in results]
        logger.info("[벡터검색] 검색 문서: %s", titles)
        return results

    def get_retriever(
        self,
        domain: str,
        search_kwargs: dict[str, Any] | None = None,
    ):
        """벡터 스토어의 Retriever를 반환합니다.

        LangChain 체인에서 사용할 수 있는 Retriever 객체를 생성합니다.

        Args:
            domain: 도메인 키
            search_kwargs: 검색 파라미터 (k, filter 등)

        Returns:
            VectorStoreRetriever 인스턴스
        """
        store = self.get_or_create_store(domain)
        search_kwargs = search_kwargs or {"k": 5}
        return store.as_retriever(search_kwargs=search_kwargs)

    def get_collection_stats(self, domain: str) -> dict[str, Any]:
        """컬렉션 통계를 반환합니다.

        Args:
            domain: 도메인 키

        Returns:
            컬렉션 통계 딕셔너리 (이름, 문서 수, 메타데이터)
        """
        store = self.get_or_create_store(domain)
        collection = store._collection

        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata,
        }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """모든 컬렉션의 통계를 반환합니다.

        Returns:
            도메인별 통계 딕셔너리
        """
        stats = {}
        for domain in COLLECTION_NAMES.keys():
            try:
                stats[domain] = self.get_collection_stats(domain)
            except Exception as e:
                stats[domain] = {"error": str(e)}
        return stats

    def delete_collection(self, domain: str) -> bool:
        """컬렉션을 삭제합니다.

        Args:
            domain: 삭제할 도메인 키

        Returns:
            삭제 성공 여부
        """
        collection_name = self._get_collection_name(domain)
        client = self._get_client()

        try:
            client.delete_collection(collection_name)
            if domain in self._stores:
                del self._stores[domain]
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """모든 컬렉션 이름을 반환합니다.

        Returns:
            컬렉션 이름 리스트
        """
        client = self._get_client()
        return [c.name for c in client.list_collections()]

    def clear_cache(self) -> int:
        """스토어 캐시를 모두 정리합니다.

        Returns:
            정리된 캐시 항목 수
        """
        with self._store_lock:
            count = len(self._stores)
            self._stores.clear()
            logger.info(f"스토어 캐시 정리 완료: {count}개 항목")
            return count

    def get_cache_info(self) -> dict[str, Any]:
        """캐시 상태 정보를 반환합니다.

        Returns:
            캐시 상태 딕셔너리
        """
        with self._store_lock:
            return {
                "cached_domains": list(self._stores.keys()),
                "cache_size": len(self._stores),
                "max_cache_size": MAX_STORE_CACHE_SIZE,
            }

    def close(self) -> None:
        """리소스를 정리합니다."""
        self.clear_cache()
        self._client = None
        logger.info("ChromaVectorStore 리소스 정리 완료")
