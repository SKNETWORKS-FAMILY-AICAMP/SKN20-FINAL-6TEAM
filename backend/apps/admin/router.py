"""관리자 API 라우터."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
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
    JobLogResponse,
    LogPageResponse,
    MetricsResponse,
    ServerStatusResponse,
)
from apps.histories.schemas import HistoryDetailResponse
from config.settings import settings

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    """AdminService 의존성 주입."""
    return AdminService(db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 확인."""
    if current_user.type_code != ADMIN_TYPE_CODE:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return current_user


@router.get("/metrics", response_model=MetricsResponse)
@limiter.limit("30/minute")
async def get_metrics(
    request: Request,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> MetricsResponse:
    """서버 리소스 사용량 조회.

    psutil로 CPU/메모리/디스크 현황을 반환합니다.
    임계치(ALERT_RESOURCE_THRESHOLD, 기본 90%) 초과 시 SES 이메일 알림을 fire-and-forget으로 발송합니다.
    """
    result = service.get_system_metrics()
    threshold = settings.ALERT_RESOURCE_THRESHOLD
    if (
        result.cpu_percent > threshold
        or result.memory_percent > threshold
        or result.disk_percent > threshold
    ):
        asyncio.create_task(
            service.send_resource_alert(
                result.cpu_percent, result.memory_percent, result.disk_percent
            )
        )
    return result


@router.get("/scheduler/status", response_model=list[JobLogResponse])
@limiter.limit("30/minute")
async def get_scheduler_status(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="최대 반환 건수"),
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> list[JobLogResponse]:
    """스케줄러 작업 실행 이력 조회.

    job_logs 테이블에서 최근 실행 이력(시작/성공/실패)을 최신 순으로 반환합니다.
    """
    return service.get_scheduler_status(limit=limit)


@router.get("/logs", response_model=LogPageResponse)
@limiter.limit("20/minute")
async def get_logs(
    request: Request,
    file: str = Query(default="backend", description="로그 파일 (backend | rag)"),
    page: int = Query(default=1, ge=1, description="페이지 번호 (1=가장 최신)"),
    page_size: int = Query(default=100, ge=10, le=500, description="페이지당 줄 수"),
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> LogPageResponse:
    """로그 파일 조회.

    /var/log/app/{file}.log 를 최신 순으로 페이징하여 반환합니다.
    file 파라미터는 'backend' 또는 'rag'만 허용합니다.
    """
    try:
        return service.get_log_content(file=file, page=page, page_size=page_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=ServerStatusResponse)
@limiter.limit("10/minute")
async def get_server_status(
    request: Request,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(require_admin),
) -> ServerStatusResponse:
    """서버 상태 조회.

    Backend, RAG, Database 상태를 반환합니다.
    """
    return await service.get_server_status()


@router.get("/histories", response_model=HistoryListResponse)
@limiter.limit("30/minute")
async def get_histories(
    request: Request,
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
@limiter.limit("10/minute")
async def get_evaluation_stats(
    request: Request,
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
@limiter.limit("30/minute")
async def get_history_detail(
    request: Request,
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
