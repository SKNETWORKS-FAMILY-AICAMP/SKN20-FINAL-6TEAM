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

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from .config import COLLECTION_NAMES, VectorDBConfig
from .embeddings import get_embeddings
# 캐시 최대 크기 (도메인 개수보다 크게 설정)
MAX_STORE_CACHE_SIZE = 10


class ChromaVectorStore:
    """ChromaDB 기반 벡터 스토어 클래스.

    하나의 persist_directory에 여러 컬렉션(테이블)을 저장하고 관리합니다.
    각 도메인(창업/세무/노무/법령)별로 별도의 컬렉션을 사용합니다.

    Attributes:
        config: VectorDB 설정 객체
        embeddings: 임베딩 인스턴스
        _client: ChromaDB 클라이언트 (싱글톤)
        _stores: 컬렉션별 Chroma 인스턴스 캐시

    Example:
        >>> store = ChromaVectorStore()
        >>> results = store.similarity_search("창업 지원금", "startup_funding", k=5)
    """

    def __init__(self, config: VectorDBConfig | None = None):
        """ChromaVectorStore를 초기화합니다.

        Args:
            config: VectorDB 설정 객체. None이면 기본 설정 사용.
        """
        self.config = config or VectorDBConfig()
        self.embeddings = get_embeddings(self.config.embedding_model)
        self._client: chromadb.ClientAPI | None = None
        # LRU 캐시 방식의 OrderedDict 사용
        self._stores: OrderedDict[str, Chroma] = OrderedDict()
        self._store_lock = threading.RLock()

        # 저장 디렉토리 생성 (로컬 모드용)
        if not self._is_remote_mode():
            self.config.persist_directory.mkdir(parents=True, exist_ok=True)

    def _is_remote_mode(self) -> bool:
        """원격 ChromaDB 서버 모드 여부를 판단합니다.

        다음 조건 중 하나라도 만족하면 HttpClient(원격 모드)를 사용합니다:
        - CHROMA_HOST가 localhost/127.0.0.1이 아닌 경우 (예: Docker 네트워크의 'chromadb')
        - CHROMA_PORT가 기본값(8000)이 아닌 경우 (예: Docker 포트 매핑 8200)

        Returns:
            원격 모드이면 True
        """
        from utils.config import get_settings

        settings = get_settings()
        chroma_host = settings.chroma_host or ""
        chroma_port = settings.chroma_port

        # 호스트가 외부 서버인 경우
        if bool(chroma_host) and chroma_host not in ("localhost", "127.0.0.1"):
            return True

        # 로컬호스트지만 포트가 기본값(8000)이 아닌 경우 (Docker 포트 매핑)
        if bool(chroma_host) and chroma_port != 8000:
            return True

        return False

    def _get_client(self) -> chromadb.ClientAPI:
        """ChromaDB 클라이언트를 가져옵니다 (싱글톤, 스레드 안전).

        이미 연결된 클라이언트가 있으면 즉시 반환합니다 (빠른 경로).
        연결이 없으면 _connect_client()를 호출하여 재시도 포함 연결을 수행합니다.

        Returns:
            ChromaDB ClientAPI 인스턴스
        """
        if self._client is not None:
            return self._client
        return self._connect_client()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _connect_client(self) -> chromadb.ClientAPI:
        """ChromaDB 클라이언트 연결을 수행합니다 (재시도 포함).

        CHROMA_HOST 환경변수에 따라 클라이언트 유형을 자동 선택합니다:
        - 미설정 또는 localhost: PersistentClient (로컬 파일 기반)
        - 그 외: HttpClient (원격 ChromaDB 서버)

        Returns:
            ChromaDB ClientAPI 인스턴스
        """
        with self._store_lock:
            if self._client is not None:
                return self._client
            if self._is_remote_mode():
                from utils.config import get_settings as _get_settings

                _s = _get_settings()
                chroma_host = _s.chroma_host or ""
                chroma_port = _s.chroma_port
                logger.info(
                    "ChromaDB HttpClient 연결: %s:%d", chroma_host, chroma_port
                )
                chroma_settings_kwargs: dict[str, Any] = {
                    "anonymized_telemetry": False,
                }
                chroma_auth_token = getattr(_s, "chroma_auth_token", "")
                if chroma_auth_token:
                    chroma_settings_kwargs.update({
                        "chroma_client_auth_provider": "chromadb.auth.token_authn.TokenAuthClientProvider",
                        "chroma_client_auth_credentials": chroma_auth_token,
                    })
                    logger.info("ChromaDB 토큰 인증 활성화")

                self._client = chromadb.HttpClient(
                    host=chroma_host,
                    port=chroma_port,
                    settings=Settings(**chroma_settings_kwargs),
                )
            else:
                logger.info(
                    "ChromaDB PersistentClient 사용: %s",
                    self.config.persist_directory,
                )
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
                logger.debug("캐시에서 제거됨: %s", removed_domain)

            self._stores[domain] = store
            return store

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def similarity_search(
        self,
        query: str,
        domain: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """유사도 검색을 수행합니다.

        연결 실패 시 최대 3회 재시도합니다 (지수 백오프).

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
        for idx, (doc, score) in enumerate(results):
            title = doc.metadata.get("title", "제목없음")[:40]
            logger.info("  [%d] %s (distance: %.4f)", idx + 1, title, score)
        return results

    def similarity_search_with_score_and_embed(
        self,
        query: str,
        domain: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """유사도 점수를 메타데이터에 포함하여 검색합니다.

        일반 similarity_search 대신 사용하면 각 문서의 metadata["score"]에
        유사도 점수가 저장됩니다 (낮을수록 유사).

        Args:
            query: 검색 쿼리 텍스트
            domain: 검색할 도메인 키
            k: 반환할 결과 수
            filter: 메타데이터 필터 (선택)

        Returns:
            유사도 점수가 메타데이터에 포함된 문서 리스트
        """
        results_with_score = self.similarity_search_with_score(query, domain, k, filter)
        documents = []
        for doc, score in results_with_score:
            doc.metadata["score"] = round(score, 4)
            documents.append(doc)
        return documents

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
        collection_name = self._get_collection_name(domain)
        client = self._get_client()
        collection = client.get_collection(collection_name)

        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata,
        }

    def get_domain_documents(self, domain: str) -> list[Document]:
        """도메인 컬렉션의 전체 문서를 반환합니다.

        BM25 인덱스 초기화 등 오프라인/초기화용 전체 문서 로딩에 사용됩니다.
        대규모 컬렉션(law_common 등)은 배치 단위로 로드합니다.

        Args:
            domain: 도메인 키

        Returns:
            Document 리스트
        """
        collection_name = self._get_collection_name(domain)
        client = self._get_client()

        try:
            collection = client.get_collection(collection_name)
            total_count = collection.count()
        except Exception as e:
            logger.warning("[벡터스토어] 전체 문서 로드 실패 (%s): %s", domain, e)
            return []

        batch_size = 5000
        raw_documents: list[str] = []
        raw_metadatas: list[dict] = []
        raw_ids: list[str] = []

        if total_count <= batch_size:
            try:
                payload = collection.get(include=["documents", "metadatas"])
            except Exception as e:
                logger.warning("[벡터스토어] 전체 문서 로드 실패 (%s): %s", domain, e)
                return []
            raw_documents = payload.get("documents", []) if isinstance(payload, dict) else []
            raw_metadatas = payload.get("metadatas", []) if isinstance(payload, dict) else []
            raw_ids = payload.get("ids", []) if isinstance(payload, dict) else []
        else:
            logger.info("[벡터스토어] 배치 로드 시작: %s (%d건, batch=%d)", domain, total_count, batch_size)
            for offset in range(0, total_count, batch_size):
                try:
                    payload = collection.get(
                        include=["documents", "metadatas"],
                        limit=batch_size,
                        offset=offset,
                    )
                except Exception as e:
                    logger.warning("[벡터스토어] 배치 로드 실패 (%s, offset=%d): %s", domain, offset, e)
                    continue
                batch_docs = payload.get("documents", []) if isinstance(payload, dict) else []
                batch_metas = payload.get("metadatas", []) if isinstance(payload, dict) else []
                batch_ids = payload.get("ids", []) if isinstance(payload, dict) else []
                raw_documents.extend(batch_docs)
                raw_metadatas.extend(batch_metas)
                raw_ids.extend(batch_ids)
            logger.info("[벡터스토어] 배치 로드 완료: %s (%d건)", domain, len(raw_documents))

        if not isinstance(raw_documents, list):
            logger.warning("[벡터스토어] 전체 문서 포맷 오류 (%s): documents 타입 불일치", domain)
            return []

        documents: list[Document] = []
        for idx, content in enumerate(raw_documents):
            if not isinstance(content, str) or not content.strip():
                continue

            metadata: dict[str, Any] = {}
            if idx < len(raw_metadatas) and isinstance(raw_metadatas[idx], dict):
                metadata = dict(raw_metadatas[idx])

            if idx < len(raw_ids) and raw_ids[idx] is not None and "id" not in metadata:
                metadata["id"] = str(raw_ids[idx])

            documents.append(Document(page_content=content, metadata=metadata))

        logger.info("[벡터스토어] 전체 문서 로드 완료: %s (%d건)", domain, len(documents))
        return documents

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
        collections = client.list_collections()
        if collections and hasattr(collections[0], "name"):
            return [c.name for c in collections]
        return [str(c) for c in collections]

    def clear_cache(self) -> int:
        """스토어 캐시를 모두 정리합니다.

        Returns:
            정리된 캐시 항목 수
        """
        with self._store_lock:
            count = len(self._stores)
            self._stores.clear()
            logger.info("스토어 캐시 정리 완료: %d개 항목", count)
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

    def health_check(self) -> dict[str, Any]:
        """ChromaDB 연결 상태를 확인합니다.

        Returns:
            연결 상태 딕셔너리 (status, heartbeat 또는 detail)
        """
        try:
            client = self._get_client()
            heartbeat = client.heartbeat()
            return {"status": "ok", "heartbeat": heartbeat}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def close(self) -> None:
        """리소스를 정리합니다."""
        self.clear_cache()
        self._client = None
        logger.info("ChromaVectorStore 리소스 정리 완료")
