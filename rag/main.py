"""RAG 서비스 FastAPI 진입점.

Bizi의 RAG 서비스 API 서버를 구동합니다.
프론트엔드와 직접 통신하여 채팅, 문서 생성 등의 기능을 제공합니다.
"""

import asyncio
import contextvars
import hmac
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp as _ASGIApp, Receive as _Receive, Scope as _Scope, Send as _Send
from utils.config import get_settings
from utils.logging_utils import SensitiveDataFilter

# 요청 ID 컨텍스트 변수
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """로그 레코드에 request_id 속성을 추가하는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


class RequestIdMiddleware:
    """Backend에서 전달된 X-Request-ID를 ContextVar에 설정하는 순수 ASGI 미들웨어."""

    def __init__(self, app: _ASGIApp):
        self.app = app

    async def __call__(self, scope: _Scope, receive: _Receive, send: _Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            request_id = headers.get(b"x-request-id", b"-").decode("latin-1")
            _request_id_var.set(request_id)
        await self.app(scope, receive, send)


# 필터를 QueueHandler 진입 전(caller 스레드)에 실행 → ContextVar 정상 동작
root_logger = logging.getLogger()
root_logger.addFilter(RequestIdFilter())
root_logger.addFilter(SensitiveDataFilter())

# 비동기 로깅 설정: QueueHandler → QueueListener(백그라운드 스레드)로 파일 I/O 분리
from utils.async_logging import setup_async_logging, stop_async_logging
from utils.json_file_logger import create_json_file_handler

_root_level = getattr(logging, get_settings().log_level, logging.INFO)

# request_id 누락 시 안전하게 기본값 사용하는 포맷터
class _SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)

# 콘솔 핸들러
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(
    _SafeFormatter("%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s")
)
_console_handler.setLevel(_root_level)

# JSON 파일 핸들러 (생성 실패 시 None)
_file_handler = create_json_file_handler(service_name="rag")

_async_handlers: list[logging.Handler] = [_console_handler]
if _file_handler:
    _async_handlers.append(_file_handler)

setup_async_logging(handlers=_async_handlers, root_level=_root_level)
logger = logging.getLogger(__name__)

from agents import ActionExecutor, MainRouter
from routes import all_routers
import routes._state as state
from utils.config import init_db, load_domain_config
from utils.middleware import RateLimitMiddleware, MetricsMiddleware, get_metrics_collector
from utils.reranker import get_reranker
from vectorstores.chroma import ChromaVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 라이프사이클 관리."""
    logger.info("RAG 서비스 초기화 중...")

    # 도메인 설정 DB 초기화 + 로드
    init_db()
    load_domain_config()
    logger.info("도메인 설정 DB 초기화 완료")

    # 공유 벡터 스토어 생성 후 ChromaDB 연결 확인
    state.vector_store = ChromaVectorStore()
    health = state.vector_store.health_check()
    if health["status"] != "ok":
        logger.error("ChromaDB 연결 실패: %s", health.get("detail", "알 수 없는 오류"))
        settings = get_settings()
        logger.error("CHROMA_HOST=%s, CHROMA_PORT=%d", settings.chroma_host, settings.chroma_port)
    else:
        logger.info("ChromaDB 연결 성공 (heartbeat: %s)", health["heartbeat"])

    state.router_agent = MainRouter(vector_store=state.vector_store)
    state.executor = ActionExecutor()

    # Redis 연결 확인 (session_memory_backend=redis인 경우)
    if settings.session_memory_backend == "redis" and settings.redis_url:
        try:
            from routes._session_memory import _get_redis_client
            redis_client = await _get_redis_client()
            await redis_client.ping()
            logger.info("Redis 연결 성공 (%s)", settings.redis_url.split("@")[-1] if "@" in settings.redis_url else settings.redis_url)
        except Exception as exc:
            logger.error("Redis 연결 실패: %s (세션 메모리가 in-memory 폴백으로 동작합니다)", exc)

    # CrossEncoder 모델 사전 로딩 / RunPod warmup / ChromaDB warmup
    settings = get_settings()
    warmup_task: asyncio.Task | None = None

    if settings.enable_reranking and settings.embedding_provider == "local":
        logger.info("CrossEncoder 모델 사전 로딩 시작...")
        reranker = get_reranker()
        await asyncio.to_thread(lambda: reranker.model)
        logger.info("CrossEncoder 모델 사전 로딩 완료")
    elif settings.embedding_provider == "runpod":
        # 시작 시 1회 warmup (워커 깨우기)
        from utils.runpod_warmup import run_periodic_warmup, warmup_runpod
        success = await warmup_runpod()
        if success:
            logger.info("RunPod 초기 warmup 성공")
        else:
            logger.warning("RunPod 초기 warmup 실패 (서비스는 정상 시작)")

        # 주기적 warmup 백그라운드 태스크 시작
        if settings.enable_runpod_warmup:
            warmup_task = asyncio.create_task(
                run_periodic_warmup(settings.runpod_warmup_interval)
            )

    # ChromaDB 컬렉션 및 BM25 인덱스 사전 로딩
    if health["status"] == "ok" and settings.enable_chromadb_warmup:
        from utils.chromadb_warmup import warmup_chromadb
        chroma_ok = await warmup_chromadb(state.vector_store)
        if chroma_ok:
            logger.info("ChromaDB 초기 warmup 성공")
        else:
            logger.warning("ChromaDB 초기 warmup 실패 (서비스는 정상 시작)")

    # 도메인 벡터 사전 계산 (첫 요청 시 이벤트 루프 블로킹 방지)
    if settings.enable_vector_domain_classification:
        try:
            from utils.domain_classifier import get_domain_classifier
            classifier = get_domain_classifier()
            await classifier._aprecompute_vectors()
            logger.info("도메인 벡터 사전 계산 완료")
        except Exception as e:
            logger.warning("도메인 벡터 사전 계산 실패 (서비스는 정상 시작): %s", e)

    # 세션 마이그레이션 백그라운드 태스크
    migration_task: asyncio.Task | None = None
    if settings.enable_session_migration and settings.session_memory_backend == "redis":
        from jobs.session_migrator import session_migration_loop
        migration_task = asyncio.create_task(session_migration_loop())
        logger.info("세션 마이그레이션 루프 시작 (interval=%ds, threshold=%ds)",
                     settings.session_migrate_interval, settings.session_migrate_ttl_threshold)

    _log_settings_summary(settings)
    logger.info("RAG 서비스 초기화 완료")

    yield

    # 종료 시 정리
    logger.info("RAG 서비스 종료 중...")
    if migration_task:
        migration_task.cancel()
        try:
            await migration_task
        except asyncio.CancelledError:
            pass
    if warmup_task:
        warmup_task.cancel()
        try:
            await warmup_task
        except asyncio.CancelledError:
            pass
    # Redis 세션 클라이언트 정리
    from routes._session_memory import close_redis_client
    await close_redis_client()
    if state.vector_store:
        state.vector_store.close()
    logger.info("RAG 서비스 종료 완료")

    # 비동기 로깅 종료 (남은 로그 flush 후 스레드 정지)
    from utils.chat_logger import stop_chat_loggers
    stop_chat_loggers()
    stop_async_logging()


