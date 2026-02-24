"""공고 스키마."""

from pydantic import BaseModel, ConfigDict
from datetime import date, datetime


class AnnounceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    announce_id: int
    ann_name: str
    source_type: str
    apply_start: date | None = None
    apply_end: date | None = None
    region: str
    organization: str
    source_url: str
    biz_code: str | None = None
    create_date: datetime | None = None
