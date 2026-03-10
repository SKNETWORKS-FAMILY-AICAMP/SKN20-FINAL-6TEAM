"""공고 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.announces.service import AnnounceService
from apps.common.deps import get_current_user, require_or_404
from apps.common.models import User
from apps.documents.s3_utils import get_presigned_url_or_raise
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


@router.get("", response_model=list[AnnounceResponse])
async def get_announces(
    biz_code: str | None = Query(None, description="업종코드 (대분류 prefix 매칭)"),
    limit: int = Query(5, ge=1, le=20, description="최대 결과 수"),
    service: AnnounceService = Depends(get_announce_service),
    current_user: User = Depends(get_current_user),
) -> list[AnnounceResponse]:
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


@router.get("/{announce_id}", response_model=AnnounceResponse)
async def get_announce(
    announce_id: int,
    service: AnnounceService = Depends(get_announce_service),
    current_user: User = Depends(get_current_user),
) -> AnnounceResponse:
    """공고 단건 조회."""
    return require_or_404(service.get_announce_by_id(announce_id), "공고를 찾을 수 없습니다")


@router.get("/{announce_id}/download")
async def download_announce_attachment(
    announce_id: int,
    type: str = Query(..., pattern="^(doc|form)$"),
    service: AnnounceService = Depends(get_announce_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """공고 첨부파일 presigned URL 반환."""
    announce = require_or_404(service.get_announce_by_id(announce_id), "공고를 찾을 수 없습니다")
    s3_key = announce.doc_s3_key if type == "doc" else announce.form_s3_key
    if not s3_key:
        raise HTTPException(status_code=404, detail="첨부파일이 없습니다")

    return {"download_url": get_presigned_url_or_raise(s3_key)}
