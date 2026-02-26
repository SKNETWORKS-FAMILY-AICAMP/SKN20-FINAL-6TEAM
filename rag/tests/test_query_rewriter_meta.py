"""Tests for query rewrite metadata path."""

import pytest
from unittest.mock import MagicMock, patch

from utils.query_rewriter import (
    QueryRewriter,
    REWRITE_STATUS_SKIP_DISABLED,
    REWRITE_STATUS_SKIP_NO_HISTORY,
)


@pytest.fixture
def rewriter():
    mock_settings = MagicMock()
    mock_settings.enable_query_rewrite = True
    mock_settings.query_rewrite_timeout = 5.0
    with patch("utils.query_rewriter.get_settings", return_value=mock_settings), patch(
        "utils.query_rewriter.create_llm"
    ) as mock_create_llm:
        mock_create_llm.return_value = MagicMock()
        yield QueryRewriter()


@pytest.mark.asyncio
async def test_meta_skip_no_history(rewriter: QueryRewriter):
    meta = await rewriter.arewrite_with_meta("질문", None)
    assert meta.query == "질문"
    assert meta.rewritten is False
    assert meta.reason == REWRITE_STATUS_SKIP_NO_HISTORY


@pytest.mark.asyncio
async def test_meta_skip_disabled(rewriter: QueryRewriter):
    rewriter.settings.enable_query_rewrite = False
    meta = await rewriter.arewrite_with_meta("질문", [{"role": "user", "content": "이전"}])
    assert meta.query == "질문"
    assert meta.rewritten is False
    assert meta.reason == REWRITE_STATUS_SKIP_DISABLED

