"""메인 라우터 모듈.

LangGraph 기반 멀티에이전트 라우터를 구현합니다.
질문을 분류하고 적절한 에이전트로 라우팅하며 응답을 통합합니다.

새로운 아키텍처 (3단계 분리):
1. 분류 (classify) → 벡터 유사도 기반 도메인 분류
2. 분해 (decompose) → 복합 질문을 단일 도메인 질문으로 분해
3. 검색 (retrieve) → 도메인별 병렬 검색 + 규칙 기반 평가 + Multi-Query 재검색
4. 생성 (generate) → 검색된 문서 기반 답변 생성
5. 평가 (evaluate) → RAGAS 평가 (로깅만, 재시도 없음)
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from agents.base import RetrievalResult
from agents.evaluator import EvaluatorAgent
from agents.finance_tax import FinanceTaxAgent
from agents.hr_labor import HRLaborAgent
from agents.startup_funding import StartupFundingAgent
from chains.rag_chain import RAGChain
from schemas.request import UserContext
from schemas.response import (
    ActionSuggestion,
    AgentTimingMetrics,
    ChatResponse,
    EvaluationDataForDB,
    EvaluationResult,
    RetrievalEvaluationData,
    SourceDocument,
    TimingMetrics,
)
from utils.config import get_settings
from utils.domain_classifier import DomainClassificationResult, get_domain_classifier
from utils.prompts import REJECTION_RESPONSE
from utils.question_decomposer import SubQuery, get_question_decomposer
from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


class RouterState(TypedDict):
    """라우터 상태 타입."""

    query: str
    user_context: UserContext | None
    domains: list[str]
    classification_result: DomainClassificationResult | None
    sub_queries: list[SubQuery]
    retrieval_results: dict[str, RetrievalResult]
    responses: dict[str, Any]
    documents: list[Document]
    final_response: str
    sources: list[SourceDocument]
    actions: list[ActionSuggestion]
    evaluation: EvaluationResult | None
    ragas_metrics: dict[str, float | None] | None
    retry_count: int
    timing_metrics: dict[str, Any]


class MainRouter:
    """메인 라우터 클래스.

    LangGraph StateGraph를 사용하여 멀티에이전트 파이프라인을 구현합니다.

    새로운 워크플로우 (3단계 분리):
    1. 질문 분류 (classify) → 벡터 유사도 기반 도메인 식별
    2. 질문 분해 (decompose) → 복합 질문을 단일 도메인 질문으로 분해
    3. 문서 검색 (retrieve) → 도메인별 병렬 검색
    4. 답변 생성 (generate) → 검색된 문서 기반 답변 생성
    5. 답변 평가 (evaluate) → RAGAS 평가 (로깅만)
    """

    def __init__(self, vector_store: ChromaVectorStore | None = None):
        """MainRouter를 초기화합니다.

        Args:
            vector_store: ChromaDB 벡터 스토어. None이면 새로 생성.
        """
        self.settings = get_settings()

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

        # 도메인 분류기 (벡터 유사도 기반)
        self._domain_classifier = None

        # 질문 분해기
        self._question_decomposer = None

        # RAGAS 평가기
        self._ragas_evaluator = None

        # 그래프 빌드 (동기/비동기 분리)
        self.graph = self._build_graph()
        self.async_graph = self._build_async_graph()

    @property
    def domain_classifier(self):
        """도메인 분류기 (지연 로딩)."""
        if self._domain_classifier is None:
            self._domain_classifier = get_domain_classifier()
        return self._domain_classifier

    @property
    def question_decomposer(self):
        """질문 분해기 (지연 로딩)."""
        if self._question_decomposer is None:
            self._question_decomposer = get_question_decomposer()
        return self._question_decomposer

    @property
    def ragas_evaluator(self):
        """RAGAS 평가기 (지연 로딩)."""
        if self._ragas_evaluator is None and self.settings.enable_ragas_evaluation:
            from evaluation.ragas_evaluator import RagasEvaluator
            self._ragas_evaluator = RagasEvaluator()
        return self._ragas_evaluator

    def _build_graph(self) -> StateGraph:
        """LangGraph StateGraph를 빌드합니다.

        Returns:
            컴파일된 StateGraph
        """
        workflow = StateGraph(RouterState)

        # 노드 추가
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("decompose", self._decompose_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_node("evaluate", self._evaluate_node)

        # 엣지 정의
        workflow.set_entry_point("classify")

        # 조건부 엣지: 분류 후 관련 질문인지 확인
        workflow.add_conditional_edges(
            "classify",
            self._should_continue_after_classify,
            {
                "continue": "decompose",
                "reject": END,
            },
        )

        workflow.add_edge("decompose", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "evaluate")
        workflow.add_edge("evaluate", END)

        return workflow.compile()

    def _build_async_graph(self) -> StateGraph:
        """비동기 LangGraph StateGraph를 빌드합니다.

        Returns:
            컴파일된 StateGraph
        """
        workflow = StateGraph(RouterState)

        # 비동기 노드 추가
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("decompose", self._adecompose_node)
        workflow.add_node("retrieve", self._aretrieve_node)
        workflow.add_node("generate", self._agenerate_node)
        workflow.add_node("evaluate", self._aevaluate_node)

        # 엣지 정의
        workflow.set_entry_point("classify")

        workflow.add_conditional_edges(
            "classify",
            self._should_continue_after_classify,
            {
                "continue": "decompose",
                "reject": END,
            },
        )

        workflow.add_edge("decompose", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "evaluate")
        workflow.add_edge("evaluate", END)

        return workflow.compile()

    def _should_continue_after_classify(self, state: RouterState) -> str:
        """분류 후 계속 진행할지 거부할지 결정합니다.

        Args:
            state: 라우터 상태

        Returns:
            "continue": 관련 질문이면 계속 진행
            "reject": 도메인 외 질문이면 종료
        """
        classification_result = state.get("classification_result")

        if classification_result is None:
            # 분류 결과가 없으면 기본적으로 계속 진행
            return "continue"

        if not classification_result.is_relevant:
            logger.info("[라우터] 도메인 외 질문 - 거부 응답 반환")
            return "reject"

        return "continue"

    def _should_continue_after_classify(self, state: RouterState) -> str:
        """분류 후 계속 진행할지 거부할지 판단합니다."""
        classification = state.get("classification_result")
        if classification and not classification.is_relevant:
            return "reject"
        return "continue"

    def _classify_node(self, state: RouterState) -> RouterState:
        """분류 노드: 벡터 유사도 기반으로 도메인을 식별합니다."""
        start = time.time()
        query = state["query"]

        # 벡터 유사도 기반 도메인 분류
        classification = self.domain_classifier.classify(query)
        state["classification_result"] = classification
        state["domains"] = classification.domains

        if not classification.is_relevant:
            # 도메인 외 질문: 거부 응답 설정
            state["final_response"] = REJECTION_RESPONSE
            state["sources"] = []
            state["actions"] = []
            logger.info(
                "[분류] 도메인 외 질문 거부 (방법: %s, 신뢰도: %.2f)",
                classification.method,
                classification.confidence,
            )
        else:
            logger.info(
                "[분류] 도메인=%s (방법: %s, 신뢰도: %.2f)",
                classification.domains,
                classification.method,
                classification.confidence,
            )

        classify_time = time.time() - start
        state["timing_metrics"]["classify_time"] = classify_time

        return state

    def _decompose_node(self, state: RouterState) -> RouterState:
        """분해 노드: 복합 질문을 단일 도메인 질문으로 분해합니다."""
        start = time.time()
        query = state["query"]
        domains = state["domains"]

        # 단일 도메인이면 QuestionDecomposer 초기화/호출 스킵
        if len(domains) <= 1:
            domain = domains[0] if domains else "startup_funding"
            state["sub_queries"] = [SubQuery(domain=domain, query=query)]
            decompose_time = time.time() - start
            state["timing_metrics"]["decompose_time"] = decompose_time
            logger.info("[분해] 단일 도메인 (%s) - 분해 스킵 (%.3fs)", domain, decompose_time)
            return state

        # 복합 질문 분해
        sub_queries = self.question_decomposer.decompose(query, domains)
        state["sub_queries"] = sub_queries

        decompose_time = time.time() - start
        state["timing_metrics"]["decompose_time"] = decompose_time

        logger.info(
            "[분해] %d개 하위 질문 생성 (%.3fs)",
            len(sub_queries),
            decompose_time,
        )

        return state

    async def _adecompose_node(self, state: RouterState) -> RouterState:
        """비동기 분해 노드."""
        start = time.time()
        query = state["query"]
        domains = state["domains"]

        # 단일 도메인이면 QuestionDecomposer 초기화/호출 스킵
        if len(domains) <= 1:
            domain = domains[0] if domains else "startup_funding"
            state["sub_queries"] = [SubQuery(domain=domain, query=query)]
            decompose_time = time.time() - start
            state["timing_metrics"]["decompose_time"] = decompose_time
            logger.info("[분해] 단일 도메인 (%s) - 분해 스킵 (%.3fs)", domain, decompose_time)
            return state

        sub_queries = await self.question_decomposer.adecompose(query, domains)
        state["sub_queries"] = sub_queries

        decompose_time = time.time() - start
        state["timing_metrics"]["decompose_time"] = decompose_time

        logger.info(
            "[분해] %d개 하위 질문 생성 (%.3fs)",
            len(sub_queries),
            decompose_time,
        )

        return state

    def _retrieve_node(self, state: RouterState) -> RouterState:
        """검색 노드: 도메인별 문서를 검색합니다."""
        start = time.time()
        sub_queries = state["sub_queries"]

        retrieval_results: dict[str, RetrievalResult] = {}
        all_documents: list[Document] = []
        agent_timings: list[dict] = []

        for sq in sub_queries:
            if sq.domain in self.agents:
                agent = self.agents[sq.domain]
                logger.info("[검색] 에이전트 [%s] 검색 시작", sq.domain)

                agent_start = time.time()
                result = agent.retrieve_only(sq.query)
                agent_elapsed = time.time() - agent_start

                retrieval_results[sq.domain] = result
                all_documents.extend(result.documents)
                agent_timings.append({
                    "domain": sq.domain,
                    "retrieve_time": result.retrieve_time,
                    "doc_count": len(result.documents),
                    "total_time": agent_elapsed,
                })

                logger.info(
                    "[검색] 에이전트 [%s] 완료: %d건, 평가=%s (%.3fs)",
                    sq.domain,
                    len(result.documents),
                    "PASS" if result.evaluation.passed else "FAIL",
                    agent_elapsed,
                )

        state["retrieval_results"] = retrieval_results
        state["documents"] = all_documents

        retrieve_time = time.time() - start
        state["timing_metrics"]["retrieve_time"] = retrieve_time
        state["timing_metrics"]["agents"] = agent_timings

        return state

    async def _aretrieve_node(self, state: RouterState) -> RouterState:
        """비동기 검색 노드: 도메인별 병렬 검색."""
        start = time.time()
        sub_queries = state["sub_queries"]

        async def retrieve_for_domain(sq: SubQuery):
            if sq.domain in self.agents:
                agent = self.agents[sq.domain]
                logger.info("[검색] 에이전트 [%s] 비동기 검색 시작", sq.domain)
                agent_start = time.time()
                result = await agent.aretrieve_only(sq.query)
                agent_elapsed = time.time() - agent_start
                return sq.domain, result, agent_elapsed
            return None

        tasks = [retrieve_for_domain(sq) for sq in sub_queries]
        results = await asyncio.gather(*tasks)

        retrieval_results: dict[str, RetrievalResult] = {}
        all_documents: list[Document] = []
        agent_timings: list[dict] = []

        for result in results:
            if result is not None:
                domain, retrieval_result, elapsed = result
                retrieval_results[domain] = retrieval_result
                all_documents.extend(retrieval_result.documents)
                agent_timings.append({
                    "domain": domain,
                    "retrieve_time": retrieval_result.retrieve_time,
                    "doc_count": len(retrieval_result.documents),
                    "total_time": elapsed,
                })

                logger.info(
                    "[검색] 에이전트 [%s] 완료: %d건, 평가=%s (%.3fs)",
                    domain,
                    len(retrieval_result.documents),
                    "PASS" if retrieval_result.evaluation.passed else "FAIL",
                    elapsed,
                )

        state["retrieval_results"] = retrieval_results
        state["documents"] = all_documents

        retrieve_time = time.time() - start
        state["timing_metrics"]["retrieve_time"] = retrieve_time
        state["timing_metrics"]["agents"] = agent_timings

        return state

    def _generate_node(self, state: RouterState) -> RouterState:
        """생성 노드: 검색된 문서 기반으로 답변을 생성합니다."""
        start = time.time()
        sub_queries = state["sub_queries"]
        retrieval_results = state["retrieval_results"]
        user_context = state.get("user_context")

        responses: dict[str, Any] = {}
        all_sources: list[SourceDocument] = []
        all_actions: list[ActionSuggestion] = []

        for sq in sub_queries:
            if sq.domain in self.agents and sq.domain in retrieval_results:
                agent = self.agents[sq.domain]
                result = retrieval_results[sq.domain]

                logger.info("[생성] 에이전트 [%s] 생성 시작", sq.domain)

                # 검색된 문서로 답변 생성
                content = agent.generate_only(
                    query=sq.query,
                    documents=result.documents,
                    user_context=user_context,
                )

                # 액션 제안
                actions = agent.suggest_actions(sq.query, content)

                responses[sq.domain] = {
                    "content": content,
                    "sources": result.sources,
                    "actions": actions,
                }

                all_sources.extend(result.sources)
                all_actions.extend(actions)

        # 응답 통합
        if len(responses) == 1:
            domain = list(responses.keys())[0]
            final_response = responses[domain]["content"]
        else:
            # 복수 도메인 응답 병합
            domain_labels = {
                "startup_funding": "창업/지원",
                "finance_tax": "재무/세무",
                "hr_labor": "인사/노무",
            }
            parts = []
            for domain, resp in responses.items():
                label = domain_labels.get(domain, domain)
                parts.append(f"## {label}\n\n{resp['content']}")
            final_response = "\n\n---\n\n".join(parts)

        state["responses"] = responses
        state["final_response"] = final_response
        state["sources"] = all_sources
        state["actions"] = all_actions

        generate_time = time.time() - start
        state["timing_metrics"]["generate_time"] = generate_time

        logger.info(
            "[생성] 완료: %d자 (%.3fs)",
            len(final_response),
            generate_time,
        )

        return state

    async def _agenerate_node(self, state: RouterState) -> RouterState:
        """비동기 생성 노드: 도메인별 병렬 생성."""
        start = time.time()
        sub_queries = state["sub_queries"]
        retrieval_results = state["retrieval_results"]
        user_context = state.get("user_context")

        async def generate_for_domain(sq: SubQuery):
            if sq.domain in self.agents and sq.domain in retrieval_results:
                agent = self.agents[sq.domain]
                result = retrieval_results[sq.domain]

                content = await agent.agenerate_only(
                    query=sq.query,
                    documents=result.documents,
                    user_context=user_context,
                )

                actions = agent.suggest_actions(sq.query, content)

                return sq.domain, {
                    "content": content,
                    "sources": result.sources,
                    "actions": actions,
                }
            return None

        tasks = [generate_for_domain(sq) for sq in sub_queries]
        results = await asyncio.gather(*tasks)

        responses: dict[str, Any] = {}
        all_sources: list[SourceDocument] = []
        all_actions: list[ActionSuggestion] = []

        for result in results:
            if result is not None:
                domain, resp = result
                responses[domain] = resp
                all_sources.extend(resp["sources"])
                all_actions.extend(resp["actions"])

        # 응답 통합
        if len(responses) == 1:
            domain = list(responses.keys())[0]
            final_response = responses[domain]["content"]
        else:
            domain_labels = {
                "startup_funding": "창업/지원",
                "finance_tax": "재무/세무",
                "hr_labor": "인사/노무",
            }
            parts = []
            for domain, resp in responses.items():
                label = domain_labels.get(domain, domain)
                parts.append(f"## {label}\n\n{resp['content']}")
            final_response = "\n\n---\n\n".join(parts)

        state["responses"] = responses
        state["final_response"] = final_response
        state["sources"] = all_sources
        state["actions"] = all_actions

        generate_time = time.time() - start
        state["timing_metrics"]["generate_time"] = generate_time

        logger.info(
            "[생성] 완료: %d자 (%.3fs)",
            len(final_response),
            generate_time,
        )

        return state

    def _evaluate_node(self, state: RouterState) -> RouterState:
        """평가 노드: LLM 평가 + RAGAS 평가 (로깅만)."""
        start = time.time()

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        # 기존 LLM 평가 수행
        if self.settings.enable_llm_evaluation:
            evaluation = self.evaluator.evaluate(
                question=state["query"],
                answer=state["final_response"],
                context=context,
            )
            state["evaluation"] = evaluation

            logger.info(
                "[LLM 평가] 점수=%d/100, %s",
                evaluation.total_score,
                "PASS" if evaluation.passed else "FAIL",
            )
        else:
            state["evaluation"] = None

        # RAGAS 평가 (로깅만, 재시도 없음)
        if self.settings.enable_ragas_evaluation and self.ragas_evaluator:
            contexts = [s.content for s in state["sources"]]
            ragas_metrics = self.ragas_evaluator.evaluate_answer_quality(
                question=state["query"],
                answer=state["final_response"],
                contexts=contexts,
            )
            state["ragas_metrics"] = ragas_metrics

            logger.info(
                "[RAGAS 평가] faithfulness=%.2f, answer_relevancy=%.2f",
                ragas_metrics.get("faithfulness") or 0,
                ragas_metrics.get("answer_relevancy") or 0,
            )
        else:
            state["ragas_metrics"] = None

        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time

        return state

    async def _aevaluate_node(self, state: RouterState) -> RouterState:
        """비동기 평가 노드."""
        start = time.time()

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        # 기존 LLM 평가 수행
        if self.settings.enable_llm_evaluation:
            evaluation = await self.evaluator.aevaluate(
                question=state["query"],
                answer=state["final_response"],
                context=context,
            )
            state["evaluation"] = evaluation

            logger.info(
                "[LLM 평가] 점수=%d/100, %s",
                evaluation.total_score,
                "PASS" if evaluation.passed else "FAIL",
            )
        else:
            state["evaluation"] = None

        # RAGAS 평가 (비동기)
        if self.settings.enable_ragas_evaluation and self.ragas_evaluator:
            contexts = [s.content for s in state["sources"]]
            ragas_metrics = await self.ragas_evaluator.aevaluate_answer_quality(
                question=state["query"],
                answer=state["final_response"],
                contexts=contexts,
            )
            state["ragas_metrics"] = ragas_metrics

            logger.info(
                "[RAGAS 평가] faithfulness=%.2f, answer_relevancy=%.2f",
                ragas_metrics.get("faithfulness") or 0,
                ragas_metrics.get("answer_relevancy") or 0,
            )
        else:
            state["ragas_metrics"] = None

        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time

        return state

    def _create_initial_state(
        self,
        query: str,
        user_context: UserContext | None,
    ) -> RouterState:
        """초기 상태를 생성합니다."""
        return {
            "query": query,
            "user_context": user_context,
            "domains": [],
            "classification_result": None,
            "sub_queries": [],
            "retrieval_results": {},
            "responses": {},
            "documents": [],
            "final_response": "",
            "sources": [],
            "actions": [],
            "evaluation": None,
            "ragas_metrics": None,
            "retry_count": 0,
            "timing_metrics": {},
        }

    def _create_response(
        self,
        final_state: RouterState,
        total_time: float,
    ) -> ChatResponse:
        """최종 응답을 생성합니다."""
        timing_data = final_state.get("timing_metrics", {})
        agent_timings = [
            AgentTimingMetrics(
                domain=a["domain"],
                retrieve_time=a.get("retrieve_time", 0.0),
                generate_time=0.0,  # 별도 측정 필요 시 추가
                total_time=a.get("total_time", 0.0),
            )
            for a in timing_data.get("agents", [])
        ]
        timing_metrics = TimingMetrics(
            classify_time=timing_data.get("classify_time", 0.0),
            agents=agent_timings,
            integrate_time=timing_data.get("generate_time", 0.0),
            evaluate_time=timing_data.get("evaluate_time", 0.0),
            total_time=total_time,
        )

        domains = final_state["domains"]

        # evaluation_data 생성 (Backend DB 저장용)
        evaluation_data = self._create_evaluation_data(final_state, total_time)

        return ChatResponse(
            content=final_state["final_response"],
            domain=domains[0] if domains else "general",
            domains=domains,
            sources=final_state["sources"],
            actions=final_state["actions"],
            evaluation=final_state.get("evaluation"),
            retry_count=final_state.get("retry_count", 0),
            ragas_metrics=final_state.get("ragas_metrics"),
            timing_metrics=timing_metrics,
            evaluation_data=evaluation_data,
        )

    def _create_evaluation_data(
        self,
        final_state: RouterState,
        total_time: float,
    ) -> EvaluationDataForDB:
        """Backend DB 저장용 evaluation_data를 생성합니다."""
        # RAGAS 메트릭
        ragas_metrics = final_state.get("ragas_metrics") or {}

        # LLM 평가 결과
        evaluation = final_state.get("evaluation")
        llm_score = evaluation.total_score if evaluation else None
        llm_passed = evaluation.passed if evaluation else None

        # 컨텍스트 (문서 내용 발췌)
        contexts = [
            s.content[:500] for s in final_state.get("sources", [])[:5]
        ]

        # 검색 평가 결과 집계
        retrieval_results = final_state.get("retrieval_results", {})
        retrieval_evaluation = None

        if retrieval_results:
            # 첫 번째 도메인의 검색 결과 사용 (또는 집계)
            for domain, result in retrieval_results.items():
                if result and result.evaluation:
                    eval_result = result.evaluation
                    # RetrievalEvaluationResult는 passed (bool) 속성만 있음
                    status = "PASS" if eval_result.passed else "FAIL"
                    retrieval_evaluation = RetrievalEvaluationData(
                        status=status,
                        doc_count=eval_result.doc_count,
                        keyword_match_ratio=eval_result.keyword_match_ratio,
                        avg_similarity=eval_result.avg_similarity_score,
                        used_multi_query=result.used_multi_query,
                    )
                    break

        return EvaluationDataForDB(
            faithfulness=ragas_metrics.get("faithfulness"),
            answer_relevancy=ragas_metrics.get("answer_relevancy"),
            context_precision=ragas_metrics.get("context_precision"),
            llm_score=llm_score,
            llm_passed=llm_passed,
            contexts=contexts,
            domains=final_state.get("domains", []),
            retrieval_evaluation=retrieval_evaluation,
            response_time=total_time,
        )

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
        total_start = time.time()
        initial_state = self._create_initial_state(query, user_context)

        # 그래프 실행
        final_state = self.graph.invoke(initial_state)

        total_time = time.time() - total_start
        return self._create_response(final_state, total_time)

    async def aprocess(
        self,
        query: str,
        user_context: UserContext | None = None,
    ) -> ChatResponse:
        """질문을 비동기로 처리합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트

        Returns:
            채팅 응답
        """
        total_start = time.time()
        initial_state = self._create_initial_state(query, user_context)

        # 비동기 그래프 실행 (전체 타임아웃 적용)
        try:
            final_state = await asyncio.wait_for(
                self.async_graph.ainvoke(initial_state),
                timeout=self.settings.total_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "[aprocess] 전체 타임아웃 (%.1fs): '%s...'",
                self.settings.total_timeout,
                query[:30],
            )
            # 타임아웃 시 fallback 응답 생성
            final_state = initial_state
            final_state["final_response"] = self.settings.fallback_message
            final_state["sources"] = []
            final_state["actions"] = []
            final_state["evaluation"] = EvaluationResult(
                scores={},
                total_score=0,
                passed=False,
                feedback="요청 처리 시간 초과",
            )

        total_time = time.time() - total_start
        return self._create_response(final_state, total_time)

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
        classification = self.domain_classifier.classify(query)

        # 도메인 외 질문 거부
        if not classification.is_relevant:
            logger.info("[스트리밍] 도메인 외 질문 - 거부 응답 반환")
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

        domains = classification.domains

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

            for char in response.content:
                yield {"type": "token", "content": char}

            yield {
                "type": "done",
                "content": response.content,
                "domain": response.domain,
                "domains": response.domains,
                "sources": response.sources,
                "actions": response.actions,
                "evaluation": response.evaluation,
                "ragas_metrics": response.ragas_metrics,
            }
