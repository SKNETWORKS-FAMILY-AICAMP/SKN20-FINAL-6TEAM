"""메인 라우터 모듈.

LangGraph 기반 멀티에이전트 라우터를 구현합니다.
질문을 분류하고 적절한 에이전트로 라우팅하며 응답을 통합합니다.
"""

import asyncio
import hashlib
import json
import random
import re
from collections import OrderedDict
from typing import Any, AsyncGenerator, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from schemas.request import UserContext
from schemas.response import (
    ActionSuggestion,
    ChatResponse,
    EvaluationResult,
    SourceDocument,
)
from chains.rag_chain import RAGChain
from utils.config import get_settings
from utils.prompts import DOMAIN_KEYWORDS, ROUTER_SYSTEM_PROMPT
from utils.feedback import FeedbackAnalyzer, SearchStrategy, get_feedback_analyzer
from vectorstores.chroma import ChromaVectorStore
from agents.evaluator import EvaluatorAgent
from agents.finance_tax import FinanceTaxAgent
from agents.hr_labor import HRLaborAgent
from agents.startup_funding import StartupFundingAgent


class RouterState(TypedDict):
    """라우터 상태 타입."""

    query: str
    user_context: UserContext | None
    domains: list[str]
    responses: dict[str, Any]
    final_response: str
    sources: list[SourceDocument]
    actions: list[ActionSuggestion]
    evaluation: EvaluationResult | None
    retry_count: int
    feedback: str | None
    search_strategy: SearchStrategy | None  # 피드백 기반 검색 전략


