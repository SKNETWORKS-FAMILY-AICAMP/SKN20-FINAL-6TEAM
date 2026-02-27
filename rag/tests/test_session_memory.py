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
    """Redis 클라이언트 목을 생성합니다."""
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
