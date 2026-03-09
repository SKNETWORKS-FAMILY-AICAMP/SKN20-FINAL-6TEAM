"""헬스체크 엔드포인트."""

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header

from routes import _state
from schemas.response import HealthResponse
from utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> HealthResponse:
    """서비스 상태를 반환합니다. 관리자 키 제공 시 상세 정보를 포함합니다."""
    settings = get_settings()

    # 관리자 키 검증 (미설정이면 상세 정보 비공개)
    is_admin = bool(
        settings.admin_api_key
        and settings.admin_api_key.strip()
        and x_admin_key
        and hmac.compare_digest(x_admin_key, settings.admin_api_key)
    )

    overall_status = "healthy"
    openai_status: dict[str, Any] = {"status": "unknown"}

    if settings.openai_api_key and settings.openai_api_key.strip():
        openai_status = {"status": "configured"}
    else:
        openai_status = {"status": "error"}
        overall_status = "unhealthy"

    # 상세 정보는 관리자에게만 공개
    vectordb_status: dict[str, Any] = {}
    rag_config: dict[str, Any] = {}

    if is_admin:
        if _state.vector_store:
            try:
                stats = _state.vector_store.get_all_stats()
                vectordb_status = {
                    domain: {"count": info.get("count", 0)}
                    for domain, info in stats.items()
                    if "error" not in info
                }
            except Exception as e:
                vectordb_status = {"error": str(e)}
                overall_status = "degraded"

        openai_status = (
            {"status": "configured", "model": settings.openai_model}
            if settings.openai_api_key and settings.openai_api_key.strip()
            else {"status": "error", "message": "API 키가 설정되지 않았습니다"}
        )

        rag_config = {
            "hybrid_search": settings.enable_hybrid_search,
            "reranking": settings.enable_reranking,
            "domain_rejection": settings.enable_domain_rejection,
            "llm_evaluation": settings.enable_llm_evaluation,
            "ragas_evaluation": settings.enable_ragas_evaluation,
            "fixed_doc_limit": settings.enable_fixed_doc_limit,
            "cross_domain_rerank": settings.enable_cross_domain_rerank,
            "embedding_provider": settings.embedding_provider,
            "llm_model": settings.openai_model,
        }

        if settings.enable_hybrid_search and _state.vector_store:
            try:
                from utils.search import get_hybrid_searcher
                from vectorstores.config import COLLECTION_NAMES
                searcher = get_hybrid_searcher(_state.vector_store)
                rag_config["bm25_ready"] = {
                    domain: domain in searcher.bm25_indices
                    for domain in COLLECTION_NAMES
                }
            except Exception as e:
                logger.warning("[Health] BM25 상태 조회 실패: %s", e)

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        vectordb_status=vectordb_status,
        openai_status=openai_status,
        rag_config=rag_config,
    )
