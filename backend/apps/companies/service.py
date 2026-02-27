"""기업 서비스."""

import os
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.common.models import Company
from apps.companies.schemas import CompanyCreate, CompanyUpdate

UPLOAD_DIR = "uploads/companies"
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class CompanyService:
    """기업 서비스 클래스."""

    @staticmethod
    async def lookup_by_biz_num(biz_num: str) -> dict:
        """bizno.net 무료 API로 사업자등록번호 조회."""
        import logging

        import httpx
        from config.settings import settings

        logger = logging.getLogger(__name__)
        clean_num = biz_num.replace("-", "")

        if not settings.BIZNO_API_KEY:
            raise ValueError("BIZNO_API_KEY가 설정되지 않았습니다.")

        url = "https://bizno.net/api/fapi"
        params = {
            "key": settings.BIZNO_API_KEY,
            "gb": "1",
            "q": clean_num,
            "type": "json",
        }

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(url, params=params)

        # 302 → /login: API 키 만료 또는 무효
        if resp.status_code in (301, 302, 403):
            logger.warning("bizno.net API 인증 실패 (HTTP %s)", resp.status_code)
            raise ValueError("bizno.net API 키가 유효하지 않습니다. 키를 갱신해주세요.")

        resp.raise_for_status()

        data = resp.json()
        items = [i for i in data.get("items", []) if i]
        if not items:
            return {"found": False}

        item = items[0]
        return {
            "found": True,
            "biz_num": item.get("bno", ""),
            "com_name": item.get("company", ""),
            "ceo": item.get("ceo", ""),
            "addr": item.get("addr", ""),
            "open_date": item.get("est_dt", ""),
            "biz_type": item.get("btype", ""),
            "biz_item": item.get("bitem", ""),
            "status": item.get("bstt", ""),
            "tax_type": item.get("taxtype", ""),
        }

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
        existing_count = self.db.execute(
            select(func.count()).select_from(Company).where(
                Company.user_id == user_id,
                Company.use_yn == True,
            )
        ).scalar_one()

        company = Company(
            user_id=user_id,
            com_name=data.com_name,
            biz_num=data.biz_num,
            addr=data.addr,
            open_date=data.open_date,
            biz_code=data.biz_code,
            main_yn=existing_count == 0,
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

    def set_main_company(self, company_id: int, user_id: int) -> Company | None:
        """대표 기업을 토글합니다.

        이미 대표인 기업을 다시 토글하면 해제(False).
        새 기업을 대표로 설정하면 기존 대표 기업은 해제됩니다.

        Args:
            company_id: 기업 ID
            user_id: 사용자 ID

        Returns:
            업데이트된 기업 객체 또는 None
        """
        company = self.get_company(company_id, user_id)
        if not company:
            return None

        if company.main_yn:
            company.main_yn = False
        else:
            stmt = select(Company).where(
                Company.user_id == user_id,
                Company.use_yn == True,
            )
            all_companies = list(self.db.execute(stmt).scalars().all())
            for c in all_companies:
                c.main_yn = False
            company.main_yn = True

        self.db.commit()
        self.db.refresh(company)
        return company

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
