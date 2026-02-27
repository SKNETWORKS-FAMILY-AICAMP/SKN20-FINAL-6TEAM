"""사용자 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from apps.users.service import UserService
from .schemas import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    UserResponse,
    UserUpdate,
    UserTypeUpdate,
)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """UserService 의존성 주입."""
    return UserService(db)


@router.get("/me", response_model=UserResponse)
async def get_me(
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """현재 로그인한 사용자 정보 조회"""
    return service.to_user_response(current_user)


@router.put("/me", response_model=UserResponse)
@limiter.limit("20/minute")
async def update_me(
    request: Request,
    user_update: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자 정보 수정"""
    updated = service.update_user(current_user, user_update)
    return service.to_user_response(updated)


@router.get("/me/notification-settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자 알림 설정 조회"""
    return service.get_notification_settings(current_user)


@router.put("/me/notification-settings", response_model=NotificationSettingsResponse)
@limiter.limit("20/minute")
async def update_notification_settings(
    request: Request,
    settings_update: NotificationSettingsUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자 알림 설정 수정"""
    return service.update_notification_settings(current_user, settings_update)


@router.put("/me/type", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_user_type(
    request: Request,
    type_update: UserTypeUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """사용자 유형 변경 (예비창업자/사업자)"""
    try:
        updated = service.update_user_type(current_user, type_update)
        return service.to_user_response(updated)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 사용자 유형입니다.",
        )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_me(
    request: Request,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """회원 탈퇴 (소프트 삭제)"""
    service.delete_user(current_user)
    return None
