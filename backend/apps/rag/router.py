import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from apps.common.deps import get_optional_user
from apps.common.models import User, Company, Code

from .schemas import (
    RagChatRequest,
    ContractGenerateRequest,
    GenerateDocumentProxyRequest,
    ModifyDocumentProxyRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

TYPE_CODE_MAP = {
    "U0000001": "sme_owner",
    "U0000002": "prospective",
    "U0000003": "sme_owner",
}

_RAG_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)


def _build_user_context(user: User, db: Session) -> dict:
    """인증된 사용자의 컨텍스트를 구성합니다."""
    context: dict = {
        "user_id": str(user.user_id),
        "user_type": TYPE_CODE_MAP.get(user.type_code, "prospective"),
        "age": user.age,
        "company": None,
        "companies": [],
    }

    # 모든 활성 기업 조회 (main_yn DESC, company_id ASC 정렬)
    stmt = select(Company).where(
        Company.user_id == user.user_id,
        Company.use_yn == True,
    ).order_by(Company.main_yn.desc(), Company.company_id.asc())
    all_companies = list(db.execute(stmt).scalars().all())
    if not all_companies:
        return context

    companies_list = []
    for comp in all_companies:
        industry_name = None
        if comp.biz_code:
            industry_name = db.execute(
                select(Code.name).where(Code.code == comp.biz_code, Code.use_yn == True)
            ).scalar_one_or_none()
        years = None
        if comp.open_date:
            years = (datetime.now() - comp.open_date).days // 365
        companies_list.append({
            "company_name": comp.com_name,
            "business_number": comp.biz_num,
            "industry_code": comp.biz_code,
            "industry_name": industry_name,
            "employee_count": None,
            "years_in_business": years,
            "region": comp.addr,
        })

    context["company"] = companies_list[0]  # 하위 호환
    context["companies"] = companies_list
    return context


