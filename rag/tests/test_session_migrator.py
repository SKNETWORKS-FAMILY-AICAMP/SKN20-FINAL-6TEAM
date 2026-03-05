"""Session Migrator 단위 테스트.

jobs/session_migrator.py의 migrate_expiring_sessions를 검증합니다.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from jobs import session_migrator as migrator


class _MockResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


class _Settings:
    session_migrate_ttl_threshold = 900
    session_migrate_interval = 300
    backend_internal_url = "http://backend:8000"
    rag_api_key = "test-key"


def _make_session(user_id: int, session_id: str, turns: list[dict] | None = None) -> dict:
    if turns is None:
        turns = [
            {"agent_code": "A0000001", "question": "Q1", "answer": "A1", "timestamp": "2026-01-01T00:00:00"},
        ]
    return {
        "v": 2,
        "user_id": user_id,
        "session_id": session_id,
        "messages": [],
        "turns": turns,
    }


# ================================================================
# migrate_expiring_sessions
# ================================================================


@pytest.mark.asyncio
async def test_migrate_no_candidates(monkeypatch):
    """후보 없으면 0 반환."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=[]))

    result = await migrator.migrate_expiring_sessions()
    assert result == 0


@pytest.mark.asyncio
async def test_migrate_normal_flow(monkeypatch):
    """정상: 후보 → Backend 201 → TTL 재확인 → 삭제."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    candidates = [
        ("rag:session:user:1:s1", _make_session(1, "s1")),
        ("rag:session:user:2:s2", _make_session(2, "s2")),
    ]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    # httpx mock
    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(201, {"saved_count": 1, "skipped_count": 0})
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    # Redis TTL 재확인: threshold 이하 → 삭제 대상
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[100, 200])  # 둘 다 threshold(900) 이하
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=2)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            result = await migrator.migrate_expiring_sessions()

    assert result == 2
    assert mock_http_client.post.call_count == 2
    mock_delete.assert_called_once()
    deleted_keys = mock_delete.call_args[0][0]
    assert len(deleted_keys) == 2


@pytest.mark.asyncio
async def test_migrate_user_resumed_skips_delete(monkeypatch):
    """마이그레이션 중 사용자 재개 → TTL 갱신 → 삭제 스킵."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    candidates = [
        ("rag:session:user:1:s1", _make_session(1, "s1")),
    ]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(201, {"saved_count": 1, "skipped_count": 0})
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    # TTL 재확인: threshold(900) 초과 → 삭제 스킵
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[4000])  # TTL 갱신됨 (사용자 재개)
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=0)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            result = await migrator.migrate_expiring_sessions()

    assert result == 1  # 마이그레이션은 성공
    mock_delete.assert_not_called()  # keys_to_delete가 비어있어 호출 안 됨


