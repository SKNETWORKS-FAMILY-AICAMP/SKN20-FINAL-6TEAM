"""상담 이력 API 라우터"""

import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import List

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from apps.histories.service import HistoryService, InvalidParentHistoryError
from apps.histories.background import run_ragas_background
from .batch_schemas import BatchHistoryCreate, BatchHistoryResponse
from .schemas import (
    HistoryCreate,
    HistoryResponse,
    HistoryThreadDetailResponse,
    HistoryThreadSummaryResponse,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/histories", tags=["histories"])


def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    """HistoryService 의존성 주입."""
    return HistoryService(db)


@router.get("", response_model=List[HistoryResponse])
async def get_histories(
    agent_code: str | None = Query(None, description="에이전트 코드 필터"),
    limit: int = Query(50, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """상담 이력 목록 조회"""
    return service.get_histories(
        user_id=current_user.user_id,
        agent_code=agent_code,
        limit=limit,
        offset=offset,
    )


@router.get("/threads", response_model=List[HistoryThreadSummaryResponse])
async def get_history_threads(
    limit: int = Query(20, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """상담 이력을 thread 단위로 조회 (DB + Redis 활성 세션)"""
    db_threads = service.get_history_threads(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    # Redis 활성 세션 조회 (RAG 서비스 호출)
    redis_threads: list[HistoryThreadSummaryResponse] = []
    try:
        import httpx
        from config.settings import get_settings as get_app_settings

        app_settings = get_app_settings()
        rag_url = app_settings.RAG_SERVICE_URL.rstrip("/")
        headers = {}
        if app_settings.RAG_API_KEY:
            headers["X-API-Key"] = app_settings.RAG_API_KEY

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{rag_url}/api/sessions/active",
                params={"user_id": current_user.user_id},
                headers=headers,
            )
            if resp.status_code == 200:
                active_sessions = resp.json()
                for idx, session in enumerate(active_sessions):
                    redis_threads.append(HistoryThreadSummaryResponse(
                        root_history_id=-(idx + 1),  # 음수 ID로 Redis 세션 구분
                        last_history_id=-(idx + 1),
                        title=session.get("title", "활성 상담"),
                        message_count=session.get("message_count", 0),
                        first_create_date=session.get("first_create_date"),
                        last_create_date=session.get("last_create_date"),
                        source="redis",
                        session_id=session.get("session_id"),
                    ))
    except Exception as exc:
        logger.warning("Redis active sessions fetch failed (graceful degradation): %s", exc)

    # Redis 세션을 상단에 배치
    return redis_threads + db_threads


@router.get("/threads/{root_history_id}", response_model=HistoryThreadDetailResponse)
async def get_history_thread_detail(
    root_history_id: int,
    session_id: str | None = Query(None, description="Redis 세션 ID (source=redis 일 때)"),
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """특정 thread의 전체 상담 이력 조회"""
    # Redis 세션 조회 (음수 ID 또는 session_id 파라미터)
    if root_history_id < 0 or session_id:
        try:
            import httpx
            from config.settings import get_settings as get_app_settings

            app_settings = get_app_settings()
            rag_url = app_settings.RAG_SERVICE_URL.rstrip("/")
            api_headers = {}
            if app_settings.RAG_API_KEY:
                api_headers["X-API-Key"] = app_settings.RAG_API_KEY

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{rag_url}/api/sessions/active",
                    params={"user_id": current_user.user_id},
                    headers=api_headers,
                )
                if resp.status_code == 200:
                    active_sessions = resp.json()
                    # Find matching session
                    target = None
                    for s in active_sessions:
                        if session_id and s.get("session_id") == session_id:
                            target = s
                            break
                    if target:
                        histories = []
                        for turn in target.get("turns", []):
                            histories.append(HistoryResponse(
                                history_id=0,
                                user_id=current_user.user_id,
                                agent_code=turn.get("agent_code", "A0000001"),
                                question=turn.get("question"),
                                answer=turn.get("answer"),
                                create_date=turn.get("timestamp"),
                            ))
                        return HistoryThreadDetailResponse(
                            root_history_id=root_history_id,
                            last_history_id=root_history_id,
                            title=target.get("title", "활성 상담"),
                            message_count=len(histories),
                            first_create_date=target.get("first_create_date"),
                            last_create_date=target.get("last_create_date"),
                            histories=histories,
                        )
        except Exception as exc:
            logger.warning("Redis thread detail fetch failed: %s", exc)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History thread not found",
        )

    # DB 조회
    thread_detail = service.get_history_thread_detail(
        user_id=current_user.user_id,
        root_history_id=root_history_id,
    )
    if thread_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History thread not found",
        )
    return thread_detail


def _verify_internal_key(request: Request) -> None:
    """내부 서비스 간 통신 인증 (X-Internal-Key 헤더)."""
    expected = os.getenv("RAG_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal key not configured")
    provided = request.headers.get("X-Internal-Key", "")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal key")


@router.post("/batch", response_model=BatchHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_history_batch(
    request: Request,
    batch_data: BatchHistoryCreate,
    service: HistoryService = Depends(get_history_service),
) -> BatchHistoryResponse:
    """배치 히스토리 저장 (RAG 마이그레이션용 내부 API).

    X-Internal-Key 헤더로 인증합니다.
    """
    _verify_internal_key(request)
    try:
        saved, skipped, ids = service.create_history_batch(batch_data)
        logger.info(
            "Batch history saved: user_id=%d, session=%s, saved=%d, skipped=%d",
            batch_data.user_id, batch_data.session_id, saved, skipped,
        )
        return BatchHistoryResponse(saved_count=saved, skipped_count=skipped, history_ids=ids)
    except Exception as exc:
        logger.error("Batch history save failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch history save failed",
        ) from exc


@router.post("", response_model=HistoryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_history(
    request: Request,
    history_data: HistoryCreate,
    background_tasks: BackgroundTasks,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    """상담 이력 저장"""
    try:
        history = service.create_history(history_data, current_user.user_id)
    except InvalidParentHistoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if history_data.evaluation_data and history_data.evaluation_data.contexts:
        background_tasks.add_task(
            run_ragas_background,
            history_id=history.history_id,
            question=history_data.question,
            answer=history_data.answer,
            contexts=history_data.evaluation_data.contexts,
        )
    return history


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history(
    history_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """상담 이력 상세 조회"""
    history = service.get_history(history_id, current_user.user_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found",
        )
    return history


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_history(
    request: Request,
    history_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """상담 이력 삭제 (소프트 삭제)"""
    if not service.delete_history(history_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found",
        )
    return None
