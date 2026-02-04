"""메인 라우터 모듈.

LangGraph 기반 멀티에이전트 라우터를 구현합니다.
질문을 분류하고 적절한 에이전트로 라우팅하며 응답을 통합합니다.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from schemas.request import UserContext
from schemas.response import (
    ActionSuggestion,
    AgentTimingMetrics,
    ChatResponse,
    EvaluationResult,
    SourceDocument,
    TimingMetrics,
)
from chains.rag_chain import RAGChain
from utils.config import get_settings
from utils.token_tracker import TokenUsageCallbackHandler
from utils.prompts import DOMAIN_KEYWORDS, REJECTION_RESPONSE, ROUTER_SYSTEM_PROMPT
from utils.feedback import FeedbackAnalyzer, SearchStrategy, get_feedback_analyzer
from vectorstores.chroma import ChromaVectorStore
from agents.evaluator import EvaluatorAgent
from agents.finance_tax import FinanceTaxAgent
from agents.hr_labor import HRLaborAgent
from agents.startup_funding import StartupFundingAgent

logger = logging.getLogger(__name__)


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
    timing_metrics: dict[str, Any]  # 단계별 타이밍 메트릭


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
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
            callbacks=[TokenUsageCallbackHandler("분류")],
        )

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

        # 노드 추가
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("route", self._route_node)
        workflow.add_node("integrate", self._integrate_node)
        workflow.add_node("evaluate", self._evaluate_node)

        # 엣지 정의
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "route")
        workflow.add_edge("route", "integrate")
        workflow.add_edge("integrate", "evaluate")

        # 조건부 엣지 (평가 결과에 따른 분기)
        workflow.add_conditional_edges(
            "evaluate",
            self._should_retry,
            {
                "retry": "route",
                "end": END,
            },
        )

        return workflow.compile()

    def _build_async_graph(self) -> StateGraph:
        """비동기 LangGraph StateGraph를 빌드합니다.

        병렬 에이전트 호출과 비동기 평가를 지원합니다.

        Returns:
            컴파일된 StateGraph
        """
        workflow = StateGraph(RouterState)

        # 비동기 노드 추가
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("route", self._aroute_node)  # 비동기 병렬 호출
        workflow.add_node("integrate", self._integrate_node)
        workflow.add_node("evaluate", self._aevaluate_node)  # 비동기 평가

        # 엣지 정의
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "route")
        workflow.add_edge("route", "integrate")
        workflow.add_edge("integrate", "evaluate")

        # 조건부 엣지
        workflow.add_conditional_edges(
            "evaluate",
            self._should_retry,
            {
                "retry": "route",
                "end": END,
            },
        )

        return workflow.compile()

    def _classify_domains(self, query: str) -> tuple[list[str], bool]:
        """질문을 분류하여 관련 도메인과 관련성 여부를 반환합니다.
    def _classify_domains(self, query: str) -> tuple[list[str], bool]:
        """질문을 분류하여 관련 도메인과 관련성 여부를 반환합니다.

        1차: 키워드 기반 분류
        2차: LLM 기반 분류 (키워드로 분류되지 않은 경우)

        Args:
            query: 사용자 질문

        Returns:
            (관련 도메인 리스트, 관련 질문 여부)
            (관련 도메인 리스트, 관련 질문 여부)
        """
        # 1차: 키워드 기반 분류
        detected_domains = []
        matched_keywords: dict[str, list[str]] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            hits = [kw for kw in keywords if kw in query]
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        if detected_domains:
            logger.info("[분류] 키워드 매칭 성공: %s", detected_domains)
            logger.info("[분류] 매칭 키워드: %s", matched_keywords)
            return detected_domains, True
            return detected_domains, True

        # 2차: LLM 기반 분류 (신뢰도 포함)
        # 2차: LLM 기반 분류 (신뢰도 포함)
        logger.info("[분류] 키워드 매칭 실패, LLM 분류 사용")

        # 도메인 외 질문 거부 기능이 활성화된 경우 신뢰도 판단
        if self.settings.enable_domain_rejection:
            domains, confidence, is_relevant = self._llm_classify_with_confidence(query)

            if not is_relevant:
                logger.info("[분류] 도메인 외 질문으로 판단됨 (신뢰도: %.2f)", confidence)
                return [], False

            logger.info("[분류] LLM 분류 결과: %s (신뢰도: %.2f)", domains, confidence)
            return domains, True

        # 기존 로직 (거부 기능 비활성화 시)

        # 도메인 외 질문 거부 기능이 활성화된 경우 신뢰도 판단
        if self.settings.enable_domain_rejection:
            domains, confidence, is_relevant = self._llm_classify_with_confidence(query)

            if not is_relevant:
                logger.info("[분류] 도메인 외 질문으로 판단됨 (신뢰도: %.2f)", confidence)
                return [], False

            logger.info("[분류] LLM 분류 결과: %s (신뢰도: %.2f)", domains, confidence)
            return domains, True

        # 기존 로직 (거부 기능 비활성화 시)
        prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", "질문: {query}"),
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"query": query})

        # JSON 파싱
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)
            return result.get("domains", ["startup_funding"]), True
            return result.get("domains", ["startup_funding"]), True
        except json.JSONDecodeError:
            return ["startup_funding"], True  # 기본값

    def _llm_classify_with_confidence(self, query: str) -> tuple[list[str], float, bool]:
        """LLM을 사용하여 도메인 분류와 신뢰도를 함께 판단합니다.

        Args:
            query: 사용자 질문

        Returns:
            (도메인 리스트, 신뢰도, 관련 질문 여부)
        """
        classification_prompt = """당신은 Bizi의 메인 라우터입니다.
사용자 질문이 Bizi의 상담 범위에 해당하는지 판단하고, 적절한 도메인으로 분류하세요.

## Bizi 상담 범위

1. **startup_funding**: 창업, 사업자등록, 법인설립, 지원사업, 보조금, 마케팅
2. **finance_tax**: 세금, 회계, 세무, 재무
3. **hr_labor**: 근로, 채용, 급여, 노무, 계약, 지식재산권

## 상담 범위 외 질문 예시

- 일상 대화: "안녕", "뭐해?", "심심해"
- 일반 상식: "날씨 어때?", "맛집 추천해줘"
- 게임/엔터: "게임 추천", "영화 뭐 볼까"
- 기타 무관: "두쫀쿠가 뭐야?", "인공지능이란?"

## 응답 형식

반드시 JSON 형식으로 응답하세요:
```json
{{
    "domains": ["도메인1"],
    "confidence": 0.0~1.0,
    "is_relevant": true/false,
    "reasoning": "판단 이유"
}}
```

- confidence: 이 질문이 Bizi 상담 범위에 해당한다는 확신 (0.0=확실히 아님, 1.0=확실히 해당)
- is_relevant: 상담 범위 내 질문이면 true, 아니면 false
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", classification_prompt),
            ("human", "질문: {query}"),
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"query": query})

        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)

            domains = result.get("domains", ["startup_funding"])
            confidence = float(result.get("confidence", 0.5))
            is_relevant = result.get("is_relevant", True)

            # 신뢰도 임계값 확인
            if confidence < self.settings.domain_confidence_threshold:
                is_relevant = False

            return domains, confidence, is_relevant

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("[분류] LLM 응답 파싱 실패: %s", e)
            # 파싱 실패 시 기본적으로 관련 질문으로 처리
            return ["startup_funding"], 0.5, True
            return ["startup_funding"], True  # 기본값

    def _llm_classify_with_confidence(self, query: str) -> tuple[list[str], float, bool]:
        """LLM을 사용하여 도메인 분류와 신뢰도를 함께 판단합니다.

        Args:
            query: 사용자 질문

        Returns:
            (도메인 리스트, 신뢰도, 관련 질문 여부)
        """
        classification_prompt = """당신은 Bizi의 메인 라우터입니다.
