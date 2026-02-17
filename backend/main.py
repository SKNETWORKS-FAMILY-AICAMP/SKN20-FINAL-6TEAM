import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config.settings import settings
from config.database import SessionLocal
from apps.auth.token_blacklist import cleanup_expired

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")

limiter = Limiter(key_func=get_remote_address)


async def _cleanup_blacklist_loop():
    """만료된 토큰 블랙리스트를 주기적으로 정리합니다."""
    while True:
        await asyncio.sleep(3600)  # 1시간마다
        try:
            db = SessionLocal()
            try:
                count = cleanup_expired(db)
                if count > 0:
                    logger.info("Cleaned up %d expired blacklist entries", count)
            finally:
                db.close()
        except Exception:
            logger.exception("Blacklist cleanup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_blacklist_loop())
    yield
    task.cancel()

# Import routers
from apps.auth.router import router as auth_router
from apps.users.router import router as users_router
from apps.companies.router import router as companies_router
from apps.histories.router import router as histories_router
from apps.schedules.router import router as schedules_router
from apps.admin.router import router as admin_router
from apps.rag.router import router as rag_router

_docs_url = "/docs" if settings.ENVIRONMENT != "production" else None
_redoc_url = "/redoc" if settings.ENVIRONMENT != "production" else None

app = FastAPI(
    title="Bizi API",
    description="통합 창업/경영 상담 챗봇 백엔드 API",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
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
            is_json = "application/json" in content_type
            is_multipart = "multipart/form-data" in content_type

            # JSON은 브라우저 폼에서 설정 불가 → CSRF-safe
            # multipart는 X-Requested-With 헤더 필요
            # 그 외 커스텀 헤더(X-Requested-With)가 있으면 허용
            if not (is_json or (is_multipart and x_requested) or x_requested):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed"},
                )
        return await call_next(request)


app.add_middleware(CSRFMiddleware)


# 감사 로깅 미들웨어 (M9)
class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """요청을 구조화 감사 로깅하는 미들웨어."""

    AUDIT_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        request_id = str(uuid.uuid4())[:8]
        response = await call_next(request)
        duration = time.time() - start

        if request.method in self.AUDIT_METHODS:
            client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.client.host if request.client else "unknown"
            audit_logger.info(
                "req_id=%s method=%s path=%s status=%d ip=%s duration=%.3fs",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                client_ip,
                duration,
            )

        return response


app.add_middleware(AuditLoggingMiddleware)

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
app.include_router(rag_router)


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


# 프로덕션 환경에서 스택 트레이스 노출 방지
if settings.ENVIRONMENT == "production":

    @app.exception_handler(Exception)
    async def production_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
