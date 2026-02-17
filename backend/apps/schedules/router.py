"""일정 관리 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from apps.schedules.service import ScheduleService
from .schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/schedules", tags=["schedules"])


def get_schedule_service(db: Session = Depends(get_db)) -> ScheduleService:
    """ScheduleService 의존성 주입."""
    return ScheduleService(db)


@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(
    company_id: int | None = Query(None, description="기업 ID 필터"),
    start_from: datetime | None = Query(None, description="시작일 이후"),
    start_to: datetime | None = Query(None, description="시작일 이전"),
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(get_current_user),
):
    """일정 목록 조회"""
    try:
        return service.get_schedules(
            user_id=current_user.user_id,
            company_id=company_id,
            start_from=start_from,
            start_to=start_to,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company",
        )


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_schedule(
    request: Request,
    schedule_data: ScheduleCreate,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(get_current_user),
):
    """일정 등록"""
    schedule = service.create_schedule(schedule_data, current_user.user_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(get_current_user),
):
    """일정 상세 조회"""
    schedule = service.get_schedule(schedule_id, current_user.user_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
@limiter.limit("20/minute")
async def update_schedule(
    request: Request,
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(get_current_user),
):
    """일정 수정"""
    schedule = service.update_schedule(schedule_id, schedule_data, current_user.user_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_schedule(
    request: Request,
    schedule_id: int,
    service: ScheduleService = Depends(get_schedule_service),
    current_user: User = Depends(get_current_user),
):
    """일정 삭제 (소프트 삭제)"""
    if not service.delete_schedule(schedule_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    return None
