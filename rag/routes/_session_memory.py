"""Session history store for multi-turn continuity.

Supports:
- memory backend (default)
- redis backend (optional)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from threading import Lock

from utils.config import get_settings

logger = logging.getLogger(__name__)

_memory_store: dict[str, tuple[float, list[dict[str, str]]]] = {}
_memory_lock = Lock()
_redis_client = None
_redis_client_lock: asyncio.Lock | None = None


def _settings():
    return get_settings()


def _session_max_messages() -> int:
    return _settings().session_memory_max_messages


def _session_ttl() -> int:
    return _settings().session_memory_ttl_seconds


def _session_backend() -> str:
    return _settings().session_memory_backend


def _redis_url() -> str:
    return _settings().redis_url


def _make_key(owner_key: str, session_id: str) -> str:
    return f"rag:session:{owner_key}:{session_id}"


def _sanitize_history(history: list[dict]) -> list[dict[str, str]]:
    max_messages = _session_max_messages()
    sanitized: list[dict[str, str]] = []
    for msg in history:
        role = str(msg.get("role", ""))
        if role not in {"user", "assistant"}:
            continue
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        sanitized.append({"role": role, "content": content})
    return sanitized[-max_messages:]


def _prune_expired(now: float) -> None:
    ttl = _session_ttl()
    expired = [k for k, (ts, _) in _memory_store.items() if now - ts > ttl]
    for key in expired:
        _memory_store.pop(key, None)


async def _get_redis_client():
    global _redis_client, _redis_client_lock
    if _redis_client is not None:
        return _redis_client
    if _redis_client_lock is None:
        _redis_client_lock = asyncio.Lock()
    async with _redis_client_lock:
        if _redis_client is None:
            from redis import asyncio as redis  # Lazy import (optional dependency)

            _redis_client = redis.from_url(
                _redis_url(),
                encoding="utf-8",
                decode_responses=True,
            )
    return _redis_client


def _use_redis() -> bool:
    if _session_backend() != "redis":
        return False
    url = _redis_url()
    if not url:
        logger.warning("SESSION_MEMORY_BACKEND=redis but REDIS_URL is empty — falling back to in-memory store")
        return False
    return True


async def get_session_history(owner_key: str, session_id: str | None) -> list[dict[str, str]]:
    if not session_id:
        return []

    key = _make_key(owner_key, session_id)
    if _use_redis():
        try:
            client = await _get_redis_client()
            raw = await client.get(key)
            if not raw:
                return []
            await client.expire(key, _session_ttl())
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            return _sanitize_history(data)
        except Exception as exc:
            logger.warning("Redis session read failed, fallback to memory: %s", exc)

    with _memory_lock:
        now = time.time()
        _prune_expired(now)
        entry = _memory_store.get(key)
        if not entry:
            return []
        _, history = entry
        return list(history)


async def upsert_session_history(owner_key: str, session_id: str | None, history: list[dict]) -> None:
    if not session_id:
        return

    sanitized = _sanitize_history(history)
    if not sanitized:
        return

    key = _make_key(owner_key, session_id)
    if _use_redis():
        try:
            client = await _get_redis_client()
            await client.set(
                key,
                json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")),
                ex=_session_ttl(),
            )
            return
        except Exception as exc:
            logger.warning("Redis session write failed, fallback to memory: %s", exc)

    with _memory_lock:
        now = time.time()
        _prune_expired(now)
        _memory_store[key] = (now, sanitized)


_APPEND_LUA = """
local raw = redis.call('GET', KEYS[1])
local data = {}
if raw then
    data = cjson.decode(raw)
    if type(data) ~= 'table' then data = {} end
end
local new_msgs = cjson.decode(ARGV[1])
for _, m in ipairs(new_msgs) do
    table.insert(data, m)
end
local max_msg = tonumber(ARGV[2])
if #data > max_msg then
    local trimmed = {}
    for i = #data - max_msg + 1, #data do
        table.insert(trimmed, data[i])
    end
    data = trimmed
end
local encoded = cjson.encode(data)
redis.call('SET', KEYS[1], encoded, 'EX', tonumber(ARGV[3]))
return encoded
"""
_append_script = None


async def append_session_turn(
    owner_key: str,
    session_id: str | None,
    user_message: str,
    assistant_message: str,
) -> None:
    global _append_script
    if not session_id:
        return

    user_message = user_message.strip()
    assistant_message = assistant_message.strip()
    if not user_message or not assistant_message:
        return

    key = _make_key(owner_key, session_id)
    max_messages = _session_max_messages()
    ttl = _session_ttl()

    if _use_redis():
        try:
            client = await _get_redis_client()
            new_msgs = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]
            if _append_script is None:
                _append_script = client.register_script(_APPEND_LUA)
            await _append_script(
                keys=[key],
                args=[
                    json.dumps(new_msgs, ensure_ascii=False, separators=(",", ":")),
                    str(max_messages),
                    str(ttl),
                ],
            )
            return
        except Exception as exc:
            logger.warning("Redis session append failed, fallback to memory: %s", exc)

    with _memory_lock:
        now = time.time()
        _prune_expired(now)
        _, existing = _memory_store.get(key, (now, []))
        combined = existing + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
        _memory_store[key] = (now, combined[-max_messages:])


async def delete_session(owner_key: str, session_id: str | None) -> bool:
    """Delete a session from the store. Returns True if deleted."""
    if not session_id:
        return False

    key = _make_key(owner_key, session_id)
    if _use_redis():
        try:
            client = await _get_redis_client()
            deleted = await client.delete(key)
            return deleted > 0
        except Exception as exc:
            logger.warning("Redis session delete failed, fallback to memory: %s", exc)

    with _memory_lock:
        return _memory_store.pop(key, None) is not None


async def close_redis_client() -> None:
    """Gracefully close the Redis client connection pool."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            logger.warning("Redis client close failed: %s", exc)
        _redis_client = None


def _reset_for_test() -> None:
    """Test helper: clear in-memory state."""
    global _redis_client, _append_script
    with _memory_lock:
        _memory_store.clear()
    _redis_client = None
    _append_script = None
