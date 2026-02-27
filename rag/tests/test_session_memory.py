import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from routes import _session_memory as sm


class _Settings:
    session_memory_backend = "memory"
    session_memory_ttl_seconds = 3600
    session_memory_max_messages = 6
    redis_url = ""


class _RedisSettings:
    session_memory_backend = "redis"
    session_memory_ttl_seconds = 3600
    session_memory_max_messages = 6
    redis_url = "redis://localhost:6379"


# ================================================================
# Memory backend tests
# ================================================================


@pytest.mark.asyncio
async def test_session_memory_isolated_by_owner(monkeypatch):
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    await sm.append_session_turn("user:2", "s1", "q2", "a2")

    h1 = await sm.get_session_history("user:1", "s1")
    h2 = await sm.get_session_history("user:2", "s1")

    assert len(h1) == 2
    assert len(h2) == 2
    assert h1[0]["content"] == "q1"
    assert h2[0]["content"] == "q2"


@pytest.mark.asyncio
async def test_upsert_and_append_respects_max_messages(monkeypatch):
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.upsert_session_history(
        "user:1",
        "s2",
        [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
            {"role": "assistant", "content": "a3"},
        ],
    )
    await sm.append_session_turn("user:1", "s2", "u4", "a4")
    history = await sm.get_session_history("user:1", "s2")

    assert len(history) == _Settings.session_memory_max_messages
    assert history[0]["content"] == "u2"
    assert history[-1]["content"] == "a4"


@pytest.mark.asyncio
async def test_ttl_expiry_memory(monkeypatch):
    """Memory backend: TTL 만료 시 세션 데이터 반환 안 됨."""

    class _ShortTTL:
        session_memory_backend = "memory"
        session_memory_ttl_seconds = 1
        session_memory_max_messages = 20
        redis_url = ""

    monkeypatch.setattr(sm, "_settings", lambda: _ShortTTL())
    sm._reset_for_test()

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2

    # TTL 만료 시뮬레이션
    key = sm._make_key("user:1", "s1")
    with sm._memory_lock:
        ts, data = sm._memory_store[key]
        sm._memory_store[key] = (ts - 2, data)  # 2초 전으로 조작

    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 0


@pytest.mark.asyncio
async def test_empty_session_id_skipped(monkeypatch):
    """session_id가 None이거나 빈 문자열이면 저장/조회 스킵."""
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.append_session_turn("user:1", None, "q1", "a1")
    await sm.append_session_turn("user:1", "", "q2", "a2")
    h = await sm.get_session_history("user:1", None)
    assert h == []
    h = await sm.get_session_history("user:1", "")
    assert h == []


@pytest.mark.asyncio
async def test_invalid_roles_filtered(monkeypatch):
    """유효하지 않은 role은 필터링됨."""
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.upsert_session_history("user:1", "s1", [
        {"role": "user", "content": "q1"},
        {"role": "system", "content": "should be filtered"},
        {"role": "assistant", "content": "a1"},
        {"role": "unknown", "content": "also filtered"},
    ])
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2
    assert h[0]["role"] == "user"
    assert h[1]["role"] == "assistant"


# ================================================================
# Redis backend tests (mocked)
# ================================================================


