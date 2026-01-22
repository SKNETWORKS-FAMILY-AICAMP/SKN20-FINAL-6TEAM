from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserResponse(BaseModel):
    user_id: int
    google_email: str
    username: str
    type_code: str
    birth: datetime | None = None
    create_date: datetime | None = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: str | None = None
    birth: datetime | None = None


class UserTypeUpdate(BaseModel):
    type_code: str  # U001: 예비창업자, U002: 사업자
