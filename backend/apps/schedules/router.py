from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from config.database import get_db
from apps.common.models import User, Company, Schedule
from apps.common.deps import get_current_user
from .schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse

router = APIRouter(prefix="/schedules", tags=["schedules"])


def check_company_ownership(db: Session, company_id: int, user_id: int) -> Company:
    """사용자의 기업인지 확인"""
    company = db.query(Company).filter(
        Company.company_id == company_id,
        Company.user_id == user_id,
        Company.use_yn == True
    ).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company


@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(
    company_id: int | None = Query(None, description="기업 ID 필터"),
    start_from: datetime | None = Query(None, description="시작일 이후"),
    start_to: datetime | None = Query(None, description="시작일 이전"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일정 목록 조회"""
    # 사용자의 기업 ID 목록
    user_company_ids = [
        c.company_id for c in db.query(Company).filter(
            Company.user_id == current_user.user_id,
            Company.use_yn == True
        ).all()
    ]

    if not user_company_ids:
        return []

    query = db.query(Schedule).filter(
        Schedule.company_id.in_(user_company_ids),
        Schedule.use_yn == True
    )

    if company_id:
        if company_id not in user_company_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this company"
            )
        query = query.filter(Schedule.company_id == company_id)

    if start_from:
        query = query.filter(Schedule.start_date >= start_from)
    if start_to:
        query = query.filter(Schedule.start_date <= start_to)

    schedules = query.order_by(Schedule.start_date.asc()).all()
    return schedules


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일정 등록"""
    check_company_ownership(db, schedule_data.company_id, current_user.user_id)

    schedule = Schedule(
        company_id=schedule_data.company_id,
        schedule_name=schedule_data.schedule_name,
        start_date=schedule_data.start_date,
        end_date=schedule_data.end_date,
        memo=schedule_data.memo,
        announce_id=schedule_data.announce_id
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일정 상세 조회"""
    user_company_ids = [
        c.company_id for c in db.query(Company).filter(
            Company.user_id == current_user.user_id,
            Company.use_yn == True
        ).all()
    ]

    schedule = db.query(Schedule).filter(
        Schedule.schedule_id == schedule_id,
        Schedule.company_id.in_(user_company_ids),
        Schedule.use_yn == True
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일정 수정"""
    user_company_ids = [
        c.company_id for c in db.query(Company).filter(
            Company.user_id == current_user.user_id,
            Company.use_yn == True
        ).all()
    ]

    schedule = db.query(Schedule).filter(
        Schedule.schedule_id == schedule_id,
        Schedule.company_id.in_(user_company_ids),
        Schedule.use_yn == True
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    update_data = schedule_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(schedule, key, value)

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일정 삭제 (소프트 삭제)"""
    user_company_ids = [
        c.company_id for c in db.query(Company).filter(
            Company.user_id == current_user.user_id,
            Company.use_yn == True
        ).all()
    ]

    schedule = db.query(Schedule).filter(
        Schedule.schedule_id == schedule_id,
        Schedule.company_id.in_(user_company_ids),
        Schedule.use_yn == True
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    schedule.use_yn = False
    db.commit()
    return None