def _make_mock_redis():
    """Redis 클라이언트 목을 생성합니다 (v2 Lua 스크립트 호환)."""
    import json as _json
    from datetime import datetime, timezone

    store: dict[str, str] = {}
    mock_client = AsyncMock()

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ex=None):
        store[key] = value

    async def mock_expire(key, ttl):
        pass

    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.set = AsyncMock(side_effect=mock_set)
    mock_client.expire = AsyncMock(side_effect=mock_expire)

    # v2 Lua 스크립트 mock: 실제 Lua 스크립트 동작을 Python으로 시뮬레이션
    async def mock_lua_call(keys=None, args=None):
        key = keys[0]
        new_msgs = _json.loads(args[0])
        max_msg = int(args[1])
        ttl = int(args[2])
        turn_json = args[3]
        user_id_val = args[4]
        session_id_val = args[5]
        now_iso = args[6]

        raw = store.get(key)
        data = None
        if raw:
            data = _json.loads(raw)

        # v1 (plain array) → v2 upgrade
        if data is not None and isinstance(data, list):
            data = {
                "v": 2,
                "messages": data,
                "turns": [],
                "created_at": now_iso,
                "updated_at": now_iso,
            }

        if data is None:
            data = {
                "v": 2,
                "messages": [],
                "turns": [],
                "created_at": now_iso,
                "updated_at": now_iso,
            }

        if user_id_val:
            data["user_id"] = int(user_id_val)
        if session_id_val:
            data["session_id"] = session_id_val
        data["updated_at"] = now_iso

        # Append messages and trim
        msgs = data.get("messages", [])
        msgs.extend(new_msgs)
        if len(msgs) > max_msg:
            msgs = msgs[-max_msg:]
        data["messages"] = msgs

        # Append turn metadata
        if turn_json:
            turn = _json.loads(turn_json)
            turns = data.get("turns", [])
            turns.append(turn)
            data["turns"] = turns

        encoded = _json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        store[key] = encoded
        return encoded

    mock_client.register_script = MagicMock(return_value=mock_lua_call)

    return mock_client, store


@pytest.mark.asyncio
async def test_redis_backend_get_set(monkeypatch):
    """Redis backend: 기본 저장/조회."""
    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, _ = _make_mock_redis()
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2
    assert h[0]["content"] == "q1"
    assert h[1]["content"] == "a1"


@pytest.mark.asyncio
async def test_redis_backend_append_respects_max(monkeypatch):
    """Redis backend: max_messages 초과 시 오래된 메시지 제거."""
    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, _ = _make_mock_redis()
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    # 3턴 = 6메시지 (max)
    for i in range(3):
        await sm.append_session_turn("user:1", "s1", f"q{i}", f"a{i}")
    # 1턴 추가 → 가장 오래된 턴 제거
    await sm.append_session_turn("user:1", "s1", "q3", "a3")

    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == _RedisSettings.session_memory_max_messages
    assert h[0]["content"] == "q1"  # q0/a0 제거됨
    assert h[-1]["content"] == "a3"


@pytest.mark.asyncio
async def test_redis_failure_fallback_to_memory(monkeypatch):
    """Redis 연결 실패 시 memory backend로 폴백."""
    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_client.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    # Redis 실패 → memory로 폴백하여 저장
    await sm.append_session_turn("user:1", "s1", "q1", "a1")

    # Redis 실패 → memory에서 조회
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2
    assert h[0]["content"] == "q1"


@pytest.mark.asyncio
async def test_redis_url_empty_warns_and_uses_memory(monkeypatch):
    """SESSION_MEMORY_BACKEND=redis인데 REDIS_URL이 비어있으면 memory 사용."""

    class _BrokenRedisSettings:
        session_memory_backend = "redis"
        session_memory_ttl_seconds = 3600
        session_memory_max_messages = 20
        redis_url = ""

    monkeypatch.setattr(sm, "_settings", lambda: _BrokenRedisSettings())
    sm._reset_for_test()

    # _use_redis()가 False 반환 → memory 사용
    assert sm._use_redis() is False

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2


@pytest.mark.asyncio
async def test_upsert_overwrites_existing(monkeypatch):
    """upsert는 기존 이력을 완전히 교체."""
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.upsert_session_history("user:1", "s1", [
        {"role": "user", "content": "old_q"},
        {"role": "assistant", "content": "old_a"},
    ])
    await sm.upsert_session_history("user:1", "s1", [
        {"role": "user", "content": "new_q"},
        {"role": "assistant", "content": "new_a"},
    ])
    h = await sm.get_session_history("user:1", "s1")
    assert len(h) == 2
    assert h[0]["content"] == "new_q"