사용자 질문이 Bizi의 상담 범위에 해당하는지 판단하고, 적절한 도메인으로 분류하세요.

## Bizi 상담 범위

1. **startup_funding**: 창업, 사업자등록, 법인설립, 지원사업, 보조금, 마케팅
2. **finance_tax**: 세금, 회계, 세무, 재무
3. **hr_labor**: 근로, 채용, 급여, 노무, 계약, 지식재산권

## 상담 범위 외 질문 예시

- 일상 대화: "안녕", "뭐해?", "심심해"
- 일반 상식: "날씨 어때?", "맛집 추천해줘"
- 게임/엔터: "게임 추천", "영화 뭐 볼까"
- 기타 무관: "두쫀쿠가 뭐야?", "인공지능이란?"

## 응답 형식

반드시 JSON 형식으로 응답하세요:
```json
{{
    "domains": ["도메인1"],
    "confidence": 0.0~1.0,
    "is_relevant": true/false,
    "reasoning": "판단 이유"
}}
```

- confidence: 이 질문이 Bizi 상담 범위에 해당한다는 확신 (0.0=확실히 아님, 1.0=확실히 해당)
- is_relevant: 상담 범위 내 질문이면 true, 아니면 false
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", classification_prompt),
            ("human", "질문: {query}"),
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"query": query})

        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)

            domains = result.get("domains", ["startup_funding"])
            confidence = float(result.get("confidence", 0.5))
            is_relevant = result.get("is_relevant", True)

            # 신뢰도 임계값 확인
            if confidence < self.settings.domain_confidence_threshold:
                is_relevant = False

            return domains, confidence, is_relevant

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("[분류] LLM 응답 파싱 실패: %s", e)
            # 파싱 실패 시 기본적으로 관련 질문으로 처리
            return ["startup_funding"], 0.5, True

    def _classify_node(self, state: RouterState) -> RouterState:
        """분류 노드: 질문을 분석하여 도메인을 식별합니다."""
        start = time.time()
        domains, is_relevant = self._classify_domains(state["query"])

        if not is_relevant:
            # 도메인 외 질문: 거부 응답 설정
            state["domains"] = []
            state["final_response"] = REJECTION_RESPONSE
            state["sources"] = []
            state["actions"] = []
            logger.info("[분류] 도메인 외 질문 거부")
        else:
            state["domains"] = domains

        domains, is_relevant = self._classify_domains(state["query"])

        if not is_relevant:
            # 도메인 외 질문: 거부 응답 설정
            state["domains"] = []
            state["final_response"] = REJECTION_RESPONSE
            state["sources"] = []
            state["actions"] = []
            logger.info("[분류] 도메인 외 질문 거부")
        else:
            state["domains"] = domains

        classify_time = time.time() - start
        state["timing_metrics"]["classify_time"] = classify_time
        logger.info("[분류] 도메인=%s, 관련=%s (%.3fs)", domains, is_relevant, classify_time)
        logger.info("[분류] 도메인=%s, 관련=%s (%.3fs)", domains, is_relevant, classify_time)
        return state

    def _route_node(self, state: RouterState) -> RouterState:
        """라우팅 노드: 해당 에이전트를 호출합니다."""
        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[라우팅] 도메인 외 질문 - 에이전트 호출 스킵")
            return state

        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[라우팅] 도메인 외 질문 - 에이전트 호출 스킵")
            return state

        responses = {}
        agent_timings = []
        feedback = state.get("feedback")
        search_strategy = state.get("search_strategy")

        logger.info("[라우팅] 호출할 에이전트: %s", state["domains"])

        for domain in state["domains"]:
            if domain in self.agents:
                agent = self.agents[domain]

                # 피드백이 있으면 쿼리에 추가
                query = state["query"]
                if feedback:
                    query = f"{query}\n\n[이전 답변 피드백: {feedback}]"

                logger.info("[라우팅] 에이전트 [%s] 호출 시작", domain)
                start = time.time()
                response = agent.process(
                    query=query,
                    user_context=state.get("user_context"),
                    search_strategy=search_strategy,
                )
                elapsed = time.time() - start
                logger.info("[라우팅] 에이전트 [%s] 완료 (%.3fs)", domain, elapsed)
                responses[domain] = response
                agent_timings.append({
                    "domain": domain,
                    "retrieve_time": response.metadata.get("retrieve_time", 0.0),
                    "generate_time": response.metadata.get("generate_time", 0.0),
                    "total_time": elapsed,
                })

        state["responses"] = responses
        state["timing_metrics"]["agents"] = agent_timings
        return state

    async def _aroute_node(self, state: RouterState) -> RouterState:
        """라우팅 노드 (비동기 병렬 처리): 해당 에이전트를 병렬로 호출합니다."""
        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[라우팅] 도메인 외 질문 - 에이전트 호출 스킵")
            return state

        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[라우팅] 도메인 외 질문 - 에이전트 호출 스킵")
            return state

        feedback = state.get("feedback")
        search_strategy = state.get("search_strategy")
        query = state["query"]
        if feedback:
            query = f"{query}\n\n[이전 답변 피드백: {feedback}]"

        logger.info("[라우팅] 비동기 병렬 호출: %s", state["domains"])

        # 병렬로 에이전트 호출 (타이밍 포함)
        async def call_agent(domain: str):
            if domain in self.agents:
                agent = self.agents[domain]
                logger.info("[라우팅] 에이전트 [%s] 비동기 호출 시작", domain)
                start = time.time()
                response = await agent.aprocess(
                    query=query,
                    user_context=state.get("user_context"),
                    search_strategy=search_strategy,
                )
                elapsed = time.time() - start
                logger.info("[라우팅] 에이전트 [%s] 완료 (%.3fs)", domain, elapsed)
                return domain, response, elapsed
            return None

        tasks = [call_agent(domain) for domain in state["domains"]]
        results = await asyncio.gather(*tasks)

        # None 결과 필터링 후 딕셔너리 변환 및 타이밍 수집
        responses = {}
        agent_timings = []
        for result in results:
            if result is not None:
                domain, response, elapsed = result
                responses[domain] = response
                agent_timings.append({
                    "domain": domain,
                    "retrieve_time": response.metadata.get("retrieve_time", 0.0),
                    "generate_time": response.metadata.get("generate_time", 0.0),
                    "total_time": elapsed,
                })

        state["responses"] = responses
        state["timing_metrics"]["agents"] = agent_timings
        return state

    def _integrate_node(self, state: RouterState) -> RouterState:
        """통합 노드: 여러 에이전트의 응답을 통합합니다."""
        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[통합] 도메인 외 질문 - 통합 스킵")
            state["timing_metrics"]["integrate_time"] = 0.0
            return state

        # 도메인 외 질문으로 이미 거부된 경우 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[통합] 도메인 외 질문 - 통합 스킵")
            state["timing_metrics"]["integrate_time"] = 0.0
            return state

        start = time.time()
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
        integrate_time = time.time() - start
        state["timing_metrics"]["integrate_time"] = integrate_time
        logger.info("[통합] 응답 통합 완료: %d자 (%.3fs)", len(final_response), integrate_time)
        return state

    def _evaluate_node(self, state: RouterState) -> RouterState:
        """평가 노드: 응답 품질을 평가합니다."""
        # 도메인 외 질문으로 이미 거부된 경우 평가 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[평가] 도메인 외 질문 - 평가 스킵 (자동 PASS)")
            state["evaluation"] = None
            state["timing_metrics"]["evaluate_time"] = 0.0
            return state

        # 도메인 외 질문으로 이미 거부된 경우 평가 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[평가] 도메인 외 질문 - 평가 스킵 (자동 PASS)")
            state["evaluation"] = None
            state["timing_metrics"]["evaluate_time"] = 0.0
            return state

        start = time.time()
        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        evaluation = self.evaluator.evaluate(
            question=state["query"],
            answer=state["final_response"],
            context=context,
        )

        state["evaluation"] = evaluation
        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time
        logger.info(
            "[평가] 점수=%d/100, %s (%.3fs)",
            evaluation.total_score,
            "PASS" if evaluation.passed else "FAIL",
            evaluate_time,
        )

        # 미통과 시 피드백 저장 및 검색 전략 조정
        if not evaluation.passed:
            state["feedback"] = evaluation.feedback
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.info("[평가] 재시도 #%d: %s", state["retry_count"], evaluation.feedback)

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
        # 도메인 외 질문으로 이미 거부된 경우 평가 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[평가] 도메인 외 질문 - 평가 스킵 (자동 PASS)")
            state["evaluation"] = None
            state["timing_metrics"]["evaluate_time"] = 0.0
            return state

        # 도메인 외 질문으로 이미 거부된 경우 평가 스킵
        if not state["domains"] and state.get("final_response"):
            logger.info("[평가] 도메인 외 질문 - 평가 스킵 (자동 PASS)")
            state["evaluation"] = None
            state["timing_metrics"]["evaluate_time"] = 0.0
            return state

        start = time.time()
        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        evaluation = await self.evaluator.aevaluate(
            question=state["query"],
            answer=state["final_response"],
            context=context,
        )

        state["evaluation"] = evaluation
        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time
        logger.info(
            "[평가] 점수=%d/100, %s (%.3fs)",
            evaluation.total_score,
            "PASS" if evaluation.passed else "FAIL",
            evaluate_time,
        )

        # 미통과 시 피드백 저장 및 검색 전략 조정
        if not evaluation.passed:
            state["feedback"] = evaluation.feedback
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.info("[평가] 재시도 #%d: %s", state["retry_count"], evaluation.feedback)

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
        # 총 시간 측정 시작
        total_start = time.time()

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
            "timing_metrics": {},
        }

        # 그래프 실행
        final_state = self.graph.invoke(initial_state)

        # 총 시간 계산
        total_time = time.time() - total_start

        # 타이밍 메트릭 객체 생성
        timing_data = final_state.get("timing_metrics", {})
        agent_timings = [
            AgentTimingMetrics(
                domain=a["domain"],
                retrieve_time=a.get("retrieve_time", 0.0),
                generate_time=a.get("generate_time", 0.0),
                total_time=a.get("total_time", 0.0),
            )
            for a in timing_data.get("agents", [])
        ]
        timing_metrics = TimingMetrics(
            classify_time=timing_data.get("classify_time", 0.0),
            agents=agent_timings,
            integrate_time=timing_data.get("integrate_time", 0.0),
            evaluate_time=timing_data.get("evaluate_time", 0.0),
            total_time=total_time,
        )

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
            timing_metrics=timing_metrics,
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
        # 총 시간 측정 시작
        total_start = time.time()

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
            "timing_metrics": {},
        }

        # 비동기 그래프 실행 (병렬 에이전트 호출 + 비동기 평가)
        final_state = await self.async_graph.ainvoke(initial_state)

        # 총 시간 계산
        total_time = time.time() - total_start

        # 타이밍 메트릭 객체 생성
        timing_data = final_state.get("timing_metrics", {})
        agent_timings = [
            AgentTimingMetrics(
                domain=a["domain"],
                retrieve_time=a.get("retrieve_time", 0.0),
                generate_time=a.get("generate_time", 0.0),
                total_time=a.get("total_time", 0.0),
            )
            for a in timing_data.get("agents", [])
        ]
        timing_metrics = TimingMetrics(
            classify_time=timing_data.get("classify_time", 0.0),
            agents=agent_timings,
            integrate_time=timing_data.get("integrate_time", 0.0),
            evaluate_time=timing_data.get("evaluate_time", 0.0),
            total_time=total_time,
        )

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
            timing_metrics=timing_metrics,
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
        domains, is_relevant = self._classify_domains(query)

        # 도메인 외 질문 거부
        if not is_relevant:
            logger.info("[스트리밍] 도메인 외 질문 - 거부 응답 반환")
            # 거부 응답을 토큰 단위로 스트리밍
            for char in REJECTION_RESPONSE:
                yield {"type": "token", "content": char}
            yield {
                "type": "done",
                "content": REJECTION_RESPONSE,
                "domain": "general",
                "domains": [],
                "sources": [],
                "actions": [],
            }
            return
        domains, is_relevant = self._classify_domains(query)

        # 도메인 외 질문 거부
        if not is_relevant:
            logger.info("[스트리밍] 도메인 외 질문 - 거부 응답 반환")
            # 거부 응답을 토큰 단위로 스트리밍
            for char in REJECTION_RESPONSE:
                yield {"type": "token", "content": char}
            yield {
                "type": "done",
                "content": REJECTION_RESPONSE,
                "domain": "general",
                "domains": [],
                "sources": [],
                "actions": [],
            }
            return

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
