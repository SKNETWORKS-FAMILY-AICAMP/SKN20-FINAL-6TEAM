import re

from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime


class CompanyCreate(BaseModel):
    com_name: str
    biz_num: str = ""
    addr: str = ""
    open_date: datetime | None = None
    biz_code: str = "BA000000"

    @field_validator("biz_num")
    @classmethod
    def validate_biz_num(cls, v: str) -> str:
        """사업자등록번호 형식을 검증합니다 (빈 문자열 허용)."""
        if not v:
            return v
        # XXX-XX-XXXXX 또는 XXXXXXXXXX 형식
        if not re.match(r"^\d{3}-\d{2}-\d{5}$", v) and not re.match(r"^\d{10}$", v):
            raise ValueError("사업자등록번호는 XXX-XX-XXXXX 또는 숫자 10자리 형식이어야 합니다")
        return v


class CompanyUpdate(BaseModel):
    com_name: str | None = None
    biz_num: str | None = None
    addr: str | None = None
    open_date: datetime | None = None
    biz_code: str | None = None
    main_yn: bool | None = None

    @field_validator("biz_num")
    @classmethod
    def validate_biz_num(cls, v: str | None) -> str | None:
        """사업자등록번호 형식을 검증합니다."""
        if v is None or not v:
            return v
        if not re.match(r"^\d{3}-\d{2}-\d{5}$", v) and not re.match(r"^\d{10}$", v):
            raise ValueError("사업자등록번호는 XXX-XX-XXXXX 또는 숫자 10자리 형식이어야 합니다")
        return v


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: int
    user_id: int
    com_name: str
    biz_num: str
    addr: str
    open_date: datetime | None = None
    biz_code: str | None = None
    file_path: str
    main_yn: bool
    create_date: datetime | None = None
