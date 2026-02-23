from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime


class ScheduleCreate(BaseModel):
    company_id: int
    schedule_name: str = Field(..., min_length=1, max_length=255)
    start_date: datetime
    end_date: datetime
    memo: str = Field("", max_length=5000)
    announce_id: int | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "ScheduleCreate":
        """종료일이 시작일 이후인지 검증합니다."""
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일 이후여야 합니다")
        return self


class ScheduleUpdate(BaseModel):
    schedule_name: str | None = Field(None, min_length=1, max_length=255)
    start_date: datetime | None = None
    end_date: datetime | None = None
    memo: str | None = Field(None, max_length=5000)
    announce_id: int | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "ScheduleUpdate":
        """종료일이 시작일 이후인지 검증합니다 (둘 다 제공된 경우)."""
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("종료일은 시작일 이후여야 합니다")
        return self


class ScheduleResponse(BaseModel):
    schedule_id: int
    company_id: int
    announce_id: int | None = None
    schedule_name: str
    start_date: datetime
    end_date: datetime
    memo: str | None = None
    create_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