def _log_settings_summary(settings) -> None:
    """설정 요약을 로그에 출력합니다."""
    def _flag(v: bool) -> str:
        return "ON" if v else "OFF"

    if settings.embedding_provider == "runpod":
        embed_info = f"RunPod GPU (endpoint: {settings.runpod_endpoint_id})"
    else:
        embed_info = f"로컬 CPU ({settings.embedding_model})"

    if not settings.enable_reranking:
        rerank_info = "OFF"
    elif settings.embedding_provider == "runpod":
        rerank_info = "RunPod GPU"
    else:
        rerank_info = f"CrossEncoder ({settings.cross_encoder_model})"

    if settings.enable_llm_domain_classification:
        classify_info = "LLM 기반"
    elif settings.enable_vector_domain_classification:
        classify_info = "벡터 기반"
    else:
        classify_info = "키워드만"

    logger.info("=" * 60)
    logger.info("[RAG 설정 요약]")
    logger.info("  임베딩       : %s", embed_info)
    logger.info("  리랭킹       : %s", rerank_info)
    logger.info("  Hybrid Search : %s (weight: %.1f)", _flag(settings.enable_hybrid_search), settings.vector_search_weight)
    logger.info("  도메인 분류   : %s", classify_info)
    logger.info("  도메인 거부   : %s", _flag(settings.enable_domain_rejection))
    logger.info("  LLM 평가     : %s", _flag(settings.enable_llm_evaluation))
    logger.info("  RAGAS 평가   : %s", _flag(settings.enable_ragas_evaluation))
    logger.info("  법률 보충     : %s", f"ON (K={settings.legal_supplement_k})" if settings.enable_legal_supplement else "OFF")
    logger.info("  응답 캐시     : %s", _flag(settings.enable_response_cache))
    logger.info("  Rate Limit   : %s", f"ON (rate={settings.rate_limit_rate}/s, capacity={settings.rate_limit_capacity})" if settings.enable_rate_limit else "OFF")
    logger.info("  ChromaDB Warmup: %s", _flag(settings.enable_chromadb_warmup))
    logger.info("  로그 레벨     : %s", settings.log_level)
    logger.info("=" * 60)


