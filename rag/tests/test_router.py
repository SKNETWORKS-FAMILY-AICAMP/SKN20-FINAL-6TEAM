"""MainRouter ?⑥쐞 ?뚯뒪??"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Any
from types import SimpleNamespace

import pytest

from agents.router import MainRouter, RouterState
from utils.domain_classifier import DomainClassificationResult


def _make_mock_query_rewriter(return_original: bool = True):
    """query_rewriter mock???앹꽦?⑸땲??

    Args:
        return_original: True硫??먮낯 荑쇰━ 諛섑솚, False硫??ъ옉??

    Returns:
        mock query_rewriter
    """
    mock_rewriter = MagicMock()
    if return_original:
        mock_rewriter.arewrite = AsyncMock(side_effect=lambda q, h: (q, False))
        mock_rewriter.arewrite_with_meta = AsyncMock(
            side_effect=lambda q, h: SimpleNamespace(
                query=q, rewritten=False, reason="skip_no_history", elapsed=0.0
            )
        )
    else:
        mock_rewriter.arewrite = AsyncMock(return_value=("?ъ옉?깅맂 吏덈Ц", True))
        mock_rewriter.arewrite_with_meta = AsyncMock(
            return_value=SimpleNamespace(
                query="?ъ옉?깅맂 吏덈Ц", rewritten=True, reason="rewritten", elapsed=0.01
            )
        )
    return mock_rewriter


class TestRouterState:
    """RouterState TypedDict 援ъ“ 寃利?"""

    def test_router_state_has_required_fields(self):
        """RouterState媛 ?꾩닔 ?꾨뱶瑜??ы븿?섎뒗吏 寃利?"""
        state: RouterState = {
            "query": "?ъ뾽?먮벑濡??덉감??",
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
    """MainRouter 珥덇린???뚯뒪??"""

    @pytest.fixture
    def mock_vector_store(self):
        """ChromaVectorStore 紐⑦궧."""
        mock_store = Mock()
        mock_store.get_retriever.return_value = Mock()
        return mock_store

    @pytest.fixture
    def mock_dependencies(self):
        """紐⑤뱺 ?섏〈??紐⑦궧."""
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
        """踰≫꽣?ㅽ넗??二쇱엯 ??珥덇린???뺤씤."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.vector_store == mock_vector_store
        mock_dependencies["chain"].assert_called_once_with(vector_store=mock_vector_store)

    def test_mainrouter_init_creates_default_vector_store(self, mock_dependencies):
        """踰≫꽣?ㅽ넗???놁씠 珥덇린????湲곕낯 ?앹꽦."""
        with patch("agents.router.ChromaVectorStore") as mock_chroma:
            mock_chroma.return_value = Mock()

            router = MainRouter()

            mock_chroma.assert_called_once()
            assert router.vector_store == mock_chroma.return_value

    def test_mainrouter_init_creates_all_agents(
        self, mock_vector_store, mock_dependencies
    ):
        """4媛??꾨찓???먯씠?꾪듃 ?앹꽦 ?뺤씤."""
        router = MainRouter(vector_store=mock_vector_store)

        assert "startup_funding" in router.agents
        assert "finance_tax" in router.agents
        assert "hr_labor" in router.agents
        assert "law_common" in router.agents
        assert len(router.agents) == 4

        # 媛??먯씠?꾪듃媛 媛숈? RAG 泥댁씤??怨듭쑀?섎뒗吏 ?뺤씤
        rag_chain_instance = mock_dependencies["chain"].return_value
        mock_dependencies["startup"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["finance"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["hr"].assert_called_once_with(rag_chain=rag_chain_instance)
        mock_dependencies["legal"].assert_called_once_with(rag_chain=rag_chain_instance)

    def test_mainrouter_init_creates_evaluator(
        self, mock_vector_store, mock_dependencies
    ):
        """EvaluatorAgent ?앹꽦 ?뺤씤."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.evaluator is not None
        mock_dependencies["evaluator"].assert_called_once()

    def test_mainrouter_init_builds_async_graph(
        self, mock_vector_store, mock_dependencies
    ):
        """鍮꾨룞湲?洹몃옒??鍮뚮뱶 ?뺤씤."""
        router = MainRouter(vector_store=mock_vector_store)

        assert router.async_graph is not None


class TestShouldContinueAfterClassify:
    """_should_continue_after_classify 硫붿꽌???뚯뒪??"""

    @pytest.fixture
    def router_with_mocks(self):
        """紐⑦궧??MainRouter ?몄뒪?댁뒪."""
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
        """遺꾨쪟 寃곌낵媛 ?놁쑝硫?continue 諛섑솚."""
        state: RouterState = {
            "query": "?뚯뒪??吏덈Ц",
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
        """愿??吏덈Ц?대㈃ continue 諛섑솚."""
        classification = DomainClassificationResult(
            domains=["finance_tax"],
            confidence=0.9,
            is_relevant=True,
            method="keyword",
        )
        state: RouterState = {
            "query": "遺媛???좉퀬??",
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
        """鍮꾧???吏덈Ц?대㈃ reject 諛섑솚."""
        classification = DomainClassificationResult(
            domains=[],
            confidence=0.95,
            is_relevant=False,
            method="vector",
        )
        state: RouterState = {
            "query": "?ㅻ뒛 ?좎뵪??",
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
    """_aclassify_node 硫붿꽌???뚯뒪??"""

    @pytest.fixture
    def router_with_mocks(self):
        """紐⑦궧??MainRouter ?몄뒪?댁뒪."""
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
        """遺꾨쪟 ?몃뱶媛 classification_result ?ㅼ젙."""
        mock_classification = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.95,
            is_relevant=True,
            method="keyword",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier
        router_with_mocks._query_rewriter = _make_mock_query_rewriter()

        state: RouterState = {
            "query": "?ъ뾽?먮벑濡??덉감??",
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
        """遺꾨쪟 ?몃뱶媛 ?꾨찓??由ъ뒪???ㅼ젙."""
        mock_classification = DomainClassificationResult(
            domains=["finance_tax", "hr_labor"],
            confidence=0.88,
            is_relevant=True,
            method="vector",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier
        router_with_mocks._query_rewriter = _make_mock_query_rewriter()

        state: RouterState = {
            "query": "吏곸썝 湲됱뿬??????멸툑 泥섎━??",
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
        """鍮꾧???吏덈Ц ??嫄곕? ?묐떟 ?ㅼ젙."""
        mock_classification = DomainClassificationResult(
            domains=[],
            confidence=0.4,
            is_relevant=False,
            method="vector",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier
        router_with_mocks._query_rewriter = _make_mock_query_rewriter()

        state: RouterState = {
            "query": "?ㅻ뒛 ?좎뵪??",
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
        """遺꾨쪟 ?몃뱶媛 ??대컢 硫뷀듃由?湲곕줉."""
        mock_classification = DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.9,
            is_relevant=True,
            method="keyword",
        )

        mock_classifier = Mock()
        mock_classifier.classify.return_value = mock_classification
        router_with_mocks._domain_classifier = mock_classifier
        router_with_mocks._query_rewriter = _make_mock_query_rewriter()

        state: RouterState = {
            "query": "李쎌뾽 ?덉감",
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
    """吏??濡쒕뵫 ?꾨줈?쇳떚 ?뚯뒪??"""

    @pytest.fixture
    def router_with_mocks(self):
        """紐⑦궧??MainRouter ?몄뒪?댁뒪."""
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
        """domain_classifier 吏??濡쒕뵫 ?뺤씤."""
        # 珥덇린???쒖젏?먮뒗 None
        assert router_with_mocks._domain_classifier is None

        # domain_classifier ?꾨줈?쇳떚 ?묎렐
        with patch("agents.router.get_domain_classifier") as mock_get:
            mock_classifier = Mock()
            mock_get.return_value = mock_classifier

            classifier = router_with_mocks.domain_classifier

            # ?묎렐 ??罹먯떛
            assert router_with_mocks._domain_classifier is not None
            assert classifier == mock_classifier
            mock_get.assert_called_once()

    def test_lazy_loading_question_decomposer(self, router_with_mocks):
        """question_decomposer 吏??濡쒕뵫 ?뺤씤."""
        assert router_with_mocks._question_decomposer is None

        with patch("agents.router.get_question_decomposer") as mock_get:
            mock_decomposer = Mock()
            mock_get.return_value = mock_decomposer

            decomposer = router_with_mocks.question_decomposer

            assert router_with_mocks._question_decomposer is not None
            assert decomposer == mock_decomposer
            mock_get.assert_called_once()

    def test_lazy_loading_query_rewriter(self, router_with_mocks):
        """query_rewriter 吏??濡쒕뵫 ?뺤씤."""
        assert router_with_mocks._query_rewriter is None

        with patch("agents.router.get_query_rewriter") as mock_get:
            mock_rewriter = Mock()
            mock_get.return_value = mock_rewriter

            rewriter = router_with_mocks.query_rewriter

            assert router_with_mocks._query_rewriter is not None
            assert rewriter == mock_rewriter
            mock_get.assert_called_once()

    def test_lazy_loading_ragas_evaluator_when_disabled(self, router_with_mocks):
        """RAGAS ?됯? 鍮꾪솢?깊솕 ??ragas_evaluator??None."""
        assert router_with_mocks._ragas_evaluator is None
        # settings.enable_ragas_evaluation??False?대?濡?
        evaluator = router_with_mocks.ragas_evaluator
        assert evaluator is None

    def test_lazy_loading_ragas_evaluator_when_enabled(self):
        """RAGAS ?됯? ?쒖꽦????ragas_evaluator ?앹꽦."""
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
    """MainRouter ?ｌ? 耳?댁뒪 ?뚯뒪??"""

    @pytest.fixture
    def mock_all_dependencies(self):
        """紐⑤뱺 ?섏〈??紐⑦궧."""
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
        """??? ?좊ː?꾩뿬??愿??吏덈Ц?대㈃ continue."""
        router = MainRouter()
        classification = DomainClassificationResult(
            domains=["hr_labor"],
            confidence=0.55,  # ??? ?좊ː??
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
        """?믪? ?좊ː?꾨줈 鍮꾧????먮떒 ??reject."""
        router = MainRouter()
        classification = DomainClassificationResult(
            domains=[],
            confidence=0.99,  # ?믪? ?좊ː??
            is_relevant=False,
            method="vector",
        )
        state: RouterState = {
            "query": "오늘 날씨 알려줘",
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
        """settings媛 get_settings()濡?濡쒕뱶?섎뒗吏 ?뺤씤."""
        router = MainRouter()

        mock_all_dependencies["settings"].assert_called()


class TestRagasEvaluationInEvaluateNode:
    """_aevaluate_node?먯꽌 RAGAS ?됯? ?ㅽ뻾 ?щ? ?뚯뒪??"""

    def _make_state(self) -> "RouterState":
        from agents.router import RouterState
        from schemas.response import SourceDocument
        return {
            "query": "?댁쭅湲?怨꾩궛 諛⑸쾿??",
            "user_context": None,
            "domains": ["hr_labor"],
            "classification_result": None,
            "sub_queries": [],
            "retrieval_results": {},
            "responses": {},
            "documents": [],
            "final_response": "퇴직금은 근로기준법에 따라 계산합니다.",
            "sources": [SourceDocument(content="근로기준법 제4조", title="근로기준법")],
            "actions": [],
            "evaluation": None,
            "ragas_metrics": None,
            "retry_count": 0,
            "timing_metrics": {"classify_time": 0.0},
        }

    @pytest.mark.asyncio
    async def test_ragas_metrics_none_when_disabled(self):
        """enable_ragas_evaluation=False????ragas_metrics??None?댁뼱???쒕떎."""
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
                "ragas_evaluator媛 None????ragas_metrics??None?댁뼱???⑸땲??"
