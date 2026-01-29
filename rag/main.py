"""RAG 서비스 FastAPI 진입점.

Bizi의 RAG 서비스 API 서버를 구동합니다.
프론트엔드와 직접 통신하여 채팅, 문서 생성 등의 기능을 제공합니다.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

# 로그 파일 설정
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOG_DIR / "chat.log"

# 로깅 설정 (로테이션 적용)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 채팅 로그용 별도 핸들러 (로테이션: 10MB, 최대 5개 파일)
chat_logger = logging.getLogger("chat")
chat_logger.setLevel(logging.INFO)
chat_handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
chat_handler.setFormatter(logging.Formatter("%(message)s"))
chat_logger.addHandler(chat_handler)
chat_logger.propagate = False
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents import ActionExecutor, MainRouter
from schemas import (
    ChatRequest,
    ChatResponse,
    ContractRequest,
    DocumentResponse,
)
from schemas.response import HealthResponse, StreamResponse
from utils.config import get_settings
from utils.middleware import (
    RateLimitMiddleware,
    MetricsMiddleware,
    MetricsCollector,
    get_metrics_collector,
)
from utils.cache import get_response_cache
from vectorstores.chroma import ChromaVectorStore


# 설정 로드
settings = get_settings()

# 메트릭 수집기 초기화
metrics_collector = get_metrics_collector()


def log_chat_interaction(
    question: str,
    answer: str,
    sources: list,
    domains: list[str],
    response_time: float,
    evaluation: Any = None,
) -> None:
    """채팅 상호작용을 로그 파일에 기록합니다.

    Args:
        question: 사용자 질문
        answer: AI 응답
        sources: 참고 문서 리스트
        domains: 처리된 도메인 리스트
        response_time: 응답 시간 (초)
        evaluation: 평가 결과 (선택)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_entry = f"""
{'='*80}
[{timestamp}] Response Time: {response_time:.2f}초
{'='*80}

[Q] {question}

[A] {answer}

[도메인] {', '.join(domains)}

[참고문서]
"""

    # 유효한 참고문서만 필터링 (content가 있는 것만)
    valid_sources = [s for s in sources if s.content and s.content.strip()]

    if valid_sources:
        for i, source in enumerate(valid_sources, 1):
            # SourceDocument (Pydantic 모델) 처리
            title = source.title
            src = source.source
            content = source.content

            # metadata에서 추가 정보 추출
            if source.metadata:
                if not title:
                    title = source.metadata.get("title")
                if not src:
                    src = (
                        source.metadata.get("source_name")
                        or source.metadata.get("source_file")
                        or source.metadata.get("source")
                    )

            title = title or "제목 없음"
            src = src or "출처 없음"
            content_preview = content[:200] + "..." if len(content) > 200 else content
            log_entry += f"  [{i}] {title}\n      출처: {src}\n      내용: {content_preview}\n\n"
    else:
        log_entry += "  (참고문서 없음 - VectorDB 데이터 확인 필요)\n"

    if evaluation:
        log_entry += f"\n[평가] 점수: {evaluation.total_score}, 통과: {evaluation.passed}\n"

    log_entry += "\n"

    # 로테이션 로거로 기록
    chat_logger.info(log_entry)

