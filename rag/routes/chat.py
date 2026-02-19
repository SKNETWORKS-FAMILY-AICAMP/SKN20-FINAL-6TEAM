"""채팅 엔드포인트 (일반 + 스트리밍)."""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from routes import _state
from schemas import ChatRequest, ChatResponse
from schemas.response import StreamResponse
from utils.cache import get_response_cache
from utils.chat_logger import log_chat_interaction
from utils.config import get_settings
from utils.token_tracker import RequestTokenTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """사용자 메시지를 처리하고 AI 응답을 반환합니다."""
    if not _state.router_agent:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    try:
        # 캐시 조회
        settings = get_settings()
        cache = get_response_cache() if settings.enable_response_cache else None
        if cache:
            cached = cache.get(request.message)
            if cached:
                logger.info("[chat] 캐시 히트: '%s...'", request.message[:30])
                cached_response = ChatResponse(**cached)
                cached_response.session_id = request.session_id
                return cached_response

        start_time = time.time()

        async with RequestTokenTracker() as tracker:
            response = await _state.router_agent.aprocess(
                query=request.message,
                user_context=request.user_context,
                history=[msg.model_dump() for msg in request.history],
            )
            response.session_id = request.session_id
            token_usage = tracker.get_usage()

        response_time = time.time() - start_time

        log_chat_interaction(
            question=request.message,
            answer=response.content,
            sources=response.sources,
            domains=response.domains,
            response_time=response_time,
            evaluation=response.evaluation,
            token_usage=token_usage,
        )

        # evaluation_data 생성
        try:
            from schemas.response import EvaluationDataForDB

            ragas_dict = response.ragas_metrics or {}
            eval_llm_score = response.evaluation.total_score if response.evaluation else None
            eval_llm_passed = response.evaluation.passed if response.evaluation else None
            contexts = [
                s.content[:500] for s in response.sources[:5]
                if hasattr(s, 'content')
            ]

            eval_data = EvaluationDataForDB(
                faithfulness=ragas_dict.get("faithfulness"),
                answer_relevancy=ragas_dict.get("answer_relevancy"),
                context_precision=ragas_dict.get("context_precision"),
                context_recall=ragas_dict.get("context_recall"),
                llm_score=eval_llm_score,
                llm_passed=eval_llm_passed,
                contexts=contexts,
                domains=response.domains,
                response_time=response_time,
            )
            response.evaluation_data = eval_data
        except Exception as e:
            logger.warning("비스트리밍 evaluation_data 생성 실패: %s", e)

        # 캐시 저장
        if cache and response.content != settings.fallback_message:
            domain = response.domains[0] if response.domains else None
            cache.set(request.message, response.model_dump(mode="json"), domain)

        return response
    except Exception as e:
        logger.error(f"채팅 처리 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="채팅 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 스트리밍 채팅 엔드포인트."""
    if not _state.router_agent:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다")

    async def generate():
        try:
            # 캐시 조회
            settings = get_settings()
            cache = get_response_cache() if settings.enable_response_cache else None
            if cache:
                cached = cache.get(request.message)
                if cached:
                    logger.info("[stream] 캐시 히트: '%s...'", request.message[:30])
                    cached_content = cached.get("content", "")
                    chunk_size = 4
                    token_index = 0
                    for i in range(0, len(cached_content), chunk_size):
                        text_chunk = cached_content[i:i + chunk_size]
                        stream_chunk = StreamResponse(
                            type="token",
                            content=text_chunk,
                            metadata={"index": token_index},
                        )
                        yield f"data: {stream_chunk.model_dump_json()}\n\n"
                        token_index += 1

                    for src in cached.get("sources", []):
                        source_chunk = StreamResponse(
                            type="source",
                            content=(src.get("content", "") or "")[:100],
                            metadata={
                                "title": src.get("title", ""),
                                "source": src.get("source", ""),
                                "url": src.get("url", ""),
                            },
                        )
                        yield f"data: {source_chunk.model_dump_json()}\n\n"

                    cached_domains = cached.get("domains", [])
                    done_chunk = StreamResponse(
                        type="done",
                        metadata={
                            "domain": cached_domains[0] if cached_domains else "general",
                            "domains": cached_domains,
                            "response_time": 0.0,
                            "cached": True,
                        },
                    )
                    yield f"data: {done_chunk.model_dump_json()}\n\n"
                    return

            start_time = time.time()
            stream_timeout = settings.total_timeout
            final_content = ""
            final_sources: list[Any] = []
            final_domains: list[str] = []
            final_actions: list[Any] = []
            token_usage = None
            done_evaluation = None
            done_ragas_metrics = None
            done_retrieval_results = None

            async with RequestTokenTracker() as tracker:
                token_index = 0
                async for chunk in _state.router_agent.astream(
                    query=request.message,
                    user_context=request.user_context,
                    history=[msg.model_dump() for msg in request.history],
                ):
                    if time.time() - start_time > stream_timeout:
                        error_chunk = StreamResponse(
                            type="error",
                            content="응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
                        )
                        yield f"data: {error_chunk.model_dump_json()}\n\n"
                        return
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
                        done_evaluation = chunk.get("evaluation")
                        done_ragas_metrics = chunk.get("ragas_metrics")
                        done_retrieval_results = chunk.get("retrieval_results")
                token_usage = tracker.get_usage()

            response_time = time.time() - start_time

            log_chat_interaction(
                question=request.message,
                answer=final_content,
                sources=final_sources,
                domains=final_domains,
                response_time=response_time,
                evaluation=done_evaluation,
                token_usage=token_usage,
            )

            # 출처 정보
            for source in final_sources:
                source_chunk = StreamResponse(
                    type="source",
                    content=source.content[:100] if hasattr(source, 'content') else "",
                    metadata={
                        "title": source.title if hasattr(source, 'title') else "",
                        "source": source.source if hasattr(source, 'source') else "",
                        "url": source.url if hasattr(source, 'url') else "",
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

            # 캐시 저장
            if cache and final_content and final_content != settings.fallback_message:
                cache_domain = final_domains[0] if final_domains else None
                cache_data = {
                    "content": final_content,
                    "domains": final_domains,
                    "sources": [
                        {
                            "content": s.content if hasattr(s, 'content') else "",
                            "title": s.title if hasattr(s, 'title') else "",
                            "source": s.source if hasattr(s, 'source') else "",
                            "url": s.url if hasattr(s, 'url') else "",
                        }
                        for s in final_sources
                    ],
                }
                cache.set(request.message, cache_data, cache_domain)

            # evaluation_data 생성
            eval_data_dict = None
            try:
                from schemas.response import EvaluationDataForDB, RetrievalEvaluationData

                ragas_dict = {}
                if done_ragas_metrics:
                    ragas_dict = done_ragas_metrics if isinstance(done_ragas_metrics, dict) else done_ragas_metrics.to_dict()

                eval_llm_score = done_evaluation.total_score if done_evaluation else None
                eval_llm_passed = done_evaluation.passed if done_evaluation else None
                contexts = [
                    s.content[:500] for s in final_sources[:5]
                    if hasattr(s, 'content')
                ]

                retrieval_eval = None
                if done_retrieval_results:
                    total_doc_count = 0
                    total_kw_ratio = 0.0
                    total_sim = 0.0
                    any_mq = False
                    all_passed = True
                    eval_count = 0
                    for _domain, result in done_retrieval_results.items():
                        if result and hasattr(result, 'evaluation') and result.evaluation:
                            er = result.evaluation
                            total_doc_count += er.doc_count
                            total_kw_ratio += er.keyword_match_ratio
                            total_sim += er.avg_similarity_score
                            any_mq = any_mq or getattr(result, 'used_multi_query', False)
                            all_passed = all_passed and er.passed
                            eval_count += 1
                    if eval_count > 0:
                        retrieval_eval = RetrievalEvaluationData(
                            status="PASS" if all_passed else "FAIL",
                            doc_count=total_doc_count,
                            keyword_match_ratio=total_kw_ratio / eval_count,
                            avg_similarity=total_sim / eval_count,
                            used_multi_query=any_mq,
                        )

                eval_data = EvaluationDataForDB(
                    faithfulness=ragas_dict.get("faithfulness"),
                    answer_relevancy=ragas_dict.get("answer_relevancy"),
                    context_precision=ragas_dict.get("context_precision"),
                    context_recall=ragas_dict.get("context_recall"),
                    llm_score=eval_llm_score,
                    llm_passed=eval_llm_passed,
                    contexts=contexts,
                    domains=final_domains,
                    retrieval_evaluation=retrieval_eval,
                    response_time=response_time,
                )
                eval_data_dict = eval_data.model_dump()
            except Exception as e:
                logger.warning("스트리밍 evaluation_data 생성 실패: %s", e)

            done_chunk = StreamResponse(
                type="done",
                metadata={
                    "domain": final_domains[0] if final_domains else "general",
                    "domains": final_domains,
                    "response_time": response_time,
                    "evaluation_data": eval_data_dict,
                },
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            logger.error("스트리밍 채팅 오류: %s", e, exc_info=True)
            error_chunk = StreamResponse(
                type="error",
                content="죄송합니다. 요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
