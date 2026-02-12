"""기업 서비스."""

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.common.models import Company
from apps.companies.schemas import CompanyCreate, CompanyUpdate

UPLOAD_DIR = "uploads/companies"
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class CompanyService:
    """기업 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    def get_companies_by_user(self, user_id: int) -> list[Company]:
        """사용자의 기업 목록을 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            기업 목록
        """
        stmt = select(Company).where(
            Company.user_id == user_id,
            Company.use_yn == True,
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_company(
        self, company_id: int, user_id: int
    ) -> Company | None:
        """사용자의 특정 기업을 조회합니다.

        Args:
            company_id: 기업 ID
            user_id: 사용자 ID

        Returns:
            기업 객체 또는 None
        """
        stmt = select(Company).where(
            Company.company_id == company_id,
            Company.user_id == user_id,
            Company.use_yn == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_company(self, data: CompanyCreate, user_id: int) -> Company:
        """기업 정보를 등록합니다.

        Args:
            data: 기업 생성 요청 데이터
            user_id: 사용자 ID

        Returns:
            생성된 기업 객체
        """
        company = Company(
            user_id=user_id,
            com_name=data.com_name,
            biz_num=data.biz_num,
            addr=data.addr,
            open_date=data.open_date,
            biz_code=data.biz_code,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def update_company(
        self, company_id: int, data: CompanyUpdate, user_id: int
    ) -> Company | None:
        """기업 정보를 수정합니다.

        Args:
            company_id: 기업 ID
            data: 기업 수정 요청 데이터
            user_id: 사용자 ID

        Returns:
            수정된 기업 객체 또는 None
        """
        company = self.get_company(company_id, user_id)
        if not company:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(company, key, value)

        self.db.commit()
        self.db.refresh(company)
        return company

    def delete_company(self, company_id: int, user_id: int) -> bool:
        """기업을 소프트 삭제합니다.

        Args:
            company_id: 기업 ID
            user_id: 사용자 ID

        Returns:
            삭제 성공 여부
        """
        company = self.get_company(company_id, user_id)
        if not company:
            return False

        company.use_yn = False
        self.db.commit()
        return True

    async def upload_business_registration(
        self,
        company_id: int,
        user_id: int,
        file_content: bytes,
        file_ext: str,
    ) -> Company | None:
        """사업자등록증 파일을 업로드합니다.

        Args:
            company_id: 기업 ID
            user_id: 사용자 ID
            file_content: 파일 내용 (바이트)
            file_ext: 파일 확장자

        Returns:
            업데이트된 기업 객체 또는 None
        """
        company = self.get_company(company_id, user_id)
        if not company:
            return None

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        company.file_path = file_path
        self.db.commit()
        self.db.refresh(company)
        return company
