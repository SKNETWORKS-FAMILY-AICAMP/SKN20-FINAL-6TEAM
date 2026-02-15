"""VectorDB 관리 엔드포인트."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from routes._state import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vectordb", tags=["VectorDB"])


@router.get("/stats")
async def vectordb_stats() -> dict[str, Any]:
    """VectorDB 통계 조회."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        return vector_store.get_all_stats()
    except Exception as e:
        logger.error(f"VectorDB 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="통계 조회 중 오류가 발생했습니다."
        )


@router.get("/collections")
async def list_collections() -> dict[str, Any]:
    """VectorDB 컬렉션 목록 조회."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        collections = vector_store.list_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"컬렉션 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="컬렉션 목록 조회 중 오류가 발생했습니다."
        )
