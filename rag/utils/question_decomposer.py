"""복합 질문 분해 모듈.

여러 도메인에 걸친 복합 질문을 단일 도메인 질문들로 분해합니다.
대화 이력을 활용하여 대명사/생략된 주어를 해소합니다.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.cache import LRUCache
from utils.config import create_llm, get_settings
from utils.prompts import QUESTION_DECOMPOSER_PROMPT

logger = logging.getLogger(__name__)

# 프롬프트에 포함할 최근 대화 턴 수
MAX_HISTORY_TURNS = 3


@dataclass
class SubQuery:
    """분해된 하위 질문.

    Attributes:
        domain: 질문이 속하는 도메인
        query: 분해된 질문 내용
    """

    domain: str
    query: str


def _format_history(history: list[dict], max_turns: int = MAX_HISTORY_TURNS) -> str:
    """대화 이력을 프롬프트용 문자열로 포맷합니다.

    Args:
        history: 대화 이력 (role, content 딕셔너리 리스트)
        max_turns: 최대 포함할 턴 수

    Returns:
        포맷된 이력 문자열
    """
    if not history:
        return ""

    # 최근 N턴만 사용 (user+assistant 쌍 기준)
    recent = history[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"사용자: {content[:200]}")
        elif role == "assistant":
            lines.append(f"AI: {content[:200]}")

    return "\n".join(lines)


def _build_cache_key(query: str, domains: list[str], history: list[dict] | None) -> str:
    """캐시 키를 생성합니다.

    Args:
        query: 원본 질문
        domains: 감지된 도메인 리스트
        history: 대화 이력

    Returns:
        해시된 캐시 키
    """
    key_parts = [query, ",".join(sorted(domains))]

    # 최근 1턴의 assistant 응답을 키에 포함 (맥락 변화 감지)
    if history:
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                key_parts.append(msg.get("content", "")[:200])
                break

    raw_key = "|".join(key_parts)
    return hashlib.md5(raw_key.encode()).hexdigest()


class QuestionDecomposer:
    """복합 질문을 단일 도메인 질문들로 분해하는 클래스.

    여러 도메인이 감지된 복합 질문을 각 도메인에 해당하는
    독립적인 질문들로 분해합니다. 대화 이력을 활용하여
    대명사와 생략된 맥락을 해소합니다.

    Example:
        입력: "창업 절차와 세금 신고 방법 알려주세요" (startup_funding, finance_tax)
        출력: [
            SubQuery(domain="startup_funding", query="창업 절차 알려주세요"),
            SubQuery(domain="finance_tax", query="세금 신고 방법 알려주세요"),
        ]
    """

    def __init__(self):
        """QuestionDecomposer를 초기화합니다."""
        self.settings = get_settings()
        self.llm = create_llm("질문분해")
        self._cache: LRUCache[list[SubQuery]] = LRUCache(
            max_size=200, default_ttl=3600,
        )

    def _build_prompt_variables(
        self,
        query: str,
        detected_domains: list[str],
        history: list[dict] | None = None,
    ) -> dict[str, str]:
        """프롬프트 변수를 구성합니다.

        Args:
            query: 원본 질문
            detected_domains: 감지된 도메인 리스트
            history: 대화 이력

        Returns:
            프롬프트 변수 딕셔너리
        """
        history_text = _format_history(history or [])
        if history_text:
            history_section = (
                f"\n## 이전 대화 (참고용)\n{history_text}\n\n"
                "위 대화 맥락을 참고하여, 대명사나 생략된 주어를 구체화한 뒤 질문을 분해하세요.\n"
            )
        else:
            history_section = ""

        return {
            "query": query,
            "domains": ", ".join(detected_domains),
            "history_section": history_section,
        }

    def _parse_response(
        self,
        response: str,
        detected_domains: list[str],
        original_query: str = "",
    ) -> list[SubQuery]:
        """LLM 응답을 파싱하여 SubQuery 리스트를 반환합니다.

        누락된 도메인이 있으면 원본 쿼리로 fallback SubQuery를 추가합니다.

        Args:
            response: LLM 응답 문자열
            detected_domains: 감지된 도메인 리스트
            original_query: 원본 질문 (누락 도메인 fallback용)

        Returns:
            파싱된 SubQuery 리스트

        Raises:
            json.JSONDecodeError: JSON 파싱 실패 시
        """
        # JSON 블록 추출
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            result = json.loads(response)

        sub_queries_data = result.get("sub_queries", [])
        sub_queries = []

        for sq in sub_queries_data:
            domain = sq.get("domain", "")
            sub_query = sq.get("query", "")

            # 유효한 도메인인지 확인
            if domain in detected_domains and sub_query:
                sub_queries.append(SubQuery(domain=domain, query=sub_query))
                logger.debug(
                    "[질문 분해] %s: '%s'",
                    domain,
                    sub_query[:50],
                )

        # 누락 도메인 감지 및 fallback SubQuery 추가
        if sub_queries and original_query:
            covered_domains = {sq.domain for sq in sub_queries}
            missing_domains = [d for d in detected_domains if d not in covered_domains]
            if missing_domains:
                logger.warning(
                    "[질문 분해] 도메인 누락 감지: %s — 원본 질문으로 fallback SubQuery 추가",
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
        """복합 질문을 단일 도메인 질문들로 분해합니다.

        Args:
            query: 원본 질문
            detected_domains: 감지된 도메인 리스트
            history: 대화 이력 (최근 N턴 활용)

        Returns:
            분해된 하위 질문 리스트
        """
        # 단일 도메인이면 분해 불필요
        if len(detected_domains) <= 1:
            domain = detected_domains[0] if detected_domains else "startup_funding"
            logger.info("[질문 분해] 단일 도메인 (%s) - 분해 불필요", domain)
            return [SubQuery(domain=domain, query=query)]

        # 캐시 확인
        cache_key = _build_cache_key(query, detected_domains, history)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("[질문 분해] 캐시 히트 - '%s...'", query[:30])
            return cached

        logger.info(
            "[질문 분해] 복합 질문 분해 시작: '%s' → %s",
            query[:30],
            detected_domains,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", QUESTION_DECOMPOSER_PROMPT),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            variables = self._build_prompt_variables(query, detected_domains, history)
            response = chain.invoke(variables)

            sub_queries = self._parse_response(response, detected_domains, query)

            # 분해 결과가 비어있으면 원본 사용
            if not sub_queries:
                logger.warning(
                    "[질문 분해] 분해 실패, 모든 도메인(%s)에 원본 질문 전달 "
                    "(도메인 간 노이즈 증가 가능)",
                    detected_domains,
                )
                return [
                    SubQuery(domain=domain, query=query)
                    for domain in detected_domains
                ]

            logger.info(
                "[질문 분해] 완료: %d개 하위 질문 생성",
                len(sub_queries),
            )

            # 캐시 저장
            self._cache.set(cache_key, sub_queries)

            return sub_queries

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                "[질문 분해] 파싱 실패: %s — 모든 도메인(%s)에 원본 질문 전달 "
                "(도메인 간 노이즈 증가 가능)",
                e,
                detected_domains,
            )
            # 실패 시 각 도메인에 원본 질문 전달
            return [
                SubQuery(domain=domain, query=query)
                for domain in detected_domains
            ]

    async def adecompose(
        self,
        query: str,
        detected_domains: list[str],
        history: list[dict] | None = None,
    ) -> list[SubQuery]:
        """복합 질문을 비동기로 분해합니다.

        chain.ainvoke()를 직접 사용하여 진정한 비동기 처리를 합니다.

        Args:
            query: 원본 질문
            detected_domains: 감지된 도메인 리스트
            history: 대화 이력 (최근 N턴 활용)

        Returns:
            분해된 하위 질문 리스트
        """
        # 단일 도메인이면 분해 불필요
        if len(detected_domains) <= 1:
            domain = detected_domains[0] if detected_domains else "startup_funding"
            logger.info("[질문 분해] 단일 도메인 (%s) - 분해 불필요", domain)
            return [SubQuery(domain=domain, query=query)]

        # 캐시 확인
        cache_key = _build_cache_key(query, detected_domains, history)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("[질문 분해] 캐시 히트 - '%s...'", query[:30])
            return cached

        logger.info(
            "[질문 분해] 복합 질문 비동기 분해 시작: '%s' → %s",
            query[:30],
            detected_domains,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", QUESTION_DECOMPOSER_PROMPT),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            variables = self._build_prompt_variables(query, detected_domains, history)
            response = await chain.ainvoke(variables)

            sub_queries = self._parse_response(response, detected_domains, query)

            # 분해 결과가 비어있으면 원본 사용
            if not sub_queries:
                logger.warning(
                    "[질문 분해] 분해 실패, 모든 도메인(%s)에 원본 질문 전달 "
                    "(도메인 간 노이즈 증가 가능)",
                    detected_domains,
                )
                return [
                    SubQuery(domain=domain, query=query)
                    for domain in detected_domains
                ]

            logger.info(
                "[질문 분해] 완료: %d개 하위 질문 생성",
                len(sub_queries),
            )

            # 캐시 저장
            self._cache.set(cache_key, sub_queries)

            return sub_queries

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                "[질문 분해] 파싱 실패: %s — 모든 도메인(%s)에 원본 질문 전달 "
                "(도메인 간 노이즈 증가 가능)",
                e,
                detected_domains,
            )
            return [
                SubQuery(domain=domain, query=query)
                for domain in detected_domains
            ]


_question_decomposer: QuestionDecomposer | None = None


def get_question_decomposer() -> QuestionDecomposer:
    """QuestionDecomposer 싱글톤 인스턴스를 반환합니다.

    Returns:
        QuestionDecomposer 인스턴스
    """
    global _question_decomposer
    if _question_decomposer is None:
        _question_decomposer = QuestionDecomposer()
    return _question_decomposer


def reset_question_decomposer() -> None:
    """QuestionDecomposer 싱글톤을 리셋합니다 (테스트용)."""
    global _question_decomposer
    _question_decomposer = None