# 전역 인스턴스
router_agent: MainRouter | None = None
executor: ActionExecutor | None = None
vector_store: ChromaVectorStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리."""
    global router_agent, executor, vector_store

    # 시작 시 초기화
    logger.info("RAG 서비스 초기화 중...")
    # 공유 벡터 스토어 생성 후 MainRouter에 주입
    vector_store = ChromaVectorStore()
    router_agent = MainRouter(vector_store=vector_store)
    executor = ActionExecutor()
    logger.info("RAG 서비스 초기화 완료")

    yield

    # 종료 시 정리
    logger.info("RAG 서비스 종료 중...")
    if vector_store:
        vector_store.close()
    logger.info("RAG 서비스 종료 완료")


# FastAPI 앱 생성
app = FastAPI(
    title="Bizi RAG Service",
    description="통합 창업/경영 상담 챗봇 RAG 서비스",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 메트릭 수집 미들웨어
app.add_middleware(MetricsMiddleware, collector=metrics_collector)

# Rate Limiting 미들웨어 (설정에 따라)
if settings.enable_rate_limit:
    app.add_middleware(
        RateLimitMiddleware,
        rate=settings.rate_limit_rate,
        capacity=settings.rate_limit_capacity,
    )
    logger.info(f"Rate Limiting 활성화: rate={settings.rate_limit_rate}/s, capacity={settings.rate_limit_capacity}")


# ============================================================
# 헬스체크 엔드포인트
# ============================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """헬스체크 엔드포인트.

    서비스 상태와 VectorDB 상태, OpenAI 연결 상태를 반환합니다.
    """
    vectordb_status: dict[str, Any] = {}
    openai_status: dict[str, Any] = {"status": "unknown"}
    overall_status = "healthy"

    # VectorDB 상태 확인
    if vector_store:
        try:
            stats = vector_store.get_all_stats()
            vectordb_status = {
                domain: {"count": info.get("count", 0)}
                for domain, info in stats.items()
                if "error" not in info
            }
        except Exception as e:
            vectordb_status = {"error": str(e)}
            overall_status = "degraded"

    # OpenAI API 연결 상태 확인
    try:
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        # 간단한 모델 목록 조회로 연결 확인
        client.models.list(limit=1)
        openai_status = {"status": "connected", "model": settings.openai_model}
    except openai.AuthenticationError:
        openai_status = {"status": "error", "message": "API 키가 유효하지 않습니다"}
        overall_status = "unhealthy"
    except openai.APIConnectionError:
        openai_status = {"status": "error", "message": "OpenAI 서버에 연결할 수 없습니다"}
        overall_status = "unhealthy"
    except Exception as e:
        openai_status = {"status": "error", "message": str(e)}
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        vectordb_status=vectordb_status,
        openai_status=openai_status,
    )


# ============================================================
# 채팅 엔드포인트
# ============================================================


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """채팅 엔드포인트.

    사용자 메시지를 처리하고 AI 응답을 반환합니다.

    Args:
        request: 채팅 요청

    Returns:
        채팅 응답
    """
    if not router_agent:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        # 시작 시간 기록
        start_time = time.time()

        response = await router_agent.aprocess(
            query=request.message,
            user_context=request.user_context,
        )
        response.session_id = request.session_id

        # 응답 시간 계산
        response_time = time.time() - start_time

        # 로그 기록
        log_chat_interaction(
            question=request.message,
            answer=response.content,
            sources=response.sources,
            domains=response.domains,
            response_time=response_time,
            evaluation=response.evaluation,
        )

        return response
    except Exception as e:
        logger.error(f"채팅 처리 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="채팅 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


@app.post("/api/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """스트리밍 채팅 엔드포인트.

    SSE(Server-Sent Events)를 사용하여 응답을 스트리밍합니다.
    단일 도메인 질문은 진정한 토큰 스트리밍, 복합 도메인은 전체 응답 후 스트리밍.

    Args:
        request: 채팅 요청

    Returns:
        스트리밍 응답
    """
    if not router_agent:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    async def generate():
        try:
            # 시작 시간 기록
            start_time = time.time()
            final_content = ""
            final_sources = []
            final_domains = []
            final_actions = []

            # 진정한 스트리밍 (MainRouter.astream 사용)
            token_index = 0
            async for chunk in router_agent.astream(
                query=request.message,
                user_context=request.user_context,
            ):
                if chunk["type"] == "token":
                    stream_chunk = StreamResponse(
                        type="token",
                        content=chunk["content"],
                        metadata={"index": token_index},
                    )
                    yield f"data: {stream_chunk.model_dump_json()}\n\n"
                    token_index += 1
                elif chunk["type"] == "done":
                    final_content = chunk["content"]
                    final_sources = chunk.get("sources", [])
                    final_domains = chunk.get("domains", [])
                    final_actions = chunk.get("actions", [])

            # 응답 시간 계산
            response_time = time.time() - start_time

            # 로그 기록
            log_chat_interaction(
                question=request.message,
                answer=final_content,
                sources=final_sources,
                domains=final_domains,
                response_time=response_time,
                evaluation=chunk.get("evaluation"),
            )

            # 출처 정보
            for source in final_sources:
                source_chunk = StreamResponse(
                    type="source",
                    content=source.content[:100] if hasattr(source, 'content') else "",
                    metadata={
                        "title": source.title if hasattr(source, 'title') else "",
                        "source": source.source if hasattr(source, 'source') else "",
                    },
                )
                yield f"data: {source_chunk.model_dump_json()}\n\n"

            # 액션 정보
            for action in final_actions:
                action_chunk = StreamResponse(
                    type="action",
                    content=action.label if hasattr(action, 'label') else "",
                    metadata={
                        "type": action.type if hasattr(action, 'type') else "",
                        "params": action.params if hasattr(action, 'params') else {},
                    },
                )
                yield f"data: {action_chunk.model_dump_json()}\n\n"

            # 완료
            done_chunk = StreamResponse(
                type="done",
                metadata={
                    "domain": final_domains[0] if final_domains else "general",
                    "domains": final_domains,
                    "response_time": response_time,
                },
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"스트리밍 채팅 오류: {e}")
            error_chunk = StreamResponse(
                type="error",
                content=str(e),
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


# ============================================================
# 문서 생성 엔드포인트
# ============================================================


@app.post("/api/documents/contract", response_model=DocumentResponse, tags=["Documents"])
async def generate_contract(request: ContractRequest) -> DocumentResponse:
    """근로계약서 생성 엔드포인트.

    Args:
        request: 근로계약서 생성 요청

    Returns:
        문서 생성 응답
    """
    if not executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        return executor.generate_labor_contract(request)
    except Exception as e:
        logger.error(f"근로계약서 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 생성 중 오류가 발생했습니다. 입력 정보를 확인해주세요."
        )


@app.post("/api/documents/business-plan", response_model=DocumentResponse, tags=["Documents"])
async def generate_business_plan(
    format: str = Query(default="docx", description="출력 형식"),
) -> DocumentResponse:
    """사업계획서 템플릿 생성 엔드포인트.

    Args:
        format: 출력 형식 (docx)

    Returns:
        문서 생성 응답
    """
    if not executor:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        return executor.generate_business_plan_template(format=format)
    except Exception as e:
        logger.error(f"사업계획서 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="문서 생성 중 오류가 발생했습니다."
        )


# ============================================================
# 지원사업 검색 엔드포인트
# ============================================================


@app.get("/api/funding/search", tags=["Funding"])
async def search_funding(
    query: str = Query(description="검색 키워드"),
    k: int = Query(default=10, description="검색 결과 개수"),
) -> dict[str, Any]:
    """지원사업 검색 엔드포인트.

    VectorDB에서 지원사업 공고를 검색합니다.

    Args:
        query: 검색 키워드
        k: 검색 결과 개수

    Returns:
        검색 결과
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        results = vector_store.similarity_search(
            query=query,
            domain="startup_funding",
            k=k,
        )

        return {
            "query": query,
            "count": len(results),
            "results": [
                {
                    "content": doc.page_content[:500],
                    "metadata": doc.metadata,
                }
                for doc in results
            ],
        }
    except Exception as e:
        logger.error(f"지원사업 검색 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


# ============================================================
# VectorDB 관리 엔드포인트
# ============================================================


@app.get("/api/vectordb/stats", tags=["VectorDB"])
async def vectordb_stats() -> dict[str, Any]:
    """VectorDB 통계 엔드포인트.

    Returns:
        VectorDB 통계 정보
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        return vector_store.get_all_stats()
    except Exception as e:
        logger.error(f"VectorDB 통계 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="통계 조회 중 오류가 발생했습니다."
        )


@app.get("/api/vectordb/collections", tags=["VectorDB"])
async def list_collections() -> dict[str, Any]:
    """VectorDB 컬렉션 목록 엔드포인트.

    Returns:
        컬렉션 목록
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        collections = vector_store.list_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"컬렉션 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="컬렉션 목록 조회 중 오류가 발생했습니다."
        )