# ============================================================
# FastAPI 앱 생성
# ============================================================

app = FastAPI(
    title="Bizi RAG Service",
    description="통합 창업/경영 상담 챗봇 RAG 서비스",
    version="1.0.0",
    lifespan=lifespan,
)

# 프로덕션 전역 예외 핸들러 (traceback 노출 방지)
_settings = get_settings()
if _settings.environment == "production":
    from fastapi import Request as _Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def production_exception_handler(_request: _Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Requested-With"],
)


# API Key 인증 미들웨어 (순수 ASGI — StreamingResponse 버퍼링 방지)
class APIKeyMiddleware:
    """RAG API Key 인증 미들웨어 (순수 ASGI)."""

    PROTECTED_PREFIXES = ("/api/chat", "/api/documents", "/api/funding", "/api/sessions")

    def __init__(self, app: _ASGIApp):
        self.app = app

    async def __call__(self, scope: _Scope, receive: _Receive, send: _Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        api_key = get_settings().rag_api_key
        if api_key and api_key.strip():
            path = scope.get("path", "")
            if any(path.startswith(prefix) for prefix in self.PROTECTED_PREFIXES):
                headers = dict(scope.get("headers", []))
                provided_key = headers.get(b"x-api-key", b"").decode("latin-1")
                if not hmac.compare_digest(provided_key, api_key):
                    body = b'{"detail":"Invalid or missing API key"}'
                    await send({
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({"type": "http.response.body", "body": body})
                    return

        await self.app(scope, receive, send)


if _settings.rag_api_key:
    app.add_middleware(APIKeyMiddleware)
    logger.info("RAG API Key 인증 활성화")

# 메트릭 수집 미들웨어
metrics_collector = get_metrics_collector()
app.add_middleware(MetricsMiddleware, collector=metrics_collector)

# Rate Limiting 미들웨어
if _settings.enable_rate_limit:
    app.add_middleware(
        RateLimitMiddleware,
        rate=_settings.rate_limit_rate,
        capacity=_settings.rate_limit_capacity,
        auth_multiplier=_settings.rate_limit_authenticated_multiplier,
    )
    logger.info(
        "Rate Limiting 활성화: rate=%.1f/s, capacity=%.0f, auth_multiplier=%.1f",
        _settings.rate_limit_rate, _settings.rate_limit_capacity,
        _settings.rate_limit_authenticated_multiplier,
    )

# Request ID 미들웨어 (순수 ASGI — 가장 외곽에서 request_id를 ContextVar에 설정)
app.add_middleware(RequestIdMiddleware)

# 라우터 등록
for r in all_routers:
    app.include_router(r)


# ============================================================
# 메인 실행
# ============================================================

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