def _build_rag_headers(request: Request | None = None) -> dict[str, str]:
    """RAG 서비스 요청 헤더를 구성합니다."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.RAG_API_KEY:
        headers["X-API-Key"] = settings.RAG_API_KEY
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            headers["X-Request-ID"] = request_id
    return headers


@router.post("/chat")
async def rag_chat(
    request: Request,
    body: RagChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """RAG 채팅 프록시 (비스트리밍)."""
    payload: dict = {"message": body.message}
    if body.history:
        payload["history"] = [msg.model_dump() for msg in body.history]
    if body.session_id:
        payload["session_id"] = body.session_id
    if user:
        payload["user_context"] = _build_user_context(user, db)

    url = f"{settings.RAG_SERVICE_URL}/api/chat"

    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(
                url, json=payload, headers=_build_rag_headers(request)
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail="RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("RAG service error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(status_code=502, detail="RAG 서비스 오류가 발생했습니다.")

    return resp.json()


def _sse_error(message: str) -> bytes:
    """SSE 에러 메시지를 JSON 직렬화하여 반환합니다."""
    return f'data: {json.dumps({"type": "error", "content": message}, ensure_ascii=False)}\n\n'.encode("utf-8")


async def _stream_rag(url: str, payload: dict, request: Request | None = None):
    """RAG SSE 스트림을 바이트 단위로 중계합니다."""
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            async with client.stream(
                "POST", url, json=payload, headers=_build_rag_headers(request)
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.error(
                        "RAG stream error: status=%d body=%s",
                        resp.status_code,
                        error_body[:500],
                    )
                    yield _sse_error("RAG 서비스 오류")
                    return
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except httpx.ConnectError:
            yield _sse_error("RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            yield _sse_error("RAG 서비스 응답 시간이 초과되었습니다.")


@router.post("/chat/stream")
async def rag_chat_stream(
    request: Request,
    body: RagChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """RAG 채팅 프록시 (SSE 스트리밍)."""
    payload: dict = {"message": body.message}
    if body.history:
        payload["history"] = [msg.model_dump() for msg in body.history]
    if body.session_id:
        payload["session_id"] = body.session_id
    if user:
        payload["user_context"] = _build_user_context(user, db)

    url = f"{settings.RAG_SERVICE_URL}/api/chat/stream"

    return StreamingResponse(
        _stream_rag(url, payload, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/documents/contract")
async def generate_contract(
    request: Request,
    body: ContractGenerateRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """근로계약서 생성 프록시."""
    payload = body.model_dump()

    # 인증 사용자의 기업 정보 자동 주입
    if user:
        payload["user_id"] = user.user_id
        context = _build_user_context(user, db)
        if context.get("company"):
            payload["company_context"] = {
                "company_name": context["company"]["company_name"],
                "business_number": context["company"]["business_number"],
                "industry_code": context["company"]["industry_code"],
                "industry_name": context["company"]["industry_name"],
            }

    url = f"{settings.RAG_SERVICE_URL}/api/documents/contract"
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Document generation error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 생성 중 오류가 발생했습니다.")

    return resp.json()


@router.post("/documents/business-plan")
async def generate_business_plan(
    request: Request,
    format: str = Query(default="docx", pattern=r"^(pdf|docx)$"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """사업계획서 템플릿 생성 프록시."""
    url = f"{settings.RAG_SERVICE_URL}/api/documents/business-plan?format={format}"

    payload: dict = {}
    if user:
        payload["user_id"] = user.user_id
        context = _build_user_context(user, db)
        if context.get("company"):
            payload["company_context"] = context["company"]

    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Business plan generation error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 생성 중 오류가 발생했습니다.")

    return resp.json()


@router.post("/documents/generate")
async def generate_document(
    request: Request,
    body: GenerateDocumentProxyRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> dict:
    """범용 문서 생성 프록시."""
    payload = body.model_dump()
    if user:
        payload["user_id"] = user.user_id
        context = _build_user_context(user, db)
        if context.get("company"):
            payload["company_context"] = {
                "company_name": context["company"]["company_name"],
                "business_number": context["company"]["business_number"],
                "industry_code": context["company"]["industry_code"],
                "industry_name": context["company"]["industry_name"],
            }

    url = f"{settings.RAG_SERVICE_URL}/api/documents/generate"
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Document generate error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 생성 중 오류가 발생했습니다.")

    return resp.json()


@router.post("/documents/modify")
async def modify_document(
    request: Request,
    body: ModifyDocumentProxyRequest,
    user: User | None = Depends(get_optional_user),
) -> dict:
    """문서 수정 프록시."""
    payload = body.model_dump()
    if user:
        payload["user_id"] = user.user_id

    url = f"{settings.RAG_SERVICE_URL}/api/documents/modify"
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Document modify error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 수정 중 오류가 발생했습니다.")

    return resp.json()


@router.get("/documents/types")
async def list_document_types(request: Request) -> list:
    """문서 유형 목록 프록시.

    Args:
        request: FastAPI Request
    """
    url = f"{settings.RAG_SERVICE_URL}/api/documents/types"
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            resp = await client.get(url, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Document types error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 유형 목록 조회 실패")

    return resp.json()


@router.get("/documents/application-forms")
async def list_application_forms(request: Request) -> list:
    """신청 양식 목록 프록시."""
    url = f"{settings.RAG_SERVICE_URL}/api/documents/application-forms"
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            resp = await client.get(url, headers=_build_rag_headers(request))
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Application forms list error: status=%d", resp.status_code)
        raise HTTPException(502, "신청 양식 목록 조회 실패")

    return resp.json()


@router.post("/documents/application-forms/analyze")
async def analyze_application_form(
    request: Request,
    form_key: str = Query(..., max_length=500),
) -> dict:
    """신청 양식 분석 프록시."""
    url = f"{settings.RAG_SERVICE_URL}/api/documents/application-forms/analyze"
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(
                url, params={"form_key": form_key}, headers=_build_rag_headers(request),
            )
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Application form analyze error: status=%d", resp.status_code)
        raise HTTPException(502, "양식 분석 중 오류가 발생했습니다.")

    return resp.json()


@router.get("/health")
async def rag_health():
    """RAG 서비스 헬스체크 프록시."""
    url = f"{settings.RAG_SERVICE_URL}/health"

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            resp = await client.get(url)
        except (httpx.ConnectError, httpx.TimeoutException):
            raise HTTPException(status_code=502, detail="RAG 서비스에 연결할 수 없습니다.")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="RAG 서비스 상태 확인 실패")

    return resp.json()
