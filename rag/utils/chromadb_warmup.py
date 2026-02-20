"""ChromaDB 컬렉션 및 BM25 인덱스 사전 로딩 모듈.

서비스 시작 시 ChromaDB 컬렉션 인스턴스와 BM25 인덱스를 미리 빌드하여
첫 번째 사용자 요청의 지연(cold start)을 방지합니다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from vectorstores.config import COLLECTION_NAMES

if TYPE_CHECKING:
    from utils.search import HybridSearcher
    from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

# vectorstores/config.py의 COLLECTION_NAMES 키와 동기화 (단일 소스)
_WARMUP_DOMAINS = list(COLLECTION_NAMES.keys())


async def warmup_chromadb(vector_store: ChromaVectorStore) -> bool:
    """ChromaDB 컬렉션 및 BM25 인덱스를 사전 로딩합니다.

    Phase 1: 4개 컬렉션 인스턴스 사전 생성 (get_or_create_store + count 확인)
    Phase 2: BM25 인덱스 병렬 사전 빌드 (enable_hybrid_search 활성화 시에만)

    Args:
        vector_store: ChromaVectorStore 인스턴스

    Returns:
        모든 단계 성공 시 True, 실패 시 False (서비스 중단 없음)
    """
    from utils.config import get_settings

    settings = get_settings()
    total_start = time.monotonic()

    logger.info("[ChromaDB Warmup] 시작 (도메인: %s)", ", ".join(_WARMUP_DOMAINS))

    # ── Phase 1: 컬렉션 인스턴스 사전 생성 ─────────────────────────────────
    phase1_start = time.monotonic()
    phase1_ok = await _warmup_collections(vector_store)
    phase1_elapsed = time.monotonic() - phase1_start
    logger.info("[ChromaDB Warmup] Phase 1 완료 (컬렉션 생성) — %.2fs", phase1_elapsed)

    # ── Phase 2: BM25 인덱스 사전 빌드 ────────────────────────────────────
    if settings.enable_hybrid_search:
        phase2_start = time.monotonic()
        phase2_ok = await _warmup_bm25_indexes(vector_store)
        phase2_elapsed = time.monotonic() - phase2_start
        logger.info("[ChromaDB Warmup] Phase 2 완료 (BM25 빌드) — %.2fs", phase2_elapsed)
    else:
        logger.info("[ChromaDB Warmup] Phase 2 스킵 (Hybrid Search 비활성화)")
        phase2_ok = True

    total_elapsed = time.monotonic() - total_start
    success = phase1_ok and phase2_ok
    if success:
        logger.info("[ChromaDB Warmup] 전체 완료 — 총 %.2fs", total_elapsed)
    else:
        logger.warning("[ChromaDB Warmup] 일부 실패 — 총 %.2fs (서비스는 정상 시작)", total_elapsed)

    return success


async def _warmup_collections(vector_store: ChromaVectorStore) -> bool:
    """Phase 1: 4개 컬렉션 인스턴스를 사전 생성하고 문서 수를 확인합니다."""
    all_ok = True

    for domain in _WARMUP_DOMAINS:
        try:
            store = await asyncio.to_thread(vector_store.get_or_create_store, domain)
            # LangChain Chroma에 count() 공식 API가 없어 내부 속성으로 직접 접근.
            # LangChain 업데이트 시 깨질 수 있으나, 현재 버전에서 유일한 대안.
            doc_count = await asyncio.to_thread(lambda s=store: s._collection.count())
            logger.info("[ChromaDB Warmup] 컬렉션 준비 완료: %s (%d건)", domain, doc_count)
        except Exception as e:
            logger.warning("[ChromaDB Warmup] 컬렉션 준비 실패: %s — %s", domain, e)
            all_ok = False

    return all_ok


async def _warmup_bm25_indexes(vector_store: ChromaVectorStore) -> bool:
    """Phase 2: 4개 도메인의 BM25 인덱스를 병렬로 사전 빌드합니다."""
    from utils.search import get_hybrid_searcher

    searcher = get_hybrid_searcher(vector_store)

    tasks = [
        asyncio.to_thread(_build_bm25_for_domain, searcher, vector_store, domain)
        for domain in _WARMUP_DOMAINS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_ok = True
    for domain, result in zip(_WARMUP_DOMAINS, results):
        if isinstance(result, Exception):
            logger.warning("[ChromaDB Warmup] BM25 빌드 실패: %s — %s", domain, result)
            all_ok = False

    return all_ok


def _build_bm25_for_domain(searcher: HybridSearcher, vector_store: ChromaVectorStore, domain: str) -> None:
    """단일 도메인의 BM25 인덱스를 빌드합니다 (동기, to_thread에서 실행).

    이미 빌드된 경우 스킵합니다.
    """
    if domain in searcher.bm25_indices:
        logger.debug("[ChromaDB Warmup] BM25 이미 빌드됨, 스킵: %s", domain)
        return

    domain_start = time.monotonic()

    try:
        documents: list[Document] = vector_store.get_domain_documents(domain)
    except Exception as e:
        raise RuntimeError(f"문서 로드 실패 ({domain}): {e}") from e

    valid_documents = [
        doc for doc in documents
        if isinstance(doc, Document)
        and isinstance(doc.page_content, str)
        and doc.page_content.strip()
    ]

    if not valid_documents:
        logger.warning("[ChromaDB Warmup] 유효 문서 없음, BM25 스킵: %s", domain)
        searcher._bm25_init_attempted.add(domain)
        return

    searcher.build_bm25_index(domain, valid_documents)
    # warmup에서 빌드했음을 표시 (HybridSearcher._ensure_bm25_index 재빌드 방지)
    searcher._bm25_init_attempted.add(domain)

    elapsed = time.monotonic() - domain_start
    logger.info(
        "[ChromaDB Warmup] BM25 빌드 완료: %s (%d건, %.2fs)",
        domain, len(valid_documents), elapsed,
    )
