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
from typing import TYPE_CHECKING, Any, ClassVar

from langchain_core.documents import Document

from chains.rag_chain import RAGChain
from schemas.request import UserContext
from schemas.response import ActionSuggestion, SourceDocument
from utils.config import get_settings

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


@dataclass
class ActionRule:
    """액션 추천 규칙.

    키워드 매칭으로 추천 액션을 결정하는 규칙을 정의합니다.

    Attributes:
        keywords: 매칭할 키워드 리스트
        action: 매칭 시 추천할 액션
        match_response: True이면 query+response 모두 검색, False이면 query만 검색
        dynamic_query_param: True이면 params["query"]에 실제 query를 동적 주입
    """

    keywords: list[str]
    action: ActionSuggestion
    match_response: bool = True
    dynamic_query_param: bool = False


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
        ...     ACTION_RULES = [...]
        ...     def get_system_prompt(self) -> str:
        ...         return "시스템 프롬프트"
    """

    domain: str = ""
    ACTION_RULES: ClassVar[list[ActionRule]] = []

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

    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """ACTION_RULES 기반으로 추천 액션을 생성합니다.

        각 규칙의 키워드를 query(및 match_response=True이면 response)와 매칭하여
        해당하는 액션을 수집합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        actions: list[ActionSuggestion] = []
        query_lower = query.lower()
        response_lower = response.lower()

        for rule in self.ACTION_RULES:
            texts = [query_lower]
            if rule.match_response:
                texts.append(response_lower)
            if any(kw in text for kw in rule.keywords for text in texts):
                base = rule.action
                params = {**base.params, "query": query} if rule.dynamic_query_param else base.params.copy()
                actions.append(ActionSuggestion(
                    type=base.type,
                    label=base.label,
                    description=base.description,
                    params=params,
                ))

        return actions

    def retrieve_only(
        self,
        query: str,
        search_strategy: "SearchStrategy | None" = None,
        include_common: bool = False,
    ) -> RetrievalResult:
        """문서 검색만 수행합니다 (생성 없음).

        역할 분리 아키텍처에서 검색 전담 메서드로 사용됩니다.
        단일 쿼리로 Hybrid Search + Re-ranking 검색 후 규칙 기반 평가를 수행합니다.

        Args:
            query: 검색 쿼리
            search_strategy: 피드백 기반 검색 전략
            include_common: 공통 법령 DB 포함 여부

        Returns:
            RetrievalResult (문서, 점수, 평가 결과 포함)
        """
        from utils.retrieval_evaluator import get_retrieval_evaluator

        logger.info("[retrieve_only] %s 검색 시작: '%s'", self.domain, query[:50])
        start = time.time()

        # 단일 쿼리 검색 (Hybrid Search + Re-ranking)
        try:
            documents = self.rag_chain._retrieve_documents(
                query=query,
                domain=self.domain,
                include_common=include_common,
                search_strategy=search_strategy,
            )
        except Exception as e:
            logger.warning("[retrieve_only] 검색 실패: %s", e)
            documents = []

        # 점수 추출 (메타데이터에서)
        scores = [doc.metadata.get("score", 0.0) for doc in documents]

        # 규칙 기반 평가
        evaluator = get_retrieval_evaluator()
        evaluation = evaluator.evaluate(query, documents, scores)

        elapsed = time.time() - start
        logger.info(
            "[retrieve_only] %s 완료: %d건 (%.3fs)",
            self.domain,
            len(documents),
            elapsed,
        )

        return RetrievalResult(
            documents=documents,
            scores=scores,
            sources=self.rag_chain.documents_to_sources(documents),
            evaluation=evaluation,
            used_multi_query=False,
            retrieve_time=elapsed,
            domain=self.domain,
            query=query,
            rewritten_query=None,
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