class MainRouter:
    """메인 라우터 클래스.

    LangGraph StateGraph를 사용하여 멀티에이전트 파이프라인을 구현합니다.

    워크플로우:
    1. 질문 분류 (classify) → 도메인 식별
    2. 에이전트 호출 (route) → 해당 에이전트 실행
    3. 응답 통합 (integrate) → 복합 질문 시 응답 병합
    4. 평가 (evaluate) → 품질 평가
    5. 재요청 판단 → 미통과 시 피드백과 함께 재시도

    Attributes:
        settings: 설정 객체
        llm: OpenAI LLM 인스턴스
        agents: 도메인별 에이전트 딕셔너리
        evaluator: 평가 에이전트
        graph: LangGraph StateGraph

    Example:
        >>> router = MainRouter()
        >>> response = router.process("사업자등록 절차 알려주세요")
        >>> print(response.content)
    """

    def __init__(self, vector_store: ChromaVectorStore | None = None):
        """MainRouter를 초기화합니다.

        Args:
            vector_store: ChromaDB 벡터 스토어. None이면 새로 생성.
        """
        self.settings = get_settings()
        # 도메인 분류용 경량 모델 (보조 작업)
        self.llm = ChatOpenAI(
            model=self.settings.auxiliary_model,
            temperature=0.0,  # 분류는 일관성 위해 낮은 temperature
            api_key=self.settings.openai_api_key,
        )

        # 도메인 분류 체인 미리 빌드 (성능 최적화)
        self._classifier_chain = self._build_classifier_chain()

        # 도메인 분류 캐시 (LRU)
        self._domain_cache: OrderedDict[str, list[str]] = OrderedDict()
        self._domain_cache_max_size = self.settings.domain_cache_size

        # 공유 인스턴스 생성
        self.vector_store = vector_store or ChromaVectorStore()
        shared_rag_chain = RAGChain(vector_store=self.vector_store)

        # 에이전트 초기화 (공유 RAG 체인 사용)
        self.agents = {
            "startup_funding": StartupFundingAgent(rag_chain=shared_rag_chain),
            "finance_tax": FinanceTaxAgent(rag_chain=shared_rag_chain),
            "hr_labor": HRLaborAgent(rag_chain=shared_rag_chain),
        }
        self.evaluator = EvaluatorAgent()

        # 그래프 빌드 (동기/비동기 분리)
        self.graph = self._build_graph()
        self.async_graph = self._build_async_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraph StateGraph를 빌드합니다.

        Returns:
            컴파일된 StateGraph
        """
        # 그래프 정의
        workflow = StateGraph(RouterState)

        # 노드 추가 (평가 노드 제거 - 성능 최적화)
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("route", self._route_node)
        workflow.add_node("integrate", self._integrate_node)

        # 엣지 정의 (integrate에서 바로 종료)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "route")
        workflow.add_edge("route", "integrate")
        workflow.add_edge("integrate", END)

        return workflow.compile()

    def _build_async_graph(self) -> StateGraph:
        """비동기 LangGraph StateGraph를 빌드합니다.

        병렬 에이전트 호출을 지원합니다.

        Returns:
            컴파일된 StateGraph
        """
        workflow = StateGraph(RouterState)

        # 비동기 노드 추가 (평가 노드 제거 - 성능 최적화)
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("route", self._aroute_node)  # 비동기 병렬 호출
        workflow.add_node("integrate", self._integrate_node)

        # 엣지 정의 (integrate에서 바로 종료)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "route")
        workflow.add_edge("route", "integrate")
        workflow.add_edge("integrate", END)

        return workflow.compile()

    def _build_classifier_chain(self):
        """도메인 분류 체인을 미리 빌드합니다 (성능 최적화)."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", "질문: {query}"),
        ])
        return prompt | self.llm | StrOutputParser()

    def _get_cache_key(self, query: str) -> str:
        """쿼리의 캐시 키를 생성합니다."""
        # 정규화: 소문자, 공백 정리
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def _get_cached_domains(self, query: str) -> list[str] | None:
        """캐시된 도메인 분류 결과를 반환합니다."""
        if not self.settings.enable_domain_cache:
            return None

        cache_key = self._get_cache_key(query)
        if cache_key in self._domain_cache:
            # LRU: 최근 사용으로 이동
            self._domain_cache.move_to_end(cache_key)
            return self._domain_cache[cache_key]
        return None

    def _cache_domains(self, query: str, domains: list[str]) -> None:
        """도메인 분류 결과를 캐싱합니다."""
        if not self.settings.enable_domain_cache:
            return

        cache_key = self._get_cache_key(query)

        # LRU 캐시 크기 제한 (max_size 정확히 유지)
        while len(self._domain_cache) > self._domain_cache_max_size:
            self._domain_cache.popitem(last=False)

        self._domain_cache[cache_key] = domains

    def _classify_domains(self, query: str) -> list[str]:
        """질문을 분류하여 관련 도메인을 반환합니다.

        1차: 캐시 확인 (가장 빠름)
        2차: 키워드 기반 분류 (빠름)
        3차: LLM 기반 분류 (키워드로 분류되지 않은 경우)

        Args:
            query: 사용자 질문

        Returns:
            관련 도메인 리스트
        """
        # 1차: 캐시 확인
        cached = self._get_cached_domains(query)
        if cached:
            return cached

        # 2차: 키워드 기반 분류 (LLM 호출 없이 빠르게)
        detected_domains = []
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                detected_domains.append(domain)

        if detected_domains:
            self._cache_domains(query, detected_domains)
            return detected_domains

        # 3차: LLM 기반 분류 (미리 빌드된 체인 사용)
        response = self._classifier_chain.invoke({"query": query})

        # JSON 파싱
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)
            domains = result.get("domains", ["startup_funding"])
        except json.JSONDecodeError:
            domains = ["startup_funding"]  # 기본값

        self._cache_domains(query, domains)
        return domains

    def _classify_node(self, state: RouterState) -> RouterState:
        """분류 노드: 질문을 분석하여 도메인을 식별합니다."""
        domains = self._classify_domains(state["query"])
        state["domains"] = domains
        return state

    def _route_node(self, state: RouterState) -> RouterState:
        """라우팅 노드: 해당 에이전트를 호출합니다."""
        responses = {}
        feedback = state.get("feedback")
        search_strategy = state.get("search_strategy")

        for domain in state["domains"]:
            if domain in self.agents:
                agent = self.agents[domain]

                # 피드백이 있으면 쿼리에 추가
                query = state["query"]
                if feedback:
                    query = f"{query}\n\n[이전 답변 피드백: {feedback}]"

                response = agent.process(
                    query=query,
                    user_context=state.get("user_context"),
                    search_strategy=search_strategy,
                )
                responses[domain] = response

        state["responses"] = responses
        return state

    async def _aroute_node(self, state: RouterState) -> RouterState:
        """라우팅 노드 (비동기 병렬 처리): 해당 에이전트를 병렬로 호출합니다."""
        feedback = state.get("feedback")
        search_strategy = state.get("search_strategy")
        query = state["query"]
        if feedback:
            query = f"{query}\n\n[이전 답변 피드백: {feedback}]"

        # 병렬로 에이전트 호출
        async def call_agent(domain: str) -> tuple[str, Any] | None:
            if domain in self.agents:
                agent = self.agents[domain]
                response = await agent.aprocess(
                    query=query,
                    user_context=state.get("user_context"),
                    search_strategy=search_strategy,
                )
                return (domain, response)
            return None

        tasks = [call_agent(domain) for domain in state["domains"]]
        results = await asyncio.gather(*tasks)

        # None 결과 필터링 후 딕셔너리 변환
        responses = {}
        for result in results:
            if result is not None:
                domain, response = result
                responses[domain] = response

        state["responses"] = responses
        return state

    def _integrate_node(self, state: RouterState) -> RouterState:
        """통합 노드: 여러 에이전트의 응답을 통합합니다."""
        responses = state["responses"]
        all_sources = []
        all_actions = []
        contents = []

        for domain, response in responses.items():
            contents.append(response.content)
            all_sources.extend(response.sources)
            all_actions.extend(response.actions)

        # 응답 통합
        if len(contents) == 1:
            final_response = contents[0]
        else:
            # 복수 도메인 응답 병합
            domain_labels = {
                "startup_funding": "창업/지원",
                "finance_tax": "재무/세무",
                "hr_labor": "인사/노무",
            }
            parts = []
            for domain, response in responses.items():
                label = domain_labels.get(domain, domain)
                parts.append(f"## {label}\n\n{response.content}")
            final_response = "\n\n---\n\n".join(parts)

        state["final_response"] = final_response
        state["sources"] = all_sources
        state["actions"] = all_actions
        return state

    def _should_skip_evaluation(self, state: RouterState) -> bool:
        """평가 스킵 여부를 판단합니다."""
        query = state["query"]

        # 이미 재시도 중이면 반드시 평가 실행
        if state.get("retry_count", 0) > 0:
            return False

        # 짧은 질문 스킵
        if (self.settings.skip_evaluation_for_short_query and
            len(query) < self.settings.short_query_threshold):
            return True

        # 확률적 스킵 (성능 최적화)
        if random.random() < self.settings.skip_evaluation_probability:
            return True

        return False

    def _evaluate_node(self, state: RouterState) -> RouterState:
        """평가 노드: 응답 품질을 평가합니다."""
        # 평가 스킵 조건 체크
        if self._should_skip_evaluation(state):
            # 기본 통과 처리
            state["evaluation"] = EvaluationResult(
                scores={"retrieval_quality": 15, "accuracy": 15, "completeness": 15, "relevance": 15, "citation": 15},
                total_score=75,
                passed=True,
                feedback=None,
            )
            return state

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        evaluation = self.evaluator.evaluate(
            question=state["query"],
            answer=state["final_response"],
            context=context,
        )

        state["evaluation"] = evaluation

        # 미통과 시 피드백 저장 및 검색 전략 조정
        if not evaluation.passed:
            state["feedback"] = evaluation.feedback
            state["retry_count"] = state.get("retry_count", 0) + 1

            # 피드백 기반 검색 전략 계산
            analyzer = get_feedback_analyzer()
            current_strategy = state.get("search_strategy")
            state["search_strategy"] = analyzer.suggest_strategy(
                feedback=evaluation.feedback,
                current_strategy=current_strategy,
                retry_count=state["retry_count"],
            )

        return state

    async def _aevaluate_node(self, state: RouterState) -> RouterState:
        """비동기 평가 노드: 응답 품질을 비동기로 평가합니다."""
        # 평가 스킵 조건 체크
        if self._should_skip_evaluation(state):
            # 기본 통과 처리
            state["evaluation"] = EvaluationResult(
                scores={"retrieval_quality": 15, "accuracy": 15, "completeness": 15, "relevance": 15, "citation": 15},
                total_score=75,
                passed=True,
                feedback=None,
            )
            return state

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        evaluation = await self.evaluator.aevaluate(
            question=state["query"],
            answer=state["final_response"],
            context=context,
        )

        state["evaluation"] = evaluation

        # 미통과 시 피드백 저장 및 검색 전략 조정
        if not evaluation.passed:
            state["feedback"] = evaluation.feedback
            state["retry_count"] = state.get("retry_count", 0) + 1

            # 피드백 기반 검색 전략 계산
            analyzer = get_feedback_analyzer()
            current_strategy = state.get("search_strategy")
            state["search_strategy"] = analyzer.suggest_strategy(
                feedback=evaluation.feedback,
                current_strategy=current_strategy,
                retry_count=state["retry_count"],
            )

        return state

    def _should_retry(self, state: RouterState) -> str:
        """재시도 여부를 판단합니다."""
        evaluation = state.get("evaluation")
        retry_count = state.get("retry_count", 0)
        max_retries = self.settings.max_retry_count

        if evaluation and not evaluation.passed and retry_count < max_retries:
            return "retry"
        return "end"

    def process(
        self,
        query: str,
        user_context: UserContext | None = None,
    ) -> ChatResponse:
        """질문을 처리하고 응답을 생성합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트

        Returns:
            채팅 응답
        """
        # 초기 상태
        initial_state: RouterState = {
            "query": query,
            "user_context": user_context,
            "domains": [],
            "responses": {},
            "final_response": "",
            "sources": [],
            "actions": [],
            "evaluation": None,
            "retry_count": 0,
            "feedback": None,
            "search_strategy": None,
        }

        # 그래프 실행
        final_state = self.graph.invoke(initial_state)

        # 응답 생성
        domains = final_state["domains"]
        return ChatResponse(
            content=final_state["final_response"],
            domain=domains[0] if domains else "general",
            domains=domains,
            sources=final_state["sources"],
            actions=final_state["actions"],
            evaluation=final_state.get("evaluation"),
            retry_count=final_state.get("retry_count", 0),
        )

    async def aprocess(
        self,
        query: str,
        user_context: UserContext | None = None,
    ) -> ChatResponse:
        """질문을 비동기로 처리합니다.

        병렬 에이전트 호출과 비동기 평가를 사용하여 성능을 최적화합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트

        Returns:
            채팅 응답
        """
        # 초기 상태
        initial_state: RouterState = {
            "query": query,
            "user_context": user_context,
            "domains": [],
            "responses": {},
            "final_response": "",
            "sources": [],
            "actions": [],
            "evaluation": None,
            "retry_count": 0,
            "feedback": None,
            "search_strategy": None,
        }

        # 비동기 그래프 실행 (병렬 에이전트 호출 + 비동기 평가)
        final_state = await self.async_graph.ainvoke(initial_state)

        # 응답 생성
        domains = final_state["domains"]
        return ChatResponse(
            content=final_state["final_response"],
            domain=domains[0] if domains else "general",
            domains=domains,
            sources=final_state["sources"],
            actions=final_state["actions"],
            evaluation=final_state.get("evaluation"),
            retry_count=final_state.get("retry_count", 0),
        )

    async def astream(
        self,
        query: str,
        user_context: UserContext | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """질문을 스트리밍으로 처리합니다.

        단일 도메인 질문에 대해 진정한 토큰 스트리밍을 지원합니다.
        복합 도메인 질문은 기존 방식으로 처리 후 스트리밍합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트

        Yields:
            스트리밍 응답 딕셔너리
        """
        # 도메인 분류
        domains = self._classify_domains(query)

        if len(domains) == 1 and domains[0] in self.agents:
            # 단일 도메인: 진정한 스트리밍
            agent = self.agents[domains[0]]
            all_sources = []
            all_actions = []
            content = ""

            async for chunk in agent.astream(query, user_context):
                if chunk["type"] == "token":
                    yield {"type": "token", "content": chunk["content"]}
                elif chunk["type"] == "done":
                    content = chunk["content"]
                    all_sources = chunk["sources"]
                    all_actions = chunk["actions"]

            # 완료 신호
            yield {
                "type": "done",
                "content": content,
                "domain": domains[0],
                "domains": domains,
                "sources": all_sources,
                "actions": all_actions,
            }
        else:
            # 복합 도메인: 기존 방식 후 스트리밍
            response = await self.aprocess(query, user_context)

            # 토큰 단위로 스트리밍
            for char in response.content:
                yield {"type": "token", "content": char}

            # 완료 신호
            yield {
                "type": "done",
                "content": response.content,
                "domain": response.domain,
                "domains": response.domains,
                "sources": response.sources,
                "actions": response.actions,
                "evaluation": response.evaluation,
            }
