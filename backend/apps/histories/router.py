from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from config.database import get_db
from apps.common.models import User, History
from apps.common.deps import get_current_user
from .schemas import HistoryCreate, HistoryResponse

router = APIRouter(prefix="/histories", tags=["histories"])


@router.get("", response_model=List[HistoryResponse])
async def get_histories(
    agent_code: str | None = Query(None, description="에이전트 코드 필터"),
    limit: int = Query(50, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상담 이력 목록 조회"""
    query = db.query(History).filter(
        History.user_id == current_user.user_id,
        History.use_yn == True
    )

    if agent_code:
        query = query.filter(History.agent_code == agent_code)

    histories = query.order_by(History.create_date.desc()).offset(offset).limit(limit).all()
    return histories


@router.post("", response_model=HistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_history(
    history_data: HistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상담 이력 저장"""
    history = History(
        user_id=current_user.user_id,
        agent_code=history_data.agent_code,
        question=history_data.question,
        answer=history_data.answer,
        parent_history_id=history_data.parent_history_id
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상담 이력 상세 조회"""
    history = db.query(History).filter(
        History.history_id == history_id,
        History.user_id == current_user.user_id,
        History.use_yn == True
    ).first()

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found"
        )
    return history


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상담 이력 삭제 (소프트 삭제)"""
    history = db.query(History).filter(
        History.history_id == history_id,
        History.user_id == current_user.user_id,
        History.use_yn == True
    ).first()

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History not found"
        )

    history.use_yn = False
    db.commit()
    return None
