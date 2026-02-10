"""기본 에이전트 모듈.

모든 전문 에이전트가 상속받는 기본 클래스를 정의합니다.
역할 분리: retrieve_only (검색 전담), generate_only (생성 전담) 지원
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncGenerator

from langchain_core.documents import Document

from chains.rag_chain import RAGChain
from schemas.request import UserContext
from schemas.response import ActionSuggestion, SourceDocument
from utils.config import create_llm, get_settings

if TYPE_CHECKING:
    from utils.feedback import SearchStrategy

logger = logging.getLogger(__name__)


class RetrievalStatus(str, Enum):
    """검색 결과 상태."""

    SUCCESS = "success"  # 검색 성공, 품질 양호
    NEEDS_RETRY = "needs_retry"  # 검색 성공했으나 품질 미달, 재검색 필요
    FAILED = "failed"  # 검색 실패


@dataclass
class RetrievalEvaluationResult:
    """검색 평가 결과.

    Attributes:
        status: 검색 상태
        doc_count: 검색된 문서 수
        keyword_match_ratio: 키워드 매칭 비율 (0.0-1.0)
        avg_similarity_score: 평균 유사도 점수 (0.0-1.0)
        reason: 평가 이유 (실패/재시도 시)
    """

    status: RetrievalStatus
    doc_count: int
    keyword_match_ratio: float
    avg_similarity_score: float
    reason: str | None = None

    @property
    def passed(self) -> bool:
        """평가 통과 여부."""
        return self.status == RetrievalStatus.SUCCESS


@dataclass
class RetrievalResult:
    """검색 결과 데이터 클래스.

    Attributes:
        documents: 검색된 문서 리스트
        scores: 유사도 점수 리스트
        sources: SourceDocument 형태의 출처 정보
        evaluation: 검색 품질 평가 결과
        used_multi_query: Multi-Query 사용 여부
        retrieve_time: 검색 소요 시간
        domain: 검색 도메인
        query: 검색에 사용된 쿼리
        rewritten_query: 확장 쿼리 목록 문자열 (있을 경우)
    """

    documents: list[Document]
    scores: list[float]
    sources: list[SourceDocument]
    evaluation: RetrievalEvaluationResult
    used_multi_query: bool = False
    retrieve_time: float = 0.0
    domain: str = ""
    query: str = ""
    rewritten_query: str | None = None


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

    @staticmethod
    def _extract_user_context(user_context: UserContext | None) -> tuple[str, str]:
        """UserContext에서 user_type과 company_context 문자열을 추출합니다.

        Args:
            user_context: 사용자 컨텍스트 (None 가능)

        Returns:
            (user_type, company_context) 튜플
        """
        user_type = "예비 창업자"
        company_context = "정보 없음"
        if user_context:
            user_type = user_context.get_user_type_label()
            if user_context.company:
                company_context = user_context.company.to_context_string()
        return user_type, company_context

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
        include_common: bool = False,
    ) -> list[Document]:
        """컨텍스트 문서를 검색합니다.

        Args:
            query: 검색 쿼리
            k: 검색 결과 개수
            include_common: 공통 법령 DB 포함 여부

        Returns:
            검색된 문서 리스트
        """
        from utils.query import MultiQueryRetriever

        multi_query_retriever = MultiQueryRetriever(self.rag_chain)
        documents, _ = multi_query_retriever.retrieve(
            query=query,
            domain=self.domain,
            k=k,
            include_common=include_common,
        )
        return documents

    def retrieve_only(
        self,
        query: str,
        search_strategy: "SearchStrategy | None" = None,
        include_common: bool = False,
    ) -> RetrievalResult:
        """문서 검색만 수행합니다 (생성 없음).

        역할 분리 아키텍처에서 검색 전담 메서드로 사용됩니다.
        규칙 기반 평가를 수행하고, 필요 시 Multi-Query 재검색을 시도합니다.

        Args:
            query: 검색 쿼리
            search_strategy: 피드백 기반 검색 전략
            include_common: 공통 법령 DB 포함 여부

        Returns:
            RetrievalResult (문서, 점수, 평가 결과 포함)
        """
        from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator

        logger.info("[retrieve_only] %s 검색 시작: '%s'", self.domain, query[:50])
        start = time.time()

        # Multi-Query 검색 (항상 기본 경로)
        rewritten_query: str | None = None
        try:
            from utils.query import MultiQueryRetriever

            multi_query_retriever = MultiQueryRetriever(self.rag_chain)
            documents, rewritten_query = multi_query_retriever.retrieve(
                query=query,
                domain=self.domain,
                include_common=include_common,
                search_strategy=search_strategy,
            )
        except Exception as e:
            logger.warning("[retrieve_only] Multi-Query 검색 실패: %s", e)
            documents = []
            rewritten_query = None

        # 점수 추출 (메타데이터에서)
        scores = [doc.metadata.get("score", 0.0) for doc in documents]

        # 규칙 기반 평가
        evaluator = RuleBasedRetrievalEvaluator()
        evaluation = evaluator.evaluate(query, documents, scores)

        elapsed = time.time() - start
        logger.info(
            "[retrieve_only] %s 완료: %d건 (%.3fs, multi_query=%s)",
            self.domain,
            len(documents),
            elapsed,
            True,
        )

        return RetrievalResult(
            documents=documents,
            scores=scores,
            sources=self.rag_chain.documents_to_sources(documents),
            evaluation=evaluation,
            used_multi_query=True,
            retrieve_time=elapsed,
            domain=self.domain,
            query=query,
            rewritten_query=rewritten_query,
        )

    async def aretrieve_only(
        self,
        query: str,
        search_strategy: "SearchStrategy | None" = None,
        include_common: bool = False,
    ) -> RetrievalResult:
        """문서 검색만 비동기로 수행합니다.

        Args:
            query: 검색 쿼리
            search_strategy: 피드백 기반 검색 전략
            include_common: 공통 법령 DB 포함 여부

        Returns:
            RetrievalResult
        """
        return await asyncio.to_thread(
            self.retrieve_only,
            query,
            search_strategy,
            include_common,
        )

    def generate_only(
        self,
        query: str,
        documents: list[Document],
        user_context: UserContext | None = None,
        evaluation_feedback: str | None = None,
    ) -> str:
        """주어진 문서로 답변만 생성합니다 (검색 없음).

        역할 분리 아키텍처에서 생성 전담 메서드로 사용됩니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            user_context: 사용자 컨텍스트
            evaluation_feedback: 이전 평가 피드백 (재시도 시)

        Returns:
            생성된 답변 문자열
        """
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        logger.info("[generate_only] %s 생성 시작: '%s'", self.domain, query[:50])
        start = time.time()

        user_type, company_context = self._extract_user_context(user_context)

        # 컨텍스트 포맷팅
        context = self.rag_chain.format_context(documents)

        # 프롬프트 구성
        messages = [
            ("system", self.get_system_prompt()),
            ("human", "{query}"),
        ]
        if evaluation_feedback:
            messages.append((
                "system",
                "이전 답변이 품질 평가를 통과하지 못했습니다. "
                "다음 피드백을 반영하여 답변을 개선하세요:\n{evaluation_feedback}",
            ))
        prompt = ChatPromptTemplate.from_messages(messages)

        # LLM 호출
        llm = create_llm("생성")

        chain = prompt | llm | StrOutputParser()
        invoke_params: dict = {
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
        }
        if evaluation_feedback:
            invoke_params["evaluation_feedback"] = evaluation_feedback

        response = chain.invoke(invoke_params)

        elapsed = time.time() - start
        logger.info("[generate_only] %s 완료 (%.3fs, %d자)", self.domain, elapsed, len(response))

        return response

    async def agenerate_only(
        self,
        query: str,
        documents: list[Document],
        user_context: UserContext | None = None,
        evaluation_feedback: str | None = None,
    ) -> str:
        """주어진 문서로 답변만 비동기로 생성합니다.

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            user_context: 사용자 컨텍스트
            evaluation_feedback: 이전 평가 피드백 (재시도 시)

        Returns:
            생성된 답변 문자열
        """
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        logger.info("[agenerate_only] %s 생성 시작: '%s'", self.domain, query[:50])
        start = time.time()

        user_type, company_context = self._extract_user_context(user_context)

        # 컨텍스트 포맷팅
        context = self.rag_chain.format_context(documents)

        # 프롬프트 구성
        messages = [
            ("system", self.get_system_prompt()),
            ("human", "{query}"),
        ]
        if evaluation_feedback:
            messages.append((
                "system",
                "이전 답변이 품질 평가를 통과하지 못했습니다. "
                "다음 피드백을 반영하여 답변을 개선하세요:\n{evaluation_feedback}",
            ))
        prompt = ChatPromptTemplate.from_messages(messages)

        # LLM 호출
        llm = create_llm("생성")

        chain = prompt | llm | StrOutputParser()
        invoke_params: dict = {
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
        }
        if evaluation_feedback:
            invoke_params["evaluation_feedback"] = evaluation_feedback

        try:
            response = await asyncio.wait_for(
                chain.ainvoke(invoke_params),
                timeout=self.settings.llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[agenerate_only] LLM 타임아웃: %s", query[:30])
            if self.settings.enable_fallback:
                response = self.settings.fallback_message
            else:
                raise

        elapsed = time.time() - start
        logger.info("[agenerate_only] %s 완료 (%.3fs, %d자)", self.domain, elapsed, len(response))

        return response

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
        logger.info("[에이전트] %s process 시작: '%s'", self.domain, query[:50])
        start = time.time()

        user_type, company_context = self._extract_user_context(user_context)

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

        elapsed = time.time() - start
        logger.info(
            "[에이전트] %s process 완료 (%.3fs, 검색=%.3fs, 생성=%.3fs)",
            self.domain,
            elapsed,
            result.get("retrieve_time", 0.0),
            result.get("generate_time", 0.0),
        )

        return AgentResponse(
            content=result["content"],
            domain=self.domain,
            sources=result["sources"],
            actions=actions,
            documents=result["documents"],
            metadata={
                "retrieve_time": result.get("retrieve_time", 0.0),
                "generate_time": result.get("generate_time", 0.0),
            },
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
        logger.info("[에이전트] %s aprocess 시작: '%s'", self.domain, query[:50])
        start = time.time()

        user_type, company_context = self._extract_user_context(user_context)

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

        elapsed = time.time() - start
        logger.info(
            "[에이전트] %s aprocess 완료 (%.3fs, 검색=%.3fs, 생성=%.3fs)",
            self.domain,
            elapsed,
            result.get("retrieve_time", 0.0),
            result.get("generate_time", 0.0),
        )

        return AgentResponse(
            content=result["content"],
            domain=self.domain,
            sources=result["sources"],
            actions=actions,
            documents=result["documents"],
            metadata={
                "retrieve_time": result.get("retrieve_time", 0.0),
                "generate_time": result.get("generate_time", 0.0),
            },
        )

    async def astream(
        self,
        query: str,
        user_context: UserContext | None = None,
        supplementary_documents: list[Document] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """질문을 스트리밍으로 처리합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            supplementary_documents: 보충 문서 리스트 (법률 보충 검색 등)

        Yields:
            스트리밍 응답 (token, sources, actions, done)
        """
        user_type, company_context = self._extract_user_context(user_context)

        # 문서 검색 (스트리밍 전에 1회 수행)
        try:
            retrieval_result = await asyncio.wait_for(
                self.aretrieve_only(
                    query=query,
                    search_strategy=None,
                    include_common=False,
                ),
                timeout=30.0,
            )
            documents = retrieval_result.documents
            sources = retrieval_result.sources
        except (asyncio.TimeoutError, Exception) as e:
            logger.error("[스트리밍] 검색 실패 (%s): %s", self.domain, e)
            documents = []
            sources = []

        # 보충 문서 병합
        if supplementary_documents:
            documents = documents + supplementary_documents
            logger.info(
                "[스트리밍] 보충 문서 %d건 병합 (총 %d건)",
                len(supplementary_documents),
                len(documents),
            )
            sources = self.rag_chain.documents_to_sources(documents)

        # 검색된 결과를 그대로 사용하기 위해 컨텍스트를 직접 전달
        context_override = self.rag_chain.format_context(documents)

        # 토큰 스트리밍
        content_buffer = ""
        async for token in self.rag_chain.astream(
            query=query,
            domain=self.domain,
            system_prompt=self.get_system_prompt(),
            user_type=user_type,
            company_context=company_context,
            context_override=context_override,
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
