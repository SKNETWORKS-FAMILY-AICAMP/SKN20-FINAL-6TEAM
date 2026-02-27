from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=50, max_length=5000)


class TestLoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=1, max_length=100)
    type_code: str | None = Field(None, pattern=r"^U\d{7}$")


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    google_email: str
    username: str
    type_code: str
    profile_image: str | None = None


class LoginResponse(BaseModel):
    user: UserInfo
