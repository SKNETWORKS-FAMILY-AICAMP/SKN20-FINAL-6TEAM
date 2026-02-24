"""기업 API 라우터."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import List

from config.database import get_db
from apps.common.models import User
from apps.common.deps import get_current_user
from apps.companies.service import CompanyService, ALLOWED_EXTENSIONS, ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE
from .schemas import CompanyCreate, CompanyUpdate, CompanyResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/companies", tags=["companies"])


def get_company_service(db: Session = Depends(get_db)) -> CompanyService:
    """CompanyService 의존성 주입."""
    return CompanyService(db)


@router.get("", response_model=List[CompanyResponse])
async def get_companies(
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 기업 목록 조회"""
    return service.get_companies_by_user(current_user.user_id)


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_company(
    request: Request,
    company_data: CompanyCreate,
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """기업 정보 등록"""
    return service.create_company(company_data, current_user.user_id)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """기업 상세 정보 조회"""
    company = service.get_company(company_id, current_user.user_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
@limiter.limit("20/minute")
async def update_company(
    request: Request,
    company_id: int,
    company_data: CompanyUpdate,
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """기업 정보 수정"""
    company = service.update_company(company_id, company_data, current_user.user_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_company(
    request: Request,
    company_id: int,
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """기업 삭제 (소프트 삭제)"""
    if not service.delete_company(company_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return None


@router.patch("/{company_id}/main", response_model=CompanyResponse)
async def toggle_main_company(
    company_id: int,
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """대표 기업 토글"""
    company = service.set_main_company(company_id, current_user.user_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


@router.post("/{company_id}/upload", response_model=CompanyResponse)
@limiter.limit("5/minute")
async def upload_business_registration(
    request: Request,
    company_id: int,
    file: UploadFile = File(...),
    service: CompanyService = Depends(get_company_service),
    current_user: User = Depends(get_current_user),
):
    """사업자등록증 파일 업로드"""
    # 파일 검증
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allowed file types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file content type",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
        )

    company = await service.upload_business_registration(
        company_id, current_user.user_id, content, file_ext
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company
