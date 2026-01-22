from pydantic import BaseModel
from datetime import datetime


class CompanyCreate(BaseModel):
    com_name: str
    biz_num: str = ""
    addr: str = ""
    open_date: datetime | None = None
    biz_code: str = "B001"


class CompanyUpdate(BaseModel):
    com_name: str | None = None
    biz_num: str | None = None
    addr: str | None = None
    open_date: datetime | None = None
    biz_code: str | None = None
    main_yn: bool | None = None


class CompanyResponse(BaseModel):
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

    class Config:
        from_attributes = True
