"""Session history store for multi-turn continuity.

Supports:
- memory backend (default)
- redis backend (optional)

v2 data format stores turns with metadata alongside trimmed messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

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


def _session_max_turns() -> int:
    return _settings().session_memory_max_turns


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_session_history(owner_key: str, session_id: str | None) -> list[dict[str, str]]:
    """Get session messages for multi-turn pipeline. Handles both v1 and v2 formats."""
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
            # v1: plain list of messages
            if isinstance(data, list):
                return _sanitize_history(data)
            # v2: dict with "messages" key
            if isinstance(data, dict) and data.get("v") == 2:
                messages = data.get("messages", [])
                return _sanitize_history(messages) if isinstance(messages, list) else []
            return []
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


async def get_session_full(owner_key: str, session_id: str) -> dict | None:
    """Get the full v2 session data (including turns). Returns None if not found."""
    if not session_id:
        return None

    key = _make_key(owner_key, session_id)
    if not _use_redis():
        return None

    try:
        client = await _get_redis_client()
        raw = await client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        # v1 format: wrap into v2 structure
        if isinstance(data, list):
            return {"v": 1, "messages": data, "turns": []}
        if isinstance(data, dict):
            return data
        return None
    except Exception as exc:
        logger.warning("Redis get_session_full failed: %s", exc)
        return None


async def get_active_sessions_for_user(user_id: int) -> list[dict]:
    """Scan Redis for all active sessions of a specific user.

    Returns list of v2 session dicts with their Redis keys.
    """
    if not _use_redis():
        return []

    try:
        client = await _get_redis_client()
        pattern = f"rag:session:user:{user_id}:*"
        sessions = []
        async for key in client.scan_iter(match=pattern, count=100):
            raw = await client.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("v") == 2:
                turns = data.get("turns", [])
                if turns:
                    data["_redis_key"] = key
                    sessions.append(data)
            elif isinstance(data, list) and data:
                # v1 sessions — include with minimal info
                sessions.append({
                    "v": 1,
                    "messages": data,
                    "turns": [],
                    "_redis_key": key,
                })
        return sessions
    except Exception as exc:
        logger.warning("Redis scan for user sessions failed: %s", exc)
        return []


async def scan_expiring_sessions(max_ttl_remaining: int) -> list[tuple[str, dict]]:
    """Scan Redis for sessions with TTL below threshold (migration candidates).

    Returns list of (redis_key, session_data) tuples.
    """
    if not _use_redis():
        return []

    try:
        client = await _get_redis_client()
        pattern = "rag:session:*"
        results = []
        async for key in client.scan_iter(match=pattern, count=200):
            ttl = await client.ttl(key)
            # ttl == -1 means no expiry, -2 means key doesn't exist
            if ttl < 0 or ttl > max_ttl_remaining:
                continue
            raw = await client.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            # Only v2 sessions with user_id and turns are migration candidates
            if isinstance(data, dict) and data.get("v") == 2 and data.get("user_id") and data.get("turns"):
                results.append((key, data))
        return results
    except Exception as exc:
        logger.warning("Redis scan_expiring_sessions failed: %s", exc)
        return []


async def delete_sessions_batch(keys: list[str]) -> int:
    """Delete multiple session keys from Redis. Returns count of deleted keys."""
    if not keys or not _use_redis():
        return 0

    try:
        client = await _get_redis_client()
        deleted = await client.delete(*keys)
        return deleted
    except Exception as exc:
        logger.warning("Redis batch delete failed: %s", exc)
        return 0


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


# v2 Lua script: append to both messages (trimmed) and turns (untrimmed)
_APPEND_V2_LUA = """
local raw = redis.call('GET', KEYS[1])
local data
if raw then
    local ok, decoded = pcall(cjson.decode, raw)
    if ok and type(decoded) == 'table' then
        data = decoded
    end
end

local ok_msgs, new_msgs = pcall(cjson.decode, ARGV[1])
if not ok_msgs then
    return redis.error_reply("ERR invalid JSON in ARGV[1]")
end
local max_msg = tonumber(ARGV[2])
local ttl_val = tonumber(ARGV[3])
local turn_json = ARGV[4]
local user_id_val = ARGV[5]
local session_id_val = ARGV[6]
local now_iso = ARGV[7]
local max_turns = tonumber(ARGV[8])

