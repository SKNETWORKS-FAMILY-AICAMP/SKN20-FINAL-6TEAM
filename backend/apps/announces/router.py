"""공고 API 라우터."""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.announces.service import AnnounceService
from apps.common.deps import get_current_user
from apps.common.models import User
from config.database import get_db

from .schemas import (
    AnnounceResponse,
    AnnounceSyncRequest,
    AnnounceSyncResponse,
)

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
    """공고 목록 조회."""
    return service.get_announces_by_biz_code(biz_code=biz_code, limit=limit)


@router.post("/sync", response_model=AnnounceSyncResponse)
async def sync_announces(
    sync_request: AnnounceSyncRequest,
    service: AnnounceService = Depends(get_announce_service),
    current_user: User = Depends(get_current_user),
) -> AnnounceSyncResponse:
    """로그인/로그아웃 시점 신규 공고 알림 동기화."""
    return service.sync_announces_for_user(
        user=current_user,
        trigger=sync_request.trigger,
    )
