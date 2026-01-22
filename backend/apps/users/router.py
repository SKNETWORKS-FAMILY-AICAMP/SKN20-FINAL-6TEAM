from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from .schemas import UserResponse, UserUpdate, UserTypeUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 조회"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자 정보 수정"""
    if user_update.username is not None:
        current_user.username = user_update.username
    if user_update.birth is not None:
        current_user.birth = user_update.birth

    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/type", response_model=UserResponse)
async def update_user_type(
    type_update: UserTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자 유형 변경 (예비창업자/사업자)"""
    if type_update.type_code not in ["U001", "U002"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid type_code. Must be U001 or U002."
        )

    current_user.type_code = type_update.type_code
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """회원 탈퇴 (소프트 삭제)"""
    current_user.use_yn = False
    db.commit()
    return None
