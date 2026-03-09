from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    google_email: str
    username: str
    type_code: str
    birth: datetime | None = None
    age: int | None = None
    create_date: datetime | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=100)
    birth: datetime | None = None
    age: int | None = Field(None, ge=0, le=150)


class UserTypeUpdate(BaseModel):
    type_code: str = Field(..., pattern=r"^U\d{7}$")


class NotificationSettingsResponse(BaseModel):
    schedule_d7: bool
    schedule_d3: bool
    new_announce: bool
    answer_complete: bool


class NotificationSettingsUpdate(BaseModel):
    schedule_d7: bool
    schedule_d3: bool
    new_announce: bool
    answer_complete: bool
