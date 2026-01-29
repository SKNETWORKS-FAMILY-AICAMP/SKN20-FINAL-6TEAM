"""기본 에이전트 모듈.

모든 전문 에이전트가 상속받는 기본 클래스를 정의합니다.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncGenerator

from langchain_core.documents import Document

from chains.rag_chain import RAGChain
from schemas.request import UserContext
from schemas.response import ActionSuggestion, SourceDocument
from utils.config import get_settings

if TYPE_CHECKING:
    from utils.feedback import SearchStrategy


@dataclass
class AgentResponse:
    """에이전트 응답 데이터 클래스.

    Attributes:
        content: 응답 내용
        domain: 처리 도메인
        sources: 참고 출처
        actions: 추천 액션
        documents: 검색된 원본 문서
        metadata: 추가 메타데이터
    """

    content: str
    domain: str
    sources: list[SourceDocument] = field(default_factory=list)
    actions: list[ActionSuggestion] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """기본 에이전트 추상 클래스.

    모든 전문 에이전트가 상속받아 구현해야 하는 기본 인터페이스를 정의합니다.

    Attributes:
        domain: 에이전트 담당 도메인
        settings: 설정 객체
        rag_chain: RAG 체인 인스턴스

    Example:
        >>> class MyAgent(BaseAgent):
        ...     domain = "my_domain"
        ...     def get_system_prompt(self) -> str:
        ...         return "시스템 프롬프트"
        ...     def suggest_actions(self, query, response) -> list:
        ...         return []
    """

    domain: str = ""

    def __init__(self, rag_chain: RAGChain | None = None):
        """BaseAgent를 초기화합니다.

        Args:
            rag_chain: RAG 체인 인스턴스. None이면 새로 생성.
        """
        self.settings = get_settings()
        self.rag_chain = rag_chain or RAGChain()

    @abstractmethod
    def get_system_prompt(self) -> str:
        """시스템 프롬프트를 반환합니다.

        Returns:
            시스템 프롬프트 문자열
        """
        pass

    @abstractmethod
    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """추천 액션을 생성합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        pass

    def retrieve_context(
        self,
        query: str,
        k: int | None = None,
        include_common: bool = True,
    ) -> list[Document]:
        """컨텍스트 문서를 검색합니다.

        Args:
            query: 검색 쿼리
            k: 검색 결과 개수
            include_common: 공통 법령 DB 포함 여부

        Returns:
            검색된 문서 리스트
        """
        return self.rag_chain.retrieve(
            query=query,
            domain=self.domain,
            k=k,
            include_common=include_common,
        )

    def process(
        self,
        query: str,
        user_context: UserContext | None = None,
        search_strategy: "SearchStrategy | None" = None,
    ) -> AgentResponse:
        """질문을 처리하고 응답을 생성합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            search_strategy: 피드백 기반 검색 전략 (재시도 시 사용)

        Returns:
            에이전트 응답
        """
        # 사용자 컨텍스트 처리
        user_type = "예비 창업자"
        company_context = "정보 없음"

        if user_context:
            user_type = user_context.get_user_type_label()
            if user_context.company:
                company_context = user_context.company.to_context_string()

        # RAG 체인 실행
        result = self.rag_chain.invoke(
            query=query,
            domain=self.domain,
            system_prompt=self.get_system_prompt(),
            user_type=user_type,
            company_context=company_context,
            search_strategy=search_strategy,
        )

        # 액션 제안
        actions = self.suggest_actions(query, result["content"])

        return AgentResponse(
            content=result["content"],
            domain=self.domain,
            sources=result["sources"],
            actions=actions,
            documents=result["documents"],
        )

    async def aprocess(
        self,
        query: str,
        user_context: UserContext | None = None,
        search_strategy: "SearchStrategy | None" = None,
    ) -> AgentResponse:
        """질문을 비동기로 처리합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            search_strategy: 피드백 기반 검색 전략 (재시도 시 사용)

        Returns:
            에이전트 응답
        """
        # 사용자 컨텍스트 처리
        user_type = "예비 창업자"
        company_context = "정보 없음"

        if user_context:
            user_type = user_context.get_user_type_label()
            if user_context.company:
                company_context = user_context.company.to_context_string()

        # RAG 체인 실행
        result = await self.rag_chain.ainvoke(
            query=query,
            domain=self.domain,
            system_prompt=self.get_system_prompt(),
            user_type=user_type,
            company_context=company_context,
            search_strategy=search_strategy,
        )

        # 액션 제안
        actions = self.suggest_actions(query, result["content"])

        return AgentResponse(
            content=result["content"],
            domain=self.domain,
            sources=result["sources"],
            actions=actions,
            documents=result["documents"],
        )

    async def astream(
        self,
        query: str,
        user_context: UserContext | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """질문을 스트리밍으로 처리합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트

        Yields:
            스트리밍 응답 (token, sources, actions, done)
        """
        # 사용자 컨텍스트 처리
        user_type = "예비 창업자"
        company_context = "정보 없음"

        if user_context:
            user_type = user_context.get_user_type_label()
            if user_context.company:
                company_context = user_context.company.to_context_string()

        # 문서 검색 (스트리밍 전에 수행)
        documents = await asyncio.to_thread(
            self.rag_chain.retrieve,
            query,
            self.domain,
            None,
            True,
        )
        sources = self.rag_chain.documents_to_sources(documents)

        # 토큰 스트리밍
        content_buffer = ""
        async for token in self.rag_chain.astream(
            query=query,
            domain=self.domain,
            system_prompt=self.get_system_prompt(),
            user_type=user_type,
            company_context=company_context,
        ):
            content_buffer += token
            yield {"type": "token", "content": token}

        # 액션 제안
        actions = self.suggest_actions(query, content_buffer)

        # 메타데이터 전송
        yield {
            "type": "done",
            "content": content_buffer,
            "domain": self.domain,
            "sources": sources,
            "actions": actions,
            "documents": documents,
        }
