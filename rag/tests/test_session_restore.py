"""MySQL → Redis 세션 복원 테스트."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes._session_memory import (
    _make_key,
    _memory_store,
    _reset_for_test,
    restore_session_from_db,
)


@pytest.fixture(autouse=True)
def _clean_memory():
    """테스트 전후 in-memory 상태 초기화."""
    _reset_for_test()
    yield
    _reset_for_test()


def _mock_settings(**overrides):
    defaults = {
        "session_restore_enabled": True,
        "session_restore_timeout": 5.0,
        "backend_internal_url": "http://backend:8000",
        "rag_api_key": "test-key",
        "session_memory_max_messages": 20,
        "session_memory_max_turns": 50,
        "session_memory_ttl_seconds": 90000,
        "session_memory_backend": "memory",
        "redis_url": "",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture
def settings_mock():
    with patch("routes._session_memory.get_settings", return_value=_mock_settings()):
        yield


def _build_db_response(turns=2):
    """Backend API 응답 형태의 스레드 이력 생성."""
    result = []
    for i in range(turns):
        result.append({
            "question": f"질문 {i + 1}",
            "answer": f"답변 {i + 1}",
            "agent_code": "A0000001",
            "evaluation_data": {
                "domains": ["startup_funding"],
                "llm_score": 80,
            },
            "create_date": f"2026-03-01T10:0{i}:00",
        })
    return result


class TestRestoreSessionFromDb:
    """restore_session_from_db 함수 테스트."""

    @pytest.mark.asyncio
    async def test_restore_success(self, settings_mock):
        """MySQL 복원 성공 → v2 세션 구조 검증, 메모리 저장 확인."""
        db_response = _build_db_response(turns=2)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = db_response

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is not None
        assert result["v"] == 2
        assert len(result["messages"]) == 4  # 2 turns * 2 messages
        assert result["messages"][0] == {"role": "user", "content": "질문 1"}
        assert result["messages"][1] == {"role": "assistant", "content": "답변 1"}
        assert len(result["turns"]) == 2
        assert result["turns"][0]["domains"] == ["startup_funding"]
        assert result["user_id"] == 1
        assert result["session_id"] == "sess-abc"

        # 메모리에 저장 확인
        key = _make_key("user:1", "sess-abc")
        assert key in _memory_store

    @pytest.mark.asyncio
    async def test_restore_empty_thread(self, settings_mock):
        """빈 스레드 → None 반환."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_backend_error(self, settings_mock):
        """Backend 에러 (500) → None 반환."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_timeout(self, settings_mock):
        """타임아웃 → None 반환."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            # asyncio.wait_for 내부에서 TimeoutError가 발생하도록
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_disabled(self):
        """session_restore_enabled=False → None 반환."""
        with patch(
            "routes._session_memory.get_settings",
            return_value=_mock_settings(session_restore_enabled=False),
        ):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_domains_extraction(self, settings_mock):
        """evaluation_data.domains 추출 → turns에 domains 정상 설정."""
        db_response = [
            {
                "question": "법률 질문",
                "answer": "법률 답변",
                "agent_code": "A0000004",
                "evaluation_data": {
                    "domains": ["law_common", "hr_labor"],
                    "llm_score": 85,
                },
                "create_date": "2026-03-01T10:00:00",
            },
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = db_response

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is not None
        assert result["turns"][0]["domains"] == ["law_common", "hr_labor"]

    @pytest.mark.asyncio
    async def test_restore_trimming(self):
        """max 초과 시 메시지/턴 잘라내기."""
        with patch(
            "routes._session_memory.get_settings",
            return_value=_mock_settings(
                session_memory_max_messages=4,
                session_memory_max_turns=2,
            ),
        ):
            db_response = _build_db_response(turns=5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = db_response

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)

            with patch("routes._write_through._get_http_client", return_value=mock_client):
                result = await restore_session_from_db(
                    owner_key="user:1",
                    session_id="sess-abc",
                    user_id=1,
                    root_history_id=100,
                )

            assert result is not None
            assert len(result["messages"]) == 4  # max_messages=4
            assert len(result["turns"]) == 2  # max_turns=2
            # 마지막 턴이 유지되는지 확인
            assert result["turns"][-1]["question"] == "질문 5"

    @pytest.mark.asyncio
    async def test_restore_no_evaluation_data(self, settings_mock):
        """evaluation_data가 None인 경우도 정상 처리."""
        db_response = [
            {
                "question": "질문",
                "answer": "답변",
                "agent_code": "A0000001",
                "evaluation_data": None,
                "create_date": "2026-03-01T10:00:00",
            },
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = db_response

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is not None
        assert "domains" not in result["turns"][0]

    @pytest.mark.asyncio
    async def test_restore_connection_error(self, settings_mock):
        """httpx 연결 에러 → None 반환."""
        import httpx

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("routes._write_through._get_http_client", return_value=mock_client):
            result = await restore_session_from_db(
                owner_key="user:1",
                session_id="sess-abc",
                user_id=1,
                root_history_id=100,
            )

        assert result is None
