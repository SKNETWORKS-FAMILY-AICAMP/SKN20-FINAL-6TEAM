from pydantic import BaseModel, ConfigDict


class GoogleLoginRequest(BaseModel):
    id_token: str


class TestLoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    type_code: str | None = None


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    google_email: str
    username: str
    type_code: str


class LoginResponse(BaseModel):
    user: UserInfo