@pytest.mark.asyncio
async def test_migrate_backend_failure_keeps_redis(monkeypatch):
    """Backend 500 → Redis 키 유지."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    candidates = [
        ("rag:session:user:1:s1", _make_session(1, "s1")),
    ]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(500, text="Internal Server Error")
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_delete = AsyncMock()
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await migrator.migrate_expiring_sessions()

    assert result == 0  # 마이그레이션 실패
    mock_delete.assert_not_called()  # 삭제 안 됨


@pytest.mark.asyncio
async def test_migrate_network_error_keeps_redis(monkeypatch):
    """네트워크 에러 → Redis 키 유지."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    candidates = [
        ("rag:session:user:1:s1", _make_session(1, "s1")),
    ]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = ConnectionError("refused")
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_delete = AsyncMock()
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await migrator.migrate_expiring_sessions()

    assert result == 0
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_empty_turns_skipped(monkeypatch):
    """빈 turns 세션 → 스킵 (마이그레이션도, 삭제도 안 함)."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    session = _make_session(1, "s1", turns=[])
    candidates = [("rag:session:user:1:s1", session)]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_delete = AsyncMock()
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await migrator.migrate_expiring_sessions()

    assert result == 0  # turns 비어있으면 continue로 스킵
    mock_http_client.post.assert_not_called()
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_all_invalid_turns_deleted(monkeypatch):
    """모든 턴이 무효 (빈 q/a) → migrated_keys에 추가 → 삭제."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    session = _make_session(1, "s1", turns=[
        {"agent_code": "A0000001", "question": "", "answer": "A1"},
        {"agent_code": "A0000001", "question": "Q2", "answer": ""},
    ])
    candidates = [("rag:session:user:1:s1", session)]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[100])
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=1)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            result = await migrator.migrate_expiring_sessions()

    assert result == 1
    mock_http_client.post.assert_not_called()  # 유효한 턴 없음
    mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_migrate_no_user_id_skipped(monkeypatch):
    """user_id 없는 세션 → 스킵."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    session = _make_session(None, "s1")
    session["user_id"] = None
    candidates = [("rag:session:anon:s1", session)]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_delete = AsyncMock()
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await migrator.migrate_expiring_sessions()

    assert result == 0
    mock_http_client.post.assert_not_called()
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_ttl_recheck_redis_failure(monkeypatch):
    """TTL 재확인 Redis 실패 → 전체 키 삭제."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    candidates = [
        ("rag:session:user:1:s1", _make_session(1, "s1")),
    ]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(201, {"saved_count": 1, "skipped_count": 0})
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    # TTL 재확인 Redis 실패
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=1)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            result = await migrator.migrate_expiring_sessions()

    assert result == 1
    mock_delete.assert_called_once()
    deleted_keys = mock_delete.call_args[0][0]
    assert "rag:session:user:1:s1" in deleted_keys


@pytest.mark.asyncio
async def test_migrate_invalid_turns_filtered(monkeypatch):
    """빈 question/answer 턴 → 필터링."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    session = _make_session(1, "s1", turns=[
        {"agent_code": "A0000001", "question": "", "answer": "A1"},  # 빈 question
        {"agent_code": "A0000001", "question": "Q2", "answer": ""},  # 빈 answer
        {"agent_code": "A0000001", "question": "Q3", "answer": "A3"},  # 유효
    ])
    candidates = [("rag:session:user:1:s1", session)]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(201, {"saved_count": 1, "skipped_count": 0})
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[100])
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=1)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            result = await migrator.migrate_expiring_sessions()

    assert result == 1
    # 유효한 턴 1개만 전송
    sent_turns = mock_http_client.post.call_args.kwargs["json"]["turns"]
    assert len(sent_turns) == 1
    assert sent_turns[0]["question"] == "Q3"


@pytest.mark.asyncio
async def test_migrate_evaluation_data_passed(monkeypatch):
    """evaluation_data가 Backend에 전달."""
    monkeypatch.setattr(migrator, "get_settings", lambda: _Settings())

    eval_data = {"llm_score": 85, "domains": ["finance_tax"]}
    session = _make_session(1, "s1", turns=[
        {"agent_code": "A0000001", "question": "Q", "answer": "A", "evaluation_data": eval_data},
    ])
    candidates = [("rag:session:user:1:s1", session)]
    monkeypatch.setattr(migrator, "scan_expiring_sessions", AsyncMock(return_value=candidates))

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = _MockResponse(201, {"saved_count": 1, "skipped_count": 0})
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[100])
    mock_redis.pipeline.return_value = mock_pipe

    mock_delete = AsyncMock(return_value=1)
    monkeypatch.setattr(migrator, "delete_sessions_batch", mock_delete)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch("routes._session_memory.get_session_redis_client", AsyncMock(return_value=mock_redis)):
            await migrator.migrate_expiring_sessions()

    sent_turn = mock_http_client.post.call_args.kwargs["json"]["turns"][0]
    assert sent_turn["evaluation_data"] == eval_data
