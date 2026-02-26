"""응답 생성 에이전트 모듈.

검색된 문서 기반 답변 생성을 전담합니다.
- 단일 도메인: 도메인 에이전트 프롬프트 + 액션 힌트 주입
- 복수 도메인: MULTI_DOMAIN_SYNTHESIS_PROMPT로 LLM 1회 통합 생성
- 액션 선제안: 생성 전에 액션을 결정하여 답변에 반영
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agents.base import BaseAgent, RetrievalResult
from chains.rag_chain import RAGChain
from schemas.request import UserContext
from schemas.response import ActionSuggestion, SourceDocument
from utils.config import DOMAIN_LABELS, create_llm, get_settings
from utils.prompts import (
    ACTION_HINT_TEMPLATE,
    MULTI_DOMAIN_SYNTHESIS_PROMPT,
    format_history_for_prompt,
)
from utils.question_decomposer import SubQuery

logger = logging.getLogger(__name__)

# 에러 종류별 Fallback 메시지
FALLBACK_NO_DOCUMENTS = (
    "검색된 참고 자료가 부족하여 정확한 답변을 드리기 어렵습니다. "
    "질문의 핵심 키워드를 포함하여 더 구체적으로 작성해 주시거나, "
    "다른 표현으로 다시 질문해 주세요."
)
FALLBACK_NO_DOCUMENTS_WITH_ACTIONS = (
    "검색된 참고 자료가 부족하여 상세한 답변을 드리기 어렵지만, "
    "요청하신 문서는 아래 버튼을 통해 바로 작성하실 수 있습니다."
)
FALLBACK_TIMEOUT = "응답 생성에 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
FALLBACK_SYSTEM_ERROR = "일시적인 시스템 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


@dataclass
class GenerationResult:
    """생성 결과 데이터 클래스.

    Attributes:
        content: 생성된 답변 텍스트
        actions: 추천 액션 리스트
        sources: 출처 문서 리스트
        metadata: 추가 메타데이터
    """

    content: str
    actions: list[ActionSuggestion]
    sources: list[SourceDocument]
    metadata: dict[str, Any] = field(default_factory=dict)


class ResponseGeneratorAgent:
    """응답 생성 전담 에이전트.

    검색 결과를 기반으로 최종 답변을 생성합니다.
    BaseAgent를 상속하지 않는 독립 클래스입니다 (검색 기능 불필요).

    주요 기능:
    - 단일 도메인: 도메인 에이전트의 시스템 프롬프트를 사용하여 생성
    - 복수 도메인: MULTI_DOMAIN_SYNTHESIS_PROMPT로 통합 생성
    - 액션 선제안: 생성 전에 액션을 결정하여 답변에 반영

    Attributes:
        settings: 설정 객체
        agents: 도메인 에이전트 딕셔너리
        rag_chain: RAG 체인 (format_context 사용)
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        rag_chain: RAGChain | None = None,
    ) -> None:
        """ResponseGeneratorAgent를 초기화합니다.

        Args:
            agents: 도메인 에이전트 딕셔너리
            rag_chain: RAG 체인 인스턴스 (None이면 새로 생성)
        """
        self.settings = get_settings()
        self.agents = agents
        self.rag_chain = rag_chain or RAGChain()

    def _get_llm(self, domain: str | None = None) -> "ChatOpenAI":
        """LLM 인스턴스를 생성합니다.

        Args:
            domain: 도메인 (주어지면 도메인별 temperature 적용)

        Returns:
            ChatOpenAI 인스턴스
        """
        if domain:
            temperature = self.settings.domain_temperatures.get(domain, 0.1)
        else:
            temperature = 0.1

        return create_llm(
            "통합생성",
            temperature=temperature,
            request_timeout=self.settings.llm_timeout,
            max_tokens=self.settings.generation_max_tokens,
        )

    def _collect_actions(
        self,
        query: str,
        retrieval_results: dict[str, RetrievalResult],
        domains: list[str],
    ) -> list[ActionSuggestion]:
        """모든 에이전트의 ACTION_RULES를 쿼리에 대해 검사하여 액션을 수집합니다.

        도메인 라우팅과 독립적으로 전체 에이전트를 스캔하여,
        키워드가 매칭되는 액션은 모두 수집합니다.

        Args:
            query: 사용자 질문
            retrieval_results: 도메인별 검색 결과
            domains: 관련 도메인 리스트

        Returns:
            수집된 액션 리스트
        """
        if not self.settings.enable_action_aware_generation:
            return []

        actions: list[ActionSuggestion] = []
        seen_keys: set[str] = set()

        def _dedup_key(action: ActionSuggestion) -> str:
            """액션의 중복 제거 키를 생성합니다.

            Args:
                action: 액션 제안 객체

            Returns:
                "type:document_type" 형태의 고유 키
            """
            doc_type: str = action.params.get("document_type", "")
            return f"{action.type}:{doc_type}" if doc_type else action.type

        # 모든 에이전트의 ACTION_RULES를 쿼리 기반으로 검사
        for agent in self.agents.values():
            domain_actions = agent.suggest_actions(query, "")

            for action in domain_actions:
                key = _dedup_key(action)
                if key not in seen_keys:
                    seen_keys.add(key)
                    actions.append(action)

        logger.info("[생성기] 액션 %d건 사전 수집", len(actions))
        return actions

    @staticmethod
    def _format_actions_context(actions: list[ActionSuggestion]) -> str:
        """액션 리스트를 프롬프트에 삽입할 문자열로 포맷팅합니다.

        Args:
            actions: 액션 리스트

        Returns:
            포맷팅된 액션 컨텍스트 문자열
        """
        if not actions:
            return "없음"

        parts = []
        for action in actions:
            desc = f" - {action.description}" if action.description else ""
            parts.append(f"- {action.label}{desc}")
        return "\n".join(parts)

    @staticmethod
    def _audit_citations(content: str, doc_count: int) -> str:
        """생성된 답변에 [번호] 인용이 있는지 감사합니다.

        문서가 제공되었는데 인용이 하나도 없으면 경고 로그를 남기고
        주의 문구를 답변 끝에 추가합니다.

        Args:
            content: 생성된 답변 텍스트
            doc_count: 제공된 문서 수

        Returns:
            (필요 시 주의 문구가 추가된) 답변 텍스트
        """
        if doc_count > 0 and not re.search(r"\[\d+\]", content):
            logger.warning(
                "[생성기] 인용 누락: 문서 %d건 제공, [번호] 인용 0건", doc_count
            )
            content += "\n\n> 주의: 이 답변은 참고 자료 인용이 누락되었을 수 있습니다."
        return content

    async def agenerate(
        self,
        query: str,
        sub_queries: list[SubQuery],
        retrieval_results: dict[str, RetrievalResult],
        user_context: UserContext | None,
        domains: list[str],
        history: list[dict] | None = None,
    ) -> GenerationResult:
        """검색 결과 기반으로 답변을 비동기 생성합니다.

        Args:
            query: 사용자 질문
            sub_queries: 분해된 하위 질문 리스트
            retrieval_results: 도메인별 검색 결과
            user_context: 사용자 컨텍스트
            domains: 분류된 도메인 리스트
            history: 대화 이력 (반복 방지용, None이면 무시)

        Returns:
            GenerationResult
        """
        start = time.time()
        user_type, company_context = BaseAgent._extract_user_context(user_context)

        # 액션 사전 수집
        actions = self._collect_actions(query, retrieval_results, domains)
        actions_context = self._format_actions_context(actions)

        # 법률 보충 문서
        legal_supplement_result = retrieval_results.get("law_common_supplement")
        legal_supplement_docs = (
            legal_supplement_result.documents if legal_supplement_result else []
        )

        # 전체 소스 수집
        all_sources: list[SourceDocument] = []
        for domain in domains:
            if domain in retrieval_results:
                all_sources.extend(retrieval_results[domain].sources)
        if legal_supplement_result:
            all_sources.extend(legal_supplement_result.sources)

        # 단일 도메인 vs 복수 도메인
        # 에이전트가 존재하고 검색 결과가 있는 도메인만 활성
        active_domains = [
            d for d in domains
            if d in self.agents and d in retrieval_results
        ]

        # 탈락된 도메인 경고 로깅
        dropped_domains = [d for d in domains if d not in active_domains]
        if dropped_domains:
            logger.warning(
                "[생성기] 도메인 탈락: %s (에이전트 미등록 또는 검색 결과 없음) — "
                "사용자가 %d개 도메인 답변을 기대했지만 %d개만 활성",
                dropped_domains,
                len(domains),
                len(active_domains),
            )

        # 빈 결과 도메인 필터링: 문서가 0건인 도메인은 실질적으로 비활성
        effective_domains = [
            d for d in active_domains
            if retrieval_results[d].documents
        ]
        empty_domains = [d for d in active_domains if d not in effective_domains]
        if empty_domains:
            logger.warning(
                "[생성기] 검색 결과 0건 도메인: %s — 실질적으로 비활성 처리",
                empty_domains,
            )

        try:
            if len(effective_domains) <= 1 and len(active_domains) <= 1:
                # 진정한 단일 도메인: 단일 프롬프트 사용
                target_domain = effective_domains[0] if effective_domains else (active_domains[0] if active_domains else domains[0])
                content = await self._agenerate_single(
                    query=query,
                    domain=target_domain,
                    retrieval_results=retrieval_results,
                    legal_supplement_docs=legal_supplement_docs,
                    user_type=user_type,
                    company_context=company_context,
                    actions_context=actions_context,
                    history=history,
                )
            elif len(effective_domains) <= 1 and len(active_domains) > 1:
                # 원래 복수 도메인이었으나 실질적으로 단일 도메인만 문서 보유
                # 단일 프롬프트 사용하되, 누락 안내 추가
                target_domain = effective_domains[0] if effective_domains else active_domains[0]
                content = await self._agenerate_single(
                    query=query,
                    domain=target_domain,
                    retrieval_results=retrieval_results,
                    legal_supplement_docs=legal_supplement_docs,
                    user_type=user_type,
                    company_context=company_context,
                    actions_context=actions_context,
                    history=history,
                )
            else:
                # 복수 도메인: effective_domains로 생성
                content = await self._agenerate_multi(
                    query=query,
                    sub_queries=sub_queries,
                    retrieval_results=retrieval_results,
                    legal_supplement_docs=legal_supplement_docs,
                    domains=effective_domains,
                    user_type=user_type,
                    company_context=company_context,
                    actions_context=actions_context,
                    history=history,
            )
        except asyncio.TimeoutError:
            logger.error("[생성기] LLM 호출 타임아웃", exc_info=True)
            content = FALLBACK_TIMEOUT
        except Exception as e:
            logger.error("[생성기] LLM 호출 실패: %s", e, exc_info=True)
            content = FALLBACK_SYSTEM_ERROR

        # 인용 감사: 문서가 제공되었는데 [번호] 인용이 없으면 경고
        total_docs = sum(
            len(retrieval_results[d].documents)
            for d in domains if d in retrieval_results
        )
        content = self._audit_citations(content, total_docs)

        elapsed = time.time() - start
        logger.info("[생성기] 비동기 완료: %d자 (%.3fs)", len(content), elapsed)

        return GenerationResult(
            content=content,
            actions=actions,
            sources=all_sources,
            metadata={"generate_time": elapsed},
        )

    async def astream_generate(
        self,
        query: str,
        documents: list[Document],
        user_context: UserContext | None,
        domain: str,
        actions: list[ActionSuggestion] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """단일 도메인 답변을 토큰 스트리밍으로 생성합니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            user_context: 사용자 컨텍스트
            domain: 도메인
            actions: 사전 수집된 액션 (None이면 수집 스킵)
            history: 대화 이력 (반복 방지용, None이면 무시)

        Yields:
            스트리밍 토큰 딕셔너리
        """
        user_type, company_context = BaseAgent._extract_user_context(user_context)
        agent = self.agents.get(domain)
        if not agent:
            logger.warning("[생성기 스트리밍] 도메인 에이전트 없음: %s", domain)
            return

        if not documents:
            msg = FALLBACK_NO_DOCUMENTS_WITH_ACTIONS if actions else FALLBACK_NO_DOCUMENTS
            yield {"type": "token", "content": msg}
            yield {"type": "generation_done", "content": msg}
            return

        context = self.rag_chain.format_context(documents)

        # 시스템 프롬프트에 액션 힌트 주입
        system_prompt = agent.get_system_prompt()
        if actions and self.settings.enable_action_aware_generation:
            actions_context = self._format_actions_context(actions)
            system_prompt += "\n" + ACTION_HINT_TEMPLATE.format(actions_context=actions_context)

        # 대화 이력 주입 (반복 방지)
        history_section = format_history_for_prompt(history)
        if history_section:
            system_prompt += history_section

        # 도메인 에이전트의 시스템 프롬프트 사용
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])

        llm = self._get_llm(domain)
        chain = prompt | llm | StrOutputParser()

        content_buffer = ""
        async for token in chain.astream({
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
        }):
            content_buffer += token
            yield {"type": "token", "content": token}

        content_buffer = self._audit_citations(content_buffer, len(documents))
        yield {"type": "generation_done", "content": content_buffer}

    async def astream_generate_multi(
        self,
        query: str,
        sub_queries: list[SubQuery],
        retrieval_results: dict[str, RetrievalResult],
        user_context: UserContext | None,
        domains: list[str],
        actions: list[ActionSuggestion] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """복수 도메인 답변을 LLM 토큰 스트리밍으로 통합 생성합니다.

        기존 방식: N회 도메인별 LLM 호출 + 마크다운 연결
        새 방식: 1회 LLM 호출로 통합 응답 스트리밍

        Args:
            query: 사용자 질문
            sub_queries: 분해된 하위 질문 리스트
            retrieval_results: 도메인별 검색 결과
            user_context: 사용자 컨텍스트
            domains: 관련 도메인 리스트
            actions: 사전 수집된 액션
            history: 대화 이력 (반복 방지용, None이면 무시)

        Yields:
            스트리밍 토큰 딕셔너리
        """
        user_type, company_context = BaseAgent._extract_user_context(user_context)

        # 빈 결과 도메인 필터링
        effective_domains = [
            d for d in domains
            if d in retrieval_results and retrieval_results[d].documents
        ]
        if not effective_domains:
            effective_domains = domains  # 전부 비어있으면 원본 유지

        # 전체 문서 병합
        all_documents: list[Document] = []
        for domain in effective_domains:
            if domain in retrieval_results:
                all_documents.extend(retrieval_results[domain].documents)
        legal_supplement = retrieval_results.get("law_common_supplement")
        if legal_supplement:
            all_documents.extend(legal_supplement.documents)

        if not all_documents:
            msg = FALLBACK_NO_DOCUMENTS_WITH_ACTIONS if actions else FALLBACK_NO_DOCUMENTS
            yield {"type": "token", "content": msg}
            yield {"type": "generation_done", "content": msg}
            return

        context = self.rag_chain.format_context(all_documents)
        domains_description = ", ".join(
            DOMAIN_LABELS.get(d, d) for d in effective_domains
        )
        actions_context = self._format_actions_context(actions or [])
        sub_queries_text = "\n".join(
            f"- [{DOMAIN_LABELS.get(sq.domain, sq.domain)}] {sq.query}"
            for sq in sub_queries
        ) if sub_queries else "없음"

        # 대화 이력 주입 (반복 방지)
        multi_system_prompt = MULTI_DOMAIN_SYNTHESIS_PROMPT
        history_section = format_history_for_prompt(history)
        if history_section:
            multi_system_prompt += history_section

        prompt = ChatPromptTemplate.from_messages([
            ("system", multi_system_prompt),
            ("human", "{query}"),
        ])

        llm = self._get_llm()
        chain = prompt | llm | StrOutputParser()

        content_buffer = ""
        async for token in chain.astream({
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
            "domains_description": domains_description,
            "actions_context": actions_context,
            "sub_queries_text": sub_queries_text,
        }):
            content_buffer += token
            yield {"type": "token", "content": token}

        content_buffer = self._audit_citations(content_buffer, len(all_documents))
        yield {"type": "generation_done", "content": content_buffer}

    # ── 내부 헬퍼 ──

    async def _agenerate_single(
        self,
        query: str,
        domain: str,
        retrieval_results: dict[str, RetrievalResult],
        legal_supplement_docs: list[Document],
        user_type: str,
        company_context: str,
        actions_context: str,
        history: list[dict] | None = None,
    ) -> str:
        """단일 도메인 답변을 비동기 생성합니다.

        Args:
            query: 사용자 질문
            domain: 도메인
            retrieval_results: 검색 결과
            legal_supplement_docs: 법률 보충 문서
            user_type: 사용자 유형
            company_context: 기업 컨텍스트
            actions_context: 액션 컨텍스트 문자열
            history: 대화 이력 (반복 방지용, None이면 무시)

        Returns:
            생성된 답변 문자열
        """
        agent = self.agents[domain]
        result = retrieval_results[domain]

        documents = result.documents
        if legal_supplement_docs and domain != "law_common":
            documents = result.documents + legal_supplement_docs

        if not documents:
            return FALLBACK_NO_DOCUMENTS

        context = self.rag_chain.format_context(documents)

        system_prompt = agent.get_system_prompt()
        if actions_context != "없음" and self.settings.enable_action_aware_generation:
            system_prompt += "\n" + ACTION_HINT_TEMPLATE.format(actions_context=actions_context)

        # 대화 이력 주입 (반복 방지)
        history_section = format_history_for_prompt(history)
        if history_section:
            system_prompt += history_section

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])

        llm = self._get_llm(domain)
        chain = prompt | llm | StrOutputParser()

        try:
            return await asyncio.wait_for(
                chain.ainvoke({
                    "query": query,
                    "context": context,
                    "user_type": user_type,
                    "company_context": company_context,
                }),
                timeout=self.settings.llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[생성기] LLM 타임아웃: %s", query[:30])
            if self.settings.enable_fallback:
                return FALLBACK_TIMEOUT
            raise
        except Exception as e:
            logger.exception("[생성기] LLM 호출 실패 (단일 도메인): %s", e)
            if self.settings.enable_fallback:
                return FALLBACK_SYSTEM_ERROR
            raise

    async def _agenerate_multi(
        self,
        query: str,
        sub_queries: list[SubQuery],
        retrieval_results: dict[str, RetrievalResult],
        legal_supplement_docs: list[Document],
        domains: list[str],
        user_type: str,
        company_context: str,
        actions_context: str,
        history: list[dict] | None = None,
    ) -> str:
        """복수 도메인 답변을 비동기 통합 생성합니다.

        Args:
            query: 사용자 질문
            sub_queries: 하위 질문 리스트
            retrieval_results: 검색 결과
            legal_supplement_docs: 법률 보충 문서
            domains: 도메인 리스트
            user_type: 사용자 유형
            company_context: 기업 컨텍스트
            actions_context: 액션 컨텍스트 문자열
            history: 대화 이력 (반복 방지용, None이면 무시)

        Returns:
            통합 생성된 답변 문자열
        """
        all_documents: list[Document] = []
        for domain in domains:
            if domain in retrieval_results:
                all_documents.extend(retrieval_results[domain].documents)
        if legal_supplement_docs:
            all_documents.extend(legal_supplement_docs)

        if not all_documents:
            return FALLBACK_NO_DOCUMENTS

        context = self.rag_chain.format_context(all_documents)
        domains_description = ", ".join(
            DOMAIN_LABELS.get(d, d) for d in domains
        )
        sub_queries_text = "\n".join(
            f"- [{DOMAIN_LABELS.get(sq.domain, sq.domain)}] {sq.query}"
            for sq in sub_queries
        ) if sub_queries else "없음"

        # 대화 이력 주입 (반복 방지)
        multi_system_prompt = MULTI_DOMAIN_SYNTHESIS_PROMPT
        history_section = format_history_for_prompt(history)
        if history_section:
            multi_system_prompt += history_section

        prompt = ChatPromptTemplate.from_messages([
            ("system", multi_system_prompt),
            ("human", "{query}"),
        ])

        llm = self._get_llm()
        chain = prompt | llm | StrOutputParser()

        try:
            return await asyncio.wait_for(
                chain.ainvoke({
                    "query": query,
                    "context": context,
                    "user_type": user_type,
                    "company_context": company_context,
                    "domains_description": domains_description,
                    "actions_context": actions_context,
                    "sub_queries_text": sub_queries_text,
                }),
                timeout=self.settings.llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[생성기] 복수 도메인 LLM 타임아웃: %s", query[:30])
            if self.settings.enable_fallback:
                return FALLBACK_TIMEOUT
            raise
        except Exception as e:
            logger.exception("[생성기] LLM 호출 실패 (복수 도메인): %s", e)
            if self.settings.enable_fallback:
                return FALLBACK_SYSTEM_ERROR
            raise
