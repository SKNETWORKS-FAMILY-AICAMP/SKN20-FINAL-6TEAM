"""Helpers for preserving active user directives across multi-turn chat."""

from __future__ import annotations

import re

_DEFAULT_MAX_TURNS = 6
_DEFAULT_MAX_MSG_CHARS = 350


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


def _recent_messages(history: list[dict], max_turns: int) -> list[dict]:
    if not history:
        return []
    return history[-(max_turns * 2) :]


def _find_latest_user_constraint(history: list[dict], pattern: re.Pattern[str], max_chars: int) -> str | None:
    for msg in reversed(history):
        if msg.get("role") != "user":
            continue
        content = str(msg.get("content", ""))
        if pattern.search(content):
            return _truncate(content.strip(), max_chars)
    return None


def build_active_directives_section(
    history: list[dict] | None,
    max_turns: int = _DEFAULT_MAX_TURNS,
    max_chars: int = _DEFAULT_MAX_MSG_CHARS,
) -> str:
    """Return prompt section that summarizes active directives from user history.

    Rules:
    - Uses recent conversation window only.
    - Takes the latest user message that matches each directive type.
    - Produces deterministic bullet list for prompt injection.
    """
    if not history:
        return ""

    recent = _recent_messages(history, max_turns=max_turns)
    if not recent:
        return ""

    latest_output_format = _find_latest_user_constraint(
        recent,
        re.compile(r"(표|테이블|체크리스트|step[- ]by[- ]step|단계별|json|요약)"),
        max_chars=max_chars,
    )
    latest_exclusion = _find_latest_user_constraint(
        recent,
        re.compile(r"(제외|빼고|말고|없이|금지|하지\s*마|원하지\s*않)"),
        max_chars=max_chars,
    )
    latest_scope = _find_latest_user_constraint(
        recent,
        re.compile(r"(예산|원|만원|억|지역|서울|부산|경기|기한|마감|이번\s*달|다음\s*주|오늘|내일)"),
        max_chars=max_chars,
    )
    latest_priority = _find_latest_user_constraint(
        recent,
        re.compile(r"(반드시|꼭|우선|중요|필수)"),
        max_chars=max_chars,
    )

    directives: list[str] = []
    if latest_scope:
        directives.append(f"- Scope/constraint: {latest_scope}")
    if latest_output_format:
        directives.append(f"- Output format: {latest_output_format}")
    if latest_exclusion:
        directives.append(f"- Exclusions: {latest_exclusion}")
    if latest_priority:
        directives.append(f"- Priority: {latest_priority}")

    if not directives:
        return ""

    return (
        "\n## Active User Directives (latest overrides older constraints)\n"
        + "\n".join(directives)
        + "\n"
    )

