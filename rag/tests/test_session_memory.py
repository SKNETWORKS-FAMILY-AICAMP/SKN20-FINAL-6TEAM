import pytest

from routes import _session_memory as sm


class _Settings:
    session_memory_backend = "memory"
    session_memory_ttl_seconds = 3600
    session_memory_max_messages = 6
    redis_url = ""


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
