from pydantic import BaseModel, ConfigDict
from datetime import datetime


class HistoryCreate(BaseModel):
    agent_code: str
    question: str
    answer: str
    parent_history_id: int | None = None


class HistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    user_id: int
    agent_code: str | None = None
    question: str | None = None
    answer: str | None = None
    parent_history_id: int | None = None
    create_date: datetime | None = None
