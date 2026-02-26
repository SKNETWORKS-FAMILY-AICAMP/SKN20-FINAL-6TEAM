"""Unit tests for query rewriter."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from utils.query_rewriter import (
    QueryRewriter,
    _format_history_for_rewrite,
    get_query_rewriter,
    reset_query_rewriter,
)


class TestFormatHistoryForRewrite:
    def test_empty_history_returns_empty_string(self):
        assert _format_history_for_rewrite([]) == ""

    def test_formats_user_and_assistant_messages(self):
        history = [
            {"role": "user", "content": "사업자등록 절차 알려주세요"},
            {"role": "assistant", "content": "사업자등록은 다음 단계에서..."},
        ]
        result = _format_history_for_rewrite(history)
        assert history[0]["content"] in result
        assert history[1]["content"] in result

    def test_truncates_long_messages(self):
        long_content = "가" * 300
        history = [{"role": "user", "content": long_content}]
        result = _format_history_for_rewrite(history, max_chars=200)
        assert "..." in result
        assert len(result) < 300

    def test_limits_to_max_turns(self):
        history = [{"role": "user", "content": f"질문 {i}"} for i in range(10)]
        result = _format_history_for_rewrite(history, max_turns=2)
        assert "질문 5" not in result
        assert "질문 6" in result
        assert "질문 9" in result


class TestQueryRewriter:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.enable_query_rewrite = True
        settings.query_rewrite_timeout = 5.0
        settings.openai_model = "gpt-4o-mini"
        settings.openai_api_key = "sk-test"
        settings.openai_temperature = 0.1
        settings.multiturn_history_turns = 6
        settings.multiturn_history_chars = 350
        settings.enable_active_directive_memory = True
        return settings

    @pytest.fixture
    def rewriter(self, mock_settings):
        with patch("utils.query_rewriter.get_settings", return_value=mock_settings), patch(
            "utils.query_rewriter.create_llm"
        ) as mock_create_llm:
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm
            instance = QueryRewriter()
            instance.llm = mock_llm
            yield instance

    @pytest.mark.asyncio
    async def test_skip_when_no_history(self, rewriter):
        result_query, was_rewritten = await rewriter.arewrite("서류?", None)
        assert result_query == "서류?"
        assert was_rewritten is False

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self, rewriter):
        rewriter.settings.enable_query_rewrite = False
        history = [
            {"role": "user", "content": "사업자등록 절차?"},
            {"role": "assistant", "content": "사업자등록은..."},
        ]
        result_query, was_rewritten = await rewriter.arewrite("서류?", history)
        assert result_query == "서류?"
        assert was_rewritten is False

    @pytest.mark.asyncio
    async def test_rewrites_context_dependent_query(self, rewriter):
        history = [
            {"role": "user", "content": "사업자등록 절차 알려주세요"},
            {"role": "assistant", "content": "사업자등록은 다음 단계에서..."},
        ]

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=json.dumps(
                {
                    "rewritten": "사업자등록에 필요한 서류는 무엇인가요?",
                    "is_rewritten": True,
                }
            )
        )

        with patch.object(rewriter, "llm"):
            with patch("utils.query_rewriter.ChatPromptTemplate") as mock_prompt:
                mock_prompt.from_messages.return_value = MagicMock()
                mock_prompt.from_messages.return_value.__or__ = Mock(return_value=MagicMock())
                mock_prompt.from_messages.return_value.__or__.return_value.__or__ = Mock(
                    return_value=mock_chain
                )

                result_query, was_rewritten = await rewriter.arewrite("서류?", history)

        assert was_rewritten is True
        assert result_query == "사업자등록에 필요한 서류는 무엇인가요?"

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, rewriter):
        history = [
            {"role": "user", "content": "사업자등록 절차?"},
            {"role": "assistant", "content": "사업자등록은..."},
        ]

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch.object(rewriter, "llm"):
            with patch("utils.query_rewriter.ChatPromptTemplate") as mock_prompt:
                mock_prompt.from_messages.return_value = MagicMock()
                mock_prompt.from_messages.return_value.__or__ = Mock(return_value=MagicMock())
                mock_prompt.from_messages.return_value.__or__.return_value.__or__ = Mock(
                    return_value=mock_chain
                )

                result_query, was_rewritten = await rewriter.arewrite("서류?", history)

        assert result_query == "서류?"
        assert was_rewritten is False


class TestParseResponse:
    def test_parses_plain_json(self):
        response = '{"rewritten": "재작성된 질문", "is_rewritten": true}'
        result = QueryRewriter._parse_response(response)
        assert result["rewritten"] == "재작성된 질문"
        assert result["is_rewritten"] is True

    def test_returns_none_on_invalid_json(self):
        result = QueryRewriter._parse_response("not-json")
        assert result is None


class TestSingleton:
    def setup_method(self):
        reset_query_rewriter()

    def teardown_method(self):
        reset_query_rewriter()

    def test_get_query_rewriter_returns_same_instance(self):
        with patch("utils.query_rewriter.get_settings") as mock_get_settings, patch(
            "utils.query_rewriter.create_llm"
        ):
            mock_settings = MagicMock()
            mock_settings.enable_query_rewrite = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_get_settings.return_value = mock_settings

            rewriter1 = get_query_rewriter()
            rewriter2 = get_query_rewriter()
            assert rewriter1 is rewriter2
