from pydantic import BaseModel, ConfigDict, Field
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
    username: str | None = Field(None, min_length=1, max_length=100)
    birth: datetime | None = None


class UserTypeUpdate(BaseModel):
    type_code: str = Field(..., pattern=r"^U\d{7}$")
