"""채팅 엔드포인트 (일반 + 스트리밍)."""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from routes import _state
from routes._session_memory import (
    append_session_turn,
    get_session_history,
    upsert_session_history,
)
from schemas import ChatRequest, ChatResponse
from schemas.response import StreamResponse
from utils.cache import get_response_cache
from utils.chat_logger import log_chat_interaction
from utils.config import get_settings
from utils.sanitizer import sanitize_query
from utils.token_tracker import RequestTokenTracker

logger = logging.getLogger(__name__)

# 감지 패턴 수가 임계값 이상이면 HTTP 400 반환
_SEVERE_INJECTION_THRESHOLD = 3

router = APIRouter(prefix="/api", tags=["Chat"])


def _build_effective_history(request: ChatRequest) -> list[dict[str, str]]:
    return [msg.model_dump() for msg in request.history]


def _build_owner_key(request: ChatRequest) -> str:
    user_id = request.user_context.user_id if request.user_context else None
    if user_id:
        return f"user:{user_id}"
    return "anon"


def _build_cache_query(query: str, history: list[dict[str, str]]) -> str:
    if not history:
        return query
    snapshot = [
        {
            "role": msg.get("role", ""),
            "content": str(msg.get("content", ""))[:200],
        }
        for msg in history[-8:]
    ]
    digest = hashlib.md5(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    return f"{query}\n#h:{digest}"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """사용자 메시지를 처리하고 AI 응답을 반환합니다."""
    if not _state.router_agent:
        raise HTTPException(status_code=503, detail="Service not initialized.")

    # 프롬프트 인젝션 방어
    sanitize_result = sanitize_query(request.message)
    if len(sanitize_result.detected_patterns) >= _SEVERE_INJECTION_THRESHOLD:
        raise HTTPException(status_code=400, detail="요청이 보안 정책에 의해 차단되었습니다.")
    query = sanitize_result.sanitized_query
    owner_key = _build_owner_key(request)
    request_history = _build_effective_history(request)
    effective_history = request_history
    if request.session_id:
        if request_history:
            await upsert_session_history(owner_key, request.session_id, request_history)
        else:
            effective_history = await get_session_history(owner_key, request.session_id)
    cache_query = _build_cache_query(query, effective_history)

    try:
        # 캐시 조회 (user_context 해시 포함)
        settings = get_settings()
        cache = get_response_cache() if settings.enable_response_cache else None
        uc_hash = request.user_context.get_filter_hash() if request.user_context else None
        if cache:
            cached = cache.get(cache_query, user_context_hash=uc_hash)
            if cached:
                logger.info("[chat] 캐시 히트: '%s...'", query[:30])
                cached_response = ChatResponse(**cached)
                cached_response.session_id = request.session_id
                await append_session_turn(
                    owner_key,
                    request.session_id,
                    request.message,
                    cached_response.content,
                )
                return cached_response

        start_time = time.time()

        async with RequestTokenTracker() as tracker:
            response = await _state.router_agent.aprocess(
                query=query,
                user_context=request.user_context,
                history=effective_history,
            )
            response.session_id = request.session_id
            token_usage = tracker.get_usage()

        await append_session_turn(
            owner_key,
            request.session_id,
            request.message,
            response.content,
        )

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
                if hasattr(s, "content")
            ]
            existing_eval_data = response.evaluation_data

            eval_data = EvaluationDataForDB(
                faithfulness=ragas_dict.get("faithfulness"),
                answer_relevancy=ragas_dict.get("answer_relevancy"),
                context_precision=ragas_dict.get("context_precision"),
                context_recall=ragas_dict.get("context_recall"),
                llm_score=eval_llm_score,
                llm_passed=eval_llm_passed,
                contexts=contexts,
                domains=response.domains,
                retrieval_evaluation=(
                    existing_eval_data.retrieval_evaluation
                    if existing_eval_data else None
                ),
                query_rewrite_applied=(
                    existing_eval_data.query_rewrite_applied
                    if existing_eval_data else None
                ),
                query_rewrite_reason=(
                    existing_eval_data.query_rewrite_reason
                    if existing_eval_data else None
                ),
                query_rewrite_time=(
                    existing_eval_data.query_rewrite_time
                    if existing_eval_data else None
                ),
                timeout_cause=(
                    existing_eval_data.timeout_cause
                    if existing_eval_data else None
                ),
                response_time=response_time,
            )
            response.evaluation_data = eval_data
        except Exception as e:
            logger.warning("일반 응답 evaluation_data 생성 실패: %s", e)

        # 캐시 저장
        if cache and response.content != settings.fallback_message:
            domain = response.domains[0] if response.domains else None
            cache.set(cache_query, response.model_dump(mode="json"), domain, user_context_hash=uc_hash)

        return response
    except Exception as e:
        logger.error("채팅 처리 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="채팅 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 스트리밍 채팅 엔드포인트."""
    if not _state.router_agent:
        raise HTTPException(status_code=503, detail="Service not initialized.")

    # 프롬프트 인젝션 방어
    sanitize_result = sanitize_query(request.message)
    if len(sanitize_result.detected_patterns) >= _SEVERE_INJECTION_THRESHOLD:
        raise HTTPException(status_code=400, detail="요청이 보안 정책에 의해 차단되었습니다.")
    stream_query = sanitize_result.sanitized_query
    owner_key = _build_owner_key(request)
    request_history = _build_effective_history(request)
    effective_history = request_history
    if request.session_id:
        if request_history:
            await upsert_session_history(owner_key, request.session_id, request_history)
        else:
            effective_history = await get_session_history(owner_key, request.session_id)
    cache_query = _build_cache_query(stream_query, effective_history)

    async def generate():
        try:
            # 캐시 조회 (user_context 해시 포함)
            settings = get_settings()
            cache = get_response_cache() if settings.enable_response_cache else None
            stream_uc_hash = request.user_context.get_filter_hash() if request.user_context else None
            if cache:
                cached = cache.get(cache_query, user_context_hash=stream_uc_hash)
                if cached:
                    logger.info("[stream] 캐시 히트: '%s...'", stream_query[:30])
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

                    # 캐시 히트 시에도 키워드 기반 액션 전송
                    cache_actions = _state.router_agent.generator._collect_actions(
                        stream_query, {}, []
                    )
                    for act in cache_actions:
                        act_chunk = StreamResponse(
                            type="action",
                            content=act.label if hasattr(act, 'label') else "",
                            metadata={
                                "type": act.type if hasattr(act, 'type') else "",
                                "params": act.params if hasattr(act, 'params') else {},
                            },
                        )
                        yield f"data: {act_chunk.model_dump_json()}\n\n"

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
                    await append_session_turn(
                        owner_key,
                        request.session_id,
                        request.message,
                        cached_content,
                    )
                    return

            start_time = time.time()
            stream_timeout = settings.total_timeout
            hard_timeout = settings.stream_hard_timeout
            final_content = ""
            final_sources: list[Any] = []
            final_domains: list[str] = []
            final_actions: list[Any] = []

            # 키워드 기반 액션 사전 수집 (타임아웃과 무관하게 즉시 실행)
            pre_collected_actions = _state.router_agent.generator._collect_actions(
                stream_query, {}, []
            )
            token_usage = None
            done_evaluation = None
            done_ragas_metrics = None
            done_retrieval_results = None

            async with RequestTokenTracker() as tracker:
                token_index = 0
                stream_iter = _state.router_agent.astream(
                    query=stream_query,
                    user_context=request.user_context,
                    history=effective_history,
                ).__aiter__()
                hard_deadline = time.time() + hard_timeout

                def _build_timeout_events(
                    timeout_content: str,
                    streamed_content: str,
                ) -> list[str]:
                    """타임아웃 시 액션 안내 토큰 + 액션 이벤트 + done 이벤트를 생성합니다."""
                    events: list[str] = []
                    # 스트리밍된 콘텐츠가 없으면 안내 메시지를 토큰으로 전송
                    if not streamed_content.strip():
                        friendly_msg = (
                            "검색된 참고 자료가 부족하여 상세한 답변을 드리기 어렵지만, "
                            "요청하신 문서는 아래 버튼을 통해 바로 작성하실 수 있습니다."
                        )
                        token_chunk = StreamResponse(
                            type="token",
                            content=friendly_msg,
                            metadata={"index": 0},
                        )
                        events.append(f"data: {token_chunk.model_dump_json()}\n\n")
                    for act in pre_collected_actions:
                        act_chunk = StreamResponse(
                            type="action",
                            content=act.label if hasattr(act, 'label') else "",
                            metadata={
                                "type": act.type if hasattr(act, 'type') else "",
                                "params": act.params if hasattr(act, 'params') else {},
                            },
                        )
                        events.append(f"data: {act_chunk.model_dump_json()}\n\n")
                    done = StreamResponse(
                        type="done",
                        metadata={
                            "domain": "general",
                            "domains": [],
                            "response_time": time.time() - start_time,
                            "timeout": True,
                        },
                    )
                    events.append(f"data: {done.model_dump_json()}\n\n")
                    return events

                # 스트리밍 도중 누적된 토큰 (타임아웃 시 콘텐츠 보존용)
                streamed_so_far = ""

                while True:
                    remaining = hard_deadline - time.time()
                    if remaining <= 0:
                        logger.warning(
                            "[stream] hard timeout 초과 (%.1fs)", hard_timeout,
                        )
                        timeout_msg = "응답 생성 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                        if pre_collected_actions:
                            for evt in _build_timeout_events(timeout_msg, streamed_so_far):
                                yield evt
                        else:
                            error_chunk = StreamResponse(
                                type="error", content=timeout_msg,
                            )
                            yield f"data: {error_chunk.model_dump_json()}\n\n"

                        return
                    try:
                        chunk = await asyncio.wait_for(
                            stream_iter.__anext__(), timeout=remaining,
                        )
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        logger.warning(
                            "[stream] hard timeout 초과 (%.1fs)", hard_timeout,
                        )
                        timeout_msg = "응답 생성 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                        if pre_collected_actions:
                            for evt in _build_timeout_events(timeout_msg, streamed_so_far):
                                yield evt
                        else:
                            error_chunk = StreamResponse(
                                type="error", content=timeout_msg,
                            )
                            yield f"data: {error_chunk.model_dump_json()}\n\n"

                        return

                    # 소프트 타임아웃 체크 (기존 호환)
                    if time.time() - start_time > stream_timeout:
                        timeout_msg = "응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                        if pre_collected_actions:
                            for evt in _build_timeout_events(timeout_msg, streamed_so_far):
                                yield evt
                        else:
                            error_chunk = StreamResponse(
                                type="error", content=timeout_msg,
                            )
                            yield f"data: {error_chunk.model_dump_json()}\n\n"

                        return

                    if chunk["type"] == "token":
                        streamed_so_far += chunk["content"]
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
            await append_session_turn(
                owner_key,
                request.session_id,
                request.message,
                final_content,
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
                cache.set(cache_query, cache_data, cache_domain, user_context_hash=stream_uc_hash)

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

