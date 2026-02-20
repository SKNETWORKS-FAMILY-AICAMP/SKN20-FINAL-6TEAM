"""응답 생성 에이전트 모듈.

검색된 문서 기반 답변 생성을 전담합니다.
- 단일 도메인: 도메인 에이전트 프롬프트 + 액션 힌트 주입
- 복수 도메인: MULTI_DOMAIN_SYNTHESIS_PROMPT로 LLM 1회 통합 생성
- 액션 선제안: 생성 전에 액션을 결정하여 답변에 반영
"""

import asyncio
import logging
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
)
from utils.question_decomposer import SubQuery

logger = logging.getLogger(__name__)


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

    def _get_llm(self) -> "ChatOpenAI":
        """LLM 인스턴스를 생성합니다.

        Returns:
            ChatOpenAI 인스턴스
        """
        return create_llm(
            "통합생성",
            temperature=0.1,
            request_timeout=self.settings.llm_timeout,
        )

    def _collect_actions(
        self,
        query: str,
        retrieval_results: dict[str, RetrievalResult],
        domains: list[str],
    ) -> list[ActionSuggestion]:
        """생성 전에 문서 내용 기반으로 액션을 수집합니다.

        기존 suggest_actions(query, content)는 응답 텍스트 기반이지만,
        여기서는 문서 내용을 프록시로 사용하여 생성 전에 액션을 결정합니다.

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
        seen_types: set[str] = set()

        for domain in domains:
            if domain not in self.agents or domain not in retrieval_results:
                continue

            agent = self.agents[domain]
            result = retrieval_results[domain]

            # 문서 내용을 응답 프록시로 사용
            doc_content = "\n".join(
                doc.page_content[:200] for doc in result.documents
            )
            domain_actions = agent.suggest_actions(query, doc_content)

            for action in domain_actions:
                if action.type not in seen_types:
                    seen_types.add(action.type)
                    actions.append(action)

        # 법률 보충 검색 결과의 액션도 수집
        if "law_common_supplement" in retrieval_results:
            legal_agent = self.agents.get("law_common")
            if legal_agent:
                supplement_result = retrieval_results["law_common_supplement"]
                doc_content = "\n".join(
                    doc.page_content[:200]
                    for doc in supplement_result.documents
                )
                legal_actions = legal_agent.suggest_actions(query, doc_content)
                for action in legal_actions:
                    if action.type not in seen_types:
                        seen_types.add(action.type)
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

    async def agenerate(
        self,
        query: str,
        sub_queries: list[SubQuery],
        retrieval_results: dict[str, RetrievalResult],
        user_context: UserContext | None,
        domains: list[str],
    ) -> GenerationResult:
        """검색 결과 기반으로 답변을 비동기 생성합니다.

        Args:
            query: 사용자 질문
            sub_queries: 분해된 하위 질문 리스트
            retrieval_results: 도메인별 검색 결과
            user_context: 사용자 컨텍스트
            domains: 분류된 도메인 리스트

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
        active_domains = [
            d for d in domains
            if d in self.agents and d in retrieval_results
        ]

        if len(active_domains) == 1:
            content = await self._agenerate_single(
                query=query,
                domain=active_domains[0],
                retrieval_results=retrieval_results,
                legal_supplement_docs=legal_supplement_docs,
                user_type=user_type,
                company_context=company_context,
                actions_context=actions_context,
            )
        else:
            content = await self._agenerate_multi(
                query=query,
                sub_queries=sub_queries,
                retrieval_results=retrieval_results,
                legal_supplement_docs=legal_supplement_docs,
                domains=active_domains,
                user_type=user_type,
                company_context=company_context,
                actions_context=actions_context,
            )

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
    ) -> AsyncGenerator[dict[str, Any], None]:
        """단일 도메인 답변을 토큰 스트리밍으로 생성합니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            user_context: 사용자 컨텍스트
            domain: 도메인
            actions: 사전 수집된 액션 (None이면 수집 스킵)

        Yields:
            스트리밍 토큰 딕셔너리
        """
        user_type, company_context = BaseAgent._extract_user_context(user_context)
        agent = self.agents.get(domain)
        if not agent:
            logger.warning("[생성기 스트리밍] 도메인 에이전트 없음: %s", domain)
            return

        if not documents:
            fallback = "검색된 참고 자료가 부족하여 정확한 답변을 드리기 어렵습니다. 질문을 더 구체적으로 작성해 주시거나, 다른 표현으로 다시 질문해 주세요."
            yield {"type": "token", "content": fallback}
            yield {"type": "generation_done", "content": fallback}
            return

        context = self.rag_chain.format_context(documents)

        # 액션 힌트 주입
        if actions and self.settings.enable_action_aware_generation:
            actions_context = self._format_actions_context(actions)
            context += ACTION_HINT_TEMPLATE.format(actions_context=actions_context)

        # 도메인 에이전트의 시스템 프롬프트 사용
        prompt = ChatPromptTemplate.from_messages([
            ("system", agent.get_system_prompt()),
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
        }):
            content_buffer += token
            yield {"type": "token", "content": token}

        yield {"type": "generation_done", "content": content_buffer}

    async def astream_generate_multi(
        self,
        query: str,
        sub_queries: list[SubQuery],
        retrieval_results: dict[str, RetrievalResult],
        user_context: UserContext | None,
        domains: list[str],
        actions: list[ActionSuggestion] | None = None,
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

        Yields:
            스트리밍 토큰 딕셔너리
        """
        user_type, company_context = BaseAgent._extract_user_context(user_context)

        # 전체 문서 병합
        all_documents: list[Document] = []
        for domain in domains:
            if domain in retrieval_results:
                all_documents.extend(retrieval_results[domain].documents)
        legal_supplement = retrieval_results.get("law_common_supplement")
        if legal_supplement:
            all_documents.extend(legal_supplement.documents)

        if not all_documents:
            fallback = "검색된 참고 자료가 부족하여 정확한 답변을 드리기 어렵습니다. 질문을 더 구체적으로 작성해 주시거나, 다른 표현으로 다시 질문해 주세요."
            yield {"type": "token", "content": fallback}
            yield {"type": "generation_done", "content": fallback}
            return

        context = self.rag_chain.format_context(all_documents)
        domains_description = ", ".join(
            DOMAIN_LABELS.get(d, d) for d in domains
        )
        actions_context = self._format_actions_context(actions or [])
        sub_queries_text = "\n".join(
            f"- [{DOMAIN_LABELS.get(sq.domain, sq.domain)}] {sq.query}"
            for sq in sub_queries
        ) if sub_queries else "없음"

        prompt = ChatPromptTemplate.from_messages([
            ("system", MULTI_DOMAIN_SYNTHESIS_PROMPT),
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

        Returns:
            생성된 답변 문자열
        """
        agent = self.agents[domain]
        result = retrieval_results[domain]

        documents = result.documents
        if legal_supplement_docs and domain != "law_common":
            documents = result.documents + legal_supplement_docs

        if not documents:
            return "검색된 참고 자료가 부족하여 정확한 답변을 드리기 어렵습니다. 질문을 더 구체적으로 작성해 주시거나, 다른 표현으로 다시 질문해 주세요."

        context = self.rag_chain.format_context(documents)

        if actions_context != "없음" and self.settings.enable_action_aware_generation:
            context += ACTION_HINT_TEMPLATE.format(actions_context=actions_context)

        prompt = ChatPromptTemplate.from_messages([
            ("system", agent.get_system_prompt()),
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
                }),
                timeout=self.settings.llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[생성기] LLM 타임아웃: %s", query[:30])
            if self.settings.enable_fallback:
                return self.settings.fallback_message
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
            return "검색된 참고 자료가 부족하여 정확한 답변을 드리기 어렵습니다. 질문을 더 구체적으로 작성해 주시거나, 다른 표현으로 다시 질문해 주세요."

        context = self.rag_chain.format_context(all_documents)
        domains_description = ", ".join(
            DOMAIN_LABELS.get(d, d) for d in domains
        )
        sub_queries_text = "\n".join(
            f"- [{DOMAIN_LABELS.get(sq.domain, sq.domain)}] {sq.query}"
            for sq in sub_queries
        ) if sub_queries else "없음"

        prompt = ChatPromptTemplate.from_messages([
            ("system", MULTI_DOMAIN_SYNTHESIS_PROMPT),
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
                return self.settings.fallback_message
            raise
