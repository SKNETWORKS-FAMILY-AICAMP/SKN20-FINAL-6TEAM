import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from apps.common.deps import get_optional_user
from apps.common.models import User, Company, Code

from .schemas import RagChatRequest, ContractGenerateRequest

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
        "company": None,
    }

    # 대표 기업 조회 (main_yn=True)
    stmt = select(Company).where(
        Company.user_id == user.user_id,
        Company.use_yn == True,
        Company.main_yn == True,
    )
    company = db.execute(stmt).scalar_one_or_none()
    if not company:
        return context

    # 업종명 조회 (Company 조회와 분리 — 1회 추가 쿼리)
    industry_name = None
    if company.biz_code:
        industry_name = db.execute(
            select(Code.name).where(Code.code == company.biz_code, Code.use_yn == True)
        ).scalar_one_or_none()

    years = None
    if company.open_date:
        years = (datetime.now() - company.open_date).days // 365

    context["company"] = {
        "company_name": company.com_name,
        "business_number": company.biz_num,
        "industry_code": company.biz_code,
        "industry_name": industry_name,
        "employee_count": None,
        "years_in_business": years,
        "region": company.addr,
        "annual_revenue": None,
    }
    return context


def _build_rag_headers() -> dict[str, str]:
    """RAG 서비스 요청 헤더를 구성합니다."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.RAG_API_KEY:
        headers["X-API-Key"] = settings.RAG_API_KEY
    return headers


@router.post("/chat")
async def rag_chat(
    body: RagChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """RAG 채팅 프록시 (비스트리밍)."""
    payload: dict = {"message": body.message}
    if body.history:
        payload["history"] = [msg.model_dump() for msg in body.history]
    if user:
        payload["user_context"] = _build_user_context(user, db)

    url = f"{settings.RAG_SERVICE_URL}/api/chat"

    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(
                url, json=payload, headers=_build_rag_headers()
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


async def _stream_rag(url: str, payload: dict):
    """RAG SSE 스트림을 바이트 단위로 중계합니다."""
    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            async with client.stream(
                "POST", url, json=payload, headers=_build_rag_headers()
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
    body: RagChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """RAG 채팅 프록시 (SSE 스트리밍)."""
    payload: dict = {"message": body.message}
    if body.history:
        payload["history"] = [msg.model_dump() for msg in body.history]
    if user:
        payload["user_context"] = _build_user_context(user, db)

    url = f"{settings.RAG_SERVICE_URL}/api/chat/stream"

    return StreamingResponse(
        _stream_rag(url, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/documents/contract")
async def generate_contract(
    body: ContractGenerateRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """근로계약서 생성 프록시."""
    payload = body.model_dump()

    # 인증 사용자의 기업 정보 자동 주입
    if user:
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
            resp = await client.post(url, json=payload, headers=_build_rag_headers())
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
    format: str = Query(default="docx", pattern=r"^(pdf|docx)$"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """사업계획서 템플릿 생성 프록시."""
    url = f"{settings.RAG_SERVICE_URL}/api/documents/business-plan?format={format}"

    payload: dict = {}
    if user:
        context = _build_user_context(user, db)
        if context.get("company"):
            payload["company_context"] = context["company"]

    async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload, headers=_build_rag_headers())
        except httpx.ConnectError:
            raise HTTPException(502, "RAG 서비스에 연결할 수 없습니다.")
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG 서비스 응답 시간이 초과되었습니다.")

    if resp.status_code != 200:
        logger.error("Business plan generation error: status=%d body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(502, "문서 생성 중 오류가 발생했습니다.")

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
