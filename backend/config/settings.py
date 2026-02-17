import logging

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

_settings_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "bizi_db"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "JWT_SECRET_KEY is required. "
                'Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if v == "your-secret-key-change-in-production":
            raise ValueError("JWT_SECRET_KEY must not be the default value")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    # Cookie
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""

    # Environment
    ENVIRONMENT: str = "development"

    # Test login
    ENABLE_TEST_LOGIN: bool = False

    # Google OAuth2 (not used yet - test login)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # RAG Service
    RAG_SERVICE_URL: str = "http://rag:8001"
    RAG_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @model_validator(mode="after")
    def enforce_production_security(self) -> "Settings":
        """프로덕션 환경에서 보안 설정을 강제합니다."""
        if self.ENVIRONMENT == "production":
            # H-03: 프로덕션에서 COOKIE_SECURE 강제
            if not self.COOKIE_SECURE:
                _settings_logger.warning(
                    "프로덕션 환경에서 COOKIE_SECURE=false → true로 강제 변경합니다."
                )
                self.COOKIE_SECURE = True

            # M-03: 프로덕션에서 MYSQL_PASSWORD 빈 값 거부
            if not self.MYSQL_PASSWORD:
                raise ValueError(
                    "프로덕션 환경에서 MYSQL_PASSWORD가 설정되지 않았습니다."
                )

            # L-01: 프로덕션에서 테스트 로그인 강제 비활성화
            if self.ENABLE_TEST_LOGIN:
                _settings_logger.warning(
                    "프로덕션 환경에서 ENABLE_TEST_LOGIN=true → false로 강제 변경합니다."
                )
                self.ENABLE_TEST_LOGIN = False

            # M-02: 프로덕션에서 RAG_API_KEY 미설정 경고
            if not self.RAG_API_KEY:
                _settings_logger.warning(
                    "프로덕션 환경에서 RAG_API_KEY가 설정되지 않았습니다. "
                    "RAG 서비스 인증이 비활성화됩니다."
                )

            # M-01: 프로덕션에서 CORS localhost 자동 제거
            filtered = [
                o for o in self.CORS_ORIGINS
                if "localhost" not in o and "127.0.0.1" not in o
            ]
            if len(filtered) != len(self.CORS_ORIGINS):
                _settings_logger.warning(
                    "프로덕션 환경에서 CORS_ORIGINS에서 localhost를 제거합니다: %s",
                    [o for o in self.CORS_ORIGINS if o not in filtered],
                )
                self.CORS_ORIGINS = filtered if filtered else self.CORS_ORIGINS
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
