"""문서 생성 엔드포인트."""

import logging

from fastapi import APIRouter, HTTPException, Query

from routes._state import executor
from schemas import ContractRequest, DocumentResponse
from utils.token_tracker import RequestTokenTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/contract", response_model=DocumentResponse)
async def generate_contract(request: ContractRequest) -> DocumentResponse:
    """근로계약서 생성 엔드포인트."""
    if not executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        async with RequestTokenTracker() as tracker:
            result = executor.generate_labor_contract(request)
            token_usage = tracker.get_usage()
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            logger.info(
                "[문서생성] 근로계약서 토큰 사용: %d (비용: $%.6f)",
                token_usage["total_tokens"],
                token_usage["cost"],
            )
        return result
    except Exception as e:
        logger.error(f"근로계약서 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 생성 중 오류가 발생했습니다. 입력 정보를 확인해주세요."
        )


@router.post("/business-plan", response_model=DocumentResponse)
async def generate_business_plan(
    format: str = Query(default="docx", description="출력 형식"),
) -> DocumentResponse:
    """사업계획서 템플릿 생성 엔드포인트."""
    if not executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        async with RequestTokenTracker() as tracker:
            result = executor.generate_business_plan_template(format=format)
            token_usage = tracker.get_usage()
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            logger.info(
                "[문서생성] 사업계획서 토큰 사용: %d (비용: $%.6f)",
                token_usage["total_tokens"],
                token_usage["cost"],
            )
        return result
    except Exception as e:
        logger.error(f"사업계획서 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 생성 중 오류가 발생했습니다."
        )
