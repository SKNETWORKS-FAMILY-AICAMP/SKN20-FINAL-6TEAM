"""Query rewrite module for multi-turn context handling."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.multiturn_context import build_active_directives_section
from utils.prompts import QUERY_REWRITE_PROMPT

logger = logging.getLogger(__name__)

_DEFAULT_HISTORY_TURNS = 6
_DEFAULT_MSG_CHARS = 350

REWRITE_STATUS_REWRITTEN = "rewritten"
REWRITE_STATUS_NO_REWRITE = "no_rewrite"
REWRITE_STATUS_SKIP_NO_HISTORY = "skip_no_history"
REWRITE_STATUS_SKIP_DISABLED = "skip_disabled"
REWRITE_STATUS_FALLBACK_TIMEOUT = "fallback_timeout"
REWRITE_STATUS_FALLBACK_EXCEPTION = "fallback_exception"
REWRITE_STATUS_FALLBACK_PARSE_ERROR = "fallback_parse_error"


def _safe_int(value: object, default: int) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


@dataclass(slots=True)
class RewriteMeta:
    query: str
    rewritten: bool
    reason: str
    elapsed: float


def _format_history_for_rewrite(
    history: list[dict],
    max_turns: int = _DEFAULT_HISTORY_TURNS,
    max_chars: int = _DEFAULT_MSG_CHARS,
) -> str:
    if not history:
        return ""

    recent = history[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        label = "user" if role == "user" else "assistant"
        lines.append(f"{label}: {content}")

    return "\n".join(lines)


class QueryRewriter:
    """LLM-based query rewriter for context-dependent follow-up questions."""

    def __init__(self):
        self.settings = get_settings()
        self.llm = create_llm(
            "query_rewriter",
            temperature=0.0,
            request_timeout=self.settings.query_rewrite_timeout,
        )

    async def arewrite(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> tuple[str, bool]:
        meta = await self.arewrite_with_meta(query=query, history=history)
        return meta.query, meta.rewritten

    async def arewrite_with_meta(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> RewriteMeta:
        started_at = time.perf_counter()

        if not history:
            return RewriteMeta(
                query=query,
                rewritten=False,
                reason=REWRITE_STATUS_SKIP_NO_HISTORY,
                elapsed=0.0,
            )
        if not self.settings.enable_query_rewrite:
            return RewriteMeta(
                query=query,
                rewritten=False,
                reason=REWRITE_STATUS_SKIP_DISABLED,
                elapsed=0.0,
            )

        try:
            max_turns = _safe_int(
                getattr(self.settings, "multiturn_history_turns", _DEFAULT_HISTORY_TURNS),
                _DEFAULT_HISTORY_TURNS,
            )
            max_chars = _safe_int(
                getattr(self.settings, "multiturn_history_chars", _DEFAULT_MSG_CHARS),
                _DEFAULT_MSG_CHARS,
            )
            history_text = _format_history_for_rewrite(history, max_turns=max_turns, max_chars=max_chars)
            if not history_text:
                return RewriteMeta(
                    query=query,
                    rewritten=False,
                    reason=REWRITE_STATUS_SKIP_NO_HISTORY,
                    elapsed=time.perf_counter() - started_at,
                )

            prompt = ChatPromptTemplate.from_messages([
                ("system", QUERY_REWRITE_PROMPT),
            ])
            chain = prompt | self.llm | StrOutputParser()
            active_directives_section = ""
            if getattr(self.settings, "enable_active_directive_memory", True):
                active_directives_section = build_active_directives_section(
                    history,
                    max_turns=max_turns,
                    max_chars=max_chars,
                )

            response = await asyncio.wait_for(
                chain.ainvoke(
                    {
                        "history": history_text,
                        "query": query,
                        "active_directives_section": active_directives_section,
                    }
                ),
                timeout=self.settings.query_rewrite_timeout,
            )

            result = self._parse_response(response)
            if result is None:
                return RewriteMeta(
                    query=query,
                    rewritten=False,
                    reason=REWRITE_STATUS_FALLBACK_PARSE_ERROR,
                    elapsed=time.perf_counter() - started_at,
                )

            rewritten = result.get("rewritten", "").strip()
            is_rewritten = result.get("is_rewritten", False)

            if is_rewritten and rewritten:
                logger.info("[query_rewrite] '%s' -> '%s'", query[:30], rewritten[:50])
                return RewriteMeta(
                    query=rewritten,
                    rewritten=True,
                    reason=REWRITE_STATUS_REWRITTEN,
                    elapsed=time.perf_counter() - started_at,
                )

            return RewriteMeta(
                query=query,
                rewritten=False,
                reason=REWRITE_STATUS_NO_REWRITE,
                elapsed=time.perf_counter() - started_at,
            )

        except asyncio.TimeoutError:
            logger.warning(
                "[query_rewrite] timeout (%.1fs), fallback to original: '%s...'",
                self.settings.query_rewrite_timeout,
                query[:30],
            )
            return RewriteMeta(
                query=query,
                rewritten=False,
                reason=REWRITE_STATUS_FALLBACK_TIMEOUT,
                elapsed=time.perf_counter() - started_at,
            )
        except Exception as e:
            logger.warning(
                "[query_rewrite] failed (%s), fallback to original: '%s...'",
                e,
                query[:30],
            )
            return RewriteMeta(
                query=query,
                rewritten=False,
                reason=REWRITE_STATUS_FALLBACK_EXCEPTION,
                elapsed=time.perf_counter() - started_at,
            )

    @staticmethod
    def _parse_response(response: str) -> dict | None:
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("[query_rewrite] JSON parse failed: %s", e)
            return None


_query_rewriter: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriter()
    return _query_rewriter


def reset_query_rewriter() -> None:
    global _query_rewriter
    _query_rewriter = None
