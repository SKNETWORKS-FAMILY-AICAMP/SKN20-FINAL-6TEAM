from pydantic import BaseModel, Field

MAX_MESSAGE_LENGTH = 2000


class RagChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=5000)


class RagChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: list[RagChatMessage] = Field(default_factory=list, max_length=50)
