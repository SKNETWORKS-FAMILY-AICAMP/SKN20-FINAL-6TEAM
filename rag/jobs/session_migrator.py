"""Session migration job: Redis → Backend DB batch transfer.

Scans for expiring Redis sessions and migrates them to the backend database.
Runs as an asyncio background task within the RAG service lifespan.
"""

import asyncio
import logging

import httpx

from routes._session_memory import delete_sessions_batch, flush_memory_to_redis, scan_expiring_sessions
from utils.config import get_settings

logger = logging.getLogger(__name__)


async def migrate_expiring_sessions() -> int:
    """Scan expiring sessions and migrate to backend DB.

    Returns:
        Number of sessions successfully migrated.
    """
    settings = get_settings()
    threshold = settings.session_migrate_ttl_threshold

    candidates = await scan_expiring_sessions(threshold)
    if not candidates:
        return 0

    logger.info("Session migration: found %d expiring sessions", len(candidates))

    migrated_keys: list[str] = []
    backend_url = settings.backend_internal_url.rstrip("/")
    api_key = settings.rag_api_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        for redis_key, session_data in candidates:
            user_id = session_data.get("user_id")
            session_id = session_data.get("session_id", "")
            turns = session_data.get("turns", [])

            if not user_id or not turns:
                continue

            # Build batch turns with agent_code defaulting
            batch_turns = []
            for turn in turns:
                agent_code = turn.get("agent_code", "A0000001")
                question = turn.get("question", "")
                answer = turn.get("answer", "")
                if not question or not answer:
                    continue

                batch_turns.append({
                    "agent_code": agent_code,
                    "question": question,
                    "answer": answer,
                    "evaluation_data": turn.get("evaluation_data"),
                    "timestamp": turn.get("timestamp"),
                })

            if not batch_turns:
                # No valid turns — delete empty session
                migrated_keys.append(redis_key)
                continue

            try:
                resp = await client.post(
                    f"{backend_url}/histories/batch",
                    json={
                        "user_id": user_id,
                        "session_id": session_id,
                        "turns": batch_turns,
                    },
                    headers={"X-Internal-Key": api_key, "Content-Type": "application/json"},
                )
                if resp.status_code == 201:
                    result = resp.json()
                    logger.info(
                        "Session migrated: user=%d, session=%s, saved=%d, skipped=%d",
                        user_id, session_id,
                        result.get("saved_count", 0),
                        result.get("skipped_count", 0),
                    )
                    migrated_keys.append(redis_key)
                else:
                    logger.warning(
                        "Backend batch save failed: status=%d, user=%d, session=%s, body=%s",
                        resp.status_code, user_id, session_id, resp.text[:200],
                    )
            except Exception as exc:
                logger.warning(
                    "Session migration request failed: user=%d, session=%s, error=%s",
                    user_id, session_id, exc,
                )
                # Keep session in Redis for next retry

    # Delete successfully migrated sessions from Redis
    # 삭제 전 TTL 재확인: 마이그레이션 중 사용자가 세션을 재개했으면 TTL이 갱신됨
    if migrated_keys:
        keys_to_delete = []
        try:
            from routes._session_memory import _get_redis_client
            client = await _get_redis_client()
            for key in migrated_keys:
                ttl = await client.ttl(key)
                if ttl <= threshold:
                    keys_to_delete.append(key)
                else:
                    logger.info("Session resumed during migration, skipping delete: key=%s, ttl=%d", key, ttl)
        except Exception:
            keys_to_delete = migrated_keys  # Redis 오류 시 원래 동작 유지

        if keys_to_delete:
            deleted = await delete_sessions_batch(keys_to_delete)
            logger.info("Session migration cleanup: deleted %d/%d keys", deleted, len(keys_to_delete))

    return len(migrated_keys)


async def session_migration_loop() -> None:
    """Background loop that periodically migrates expiring sessions."""
    settings = get_settings()
    interval = settings.session_migrate_interval

    # Run once immediately on startup (handle sessions accumulated during downtime)
    try:
        await flush_memory_to_redis()
        count = await migrate_expiring_sessions()
        if count:
            logger.info("Startup migration: migrated %d sessions", count)
    except Exception as exc:
        logger.warning("Startup migration failed: %s", exc)

    while True:
        try:
            await asyncio.sleep(interval)
            await flush_memory_to_redis()
            count = await migrate_expiring_sessions()
            if count:
                logger.info("Periodic migration: migrated %d sessions", count)
        except asyncio.CancelledError:
            logger.info("Session migration loop cancelled")
            raise
        except Exception as exc:
            logger.warning("Session migration loop error: %s", exc)