@pytest.mark.asyncio
async def test_delete_session_memory(monkeypatch):
    """Memory backend: 세션 삭제."""
    monkeypatch.setattr(sm, "_settings", lambda: _Settings())
    sm._reset_for_test()

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    assert len(await sm.get_session_history("user:1", "s1")) == 2

    deleted = await sm.delete_session("user:1", "s1")
    assert deleted is True
    assert await sm.get_session_history("user:1", "s1") == []

    # 이미 삭제된 세션 재삭제
    deleted = await sm.delete_session("user:1", "s1")
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_session_redis(monkeypatch):
    """Redis backend: 세션 삭제."""
    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, store = _make_mock_redis()

    async def mock_delete(key):
        return 1 if store.pop(key, None) is not None else 0

    mock_client.delete = AsyncMock(side_effect=mock_delete)
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    assert len(await sm.get_session_history("user:1", "s1")) == 2

    deleted = await sm.delete_session("user:1", "s1")
    assert deleted is True
    assert await sm.get_session_history("user:1", "s1") == []


# ================================================================
# v2 format tests (Redis mock)
# ================================================================


@pytest.mark.asyncio
async def test_redis_v2_turns_metadata_stored(monkeypatch):
    """Redis v2: append_session_turn이 turns 메타데이터를 저장."""
    import json as _json

    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, store = _make_mock_redis()
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    await sm.append_session_turn(
        "user:1", "s1", "q1", "a1",
        user_id=1, agent_code="A0000002", domains=["finance_tax"],
    )

    key = sm._make_key("user:1", "s1")
    raw = store[key]
    data = _json.loads(raw)

    assert data["v"] == 2
    assert len(data["messages"]) == 2
    assert len(data["turns"]) == 1
    assert data["turns"][0]["question"] == "q1"
    assert data["turns"][0]["answer"] == "a1"
    assert data["turns"][0]["agent_code"] == "A0000002"
    assert data["turns"][0]["domains"] == ["finance_tax"]
    assert data["user_id"] == 1
    assert data["session_id"] == "s1"


@pytest.mark.asyncio
async def test_redis_v2_get_session_full(monkeypatch):
    """Redis v2: get_session_full이 전체 v2 데이터를 반환."""
    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, _ = _make_mock_redis()
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    await sm.append_session_turn(
        "user:1", "s1", "q1", "a1",
        user_id=1, agent_code="A0000001",
    )
    await sm.append_session_turn(
        "user:1", "s1", "q2", "a2",
        user_id=1, agent_code="A0000003",
    )

    full = await sm.get_session_full("user:1", "s1")
    assert full is not None
    assert full["v"] == 2
    assert len(full["messages"]) == 4
    assert len(full["turns"]) == 2
    assert full["turns"][0]["question"] == "q1"
    assert full["turns"][1]["question"] == "q2"


@pytest.mark.asyncio
async def test_redis_v2_evaluation_data_in_turns(monkeypatch):
    """Redis v2: evaluation_data가 turns에 포함."""
    import json as _json

    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    mock_client, store = _make_mock_redis()
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_client))

    eval_data = {"llm_score": 85, "llm_passed": True, "domains": ["hr_labor"]}
    await sm.append_session_turn(
        "user:1", "s1", "q1", "a1",
        user_id=1, evaluation_data=eval_data,
    )

    key = sm._make_key("user:1", "s1")
    data = _json.loads(store[key])
    assert data["turns"][0]["evaluation_data"] == eval_data


# ================================================================
# flush_memory_to_redis tests
# ================================================================


@pytest.mark.asyncio
async def test_flush_memory_to_redis(monkeypatch):
    """Redis 장애 후 복구 시 메모리 데이터를 Redis로 동기화."""
    import json as _json

    monkeypatch.setattr(sm, "_settings", lambda: _RedisSettings())
    sm._reset_for_test()

    # 1단계: Redis 실패 → 메모리 폴백에 저장
    mock_fail = AsyncMock()
    mock_fail.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_fail.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_fail))

    await sm.append_session_turn("user:1", "s1", "q1", "a1")
    assert len(sm._memory_store) == 1

    # 2단계: Redis 복구 → flush
    redis_store: dict[str, str] = {}

    mock_ok = AsyncMock()
    mock_ok.ping = AsyncMock(return_value=True)

    async def mock_set(key, value, ex=None):
        redis_store[key] = value

    mock_ok.set = AsyncMock(side_effect=mock_set)
    monkeypatch.setattr(sm, "_get_redis_client", AsyncMock(return_value=mock_ok))

    flushed = await sm.flush_memory_to_redis()
    assert flushed == 1
    assert len(sm._memory_store) == 0
    assert len(redis_store) == 1
