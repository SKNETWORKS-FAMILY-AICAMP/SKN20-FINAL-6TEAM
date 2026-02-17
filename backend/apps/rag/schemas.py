from pydantic import BaseModel, Field

MAX_MESSAGE_LENGTH = 2000


class RagChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