# ============================================================
# 메트릭 및 캐시 엔드포인트
# ============================================================


@app.get("/api/metrics", tags=["Monitoring"])
async def get_metrics(
    window: int = Query(default=3600, description="통계 윈도우 (초)"),
) -> dict[str, Any]:
    """메트릭 조회 엔드포인트.

    Args:
        window: 통계 계산 윈도우 (초, 기본 1시간)

    Returns:
        메트릭 통계
    """
    return metrics_collector.get_stats(window_seconds=window)


@app.get("/api/metrics/endpoints", tags=["Monitoring"])
async def get_endpoint_metrics() -> dict[str, Any]:
    """엔드포인트별 메트릭 조회.

    Returns:
        엔드포인트별 통계
    """
    return metrics_collector.get_endpoint_stats()


@app.get("/api/cache/stats", tags=["Monitoring"])
async def get_cache_stats() -> dict[str, Any]:
    """캐시 통계 조회 엔드포인트.

    Returns:
        캐시 통계 (히트율, 크기 등)
    """
    try:
        cache = get_response_cache()
        return cache.get_stats()
    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: {e}", exc_info=True)
        return {"error": "캐시 통계를 조회할 수 없습니다."}


@app.post("/api/cache/clear", tags=["Monitoring"])
async def clear_cache() -> dict[str, Any]:
    """캐시 전체 삭제 엔드포인트.

    Returns:
        삭제된 항목 수
    """
    try:
        cache = get_response_cache()
        count = cache.clear()
        return {"cleared": count, "message": f"{count}개 캐시 항목이 삭제되었습니다"}
    except Exception as e:
        logger.error(f"캐시 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="캐시 삭제 중 오류가 발생했습니다."
        )


@app.get("/api/config", tags=["Monitoring"])
async def get_config() -> dict[str, Any]:
    """현재 설정 조회 엔드포인트 (민감 정보 제외).

    Returns:
        현재 설정 값
    """
    return {
        "openai_model": settings.openai_model,
        "openai_temperature": settings.openai_temperature,
        "retrieval_k": settings.retrieval_k,
        "retrieval_k_common": settings.retrieval_k_common,
        "mmr_lambda_mult": settings.mmr_lambda_mult,
        "evaluation_threshold": settings.evaluation_threshold,
        "max_retry_count": settings.max_retry_count,
        "enable_query_rewrite": settings.enable_query_rewrite,
        "enable_hybrid_search": settings.enable_hybrid_search,
        "enable_reranking": settings.enable_reranking,
        "enable_context_compression": settings.enable_context_compression,
        "enable_response_cache": settings.enable_response_cache,
        "cache_ttl": settings.cache_ttl,
        "enable_rate_limit": settings.enable_rate_limit,
        "llm_timeout": settings.llm_timeout,
        "enable_fallback": settings.enable_fallback,
    }


# ============================================================
# 메인 실행
# ============================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
