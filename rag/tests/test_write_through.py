"""Write-through 모듈 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from routes._write_through import (
    init_http_client,
    save_turn_to_db,
    schedule_write_through,
)
import routes._write_through as wt_module


@pytest.fixture(autouse=True)
def _setup_client():
    """각 테스트마다 httpx 클라이언트 초기화/정리."""
    init_http_client()
    yield
    wt_module._http_client = None


# -- save_turn_to_db --


@pytest.mark.asyncio
async def test_save_turn_success():
    """201 응답 시 정상 처리."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"saved_count": 1, "skipped_count": 0, "history_ids": [1]}

    with patch.object(wt_module._http_client, "post", new_callable=AsyncMock, return_value=mock_resp):
        await save_turn_to_db(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000001",
        )
    # 예외 없이 완료되면 성공


@pytest.mark.asyncio
async def test_save_turn_backend_error(caplog):
    """Backend 4xx/5xx 시 warning 로그."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch.object(wt_module._http_client, "post", new_callable=AsyncMock, return_value=mock_resp):
        await save_turn_to_db(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000001",
        )

    assert any("write-through failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_save_turn_timeout(caplog):
    """네트워크 타임아웃 시 warning 로그."""
    with patch.object(
        wt_module._http_client, "post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        await save_turn_to_db(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000001",
        )

    assert any("write-through error" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_save_turn_idempotent_skip():
    """201 + skipped_count=1 (멱등 skip)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"saved_count": 0, "skipped_count": 1, "history_ids": [1]}

    with patch.object(wt_module._http_client, "post", new_callable=AsyncMock, return_value=mock_resp):
        await save_turn_to_db(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000001",
        )
    # 예외 없이 완료되면 성공


# -- schedule_write_through --


def test_schedule_skip_anonymous():
    """익명(user_id=None) → create_task 호출 안 됨."""
    with patch("routes._write_through.asyncio.create_task") as mock_ct:
        schedule_write_through(
            user_id=None,
            session_id="sess-1",
            question="질문",
            answer="답변",
        )
    mock_ct.assert_not_called()


def test_schedule_skip_no_session():
    """session_id=None → create_task 호출 안 됨."""
    with patch("routes._write_through.asyncio.create_task") as mock_ct:
        schedule_write_through(
            user_id=1,
            session_id=None,
            question="질문",
            answer="답변",
        )
    mock_ct.assert_not_called()


def test_schedule_skip_empty_question():
    """빈 question → create_task 호출 안 됨."""
    with patch("routes._write_through.asyncio.create_task") as mock_ct:
        schedule_write_through(
            user_id=1,
            session_id="sess-1",
            question="",
            answer="답변",
        )
    mock_ct.assert_not_called()


def test_schedule_normal():
    """정상 호출 → create_task 호출됨."""
    with patch("routes._write_through.asyncio.create_task") as mock_ct:
        schedule_write_through(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000002",
        )
    mock_ct.assert_called_once()


# -- init / close --


def test_get_http_client_not_initialized():
    """초기화 전 호출 시 RuntimeError."""
    wt_module._http_client = None
    with pytest.raises(RuntimeError, match="not initialized"):
        wt_module._get_http_client()


def test_get_http_client_closed():
    """닫힌 클라이언트 → RuntimeError."""
    mock = MagicMock()
    mock.is_closed = True
    wt_module._http_client = mock
    with pytest.raises(RuntimeError, match="not initialized"):
        wt_module._get_http_client()
    wt_module._http_client = None


def test_schedule_skip_empty_answer():
    """빈 answer → create_task 호출 안 됨."""
    with patch("routes._write_through.asyncio.create_task") as mock_ct:
        schedule_write_through(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="",
        )
    mock_ct.assert_not_called()


@pytest.mark.asyncio
async def test_save_turn_evaluation_data_included():
    """evaluation_data가 턴에 포함."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"saved_count": 1, "skipped_count": 0, "history_ids": [1]}

    with patch.object(wt_module._http_client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await save_turn_to_db(
            user_id=1,
            session_id="sess-1",
            question="질문",
            answer="답변",
            agent_code="A0000001",
            evaluation_data={"llm_score": 85, "domains": ["finance_tax"]},
        )

    sent_turn = mock_post.call_args.kwargs["json"]["turns"][0]
    assert sent_turn["evaluation_data"]["llm_score"] == 85


@pytest.mark.asyncio
async def test_save_turn_api_key_header():
    """X-Internal-Key 헤더 전달 확인."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"saved_count": 1, "skipped_count": 0, "history_ids": [1]}

    with patch.object(wt_module._http_client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await save_turn_to_db(
            user_id=1, session_id="sess-1", question="Q", answer="A", agent_code="A0000001",
        )

    headers = mock_post.call_args.kwargs["headers"]
    assert "X-Internal-Key" in headers


@pytest.mark.asyncio
async def test_close_http_client():
    """close_http_client가 클라이언트를 닫고 None으로 설정."""
    mock = AsyncMock()
    wt_module._http_client = mock
    await wt_module.close_http_client()
    assert wt_module._http_client is None
    mock.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close_http_client_when_none():
    """이미 None인 경우 에러 없이 완료."""
    wt_module._http_client = None
    await wt_module.close_http_client()
    assert wt_module._http_client is None
