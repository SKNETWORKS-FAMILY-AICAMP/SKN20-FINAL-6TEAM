from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config.settings import settings

limiter = Limiter(key_func=get_remote_address)

# Import routers
from apps.auth.router import router as auth_router
from apps.users.router import router as users_router
from apps.companies.router import router as companies_router
from apps.histories.router import router as histories_router
from apps.schedules.router import router as schedules_router
from apps.admin.router import router as admin_router

_docs_url = "/docs" if settings.ENVIRONMENT != "production" else None
_redoc_url = "/redoc" if settings.ENVIRONMENT != "production" else None

app = FastAPI(
    title="Bizi API",
    description="통합 창업/경영 상담 챗봇 백엔드 API",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"],
)


# CSRF 보호 미들웨어
class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 보호 미들웨어.

    POST/PUT/DELETE 요청에서 Content-Type: application/json 또는
    X-Requested-With 헤더를 요구합니다.
    HTML form은 application/json을 설정할 수 없으므로 CSRF 공격을 차단합니다.
    """

    MUTATING_METHODS = ("POST", "PUT", "DELETE", "PATCH")

    async def dispatch(self, request: Request, call_next):
        if request.method in self.MUTATING_METHODS:
            content_type = request.headers.get("content-type", "")
            x_requested = request.headers.get("x-requested-with", "")
            if "application/json" not in content_type and "multipart/form-data" not in content_type and not x_requested:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed"},
                )
        return await call_next(request)


app.add_middleware(CSRFMiddleware)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 라우터 등록
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(companies_router)
app.include_router(histories_router)
app.include_router(schedules_router)
app.include_router(admin_router)


@app.get("/")
async def root() -> dict[str, str]:
    result: dict[str, str] = {"message": "Welcome to Bizi API"}
    if _docs_url:
        result["docs"] = _docs_url
    if _redoc_url:
        result["redoc"] = _redoc_url
    return result


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
