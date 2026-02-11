from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    id_token: str


class TestLoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    type_code: str | None = None


class UserInfo(BaseModel):
    user_id: int
    google_email: str
    username: str
    type_code: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    user: UserInfo
