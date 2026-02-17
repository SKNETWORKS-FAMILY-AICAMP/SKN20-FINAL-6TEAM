"""VectorDB 빌드 전용 모듈.

ChromaDB에 직접 연결하여 벡터 데이터를 빌드합니다.
RAG 런타임(ChromaVectorStore)과 독립적으로 동작합니다.
"""

import gc
import logging
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential

from vectorstores.config import COLLECTION_NAMES, VectorDBConfig
from vectorstores.embeddings import get_embeddings
from .loader import DataLoader

logger = logging.getLogger(__name__)


class VectorDBBuilder:
    """VectorDB 빌드 전용 클래스.

    ChromaDB에 직접 연결하여 벡터 데이터를 빌드합니다.
    RAG 런타임(ChromaVectorStore)과 독립적으로 동작합니다.

    Attributes:
        config: VectorDB 설정 객체
        embeddings: 임베딩 인스턴스
        loader: 데이터 로더 인스턴스
    """

    def __init__(self, config: VectorDBConfig | None = None):
        """VectorDBBuilder를 초기화합니다.

        Args:
            config: VectorDB 설정 객체. None이면 기본 설정 사용.
        """
        self.config = config or VectorDBConfig()
        self.embeddings = get_embeddings(self.config.embedding_model)
        self.loader = DataLoader()
        self._client: chromadb.ClientAPI | None = None

    def _is_remote_mode(self) -> bool:
        """원격 ChromaDB 서버 모드 여부를 판단합니다.

        Returns:
            원격 모드이면 True
        """
        from utils.config import get_settings

        settings = get_settings()
        chroma_host = settings.chroma_host or ""
        chroma_port = settings.chroma_port

        if bool(chroma_host) and chroma_host not in ("localhost", "127.0.0.1"):
            return True
        if bool(chroma_host) and chroma_port != 8000:
            return True

        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _get_client(self) -> chromadb.ClientAPI:
        """ChromaDB 클라이언트를 가져옵니다 (싱글톤).

        Returns:
            ChromaDB ClientAPI 인스턴스
        """
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
            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            self.config.persist_directory.mkdir(parents=True, exist_ok=True)
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

    def _get_store(self, domain: str) -> Chroma:
        """도메인에 해당하는 Chroma 벡터 스토어를 생성합니다.

        Args:
            domain: 도메인 키

        Returns:
            Chroma 벡터 스토어 인스턴스
        """
        collection_name = COLLECTION_NAMES.get(domain, domain)
        client = self._get_client()

        return Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
            collection_metadata=self.config.collection_metadata,
        )

    def build_vectordb(
        self,
        domain: str,
        force_rebuild: bool = False,
        resume: bool = False,
    ) -> int:
        """특정 도메인의 벡터 데이터베이스를 빌드합니다.

        Args:
            domain: 빌드할 도메인 키
            force_rebuild: True이면 기존 데이터를 삭제하고 재빌드
            resume: True이면 기존 데이터를 유지하고 누락된 문서만 추가

        Returns:
            추가된 문서 수
        """
        collection_name = COLLECTION_NAMES.get(domain, domain)
        client = self._get_client()

        # 기존 컬렉션 확인
        existing_collections = self.list_collections()
        existing_ids: set[str] = set()

        if collection_name in existing_collections:
            collection = client.get_collection(collection_name)
            existing_count = collection.count()

            if resume and existing_count > 0:
                logger.info(
                    "Resume 모드: %s에 %d개 문서 존재, 누락분만 추가합니다.",
                    collection_name, existing_count,
                )
                result = collection.get(include=[])
                existing_ids = set(result.get("ids", []))
                logger.info("기존 ID %d개 로드 완료", len(existing_ids))
            elif not force_rebuild and existing_count > 0:
                logger.info(
                    "컬렉션 %s이(가) 이미 존재합니다 (%d개 문서).",
                    collection_name, existing_count,
                )
                logger.info("재빌드하려면 force_rebuild=True, 이어서 빌드하려면 resume=True를 사용하세요.")
                return existing_count

        # 강제 재빌드 시 기존 컬렉션 삭제
        if force_rebuild and collection_name in existing_collections:
            client.delete_collection(collection_name)
            existing_ids.clear()
            logger.info("기존 컬렉션 %s 삭제됨", collection_name)

        store = self._get_store(domain)

        # 스트리밍 배치 처리 (메모리 효율)
        batch_size = self.config.batch_size
        total_added = 0
        skipped = 0
        file_counts: dict[str, int] = {}
        seen_ids: set[str] = set()
        duplicates = 0
        batch: list[Document] = []

        for doc in self.loader.load_db_documents(domain):
            sf = doc.metadata.get("source_file", "unknown")
            file_counts[sf] = file_counts.get(sf, 0) + 1

            doc_id = doc.metadata.get("id", "")
            if doc_id in seen_ids:
                duplicates += 1
            seen_ids.add(doc_id)

            # Resume 모드: 이미 저장된 문서는 건너뛰기
            if doc_id in existing_ids:
                skipped += 1
                continue

            batch.append(doc)

            if len(batch) >= batch_size:
                self._add_batch(store, batch, total_added)
                total_added += len(batch)
                batch = []
                # 진행 상황 로깅 + 메모리 정리 (1000건마다)
                if total_added % 1000 == 0:
                    logger.info("  %d건 추가 완료 (건너뜀: %d)", total_added, skipped)
                    self._cleanup_memory()

        # 남은 배치 처리
        if batch:
            self._add_batch(store, batch, total_added)
            total_added += len(batch)

        if total_added == 0 and skipped == 0:
            logger.warning("%s에 대한 문서를 찾을 수 없습니다", domain)
            return 0

        # 최종 메모리 정리
        self._cleanup_memory()

        # 통계 출력
        for sf, cnt in file_counts.items():
            logger.info("  %-40s → %d건", sf, cnt)
        if duplicates:
            logger.warning("중복 ID %d건 감지 (domain: %s)", duplicates, domain)
        if skipped:
            logger.info("Resume 모드: %d건 건너뜀 (이미 존재)", skipped)

        logger.info("%d개 문서가 %s에 성공적으로 추가됨", total_added, collection_name)
        final_count = (len(existing_ids) + total_added) if existing_ids else total_added
        logger.info("최종: %d건", final_count)
        return final_count

    def _add_batch(self, store: Chroma, batch: list[Document], offset: int) -> None:
        """배치 단위로 문서를 벡터 스토어에 추가합니다.

        Args:
            store: Chroma 벡터 스토어 인스턴스
            batch: 추가할 문서 배치
            offset: 현재까지 추가된 문서 수 (ID 생성용)
        """
        texts = [doc.page_content for doc in batch]
        metadatas = [
            {k: ("" if v is None else v) for k, v in doc.metadata.items()}
            for doc in batch
        ]
        ids = [
            doc.metadata.get("id", f"doc_{offset + j}")
            for j, doc in enumerate(batch)
        ]
        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    @staticmethod
    def _cleanup_memory() -> None:
        """GPU VRAM 및 시스템 메모리를 정리합니다."""
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def build_all_vectordbs(
        self,
        force_rebuild: bool = False,
        resume: bool = False,
    ) -> dict[str, int]:
        """모든 도메인의 벡터 데이터베이스를 빌드합니다.

        Args:
            force_rebuild: True이면 기존 데이터를 삭제하고 재빌드
            resume: True이면 기존 데이터를 유지하고 누락된 문서만 추가

        Returns:
            도메인별 추가된 문서 수 딕셔너리
        """
        results = {}
        for domain in COLLECTION_NAMES.keys():
            logger.info("=" * 50)
            logger.info("%s 빌드 중...", domain)
            logger.info("=" * 50)
            count = self.build_vectordb(
                domain, force_rebuild=force_rebuild, resume=resume,
            )
            results[domain] = count

        return results

    def update_announcements(self, domain: str = "startup_funding") -> dict[str, int]:
        """공고 문서만 선택적으로 갱신합니다.

        기존 ANNOUNCE_* 접두사 ID를 가진 문서를 삭제하고,
        새로운 announcements.jsonl 데이터를 추가합니다.
        가이드/절차 등 다른 문서는 보존됩니다.

        Args:
            domain: 대상 도메인 키 (기본: startup_funding)

        Returns:
            {"deleted": 삭제 수, "added": 추가 수} 딕셔너리
        """
        collection_name = COLLECTION_NAMES.get(domain, domain)
        client = self._get_client()

        # 1. 기존 ANNOUNCE_* ID 조회 + 삭제
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            logger.warning("컬렉션 %s이(가) 존재하지 않습니다. 전체 빌드를 먼저 실행하세요.", collection_name)
            return {"deleted": 0, "added": 0}

        all_ids = collection.get(include=[])["ids"]
        announce_ids = [doc_id for doc_id in all_ids if doc_id.startswith("ANNOUNCE_")]
        deleted_count = len(announce_ids)

        if announce_ids:
            # ChromaDB delete는 최대 ~5000건씩 처리
            for i in range(0, len(announce_ids), 5000):
                batch_ids = announce_ids[i:i + 5000]
                collection.delete(ids=batch_ids)
            logger.info("기존 공고 문서 %d건 삭제 완료", deleted_count)
        else:
            logger.info("삭제할 기존 공고 문서 없음")

        # 2. 새 announcements.jsonl 로드 (source_file 필터)
        store = self._get_store(domain)
        batch: list[Document] = []
        total_added = 0
        batch_size = self.config.batch_size

        for doc in self.loader.load_db_documents(domain):
            if doc.metadata.get("source_file") != "announcements.jsonl":
                continue
            batch.append(doc)

            if len(batch) >= batch_size:
                self._add_batch(store, batch, total_added)
                total_added += len(batch)
                batch = []
                if total_added % 1000 == 0:
                    logger.info("  공고 문서 %d건 추가 완료", total_added)
                    self._cleanup_memory()

        # 남은 배치 처리
        if batch:
            self._add_batch(store, batch, total_added)
            total_added += len(batch)

        self._cleanup_memory()

        logger.info(
            "공고 갱신 완료: 삭제 %d건, 추가 %d건 (컬렉션: %s)",
            deleted_count, total_added, collection_name,
        )
        return {"deleted": deleted_count, "added": total_added}

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """모든 컬렉션의 통계를 반환합니다.

        Returns:
            도메인별 통계 딕셔너리
        """
        stats = {}
        client = self._get_client()
        for domain, collection_name in COLLECTION_NAMES.items():
            try:
                collection = client.get_collection(collection_name)
                stats[domain] = {
                    "name": collection.name,
                    "count": collection.count(),
                    "metadata": collection.metadata,
                }
            except Exception as e:
                stats[domain] = {"error": str(e)}
        return stats

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
