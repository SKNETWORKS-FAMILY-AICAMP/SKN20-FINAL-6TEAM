"""문서 생성 엔드포인트."""

import logging
from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from routes import _state
from schemas import ContractRequest, DocumentResponse, GenerateDocumentRequest, ModifyDocumentRequest
from utils.token_tracker import RequestTokenTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


async def _exec_document(fn: Callable[[], DocumentResponse], log_label: str, error_detail: str = "문서 생성 중 오류가 발생했습니다.") -> DocumentResponse:
    """문서 생성/수정 공통 실행 핸들러."""
    if not _state.executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")
    try:
        async with RequestTokenTracker() as tracker:
            result = fn()
            token_usage = tracker.get_usage()
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            logger.info(
                "[문서생성] %s 토큰 사용: %d (비용: $%.6f)",
                log_label,
                token_usage["total_tokens"],
                token_usage["cost"],
            )
        return result
    except Exception as e:
        logger.error("%s 실패: %s", log_label, e, exc_info=True)
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/contract", response_model=DocumentResponse)
async def generate_contract(request: ContractRequest) -> DocumentResponse:
    """근로계약서 생성 엔드포인트."""
    return await _exec_document(
        lambda: _state.executor.generate_labor_contract(
            request, user_id=request.user_id, company_id=request.company_id,
        ),
        "근로계약서",
        "문서 생성 중 오류가 발생했습니다. 입력 정보를 확인해주세요.",
    )


@router.post("/business-plan", response_model=DocumentResponse)
async def generate_business_plan(
    format: str = Query(default="docx", description="출력 형식", pattern=r"^(pdf|docx)$"),
) -> DocumentResponse:
    """사업계획서 템플릿 생성 엔드포인트."""
    return await _exec_document(
        lambda: _state.executor.generate_business_plan_template(format=format),
        "사업계획서",
    )


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(request: GenerateDocumentRequest) -> DocumentResponse:
    """범용 문서 생성 엔드포인트.

    레지스트리에 정의된 모든 문서 유형을 처리합니다.
    hardcoded 유형은 기존 로직으로, llm 유형은 LLM 기반으로 생성합니다.
    """
    params = dict(request.params)
    if request.company_context:
        params["company_context"] = request.company_context.model_dump()

    return await _exec_document(
        lambda: _state.executor.generate_document(
            document_type=request.doc_type_id,
            params=params,
            format=request.format,
            user_id=request.user_id,
            company_id=request.company_id,
        ),
        request.doc_type_id,
    )


@router.post("/modify", response_model=DocumentResponse)
async def modify_document(request: ModifyDocumentRequest) -> DocumentResponse:
    """문서 수정 엔드포인트.

    업로드된 문서(DOCX/PDF)를 사용자 지시에 따라 수정합니다.
    """
    return await _exec_document(
        lambda: _state.executor.modify_document(
            file_content=request.file_content,
            file_name=request.file_name,
            instructions=request.instructions,
            format=request.format,
            user_id=request.user_id,
            document_id=request.document_id,
        ),
        "문서수정",
        "문서 수정 중 오류가 발생했습니다.",
    )


@router.get("/application-forms")
async def list_application_forms() -> list[dict[str, str]]:
    """S3에 저장된 신청 양식 목록을 반환합니다."""
    from utils.s3_client import get_s3_client

    try:
        s3 = get_s3_client()
        return s3.list_application_forms()
    except Exception as e:
        logger.error("신청 양식 목록 조회 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="양식 목록을 불러올 수 없습니다.")


@router.post("/application-forms/analyze")
async def analyze_application_form(form_key: str = Query(..., description="S3 양식 파일 키", max_length=500, pattern=r"^[a-zA-Z0-9/_\-\.]+$")) -> dict:
    """S3 양식 파일을 LLM으로 분석하여 필드 정보를 반환합니다."""
    import json

    from utils.config.llm import create_llm
    from utils.s3_client import get_s3_client

    try:
        import base64

        from utils import prompts
        from utils.file_parser import extract_text_from_base64

        s3 = get_s3_client()
        file_bytes = s3.get_application_form(form_key)

        file_name = form_key.split("/")[-1]
        b64_content = base64.b64encode(file_bytes).decode()
        form_text = extract_text_from_base64(b64_content, file_name)

        prompt = prompts.APPLICATION_FORM_ANALYSIS_PROMPT.format(form_text=form_text)
        llm = create_llm(label="양식분석", temperature=0.0, max_tokens=2048)
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = response.content.strip()

        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="양식 분석 결과를 파싱할 수 없습니다.")
    except Exception as e:
        logger.error("양식 분석 실패 (%s): %s", form_key, e, exc_info=True)
        raise HTTPException(status_code=500, detail="양식 분석 중 오류가 발생했습니다.")


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
