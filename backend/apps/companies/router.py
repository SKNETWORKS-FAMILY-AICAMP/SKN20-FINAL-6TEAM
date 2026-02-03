from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from datetime import datetime

from config.database import get_db
from apps.common.models import User, Company
from apps.common.deps import get_current_user
from .schemas import CompanyCreate, CompanyUpdate, CompanyResponse

router = APIRouter(prefix="/companies", tags=["companies"])

UPLOAD_DIR = "uploads/companies"


@router.get("", response_model=List[CompanyResponse])
async def get_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자의 기업 목록 조회"""
    companies = db.query(Company).filter(
        Company.user_id == current_user.user_id,
        Company.use_yn == True
    ).all()
    return companies


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """기업 정보 등록"""
    company = Company(
        user_id=current_user.user_id,
        com_name=company_data.com_name,
        biz_num=company_data.biz_num,
        addr=company_data.addr,
        open_date=company_data.open_date,
        biz_code=company_data.biz_code
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """기업 상세 정보 조회"""
    company = db.query(Company).filter(
        Company.company_id == company_id,
        Company.user_id == current_user.user_id,
        Company.use_yn == True
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """기업 정보 수정"""
    company = db.query(Company).filter(
        Company.company_id == company_id,
        Company.user_id == current_user.user_id,
        Company.use_yn == True
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    update_data = company_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)

    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """기업 삭제 (소프트 삭제)"""
    company = db.query(Company).filter(
        Company.company_id == company_id,
        Company.user_id == current_user.user_id,
        Company.use_yn == True
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    company.use_yn = False
    db.commit()
    return None


@router.post("/{company_id}/upload", response_model=CompanyResponse)
async def upload_business_registration(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사업자등록증 파일 업로드"""
    company = db.query(Company).filter(
        Company.company_id == company_id,
        Company.user_id == current_user.user_id,
        Company.use_yn == True
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    # 파일 저장
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    company.file_path = file_path
    db.commit()
    db.refresh(company)
    return company
