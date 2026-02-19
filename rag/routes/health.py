"""헬스체크 엔드포인트."""

import logging
from typing import Any

from fastapi import APIRouter

from routes import _state
from schemas.response import HealthResponse
from utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """서비스 상태와 VectorDB 상태를 반환합니다."""
    vectordb_status: dict[str, Any] = {}
    openai_status: dict[str, Any] = {"status": "unknown"}
    overall_status = "healthy"

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

    settings = get_settings()
    if settings.openai_api_key and settings.openai_api_key.strip():
        openai_status = {"status": "configured", "model": settings.openai_model}
    else:
        openai_status = {"status": "error", "message": "API 키가 설정되지 않았습니다"}
        overall_status = "unhealthy"

    rag_config: dict[str, Any] = {
        "hybrid_search": settings.enable_hybrid_search,
        "reranking": settings.enable_reranking,
        "domain_rejection": settings.enable_domain_rejection,
        "llm_evaluation": settings.enable_llm_evaluation,
        "ragas_evaluation": settings.enable_ragas_evaluation,
        "legal_supplement": settings.enable_legal_supplement,
        "fixed_doc_limit": settings.enable_fixed_doc_limit,
        "cross_domain_rerank": settings.enable_cross_domain_rerank,
        "embedding_provider": settings.embedding_provider,
        "llm_model": settings.openai_model,
    }

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        vectordb_status=vectordb_status,
        openai_status=openai_status,
        rag_config=rag_config,
    )
