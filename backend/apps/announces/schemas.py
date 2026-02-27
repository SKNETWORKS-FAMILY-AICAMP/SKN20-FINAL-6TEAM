"""공고 스키마."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class AnnounceSyncTrigger(str, Enum):
    login = "login"
    logout = "logout"


class AnnounceSyncRequest(BaseModel):
    trigger: AnnounceSyncTrigger


class AnnounceSyncItem(BaseModel):
    id: str
    title: str
    message: str
    company_label: str
    type: Literal["info"]
    created_at: datetime
    link: str


class AnnounceSyncResponse(BaseModel):
    trigger: AnnounceSyncTrigger
    cursor_from: datetime | None = None
    cursor_to: datetime
    synced_at: datetime
    items: list[AnnounceSyncItem]
