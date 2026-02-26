"""상담 이력 API 라우터"""

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
from .schemas import (
    HistoryCreate,
    HistoryResponse,
    HistoryThreadDetailResponse,
    HistoryThreadSummaryResponse,
)

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
    """상담 이력을 thread 단위로 조회"""
    return service.get_history_threads(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/threads/{root_history_id}", response_model=HistoryThreadDetailResponse)
async def get_history_thread_detail(
    root_history_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(get_current_user),
):
    """특정 thread의 전체 상담 이력 조회"""
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
