from pydantic import BaseModel
from datetime import datetime


class ScheduleCreate(BaseModel):
    company_id: int
    schedule_name: str
    start_date: datetime
    end_date: datetime
    memo: str = ""
    announce_id: int | None = None


class ScheduleUpdate(BaseModel):
    schedule_name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    memo: str | None = None
    announce_id: int | None = None


class ScheduleResponse(BaseModel):
    schedule_id: int
    company_id: int
    announce_id: int | None = None
    schedule_name: str
    start_date: datetime
    end_date: datetime
    memo: str | None = None
    create_date: datetime | None = None

    class Config:
        from_attributes = True
