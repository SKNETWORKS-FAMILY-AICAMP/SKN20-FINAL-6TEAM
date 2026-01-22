from pydantic import BaseModel
from datetime import datetime


class HistoryCreate(BaseModel):
    agent_code: str
    question: str
    answer: str
    parent_history_id: int | None = None


class HistoryResponse(BaseModel):
    history_id: int
    user_id: int
    agent_code: str | None = None
    question: str | None = None
    answer: str | None = None
    parent_history_id: int | None = None
    create_date: datetime | None = None

    class Config:
        from_attributes = True
