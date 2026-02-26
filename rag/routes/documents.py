"""문서 생성 엔드포인트."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from routes import _state
from schemas import ContractRequest, DocumentResponse, GenerateDocumentRequest, ModifyDocumentRequest
from utils.token_tracker import RequestTokenTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/contract", response_model=DocumentResponse)
async def generate_contract(request: ContractRequest) -> DocumentResponse:
    """근로계약서 생성 엔드포인트."""
    if not _state.executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        async with RequestTokenTracker() as tracker:
            result = _state.executor.generate_labor_contract(request)
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
    if not _state.executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        async with RequestTokenTracker() as tracker:
            result = _state.executor.generate_business_plan_template(format=format)
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


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(request: GenerateDocumentRequest) -> DocumentResponse:
    """범용 문서 생성 엔드포인트.

    레지스트리에 정의된 모든 문서 유형을 처리합니다.
    hardcoded 유형은 기존 로직으로, llm 유형은 LLM 기반으로 생성합니다.
    """
    if not _state.executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        params = dict(request.params)
        if request.company_context:
            params["company_context"] = request.company_context.model_dump()

        async with RequestTokenTracker() as tracker:
            result = _state.executor.generate_document(
                document_type=request.document_type,
                params=params,
                format=request.format,
            )
            token_usage = tracker.get_usage()
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            logger.info(
                "[문서생성] %s 토큰 사용: %d (비용: $%.6f)",
                request.document_type,
                token_usage["total_tokens"],
                token_usage["cost"],
            )
        return result
    except Exception as e:
        logger.error("문서 생성 실패 (%s): %s", request.document_type, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 생성 중 오류가 발생했습니다."
        )


@router.post("/modify", response_model=DocumentResponse)
async def modify_document(request: ModifyDocumentRequest) -> DocumentResponse:
    """문서 수정 엔드포인트.

    업로드된 문서(DOCX/PDF)를 사용자 지시에 따라 수정합니다.
    """
    if not _state.executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        async with RequestTokenTracker() as tracker:
            result = _state.executor.modify_document(
                file_content=request.file_content,
                file_name=request.file_name,
                instructions=request.instructions,
                format=request.format,
            )
            token_usage = tracker.get_usage()
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            logger.info(
                "[문서수정] 토큰 사용: %d (비용: $%.6f)",
                token_usage["total_tokens"],
                token_usage["cost"],
            )
        return result
    except Exception as e:
        logger.error("문서 수정 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 수정 중 오류가 발생했습니다."
        )


@router.get("/types")
async def list_document_types() -> list[dict]:
    """사용 가능한 문서 유형 목록을 반환합니다."""
    from agents.document_registry import DOCUMENT_TYPE_REGISTRY

    return [
        {
            "type_key": td.type_key,
            "label": td.label,
            "description": td.description,
            "fields": [asdict(f) for f in td.fields],
            "default_format": td.default_format,
        }
        for td in DOCUMENT_TYPE_REGISTRY.values()
    ]
