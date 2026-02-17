"""메트릭, 캐시, 설정, 도메인 설정 관리 엔드포인트."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from utils.cache import get_response_cache
from utils.config import get_settings, reload_domain_config
from utils.middleware import get_metrics_collector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Monitoring"])

metrics_collector = get_metrics_collector()


async def verify_admin_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """관리자 API 키를 검증합니다."""
    settings = get_settings()
    if settings.admin_api_key and settings.admin_api_key.strip():
        if x_admin_key != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="관리자 인증이 필요합니다")


# --- 도메인 설정 ---


@router.post("/api/domain-config/reload", tags=["DomainConfig"], dependencies=[Depends(verify_admin_key)])
async def reload_domain_config_endpoint() -> dict[str, Any]:
    """도메인 설정을 MySQL DB에서 다시 로드합니다."""
    try:
        config = reload_domain_config()
        return {
            "status": "reloaded",
            "keywords_count": sum(len(kws) for kws in config.keywords.values()),
            "compound_rules_count": len(config.compound_rules),
            "representative_queries_count": sum(
                len(qs) for qs in config.representative_queries.values()
            ),
        }
    except Exception as e:
        logger.error("도메인 설정 리로드 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="도메인 설정 리로드 중 오류가 발생했습니다."
        )


# --- 메트릭 ---


@router.get("/api/metrics", dependencies=[Depends(verify_admin_key)])
async def get_metrics(
    window: int = Query(default=3600, description="통계 윈도우 (초)"),
) -> dict[str, Any]:
    """메트릭 조회."""
    return metrics_collector.get_stats(window_seconds=window)


@router.get("/api/metrics/endpoints", dependencies=[Depends(verify_admin_key)])
async def get_endpoint_metrics() -> dict[str, Any]:
    """엔드포인트별 메트릭 조회."""
    return metrics_collector.get_endpoint_stats()


# --- 캐시 ---


@router.get("/api/cache/stats", dependencies=[Depends(verify_admin_key)])
async def get_cache_stats() -> dict[str, Any]:
    """캐시 통계 조회."""
    try:
        cache = get_response_cache()
        return cache.get_stats()
    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: {e}", exc_info=True)
        return {"error": "캐시 통계를 조회할 수 없습니다."}


@router.post("/api/cache/clear", dependencies=[Depends(verify_admin_key)])
async def clear_cache() -> dict[str, Any]:
    """캐시 전체 삭제."""
    try:
        cache = get_response_cache()
        count = cache.clear()
        return {"cleared": count, "message": f"{count}개 캐시 항목이 삭제되었습니다"}
    except Exception as e:
        logger.error(f"캐시 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="캐시 삭제 중 오류가 발생했습니다."
        )


# --- 설정 ---


@router.get("/api/config", dependencies=[Depends(verify_admin_key)])
async def get_config() -> dict[str, Any]:
    """현재 설정 조회 (민감 정보 제외)."""
    settings = get_settings()
    return {
        "openai_model": settings.openai_model,
        "openai_temperature": settings.openai_temperature,
        "retrieval_k": settings.retrieval_k,
        "retrieval_k_common": settings.retrieval_k_common,
        "mmr_lambda_mult": settings.mmr_lambda_mult,
        "query_expansion_mode": "multi_query_only",
        "multi_query_count": settings.multi_query_count,
        "evaluation_threshold": settings.evaluation_threshold,
        "max_retry_count": settings.max_retry_count,
        "enable_hybrid_search": settings.enable_hybrid_search,
        "vector_search_weight": settings.vector_search_weight,
        "enable_reranking": settings.enable_reranking,
        "enable_context_compression": settings.enable_context_compression,
        "enable_response_cache": settings.enable_response_cache,
        "cache_ttl": settings.cache_ttl,
        "enable_rate_limit": settings.enable_rate_limit,
        "llm_timeout": settings.llm_timeout,
        "enable_fallback": settings.enable_fallback,
        "enable_ragas_evaluation": settings.enable_ragas_evaluation,
        "enable_vector_domain_classification": settings.enable_vector_domain_classification,
        "enable_llm_domain_classification": settings.enable_llm_domain_classification,
    }
