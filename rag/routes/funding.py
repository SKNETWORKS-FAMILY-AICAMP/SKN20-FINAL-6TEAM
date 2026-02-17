"""지원사업 검색 엔드포인트."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from routes import _state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/funding", tags=["Funding"])


@router.get("/search")
async def search_funding(
    query: str = Query(description="검색 키워드"),
    k: int = Query(default=10, description="검색 결과 개수"),
) -> dict[str, Any]:
    """VectorDB에서 지원사업 공고를 검색합니다."""
    if not _state.vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        results = _state.vector_store.similarity_search(
            query=query,
            domain="startup_funding",
            k=k,
        )

        return {
            "query": query,
            "count": len(results),
            "results": [
                {
                    "content": doc.page_content[:500],
                    "metadata": doc.metadata,
                }
                for doc in results
            ],
        }
    except Exception as e:
        logger.error(f"지원사업 검색 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
