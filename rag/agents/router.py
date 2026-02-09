"""메인 라우터 모듈.

LangGraph 기반 멀티에이전트 라우터를 구현합니다.
질문을 분류하고 적절한 에이전트로 라우팅하며 응답을 통합합니다.

워크플로우 (5단계):
1. 분류 (classify) → 벡터 유사도 기반 도메인 분류
2. 분해 (decompose) → 복합 질문을 단일 도메인 질문으로 분해
3. 검색 (retrieve) → 도메인별 병렬 검색 + 규칙 기반 평가 + Multi-Query 재검색
4. 생성 (generate) → 검색된 문서 기반 답변 생성
5. 평가 (evaluate) → LLM 평가 (FAIL 시 재시도) + RAGAS 평가 (최종 시도에서만, 로깅용)
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from agents.base import RetrievalEvaluationResult, RetrievalResult, RetrievalStatus
from agents.evaluator import EvaluatorAgent
from agents.generator import ResponseGeneratorAgent
from agents.finance_tax import FinanceTaxAgent
from agents.hr_labor import HRLaborAgent
from agents.legal import LegalAgent
from agents.retrieval_agent import RetrievalAgent
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
from utils.legal_supplement import needs_legal_supplement
from utils.prompts import REJECTION_RESPONSE
from utils.question_decomposer import SubQuery, get_question_decomposer
from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


class RouterState(TypedDict):
    """라우터 상태 타입."""

    query: str
    history: list[dict]
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

    워크플로우:
    1. 질문 분류 (classify) → 벡터 유사도 기반 도메인 식별
    2. 질문 분해 (decompose) → 복합 질문을 단일 도메인 질문으로 분해
    3. 문서 검색 (retrieve) → 도메인별 병렬 검색
    4. 답변 생성 (generate) → 검색된 문서 기반 답변 생성
    5. 답변 평가 (evaluate) → LLM 평가 (FAIL 시 generate 재실행) + RAGAS 평가 (최종 시도)
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
            "law_common": LegalAgent(rag_chain=shared_rag_chain),
        }
        self.evaluator = EvaluatorAgent()
        self.generator = ResponseGeneratorAgent(
            agents=self.agents,
            rag_chain=shared_rag_chain,
        )

        # 검색 에이전트 (3번 retrieve 파트 전담)
        self.retrieval_agent = RetrievalAgent(
            agents=self.agents,
            rag_chain=shared_rag_chain,
            vector_store=self.vector_store,
        )

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
        workflow.add_conditional_edges(
            "evaluate",
            self._should_retry_after_evaluate,
            {"generate": "generate", "__end__": END},
        )

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
        workflow.add_conditional_edges(
            "evaluate",
            self._should_retry_after_evaluate,
            {"generate": "generate", "__end__": END},
        )

        return workflow.compile()

    def _should_continue_after_classify(self, state: RouterState) -> str:
        """분류 후 계속 진행할지 거부할지 판단합니다.

        Args:
            state: 라우터 상태

        Returns:
            "continue": 관련 질문이면 계속 진행
            "reject": 도메인 외 질문이면 종료
        """
        classification = state.get("classification_result")
        if classification and not classification.is_relevant:
            return "reject"
        return "continue"

    def _should_retry_after_evaluate(self, state: RouterState) -> str:
        """평가 결과에 따라 재시도 여부를 결정합니다.

        LLM 평가 실패 시 generate 노드로 돌아가 피드백 기반 재생성을 시도합니다.
        PASS이거나 최대 재시도 횟수에 도달하면 종료합니다.

        Args:
            state: 라우터 상태

        Returns:
            "generate": 재시도 필요
            "__end__": 종료
        """
        evaluation = state.get("evaluation")
        retry_count = state.get("retry_count", 0)

        if (
            self.settings.enable_post_eval_retry
            and evaluation
            and not evaluation.passed
            and retry_count < self.settings.max_retry_count
        ):
            logger.info(
                "[평가→재시도] FAIL (점수=%d, retry=%d/%d) → generate 재실행",
                evaluation.total_score,
                retry_count,
                self.settings.max_retry_count,
            )
            return "generate"
        return "__end__"

    def _augment_query_for_classification(self, query: str, history: list[dict]) -> str:
        """분류 전 대명사/지시어 질문을 history로 보강합니다.

        짧은 후속 질문("그럼 세금은요?")에 이전 사용자 메시지를 접두사로 붙여
        도메인 분류 정확도를 높입니다. LLM 호출 없이 휴리스틱으로 동작합니다.

        Args:
            query: 현재 사용자 질문
            history: 대화 이력 (role/content dict 리스트)

        Returns:
            보강된 쿼리 (조건 불충족 시 원본 그대로 반환)
        """
        if not history or len(query) > 30:
            return query

        pronouns = ["그럼", "그거", "그건", "그러면", "이거", "저거", "거기", "이건"]
        if not any(p in query for p in pronouns):
            return query

        for msg in reversed(history):
            if msg.get("role") == "user":
                logger.info("[분류 보강] '%s' → '%s %s'", query, msg["content"][:30], query)
                return f"{msg['content']} {query}"

        return query

    def _classify_node(self, state: RouterState) -> RouterState:
        """분류 노드: 벡터 유사도 기반으로 도메인을 식별합니다."""
        start = time.time()
        query = state["query"]
        history = state.get("history", [])

        # 대명사/지시어 질문 보강 (분류용, 원본 query는 유지)
        augmented_query = self._augment_query_for_classification(query, history)

        # 벡터 유사도 기반 도메인 분류
        classification = self.domain_classifier.classify(augmented_query)
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
        history = state.get("history", [])

        # 단일 도메인이면 QuestionDecomposer 초기화/호출 스킵
        if len(domains) <= 1:
            domain = domains[0] if domains else "startup_funding"
            state["sub_queries"] = [SubQuery(domain=domain, query=query)]
            decompose_time = time.time() - start
            state["timing_metrics"]["decompose_time"] = decompose_time
            logger.info("[분해] 단일 도메인 (%s) - 분해 스킵 (%.3fs)", domain, decompose_time)
            return state

        # 복합 질문 분해 (대화 이력 전달)
        sub_queries = self.question_decomposer.decompose(query, domains, history)
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
        history = state.get("history", [])

        # 단일 도메인이면 QuestionDecomposer 초기화/호출 스킵
        if len(domains) <= 1:
            domain = domains[0] if domains else "startup_funding"
            state["sub_queries"] = [SubQuery(domain=domain, query=query)]
            decompose_time = time.time() - start
            state["timing_metrics"]["decompose_time"] = decompose_time
            logger.info("[분해] 단일 도메인 (%s) - 분해 스킵 (%.3fs)", domain, decompose_time)
            return state

        sub_queries = await self.question_decomposer.adecompose(query, domains, history)
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
        """검색 노드: RetrievalAgent에 위임합니다."""
        return self.retrieval_agent.retrieve(state)

    async def _aretrieve_node(self, state: RouterState) -> RouterState:
        """비동기 검색 노드: RetrievalAgent에 위임합니다."""
        return await self.retrieval_agent.aretrieve(state)

    def _generate_node(self, state: RouterState) -> RouterState:
        """생성 노드: 검색된 문서 기반으로 답변을 생성합니다."""
        start = time.time()

        if self.settings.enable_integrated_generation:
            result = self.generator.generate(
                query=state["query"],
                sub_queries=state["sub_queries"],
                retrieval_results=state["retrieval_results"],
                user_context=state.get("user_context"),
                domains=state["domains"],
            )
            state["final_response"] = result.content
            state["actions"] = result.actions
            state["sources"] = result.sources
        else:
            # 기존 로직 (backward compatibility)
            self._generate_node_legacy(state)

        generate_time = time.time() - start
        state["timing_metrics"]["generate_time"] = generate_time

        logger.info(
            "[생성] 완료: %d자 (%.3fs)",
            len(state["final_response"]),
            generate_time,
        )

        return state

    def _generate_node_legacy(self, state: RouterState) -> None:
        """기존 생성 로직 (enable_integrated_generation=False 시 사용).

        Args:
            state: 라우터 상태 (in-place 수정)
        """
        sub_queries = state["sub_queries"]
        retrieval_results = state["retrieval_results"]
        user_context = state.get("user_context")

        # 재시도 시 이전 평가 피드백 추출
        evaluation_feedback = None
        if state.get("retry_count", 0) > 0 and state.get("evaluation"):
            evaluation_feedback = state["evaluation"].feedback
            logger.info(
                "[생성] 재시도 %d회차 - 피드백: %s",
                state["retry_count"],
                (evaluation_feedback or "")[:100],
            )

        responses: dict[str, Any] = {}
        all_sources: list[SourceDocument] = []
        all_actions: list[ActionSuggestion] = []

        legal_supplement_result = retrieval_results.get("law_common_supplement")
        legal_supplement_docs = legal_supplement_result.documents if legal_supplement_result else []

        for sq in sub_queries:
            if sq.domain in self.agents and sq.domain in retrieval_results:
                agent = self.agents[sq.domain]
                result = retrieval_results[sq.domain]

                merged_documents = result.documents
                if legal_supplement_docs and sq.domain != "law_common":
                    merged_documents = result.documents + legal_supplement_docs

                content = agent.generate_only(
                    query=sq.query,
                    documents=merged_documents,
                    user_context=user_context,
                    evaluation_feedback=evaluation_feedback,
                )

                actions = agent.suggest_actions(sq.query, content)

                if legal_supplement_docs and sq.domain != "law_common":
                    legal_agent = self.agents["law_common"]
                    legal_actions = legal_agent.suggest_actions(sq.query, content)
                    actions.extend(legal_actions)

                responses[sq.domain] = {
                    "content": content,
                    "sources": result.sources,
                    "actions": actions,
                }

                all_sources.extend(result.sources)
                all_actions.extend(actions)

        if legal_supplement_result:
            all_sources.extend(legal_supplement_result.sources)

        if len(responses) == 1:
            domain = list(responses.keys())[0]
            final_response = responses[domain]["content"]
        else:
            domain_labels = {
                "startup_funding": "창업/지원",
                "finance_tax": "재무/세무",
                "hr_labor": "인사/노무",
                "law_common": "법률",
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

    async def _agenerate_node(self, state: RouterState) -> RouterState:
        """비동기 생성 노드: 통합 생성 에이전트 사용."""
        start = time.time()

        if self.settings.enable_integrated_generation:
            result = await self.generator.agenerate(
                query=state["query"],
                sub_queries=state["sub_queries"],
                retrieval_results=state["retrieval_results"],
                user_context=state.get("user_context"),
                domains=state["domains"],
            )
            state["final_response"] = result.content
            state["actions"] = result.actions
            state["sources"] = result.sources
        else:
            # 기존 로직 (backward compatibility)
            await self._agenerate_node_legacy(state)

        generate_time = time.time() - start
        state["timing_metrics"]["generate_time"] = generate_time

        logger.info(
            "[생성] 완료: %d자 (%.3fs)",
            len(state["final_response"]),
            generate_time,
        )

        return state

    async def _agenerate_node_legacy(self, state: RouterState) -> None:
        """기존 비동기 생성 로직 (enable_integrated_generation=False 시 사용).

        Args:
            state: 라우터 상태 (in-place 수정)
        """
        sub_queries = state["sub_queries"]
        retrieval_results = state["retrieval_results"]
        user_context = state.get("user_context")

        # 재시도 시 이전 평가 피드백 추출
        evaluation_feedback = None
        if state.get("retry_count", 0) > 0 and state.get("evaluation"):
            evaluation_feedback = state["evaluation"].feedback
            logger.info(
                "[생성] 재시도 %d회차 - 피드백: %s",
                state["retry_count"],
                (evaluation_feedback or "")[:100],
            )

        legal_supplement_result = retrieval_results.get("law_common_supplement")
        legal_supplement_docs = legal_supplement_result.documents if legal_supplement_result else []

        async def generate_for_domain(sq: SubQuery) -> tuple[str, dict[str, Any]] | None:
            if sq.domain in self.agents and sq.domain in retrieval_results:
                agent = self.agents[sq.domain]
                result = retrieval_results[sq.domain]

                merged_documents = result.documents
                if legal_supplement_docs and sq.domain != "law_common":
                    merged_documents = result.documents + legal_supplement_docs

                content = await agent.agenerate_only(
                    query=sq.query,
                    documents=merged_documents,
                    user_context=user_context,
                    evaluation_feedback=evaluation_feedback,
                )

                actions = agent.suggest_actions(sq.query, content)

                if legal_supplement_docs and sq.domain != "law_common":
                    legal_agent = self.agents["law_common"]
                    legal_actions = legal_agent.suggest_actions(sq.query, content)
                    actions.extend(legal_actions)

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

        if legal_supplement_result:
            all_sources.extend(legal_supplement_result.sources)

        if len(responses) == 1:
            domain = list(responses.keys())[0]
            final_response = responses[domain]["content"]
        else:
            domain_labels = {
                "startup_funding": "창업/지원",
                "finance_tax": "재무/세무",
                "hr_labor": "인사/노무",
                "law_common": "법률",
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

    def _evaluate_node(self, state: RouterState) -> RouterState:
        """평가 노드: LLM 평가 (FAIL 시 재시도) + RAGAS 평가 (항상 로깅용)."""
        start = time.time()

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        # LLM 평가 수행
        if self.settings.enable_llm_evaluation:
            evaluation = self.evaluator.evaluate(
                question=state["query"],
                answer=state["final_response"],
                context=context,
            )
            state["evaluation"] = evaluation

            logger.info(
                "[LLM 평가] 점수=%d/100, %s (retry=%d/%d)",
                evaluation.total_score,
                "PASS" if evaluation.passed else "FAIL",
                state.get("retry_count", 0),
                self.settings.max_retry_count,
            )
        else:
            state["evaluation"] = None

        # RAGAS 평가 (항상 실행, 로깅/모니터링용)
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

        # 재시도 판단: FAIL이고 재시도 가능하면 retry_count 증가
        if (
            self.settings.enable_post_eval_retry
            and state.get("evaluation")
            and not state["evaluation"].passed
            and state.get("retry_count", 0) < self.settings.max_retry_count
        ):
            state["retry_count"] = state.get("retry_count", 0) + 1
        elif (
            self.settings.enable_post_eval_retry
            and state.get("evaluation")
            and not state["evaluation"].passed
            and state.get("retry_count", 0) >= self.settings.max_retry_count
        ):
            # 최대 재시도 후에도 FAIL → 사과 메시지로 교체
            logger.warning(
                "[평가] 최대 재시도(%d회) 후에도 FAIL (점수=%d) → 사과 응답",
                self.settings.max_retry_count,
                state["evaluation"].total_score,
            )
            state["final_response"] = (
                "죄송합니다. 질문에 대한 충분한 품질의 답변을 생성하지 못했습니다. "
                "질문을 다른 방식으로 다시 해주시면 더 나은 답변을 드리겠습니다."
            )

        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time

        return state

    async def _aevaluate_node(self, state: RouterState) -> RouterState:
        """비동기 평가 노드: LLM 평가 (FAIL 시 재시도) + RAGAS 평가 (항상 로깅용)."""
        start = time.time()

        # 컨텍스트 생성
        context = "\n".join([s.content for s in state["sources"][:5]])

        # LLM 평가 수행
        if self.settings.enable_llm_evaluation:
            evaluation = await self.evaluator.aevaluate(
                question=state["query"],
                answer=state["final_response"],
                context=context,
            )
            state["evaluation"] = evaluation

            logger.info(
                "[LLM 평가] 점수=%d/100, %s (retry=%d/%d)",
                evaluation.total_score,
                "PASS" if evaluation.passed else "FAIL",
                state.get("retry_count", 0),
                self.settings.max_retry_count,
            )
        else:
            state["evaluation"] = None

        # RAGAS 평가 (항상 실행, 로깅/모니터링용)
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

        # 재시도 판단: FAIL이고 재시도 가능하면 retry_count 증가
        if (
            self.settings.enable_post_eval_retry
            and state.get("evaluation")
            and not state["evaluation"].passed
            and state.get("retry_count", 0) < self.settings.max_retry_count
        ):
            state["retry_count"] = state.get("retry_count", 0) + 1
        elif (
            self.settings.enable_post_eval_retry
            and state.get("evaluation")
            and not state["evaluation"].passed
            and state.get("retry_count", 0) >= self.settings.max_retry_count
        ):
            # 최대 재시도 후에도 FAIL → 사과 메시지로 교체
            logger.warning(
                "[평가] 최대 재시도(%d회) 후에도 FAIL (점수=%d) → 사과 응답",
                self.settings.max_retry_count,
                state["evaluation"].total_score,
            )
            state["final_response"] = (
                "죄송합니다. 질문에 대한 충분한 품질의 답변을 생성하지 못했습니다. "
                "질문을 다른 방식으로 다시 해주시면 더 나은 답변을 드리겠습니다."
            )

        evaluate_time = time.time() - start
        state["timing_metrics"]["evaluate_time"] = evaluate_time

        return state

    def _create_initial_state(
        self,
        query: str,
        user_context: UserContext | None,
        history: list[dict] | None = None,
    ) -> RouterState:
        """초기 상태를 생성합니다."""
        return {
            "query": query,
            "history": history or [],
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
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """질문을 처리하고 응답을 생성합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            history: 대화 이력

        Returns:
            채팅 응답
        """
        total_start = time.time()
        initial_state = self._create_initial_state(query, user_context, history)

        # 그래프 실행
        final_state = self.graph.invoke(initial_state)

        total_time = time.time() - total_start
        return self._create_response(final_state, total_time)

    async def aprocess(
        self,
        query: str,
        user_context: UserContext | None = None,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """질문을 비동기로 처리합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            history: 대화 이력

        Returns:
            채팅 응답
        """
        total_start = time.time()
        initial_state = self._create_initial_state(query, user_context, history)

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
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """질문을 스트리밍으로 처리합니다.

        단일 도메인 질문에 대해 진정한 토큰 스트리밍을 지원합니다.
        복합 도메인 질문은 기존 방식으로 처리 후 스트리밍합니다.

        Args:
            query: 사용자 질문
            user_context: 사용자 컨텍스트
            history: 대화 이력

        Yields:
            스트리밍 응답 딕셔너리
        """
        # 대명사/지시어 질문 보강 (분류용)
        augmented_query = self._augment_query_for_classification(query, history or [])

        # 도메인 분류
        classification = self.domain_classifier.classify(augmented_query)

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
            domain = domains[0]
            agent = self.agents[domain]
            all_sources: list[SourceDocument] = []
            all_actions: list[ActionSuggestion] = []
            content = ""

            # 법률 보충 검색 판단 (law_common이 아닌 경우만)
            supplementary_documents: list[Document] | None = None
            if (
                domain != "law_common"
                and self.settings.enable_legal_supplement
                and needs_legal_supplement(query, [], domains)
            ):
                logger.info("[스트리밍] 쿼리 기반 법률 보충 검색 시작")
                try:
                    legal_agent = self.agents["law_common"]
                    legal_result = await legal_agent.aretrieve_only(query)
                    supplementary_documents = legal_result.documents[:self.settings.legal_supplement_k]
                    all_sources.extend(
                        legal_result.sources[:self.settings.legal_supplement_k]
                    )
                    logger.info(
                        "[스트리밍] 법률 보충 검색 완료: %d건",
                        len(supplementary_documents),
                    )
                except Exception as e:
                    logger.warning("[스트리밍] 법률 보충 검색 실패: %s", e)

            if self.settings.enable_integrated_generation:
                # 통합 생성 에이전트 사용 스트리밍
                # 검색 수행
                retrieval_result = await agent.aretrieve_only(query)
                documents = retrieval_result.documents
                all_sources.extend(retrieval_result.sources)

                if supplementary_documents:
                    documents = documents + supplementary_documents

                # 액션 사전 수집 (이미 검색된 결과 재사용)
                retrieval_results_map: dict[str, RetrievalResult] = {
                    domain: retrieval_result,
                }
                if supplementary_documents:
                    legal_supp_sources = self.generator.rag_chain.documents_to_sources(
                        supplementary_documents
                    )
                    retrieval_results_map["law_common_supplement"] = RetrievalResult(
                        documents=supplementary_documents,
                        scores=[],
                        sources=legal_supp_sources,
                        evaluation=RetrievalEvaluationResult(
                            status=RetrievalStatus.SUCCESS,
                            doc_count=len(supplementary_documents),
                            keyword_match_ratio=0.0,
                            avg_similarity_score=0.0,
                        ),
                    )

                pre_actions = self.generator._collect_actions(
                    query, retrieval_results_map, [domain]
                )

                async for chunk in self.generator.astream_generate(
                    query=query,
                    documents=documents,
                    user_context=user_context,
                    domain=domain,
                    actions=pre_actions,
                ):
                    if chunk["type"] == "token":
                        yield {"type": "token", "content": chunk["content"]}
                    elif chunk["type"] == "generation_done":
                        content = chunk["content"]
                        all_actions = pre_actions
            else:
                # 기존 방식 (BaseAgent.astream)
                async for chunk in agent.astream(
                    query, user_context, supplementary_documents=supplementary_documents
                ):
                    if chunk["type"] == "token":
                        yield {"type": "token", "content": chunk["content"]}
                    elif chunk["type"] == "done":
                        content = chunk["content"]
                        all_sources.extend(chunk["sources"])
                        all_actions = chunk["actions"]

                        if supplementary_documents:
                            legal_agent = self.agents["law_common"]
                            legal_actions = legal_agent.suggest_actions(query, content)
                            all_actions.extend(legal_actions)

            yield {
                "type": "done",
                "content": content,
                "domain": domain,
                "domains": domains,
                "sources": all_sources,
                "actions": all_actions,
            }
        elif self.settings.enable_integrated_generation:
            # 복수 도메인: 통합 생성 에이전트로 LLM 토큰 스트리밍
            # 분해 + 검색 수행
            initial_state = self._create_initial_state(query, user_context, history)
            initial_state["domains"] = domains
            initial_state["classification_result"] = classification

            # 분해
            decompose_state = await self._adecompose_node(initial_state)
            # 검색
            retrieve_state = await self._aretrieve_node(decompose_state)

            retrieval_results = retrieve_state["retrieval_results"]
            sub_queries = retrieve_state["sub_queries"]

            # 액션 사전 수집
            pre_actions = self.generator._collect_actions(
                query, retrieval_results, domains
            )

            # 소스 수집
            all_sources_multi: list[SourceDocument] = []
            for d in domains:
                if d in retrieval_results:
                    all_sources_multi.extend(retrieval_results[d].sources)
            legal_supp = retrieval_results.get("law_common_supplement")
            if legal_supp:
                all_sources_multi.extend(legal_supp.sources)

            content = ""
            async for chunk in self.generator.astream_generate_multi(
                query=query,
                sub_queries=sub_queries,
                retrieval_results=retrieval_results,
                user_context=user_context,
                domains=domains,
                actions=pre_actions,
            ):
                if chunk["type"] == "token":
                    yield {"type": "token", "content": chunk["content"]}
                elif chunk["type"] == "generation_done":
                    content = chunk["content"]

            yield {
                "type": "done",
                "content": content,
                "domain": domains[0] if domains else "general",
                "domains": domains,
                "sources": all_sources_multi,
                "actions": pre_actions,
            }
        else:
            # 복합 도메인: 기존 방식 (전체 처리 후 문자 단위 스트리밍)
            response = await self.aprocess(query, user_context, history)

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
