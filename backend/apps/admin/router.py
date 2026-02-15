"""관리자 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime

from apps.common.deps import get_db, get_current_user
from apps.common.models import User
from apps.admin.service import AdminService
from apps.users.service import ADMIN_TYPE_CODE
from apps.admin.schemas import (
    HistoryListResponse,
    EvaluationStats,
    HistoryFilterParams,
    ServerStatusResponse,
)
from apps.histories.schemas import HistoryDetailResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    """AdminService 의존성 주입."""
    return AdminService(db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 확인."""
    if current_user.type_code != ADMIN_TYPE_CODE:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return current_user


@router.get("/status", response_model=ServerStatusResponse)
async def get_server_status(
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> ServerStatusResponse:
    """서버 상태 조회.

    Backend, RAG, Database 상태를 반환합니다.
    """
    return await service.get_server_status()


@router.get("/histories", response_model=HistoryListResponse)
async def get_histories(
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지 크기"),
    start_date: datetime | None = Query(default=None, description="시작일"),
    end_date: datetime | None = Query(default=None, description="종료일"),
    domain: str | None = Query(default=None, description="도메인 필터"),
    agent_code: str | None = Query(default=None, description="에이전트 코드 필터"),
    min_score: int | None = Query(default=None, ge=0, le=100, description="최소 LLM 점수"),
    max_score: int | None = Query(default=None, ge=0, le=100, description="최대 LLM 점수"),
    passed_only: bool | None = Query(default=None, description="통과된 것만"),
    user_id: int | None = Query(default=None, description="사용자 ID 필터"),
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> HistoryListResponse:
    """관리자용 상담 이력 목록 조회.

    페이지네이션과 다양한 필터를 지원합니다.
    """
    filters = HistoryFilterParams(
        start_date=start_date,
        end_date=end_date,
        domain=domain,
        agent_code=agent_code,
        min_score=min_score,
        max_score=max_score,
        passed_only=passed_only,
        user_id=user_id,
    )

    return service.get_histories(page=page, page_size=page_size, filters=filters)


@router.get("/histories/stats", response_model=EvaluationStats)
async def get_evaluation_stats(
    start_date: datetime | None = Query(default=None, description="시작일"),
    end_date: datetime | None = Query(default=None, description="종료일"),
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> EvaluationStats:
    """평가 통계 조회.

    전체 상담 수, 평가된 상담 수, 통과/실패 수, 평균 점수 등을 반환합니다.
    """
    return service.get_evaluation_stats(start_date=start_date, end_date=end_date)


@router.get("/histories/{history_id}", response_model=HistoryDetailResponse)
async def get_history_detail(
    history_id: int,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> HistoryDetailResponse:
    """상담 이력 상세 조회.

    evaluation_data를 포함한 전체 정보를 반환합니다.
    """
    result = service.get_history_detail(history_id)
    if not result:
        raise HTTPException(status_code=404, detail="상담 이력을 찾을 수 없습니다")
    return result