-- Upgrade v1 (plain array) to v2
if data and data['v'] == nil then
    local old_messages = data
    data = {
        v = 2,
        messages = old_messages,
        turns = {},
        created_at = now_iso,
        updated_at = now_iso,
    }
end

if not data then
    data = {
        v = 2,
        messages = {},
        turns = {},
        created_at = now_iso,
        updated_at = now_iso,
    }
end

-- Set user_id and session_id if provided
if user_id_val ~= '' then
    data['user_id'] = tonumber(user_id_val)
end
if session_id_val ~= '' then
    data['session_id'] = session_id_val
end
data['updated_at'] = now_iso

-- Append new messages and trim
local msgs = data['messages'] or {}
for _, m in ipairs(new_msgs) do
    table.insert(msgs, m)
end
if #msgs > max_msg then
    local trimmed = {}
    for i = #msgs - max_msg + 1, #msgs do
        table.insert(trimmed, msgs[i])
    end
    msgs = trimmed
end
data['messages'] = msgs

-- Append turn metadata and trim to max_turns
if turn_json ~= '' then
    local ok_turn, turn = pcall(cjson.decode, turn_json)
    if ok_turn then
        local turns = data['turns'] or {}
        table.insert(turns, turn)
        if max_turns and #turns > max_turns then
            local trimmed = {}
            for i = #turns - max_turns + 1, #turns do
                table.insert(trimmed, turns[i])
            end
            turns = trimmed
        end
        data['turns'] = turns
    end
end

local encoded = cjson.encode(data)
redis.call('SET', KEYS[1], encoded, 'EX', ttl_val)
return encoded
"""
_append_v2_script = None


async def append_session_turn(
    owner_key: str,
    session_id: str | None,
    user_message: str,
    assistant_message: str,
    *,
    user_id: int | None = None,
    agent_code: str | None = None,
    domains: list[str] | None = None,
    sources: list[dict] | None = None,
    evaluation_data: dict[str, Any] | None = None,
) -> None:
    global _append_v2_script
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
            now_iso = _now_iso()

            # Build turn metadata
            turn_data: dict[str, Any] = {
                "question": user_message,
                "answer": assistant_message,
                "timestamp": now_iso,
            }
            if agent_code:
                turn_data["agent_code"] = agent_code
            if domains:
                turn_data["domains"] = domains
            if sources:
                turn_data["sources"] = sources[:5]
            if evaluation_data:
                turn_data["evaluation_data"] = evaluation_data

            if _append_v2_script is None:
                _append_v2_script = client.register_script(_APPEND_V2_LUA)
            await _append_v2_script(
                keys=[key],
                args=[
                    json.dumps(new_msgs, ensure_ascii=False, separators=(",", ":")),
                    str(max_messages),
                    str(ttl),
                    json.dumps(turn_data, ensure_ascii=False, separators=(",", ":")),
                    str(user_id) if user_id is not None else "",
                    session_id,
                    now_iso,
                    str(_session_max_turns()),
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


async def flush_memory_to_redis() -> int:
    """Try to sync in-memory fallback data back to Redis.

    Called periodically to recover data that was stored in memory
    during Redis outages. Returns number of keys flushed.
    """
    if not _use_redis():
        return 0

    with _memory_lock:
        keys_to_flush = list(_memory_store.keys())
    if not keys_to_flush:
        return 0

    flushed = 0
    try:
        client = await _get_redis_client()
        await client.ping()
    except Exception:
        return 0

    for key in keys_to_flush:
        with _memory_lock:
            entry = _memory_store.get(key)
        if not entry:
            continue
        ts, history = entry
        try:
            remaining_ttl = max(1, _session_ttl() - int(time.time() - ts))
            await client.set(
                key,
                json.dumps(history, ensure_ascii=False, separators=(",", ":")),
                ex=remaining_ttl,
            )
            with _memory_lock:
                # 경쟁조건 방지: I/O 중 새 데이터가 추가됐으면 pop하지 않음
                current = _memory_store.get(key)
                if current is None or current[0] <= ts:
                    _memory_store.pop(key, None)
            flushed += 1
        except Exception as exc:
            logger.warning("flush_memory_to_redis: key=%s failed: %s", key, exc)
            break  # Redis still down, stop trying
    if flushed:
        logger.info("Flushed %d/%d memory-fallback sessions to Redis", flushed, len(keys_to_flush))
    return flushed


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
    global _redis_client, _append_v2_script
    with _memory_lock:
        _memory_store.clear()
    _redis_client = None
    _append_v2_script = None
