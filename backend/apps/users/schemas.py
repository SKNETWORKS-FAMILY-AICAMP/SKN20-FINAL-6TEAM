from pydantic import BaseModel, ConfigDict
from datetime import datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    google_email: str
    username: str
    type_code: str
    birth: datetime | None = None
    create_date: datetime | None = None


class UserUpdate(BaseModel):
    username: str | None = None
    birth: datetime | None = None


class UserTypeUpdate(BaseModel):
    type_code: str  # U0000001: 관리자, U0000002: 예비창업자, U0000003: 사업자
