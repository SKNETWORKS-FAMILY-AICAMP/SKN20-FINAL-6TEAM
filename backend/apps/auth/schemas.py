from pydantic import BaseModel, EmailStr
from datetime import datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleLoginRequest(BaseModel):
    code: str


class TestLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    user_id: int
    google_email: str
    username: str
    type_code: str

    class Config:
        from_attributes = True


TestLoginResponse.model_rebuild()
