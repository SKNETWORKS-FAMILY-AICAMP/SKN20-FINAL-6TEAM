"""Utilities to decompose cross-domain questions into domain-specific sub-queries."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.cache import LRUCache
from utils.config import create_llm, get_settings
from utils.multiturn_context import build_active_directives_section
from utils.prompts import QUESTION_DECOMPOSER_PROMPT

logger = logging.getLogger(__name__)

_DEFAULT_HISTORY_TURNS = 6
_DEFAULT_HISTORY_CHARS = 350
_CACHE_HISTORY_MESSAGES = 8


def _safe_int(value: object, default: int) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


@dataclass
class SubQuery:
    domain: str
    query: str


def _format_history(
    history: list[dict],
    max_turns: int = _DEFAULT_HISTORY_TURNS,
    max_chars: int = _DEFAULT_HISTORY_CHARS,
) -> str:
    if not history:
        return ""

    recent = history[-(max_turns * 2) :]
    lines: list[str] = []
    for msg in recent:
        role = msg.get("role", "")
        content = str(msg.get("content", ""))
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        if role == "user":
            lines.append(f"user: {content}")
        elif role == "assistant":
            lines.append(f"assistant: {content}")

    return "\n".join(lines)


def _build_cache_key(query: str, domains: list[str], history: list[dict] | None) -> str:
    key_parts = [query, ",".join(sorted(domains))]

    if history:
        recent = history[-_CACHE_HISTORY_MESSAGES:]
        snapshot_parts: list[str] = []
        for msg in recent:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content", ""))
            snapshot_parts.append(f"{role}:{content[:200]}")
        if snapshot_parts:
            key_parts.append("|".join(snapshot_parts))

    raw_key = "|".join(key_parts)
    return hashlib.md5(raw_key.encode()).hexdigest()


class QuestionDecomposer:
    """Split a multi-domain user question into domain-specific sub-queries."""

    def __init__(self):
        self.settings = get_settings()
        self.llm = create_llm("질문분해")
        self._cache: LRUCache[list[SubQuery]] = LRUCache(max_size=200, default_ttl=3600)

    def _build_prompt_variables(
        self,
        query: str,
        detected_domains: list[str],
        history: list[dict] | None = None,
    ) -> dict[str, str]:
        max_turns = _safe_int(
            getattr(self.settings, "multiturn_history_turns", _DEFAULT_HISTORY_TURNS),
            _DEFAULT_HISTORY_TURNS,
        )
        max_chars = _safe_int(
            getattr(self.settings, "multiturn_history_chars", _DEFAULT_HISTORY_CHARS),
            _DEFAULT_HISTORY_CHARS,
        )

        history_text = _format_history(history or [], max_turns=max_turns, max_chars=max_chars)
        if history_text:
            history_section = (
                "\n## 이전 대화(참고)\n"
                f"{history_text}\n\n"
                "이전 대화 맥락을 참고하여, 대명사나 생략된 주어를 구체화한 뒤 질문을 분해하세요.\n"
            )
        else:
            history_section = ""

        active_directives_section = ""
        if getattr(self.settings, "enable_active_directive_memory", True):
            active_directives_section = build_active_directives_section(
                history or [],
                max_turns=max_turns,
                max_chars=max_chars,
            )

        return {
            "query": query,
            "domains": ", ".join(detected_domains),
            "history_section": history_section,
            "active_directives_section": active_directives_section,
        }

    def _parse_response(
        self,
        response: str,
        detected_domains: list[str],
        original_query: str = "",
    ) -> list[SubQuery]:
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            result = json.loads(response)

        sub_queries_data = result.get("sub_queries", [])
        sub_queries: list[SubQuery] = []

        for sq in sub_queries_data:
            domain = sq.get("domain", "")
            sub_query = sq.get("query", "")

            if domain in detected_domains and sub_query:
                sub_queries.append(SubQuery(domain=domain, query=sub_query))
                logger.debug("[질문 분해] %s: '%s'", domain, sub_query[:50])

        if sub_queries and original_query:
            covered_domains = {sq.domain for sq in sub_queries}
            missing_domains = [d for d in detected_domains if d not in covered_domains]
            if missing_domains:
                logger.warning(
                    "[질문 분해] 누락 도메인 감지: %s -> 원본 질문으로 fallback SubQuery 추가",
                    missing_domains,
                )
                for domain in missing_domains:
                    sub_queries.append(SubQuery(domain=domain, query=original_query))

        return sub_queries

    def decompose(
        self,
        query: str,
        detected_domains: list[str],
        history: list[dict] | None = None,
    ) -> list[SubQuery]:
        if len(detected_domains) <= 1:
            domain = detected_domains[0] if detected_domains else "startup_funding"
            logger.info("[질문 분해] 단일 도메인(%s) - 분해 스킵", domain)
            return [SubQuery(domain=domain, query=query)]

        cache_key = _build_cache_key(query, detected_domains, history)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("[질문 분해] 캐시 히트 - '%s...'", query[:30])
            return cached

        logger.info("[질문 분해] 복합 질문 분해 시작: '%s' -> %s", query[:30], detected_domains)

        prompt = ChatPromptTemplate.from_messages([("system", QUESTION_DECOMPOSER_PROMPT)])
        chain = prompt | self.llm | StrOutputParser()

        try:
            variables = self._build_prompt_variables(query, detected_domains, history)
            response = chain.invoke(variables)

            sub_queries = self._parse_response(response, detected_domains, query)
            if not sub_queries:
                logger.warning(
                    "[질문 분해] 분해 실패, 모든 도메인(%s)에 원본 질문 전달",
                    detected_domains,
                )
                return [SubQuery(domain=domain, query=query) for domain in detected_domains]

            logger.info("[질문 분해] 완료: %d개 하위 질문 생성", len(sub_queries))
            self._cache.set(cache_key, sub_queries)
            return sub_queries

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                "[질문 분해] 파싱 실패: %s -> 모든 도메인(%s)에 원본 질문 전달",
                e,
                detected_domains,
            )
            return [SubQuery(domain=domain, query=query) for domain in detected_domains]

    async def adecompose(
        self,
        query: str,
        detected_domains: list[str],
        history: list[dict] | None = None,
    ) -> list[SubQuery]:
        if len(detected_domains) <= 1:
            domain = detected_domains[0] if detected_domains else "startup_funding"
            logger.info("[질문 분해] 단일 도메인(%s) - 분해 스킵", domain)
            return [SubQuery(domain=domain, query=query)]

        cache_key = _build_cache_key(query, detected_domains, history)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("[질문 분해] 캐시 히트 - '%s...'", query[:30])
            return cached

        logger.info("[질문 분해] 복합 질문 비동기 분해 시작: '%s' -> %s", query[:30], detected_domains)

        prompt = ChatPromptTemplate.from_messages([("system", QUESTION_DECOMPOSER_PROMPT)])
        chain = prompt | self.llm | StrOutputParser()

        try:
            variables = self._build_prompt_variables(query, detected_domains, history)
            response = await chain.ainvoke(variables)

            sub_queries = self._parse_response(response, detected_domains, query)
            if not sub_queries:
                logger.warning(
                    "[질문 분해] 분해 실패, 모든 도메인(%s)에 원본 질문 전달",
                    detected_domains,
                )
                return [SubQuery(domain=domain, query=query) for domain in detected_domains]

            logger.info("[질문 분해] 완료: %d개 하위 질문 생성", len(sub_queries))
            self._cache.set(cache_key, sub_queries)
            return sub_queries

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                "[질문 분해] 파싱 실패: %s -> 모든 도메인(%s)에 원본 질문 전달",
                e,
                detected_domains,
            )
            return [SubQuery(domain=domain, query=query) for domain in detected_domains]


_question_decomposer: QuestionDecomposer | None = None


def get_question_decomposer() -> QuestionDecomposer:
    global _question_decomposer
    if _question_decomposer is None:
        _question_decomposer = QuestionDecomposer()
    return _question_decomposer


def reset_question_decomposer() -> None:
    global _question_decomposer
    _question_decomposer = None
