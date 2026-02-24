"""공고 API 라우터."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from apps.announces.service import AnnounceService
from .schemas import AnnounceResponse

router = APIRouter(prefix="/announces", tags=["announces"])


def get_announce_service(db: Session = Depends(get_db)) -> AnnounceService:
    """AnnounceService 의존성 주입."""
    return AnnounceService(db)


@router.get("", response_model=List[AnnounceResponse])
async def get_announces(
    biz_code: str | None = Query(None, description="업종코드 (대분류 prefix 매칭)"),
    limit: int = Query(5, ge=1, le=20, description="최대 결과 수"),
    service: AnnounceService = Depends(get_announce_service),
    current_user: User = Depends(get_current_user),
) -> List[AnnounceResponse]:
    """공고 목록 조회 (업종코드 대분류 기준 필터링)"""
    return service.get_announces_by_biz_code(biz_code=biz_code, limit=limit)
