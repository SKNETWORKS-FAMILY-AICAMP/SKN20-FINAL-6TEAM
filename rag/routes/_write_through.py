"""Write-through: 매 턴마다 비동기로 MySQL에 즉시 저장.

Redis에만 의존하던 데이터를 MySQL에도 이중 저장하여 Redis 장애 시
데이터 손실을 방지합니다. fire-and-forget 방식으로 채팅 응답에 영향 없음.
"""

import asyncio
import logging

import httpx

from utils.config import get_settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None
_pending_tasks: set[asyncio.Task] = set()


def init_http_client() -> None:
    """lifespan startup에서 1회 호출."""
    global _http_client
    _http_client = httpx.AsyncClient(timeout=10.0)


def _get_http_client() -> httpx.AsyncClient:
    if _http_client is None or _http_client.is_closed:
        raise RuntimeError("write-through http client not initialized")
    return _http_client


async def close_http_client() -> None:
    """Shutdown hook: httpx 클라이언트 정리."""
    global _http_client
    if _http_client is not None:
        try:
            await _http_client.aclose()
        except Exception as exc:
            logger.warning("write-through http client close failed: %s", exc)
        _http_client = None


async def save_turn_to_db(
    user_id: int,
    session_id: str,
    question: str,
    answer: str,
    agent_code: str,
    evaluation_data: dict | None = None,
    sources: list[dict] | None = None,
) -> None:
    """단건 턴을 Backend /histories/batch로 저장. 실패 시 로그만 남김."""
    settings = get_settings()
    backend_url = settings.backend_internal_url.rstrip("/")
    api_key = settings.rag_api_key

    turn: dict = {
        "agent_code": agent_code,
        "question": question,
        "answer": answer,
    }
    if sources:
        # sources를 evaluation_data에 병합 (복사 후 추가)
        merged = dict(evaluation_data) if evaluation_data else {}
        merged["sources"] = sources
        turn["evaluation_data"] = merged
    elif evaluation_data:
        turn["evaluation_data"] = evaluation_data

    try:
        client = _get_http_client()
        resp = await client.post(
            f"{backend_url}/histories/batch",
            json={
                "user_id": user_id,
                "session_id": session_id,
                "turns": [turn],
            },
            headers={"X-Internal-Key": api_key, "Content-Type": "application/json"},
        )
        if resp.status_code == 201:
            result = resp.json()
            saved = result.get("saved_count", 0)
            skipped = result.get("skipped_count", 0)
            logger.info(
                "write-through OK: user=%d, session=%s, saved=%d, skipped=%d",
                user_id, session_id, saved, skipped,
            )
        else:
            logger.warning(
                "write-through failed: status=%d, user=%d, session=%s",
                resp.status_code, user_id, session_id,
            )
    except Exception as exc:
        logger.warning("write-through error: user=%d, session=%s, %s", user_id, session_id, exc)


def schedule_write_through(
    user_id: int | None,
    session_id: str | None,
    question: str,
    answer: str,
    agent_code: str = "A0000001",
    evaluation_data: dict | None = None,
    sources: list[dict] | None = None,
) -> None:
    """Fire-and-forget으로 MySQL 저장을 스케줄링.

    익명 사용자(user_id=None)는 skip합니다.
    """
    if not user_id or not session_id:
        return
    if not question or not answer:
        return

    async def _save_with_retry():
        try:
            await save_turn_to_db(
                user_id=user_id,
                session_id=session_id,
                question=question,
                answer=answer,
                agent_code=agent_code,
                evaluation_data=evaluation_data,
                sources=sources,
            )
        except Exception:
            # 1회 재시도
            try:
                await asyncio.sleep(1.0)
                await save_turn_to_db(
                    user_id=user_id,
                    session_id=session_id,
                    question=question,
                    answer=answer,
                    agent_code=agent_code,
                    evaluation_data=evaluation_data,
                    sources=sources,
                )
            except Exception as retry_exc:
                logger.warning("write-through retry failed: %s", retry_exc)

    task = asyncio.create_task(_save_with_retry())
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)
