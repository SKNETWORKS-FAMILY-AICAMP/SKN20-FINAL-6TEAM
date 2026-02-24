"""MainRouter 단위 테스트."""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Any

import pytest

from agents.router import MainRouter, RouterState
from utils.domain_classifier import DomainClassificationResult


class TestRouterState:
    """RouterState TypedDict 구조 검증."""

    def test_router_state_has_required_fields(self):
        """RouterState가 필수 필드를 포함하는지 검증."""
        state: RouterState = {
            "query": "사업자등록 절차는?",
            "user_context": None,
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

        assert "query" in state
        assert "user_context" in state
        assert "domains" in state
        assert "classification_result" in state
        assert "sub_queries" in state
        assert "retrieval_results" in state
        assert "responses" in state
        assert "documents" in state
        assert "final_response" in state
        assert "sources" in state
        assert "actions" in state
        assert "evaluation" in state
        assert "ragas_metrics" in state
        assert "retry_count" in state
        assert "timing_metrics" in state


class TestMainRouterInit:
    """MainRouter 초기화 테스트."""

    @pytest.fixture
    def mock_vector_store(self):
        """ChromaVectorStore 모킹."""
        mock_store = Mock()
        mock_store.get_retriever.return_value = Mock()
        return mock_store

    @pytest.fixture
    def mock_dependencies(self):
        """모든 의존성 모킹."""
        with patch("agents.router.RAGChain") as mock_chain, \
             patch("agents.router.StartupFundingAgent") as mock_startup, \
             patch("agents.router.FinanceTaxAgent") as mock_finance, \
             patch("agents.router.HRLaborAgent") as mock_hr, \
             patch("agents.router.LegalAgent") as mock_legal, \
             patch("agents.router.EvaluatorAgent") as mock_evaluator, \
             patch("agents.router.get_settings") as mock_get_settings:

            mock_chain.return_value = Mock(name="rag_chain")
            mock_startup.return_value = Mock(name="startup_agent")
            mock_finance.return_value = Mock(name="finance_agent")
            mock_hr.return_value = Mock(name="hr_agent")
            mock_legal.return_value = Mock(name="legal_agent")
            mock_evaluator.return_value = Mock(name="evaluator")

            mock_settings = Mock()
            mock_settings.enable_ragas_evaluation = False
            mock_get_settings.return_value = mock_settings

            yield {
                "chain": mock_chain,
                "startup": mock_startup,
                "finance": mock_finance,
                "hr": mock_hr,
                "legal": mock_legal,
                "evaluator": mock_evaluator,
                "settings": mock_settings,
            }

    def test_mainrouter_init_with_vector_store(
        self, mock_vector_store, mock_dependencies
    ):
        """벡터스토어 주입 시 초기화 확인."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.vector_store == mock_vector_store
        mock_dependencies["chain"].assert_called_once_with(vector_store=mock_vector_store)

    def test_mainrouter_init_creates_default_vector_store(self, mock_dependencies):
        """벡터스토어 없이 초기화 시 기본 생성."""
        with patch("agents.router.ChromaVectorStore") as mock_chroma:
            mock_chroma.return_value = Mock()

            router = MainRouter()

            mock_chroma.assert_called_once()
            assert router.vector_store == mock_chroma.return_value

    def test_mainrouter_init_creates_all_agents(
        self, mock_vector_store, mock_dependencies
    ):
        """4개 도메인 에이전트 생성 확인."""
        router = MainRouter(vector_store=mock_vector_store)

        assert "startup_funding" in router.agents
        assert "finance_tax" in router.agents
        assert "hr_labor" in router.agents
        assert "law_common" in router.agents
        assert len(router.agents) == 4

        # 각 에이전트가 같은 RAG 체인을 공유하는지 확인
        rag_chain_instance = mock_dependencies["chain"].return_value
        mock_dependencies["startup"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["finance"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["hr"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["legal"].assert_called_once_with(rag_chain=rag_chain_instance)

    def test_mainrouter_init_creates_evaluator(
        self, mock_vector_store, mock_dependencies
    ):
        """EvaluatorAgent 생성 확인."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.evaluator is not None
        mock_dependencies["evaluator"].assert_called_once()

    def test_mainrouter_init_builds_async_graph(
        self, mock_vector_store, mock_dependencies
    ):
        """비동기 그래프 빌드 확인."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.async_graph is not None


class TestShouldContinueAfterClassify:
    """_should_continue_after_classify 메서드 테스트."""

    @pytest.fixture
    def router_with_mocks(self):
        """모킹된 MainRouter 인스턴스."""
        with patch("agents.router.ChromaVectorStore"), \
             patch("agents.router.RAGChain"), \
             patch("agents.router.StartupFundingAgent"), \
             patch("agents.router.FinanceTaxAgent"), \
             patch("agents.router.HRLaborAgent"), \
             patch("agents.router.EvaluatorAgent"), \
             patch("agents.router.get_settings") as mock_settings:

            mock_settings.return_value = Mock(enable_ragas_evaluation=False)
            yield MainRouter()

    def test_should_continue_when_no_classification(self, router_with_mocks):
        """분류 결과가 없으면 continue 반환."""
        state: RouterState = {
            "query": "테스트 질문",
            "user_context": None,
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

        result = router_with_mocks._should_continue_after_classify(state)

        assert result == "continue"

    def test_should_continue_when_relevant(self, router_with_mocks):
        """관련 질문이면 continue 반환."""
        classification = DomainClassificationResult(
            domains=["finance_tax"],
            confidence=0.9,
            is_relevant=True,
            method="keyword",
        )
        state: RouterState = {
            "query": "부가세 신고는?",
            "user_context": None,
            "domains": ["finance_tax"],
            "classification_result": classification,
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

        result = router_with_mocks._should_continue_after_classify(state)

        assert result == "continue"

    def test_should_reject_when_not_relevant(self, router_with_mocks):
        """비관련 질문이면 reject 반환."""
        classification = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="vector",
        )
        state: RouterState = {
            "query": "오늘 날씨는?",
            "user_context": None,
            "domains": [],
            "classification_result": classification,
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

        result = router_with_mocks._should_continue_after_classify(state)

        assert result == "reject"


class TestClassifyNode:
    """_aclassify_node 메서드 테스트."""

    @pytest.fixture
    def router_with_mocks(self):
        """모킹된 MainRouter 인스턴스."""
        with patch("agents.router.ChromaVectorStore"), \
             patch("agents.router.RAGChain"), \
             patch("agents.router.StartupFundingAgent"), \
             patch("agents.router.FinanceTaxAgent"), \
             patch("agents.router.HRLaborAgent"), \
             patch("agents.router.EvaluatorAgent"), \
             patch("agents.router.get_settings") as mock_settings:

            mock_settings.return_value = Mock(enable_ragas_evaluation=False)
            yield MainRouter()

    @pytest.mark.asyncio
    async def test_classify_node_sets_classification_result(self, router_with_mocks):
        """분류 노드가 classification_result 설정."""
        mock_classification = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.95,
            is_relevant=True,
            method="keyword",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier

        state: RouterState = {
            "query": "사업자등록 절차는?",
            "user_context": None,
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

        updated_state = await router_with_mocks._aclassify_node(state)

        assert updated_state["classification_result"] is not None
        assert updated_state["classification_result"].is_relevant is True
        assert "startup_funding" in updated_state["classification_result"].domains
        mock_classifier.classify.assert_called_once_with(state["query"])

    @pytest.mark.asyncio
    async def test_classify_node_sets_domains(self, router_with_mocks):
        """분류 노드가 도메인 리스트 설정."""
        mock_classification = DomainClassificationResult(
            domains=["finance_tax", "hr_labor"],
            confidence=0.88,
            is_relevant=True,
            method="vector",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier

        state: RouterState = {
            "query": "직원 급여에 대한 세금 처리는?",
            "user_context": None,
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

        updated_state = await router_with_mocks._aclassify_node(state)

        assert updated_state["domains"] == ["finance_tax", "hr_labor"]

    @pytest.mark.asyncio
    async def test_classify_node_sets_rejection_when_irrelevant(self, router_with_mocks):
        """비관련 질문 시 거부 응답 설정."""
        mock_classification = DomainClassificationResult(
            domains=[],
            confidence=0.4,
            is_relevant=False,
            method="vector",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier

        state: RouterState = {
            "query": "오늘 날씨는?",
            "user_context": None,
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

        updated_state = await router_with_mocks._aclassify_node(state)

        assert updated_state["final_response"] != ""
        assert updated_state["sources"] == []
        assert updated_state["actions"] == []

    @pytest.mark.asyncio
    async def test_classify_node_records_timing_metrics(self, router_with_mocks):
        """분류 노드가 타이밍 메트릭 기록."""
        mock_classification = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.9,
            is_relevant=True,
            method="keyword",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier

        state: RouterState = {
            "query": "창업 절차",
            "user_context": None,
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

        updated_state = await router_with_mocks._aclassify_node(state)

        assert "classify_time" in updated_state["timing_metrics"]
        assert updated_state["timing_metrics"]["classify_time"] >= 0


class TestLazyLoadingProperties:
    """지연 로딩 프로퍼티 테스트."""

    @pytest.fixture
    def router_with_mocks(self):
        """모킹된 MainRouter 인스턴스."""
        with patch("agents.router.ChromaVectorStore"), \
             patch("agents.router.RAGChain"), \
             patch("agents.router.StartupFundingAgent"), \
             patch("agents.router.FinanceTaxAgent"), \
             patch("agents.router.HRLaborAgent"), \
             patch("agents.router.EvaluatorAgent"), \
             patch("agents.router.get_settings") as mock_settings:

            mock_settings.return_value = Mock(enable_ragas_evaluation=False)
            yield MainRouter()

    def test_lazy_loading_domain_classifier(self, router_with_mocks):
        """domain_classifier 지연 로딩 확인."""
        # 초기화 시점에는 None
        assert router_with_mocks._domain_classifier is None

        # domain_classifier 프로퍼티 접근
        with patch("agents.router.get_domain_classifier") as mock_get:
            mock_classifier = Mock()
            mock_get.return_value = mock_classifier

            classifier = router_with_mocks.domain_classifier

            # 접근 후 캐싱
            assert router_with_mocks._domain_classifier is not None
            assert classifier == mock_classifier
            mock_get.assert_called_once()

    def test_lazy_loading_question_decomposer(self, router_with_mocks):
        """question_decomposer 지연 로딩 확인."""
        assert router_with_mocks._question_decomposer is None

        with patch("agents.router.get_question_decomposer") as mock_get:
            mock_decomposer = Mock()
            mock_get.return_value = mock_decomposer

            decomposer = router_with_mocks.question_decomposer

            assert router_with_mocks._question_decomposer is not None
            assert decomposer == mock_decomposer
            mock_get.assert_called_once()

    def test_lazy_loading_ragas_evaluator_when_disabled(self, router_with_mocks):
        """RAGAS 평가 비활성화 시 ragas_evaluator는 None."""
        assert router_with_mocks._ragas_evaluator is None
        # settings.enable_ragas_evaluation이 False이므로
        evaluator = router_with_mocks.ragas_evaluator
        assert evaluator is None

    def test_lazy_loading_ragas_evaluator_when_enabled(self):
        """RAGAS 평가 활성화 시 ragas_evaluator 생성."""
        with patch("agents.router.ChromaVectorStore"), \
             patch("agents.router.RAGChain"), \
             patch("agents.router.StartupFundingAgent"), \
             patch("agents.router.FinanceTaxAgent"), \
             patch("agents.router.HRLaborAgent"), \
             patch("agents.router.EvaluatorAgent"), \
             patch("agents.router.get_settings") as mock_settings:

            mock_settings.return_value = Mock(enable_ragas_evaluation=True)
            router = MainRouter()

            with patch("evaluation.ragas_evaluator.RagasEvaluator") as mock_ragas:
                mock_evaluator = Mock()
                mock_ragas.return_value = mock_evaluator

                evaluator = router.ragas_evaluator

                assert evaluator == mock_evaluator
                mock_ragas.assert_called_once()


class TestMainRouterEdgeCases:
    """MainRouter 엣지 케이스 테스트."""

    @pytest.fixture
    def mock_all_dependencies(self):
        """모든 의존성 모킹."""
        with patch("agents.router.ChromaVectorStore") as mock_store, \
             patch("agents.router.RAGChain") as mock_chain, \
             patch("agents.router.StartupFundingAgent") as mock_startup, \
             patch("agents.router.FinanceTaxAgent") as mock_finance, \
             patch("agents.router.HRLaborAgent") as mock_hr, \
             patch("agents.router.EvaluatorAgent") as mock_evaluator, \
             patch("agents.router.get_settings") as mock_settings:

            mock_settings.return_value = Mock(enable_ragas_evaluation=False)

            yield {
                "store": mock_store,
                "chain": mock_chain,
                "startup": mock_startup,
                "finance": mock_finance,
                "hr": mock_hr,
                "evaluator": mock_evaluator,
                "settings": mock_settings,
            }

    def test_should_continue_with_low_confidence_relevant(
        self, mock_all_dependencies
    ):
        """낮은 신뢰도여도 관련 질문이면 continue."""
        router = MainRouter()
        classification = DomainClassificationResult(
            domains=["hr_labor"],
            confidence=0.55,  # 낮은 신뢰도
            is_relevant=True,
            method="vector",
        )
        state: RouterState = {
            "query": "직원 관리",
            "user_context": None,
            "domains": ["hr_labor"],
            "classification_result": classification,
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

        result = router._should_continue_after_classify(state)

        assert result == "continue"

    def test_should_reject_with_high_confidence_irrelevant(
        self, mock_all_dependencies
    ):
        """높은 신뢰도로 비관련 판단 시 reject."""
        router = MainRouter()
        classification = DomainClassificationResult(
            domains=[],
            confidence=0.99,  # 높은 신뢰도
            is_relevant=False,
            method="vector",
        )
        state: RouterState = {
            "query": "날씨 알려줘",
            "user_context": None,
            "domains": [],
            "classification_result": classification,
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

        result = router._should_continue_after_classify(state)

        assert result == "reject"

    def test_settings_loaded_from_get_settings(self, mock_all_dependencies):
        """settings가 get_settings()로 로드되는지 확인."""
        router = MainRouter()

        mock_all_dependencies["settings"].assert_called()


class TestRagasEvaluationInEvaluateNode:
    """_aevaluate_node에서 RAGAS 평가 실행 여부 테스트."""

    def _make_state(self) -> "RouterState":
        from agents.router import RouterState
        from schemas.response import SourceDocument
        return {
            "query": "퇴직금 계산 방법은?",
            "user_context": None,
            "domains": ["hr_labor"],
            "classification_result": None,
            "sub_queries": [],
            "retrieval_results": {},
            "responses": {},
            "documents": [],
            "final_response": "퇴직금은 근로기준법에 따라 계산합니다.",
            "sources": [SourceDocument(content="근로기준법 제34조", title="근로기준법")],
            "actions": [],
            "evaluation": None,
            "ragas_metrics": None,
            "retry_count": 0,
            "timing_metrics": {"classify_time": 0.0},
        }

    @pytest.mark.asyncio
    async def test_ragas_metrics_none_when_disabled(self):
        """enable_ragas_evaluation=False일 때 ragas_metrics는 None이어야 한다."""
        with patch("agents.router.RAGChain"), \
             patch("agents.router.StartupFundingAgent"), \
             patch("agents.router.FinanceTaxAgent"), \
             patch("agents.router.HRLaborAgent"), \
             patch("agents.router.LegalAgent"), \
             patch("agents.router.EvaluatorAgent") as mock_eval_cls, \
             patch("agents.router.get_settings") as mock_get_settings:

            mock_settings = MagicMock()
            mock_settings.enable_llm_evaluation = False
            mock_settings.enable_ragas_evaluation = False
            mock_settings.evaluation_threshold = 70
            mock_settings.evaluator_context_length = 4000
            mock_settings.domain_evaluation_thresholds = {}
            mock_get_settings.return_value = mock_settings

            mock_evaluator = MagicMock()
            mock_eval_cls.return_value = mock_evaluator

            router = MainRouter()
            router._ragas_evaluator = None

            state = self._make_state()
            result = await router._aevaluate_node(state)

            assert result["ragas_metrics"] is None, \
                "ragas_evaluator가 None일 때 ragas_metrics는 None이어야 합니다."
