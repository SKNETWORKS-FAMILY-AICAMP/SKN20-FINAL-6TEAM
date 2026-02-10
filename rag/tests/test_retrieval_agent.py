"""RetrievalAgent 단위 테스트.

SearchStrategySelector, DocumentBudgetCalculator, DocumentMerger,
GraduatedRetryHandler의 규칙 기반 로직을 검증합니다.

로컬 환경에서 torch 등 무거운 의존성 없이 실행 가능하도록
sys.modules 모킹을 적용합니다.
"""

import math
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 무거운 의존성 모킹 (torch, sentence_transformers 등)
# import chain: agents.base → chains.rag_chain → vectorstores → embeddings → torch
# ---------------------------------------------------------------------------

_HEAVY_MODULES = [
    # PyTorch
    "torch", "torch.nn", "torch.cuda", "torch.nn.functional",
    # ML/NLP
    "sentence_transformers",
    # LangChain extras
    "langchain_huggingface", "langchain_groq", "langchain_chroma",
    # LangGraph
    "langgraph", "langgraph.graph", "langgraph.graph.state",
    # External APIs
    "tavily", "tavily.client",
    # Document generation
    "reportlab", "reportlab.lib", "reportlab.lib.pagesizes",
    "reportlab.platypus",
    "docx", "docx.shared", "docx.enum", "docx.enum.text",
    # Korean NLP
    "kiwipiepy",
    # Web/HTTP (may not be installed)
    "aiohttp", "beautifulsoup4", "bs4",
]

_mocked = {}
for _mod_name in _HEAVY_MODULES:
    if _mod_name not in sys.modules:
        mock_mod = MagicMock()
        mock_mod.__spec__ = None
        _mocked[_mod_name] = sys.modules[_mod_name] = mock_mod

# langgraph.graph needs END and StateGraph attributes
if "langgraph.graph" in _mocked:
    _mocked["langgraph.graph"].END = "END"
    _mocked["langgraph.graph"].StateGraph = MagicMock()

# ---------------------------------------------------------------------------
# 이제 안전하게 import
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from langchain_core.documents import Document  # noqa: E402

from agents.base import (  # noqa: E402
    RetrievalEvaluationResult,
    RetrievalResult,
    RetrievalStatus,
)
from agents.retrieval_agent import (  # noqa: E402
    ADJACENT_DOMAINS,
    DocumentBudget,
    DocumentBudgetCalculator,
    DocumentMerger,
    GraduatedRetryHandler,
    QueryCharacteristics,
    RetryLevel,
    SearchMode,
    SearchStrategySelector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(content: str, score: float = 0.5) -> Document:
    """테스트용 Document를 생성합니다."""
    return Document(page_content=content, metadata={"score": score})


def _make_eval(passed: bool) -> RetrievalEvaluationResult:
    """테스트용 RetrievalEvaluationResult를 생성합니다."""
    return RetrievalEvaluationResult(
        status=RetrievalStatus.SUCCESS if passed else RetrievalStatus.NEEDS_RETRY,
        doc_count=3,
        keyword_match_ratio=0.5,
        avg_similarity_score=0.6,
    )


def _make_result(
    docs: list[Document] | None = None,
    passed: bool = False,
    domain: str = "finance_tax",
    query: str = "테스트 쿼리",
) -> RetrievalResult:
    """테스트용 RetrievalResult를 생성합니다."""
    if docs is None:
        docs = [_make_doc("테스트 문서")]
    return RetrievalResult(
        documents=docs,
        scores=[d.metadata.get("score", 0.0) for d in docs],
        sources=[],
        evaluation=_make_eval(passed),
        used_multi_query=False,
        retrieve_time=0.1,
        domain=domain,
        query=query,
    )


# ===========================================================================
# SearchStrategySelector 테스트
# ===========================================================================


class TestSearchStrategySelector:
    """SearchStrategySelector.analyze() 테스트."""

    def setup_method(self) -> None:
        self.selector = SearchStrategySelector()

    # -- 법조문 인용 → EXACT_PLUS_VECTOR, K=5 --

    def test_legal_citation_je_jo(self) -> None:
        """'제X조' 패턴 → EXACT_PLUS_VECTOR."""
        result = self.selector.analyze("근로기준법 제60조 연차 규정", ["hr_labor"])
        assert result.has_legal_citation is True
        assert result.recommended_mode == SearchMode.EXACT_PLUS_VECTOR
        assert result.recommended_k == 5

    def test_legal_citation_bup_je(self) -> None:
        """'법 제X조' 패턴 → EXACT_PLUS_VECTOR."""
        result = self.selector.analyze("상법 제28조에 대해 알려주세요", ["law_common"])
        assert result.has_legal_citation is True
        assert result.recommended_mode == SearchMode.EXACT_PLUS_VECTOR

    def test_legal_citation_sihaengryeong(self) -> None:
        """'시행령' 패턴 → EXACT_PLUS_VECTOR."""
        result = self.selector.analyze("소득세법 시행령 관련 질문", ["finance_tax"])
        assert result.has_legal_citation is True
        assert result.recommended_mode == SearchMode.EXACT_PLUS_VECTOR

    # -- 짧은 사실형 (≤20자 + density≥0.3) → BM25_HEAVY, K=3 --

    def test_short_factual_query(self) -> None:
        """짧은 사실형 쿼리 → BM25_HEAVY, K=3."""
        result = self.selector.analyze("부가세 신고 기한", ["finance_tax"])
        assert result.is_factual is True
        assert result.recommended_mode == SearchMode.BM25_HEAVY
        assert result.recommended_k == 3

    def test_short_factual_startup(self) -> None:
        """짧은 창업 관련 쿼리 → BM25_HEAVY."""
        result = self.selector.analyze("사업자등록 방법", ["startup_funding"])
        assert result.is_factual is True
        assert result.recommended_mode == SearchMode.BM25_HEAVY

    # -- 긴 서술형 (≥50자 or ≥10단어) → VECTOR_HEAVY, K=7 --

    def test_complex_long_query(self) -> None:
        """긴 서술형 쿼리 → VECTOR_HEAVY, K=7."""
        query = "창업하면서 세무 처리도 해야 하고 근로계약서도 작성해야 하는데 어떤 순서로 진행하면 좋을까요?"
        result = self.selector.analyze(query, ["startup_funding", "hr_labor"])
        assert result.is_complex is True
        assert result.recommended_mode == SearchMode.VECTOR_HEAVY
        assert result.recommended_k == 7

    def test_complex_many_words(self) -> None:
        """단어 수가 10개 이상인 쿼리 → VECTOR_HEAVY."""
        query = "스타트업 대표가 알아야 할 세금 종류와 신고 기한 그리고 절세 방법"
        result = self.selector.analyze(query, ["finance_tax"])
        assert result.is_complex is True
        assert result.recommended_mode == SearchMode.VECTOR_HEAVY

    # -- 모호/광범위 (≥15자 + density<0.1) → MMR_DIVERSE, K=7 --

    def test_vague_query(self) -> None:
        """모호한 쿼리 → MMR_DIVERSE, K=7."""
        query = "사업 시작하려면 뭘 해야 하나요 알려주세요"
        result = self.selector.analyze(query, ["startup_funding"])
        assert result.is_vague is True
        assert result.recommended_mode == SearchMode.MMR_DIVERSE
        assert result.recommended_k == 7

    # -- 일반 질문 → HYBRID, K=5 --

    def test_general_query(self) -> None:
        """일반 질문 → HYBRID, K=5."""
        query = "법인세 신고 절차 안내해주세요"
        result = self.selector.analyze(query, ["finance_tax"])
        assert result.recommended_mode == SearchMode.HYBRID
        assert result.recommended_k == 5

    # -- 기본 속성 검증 --

    def test_query_length_and_word_count(self) -> None:
        """쿼리 길이 및 단어 수가 정확히 계산되는지 검증."""
        query = "부가세 세금"
        result = self.selector.analyze(query, ["finance_tax"])
        assert result.length == len(query)
        assert result.word_count == 2

    def test_has_numbers_detected(self) -> None:
        """숫자 포함 여부 감지."""
        result = self.selector.analyze("2024년 법인세 세율", ["finance_tax"])
        assert result.has_numbers is True

    def test_keyword_density_calculation(self) -> None:
        """키워드 밀도가 올바르게 계산되는지 검증."""
        result = self.selector.analyze("세금 납부", ["finance_tax"])
        assert result.keyword_density == pytest.approx(0.5)

    def test_legal_citation_priority_over_factual(self) -> None:
        """법조문 인용이 사실형보다 우선순위 높음."""
        result = self.selector.analyze("제3조", ["law_common"])
        assert result.has_legal_citation is True
        assert result.recommended_mode == SearchMode.EXACT_PLUS_VECTOR


# ===========================================================================
# DocumentBudgetCalculator 테스트
# ===========================================================================


class TestDocumentBudgetCalculator:
    """DocumentBudgetCalculator.calculate() 테스트."""

    def setup_method(self) -> None:
        self.calculator = DocumentBudgetCalculator()
        self.default_chars = QueryCharacteristics(
            length=30,
            word_count=5,
            has_legal_citation=False,
            has_numbers=False,
            is_factual=False,
            is_complex=False,
            is_vague=False,
            keyword_density=0.3,
            recommended_mode=SearchMode.HYBRID,
            recommended_k=5,
        )

    @patch("agents.retrieval_agent.get_settings")
    def test_single_domain_uses_recommended_k(self, mock_settings) -> None:
        """단일 도메인은 recommended_k를 사용."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["finance_tax"],
            query_chars=self.default_chars,
            max_total=12,
        )

        assert len(budgets) == 1
        assert budgets["finance_tax"].allocated_k == 5
        assert budgets["finance_tax"].is_primary is True
        assert budgets["finance_tax"].priority == 1

    @patch("agents.retrieval_agent.get_settings")
    def test_single_domain_capped_by_max_total(self, mock_settings) -> None:
        """단일 도메인에서 K가 max_total로 제한됨."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        chars = QueryCharacteristics(
            length=100, word_count=15,
            has_legal_citation=False, has_numbers=False,
            is_factual=False, is_complex=True, is_vague=False,
            keyword_density=0.2,
            recommended_mode=SearchMode.VECTOR_HEAVY,
            recommended_k=7,
        )
        budgets = self.calculator.calculate(
            domains=["hr_labor"],
            query_chars=chars,
            max_total=5,
        )

        assert budgets["hr_labor"].allocated_k == 5

    @patch("agents.retrieval_agent.get_settings")
    def test_dynamic_k_disabled_uses_retrieval_k(self, mock_settings) -> None:
        """enable_dynamic_k=False이면 settings.retrieval_k 사용."""
        settings = MagicMock()
        settings.enable_dynamic_k = False
        settings.retrieval_k = 4
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["finance_tax"],
            query_chars=self.default_chars,
            max_total=12,
        )

        assert budgets["finance_tax"].allocated_k == 4

    @patch("agents.retrieval_agent.get_settings")
    def test_dual_domain_budget_split(self, mock_settings) -> None:
        """2개 도메인: primary_ratio에 따라 예산 분배."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["finance_tax", "hr_labor"],
            query_chars=self.default_chars,
            max_total=10,
            primary_ratio=0.6,
        )

        assert len(budgets) == 2
        assert budgets["finance_tax"].allocated_k == math.ceil(10 * 0.6)
        assert budgets["hr_labor"].allocated_k == 10 - math.ceil(10 * 0.6)
        assert budgets["finance_tax"].is_primary is True
        assert budgets["hr_labor"].is_primary is False

    @patch("agents.retrieval_agent.get_settings")
    def test_dual_domain_priority_order(self, mock_settings) -> None:
        """2개 도메인에서 primary=1, secondary=2 우선순위."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["startup_funding", "finance_tax"],
            query_chars=self.default_chars,
            max_total=10,
        )

        assert budgets["startup_funding"].priority == 1
        assert budgets["finance_tax"].priority == 2

    @patch("agents.retrieval_agent.get_settings")
    def test_triple_domain_budget_split(self, mock_settings) -> None:
        """3개 도메인: primary=50%, 나머지 균등 분배."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["startup_funding", "finance_tax", "hr_labor"],
            query_chars=self.default_chars,
            max_total=10,
        )

        assert len(budgets) == 3
        primary_k = math.ceil(10 * 0.5)
        remaining = 10 - primary_k
        per_secondary = max(1, remaining // 2)

        assert budgets["startup_funding"].allocated_k == primary_k
        assert budgets["finance_tax"].allocated_k == per_secondary
        assert budgets["hr_labor"].allocated_k == per_secondary
        assert budgets["startup_funding"].is_primary is True

    @patch("agents.retrieval_agent.get_settings")
    def test_triple_domain_priorities(self, mock_settings) -> None:
        """3개 도메인에서 우선순위가 1, 2, 3 순서."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        budgets = self.calculator.calculate(
            domains=["startup_funding", "finance_tax", "hr_labor"],
            query_chars=self.default_chars,
            max_total=10,
        )

        assert budgets["startup_funding"].priority == 1
        assert budgets["finance_tax"].priority == 2
        assert budgets["hr_labor"].priority == 3


# ===========================================================================
# DocumentMerger 테스트
# ===========================================================================


class TestDocumentMerger:
    """DocumentMerger.merge_and_prioritize() 테스트."""

    def setup_method(self) -> None:
        self.merger = DocumentMerger()

    def test_single_domain_passthrough(self) -> None:
        """단일 도메인은 문서를 그대로 반환."""
        docs = [_make_doc("문서 A", 0.9), _make_doc("문서 B", 0.7)]
        result = _make_result(docs, passed=True, domain="finance_tax")
        budgets = {"finance_tax": DocumentBudget("finance_tax", 5, True, 1)}

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result}, budgets, max_total=10
        )

        assert len(merged) == 2

    def test_deduplication_by_content_hash(self) -> None:
        """동일 내용 문서가 중복 제거됨."""
        doc1 = _make_doc("동일한 문서 내용", 0.9)
        doc2 = _make_doc("동일한 문서 내용", 0.8)
        doc3 = _make_doc("다른 문서 내용", 0.7)

        result_a = _make_result([doc1, doc3], passed=True, domain="finance_tax")
        result_b = _make_result([doc2], passed=True, domain="hr_labor")

        budgets = {
            "finance_tax": DocumentBudget("finance_tax", 5, True, 1),
            "hr_labor": DocumentBudget("hr_labor", 5, False, 2),
        }

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result_a, "hr_labor": result_b},
            budgets,
            max_total=10,
        )

        assert len(merged) == 2

    def test_primary_domain_docs_first(self) -> None:
        """primary 도메인 문서가 먼저 배치됨."""
        doc_primary = _make_doc("주 도메인 문서", 0.8)
        doc_secondary = _make_doc("보조 도메인 문서", 0.9)

        result_a = _make_result([doc_primary], passed=True, domain="finance_tax")
        result_b = _make_result([doc_secondary], passed=True, domain="hr_labor")

        budgets = {
            "finance_tax": DocumentBudget("finance_tax", 5, True, 1),
            "hr_labor": DocumentBudget("hr_labor", 5, False, 2),
        }

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result_a, "hr_labor": result_b},
            budgets,
            max_total=10,
        )

        assert merged[0].page_content == "주 도메인 문서"

    def test_budget_enforcement_per_domain(self) -> None:
        """도메인별 allocated_k로 문서가 잘림."""
        docs = [_make_doc(f"문서 {i}", 0.9 - i * 0.1) for i in range(5)]
        result = _make_result(docs, passed=True, domain="finance_tax")

        budgets = {"finance_tax": DocumentBudget("finance_tax", 3, True, 1)}

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result}, budgets, max_total=10
        )

        assert len(merged) == 3

    def test_total_budget_enforcement(self) -> None:
        """전체 max_total로 문서가 잘림."""
        docs_a = [_make_doc(f"A-{i}", 0.9 - i * 0.1) for i in range(5)]
        docs_b = [_make_doc(f"B-{i}", 0.8 - i * 0.1) for i in range(5)]

        result_a = _make_result(docs_a, passed=True, domain="finance_tax")
        result_b = _make_result(docs_b, passed=True, domain="hr_labor")

        budgets = {
            "finance_tax": DocumentBudget("finance_tax", 5, True, 1),
            "hr_labor": DocumentBudget("hr_labor", 5, False, 2),
        }

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result_a, "hr_labor": result_b},
            budgets,
            max_total=7,
        )

        assert len(merged) == 7

    def test_score_descending_within_domain(self) -> None:
        """같은 도메인 내 문서가 점수 내림차순으로 정렬됨."""
        docs = [
            _make_doc("낮은 점수", 0.3),
            _make_doc("높은 점수", 0.9),
            _make_doc("중간 점수", 0.6),
        ]
        result = _make_result(docs, passed=True, domain="finance_tax")
        budgets = {"finance_tax": DocumentBudget("finance_tax", 3, True, 1)}

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result}, budgets, max_total=10
        )

        scores = [d.metadata["score"] for d in merged]
        assert scores == sorted(scores, reverse=True)

    def test_empty_results(self) -> None:
        """빈 검색 결과 처리."""
        result = _make_result([], passed=False, domain="finance_tax")
        budgets = {"finance_tax": DocumentBudget("finance_tax", 5, True, 1)}

        merged = self.merger.merge_and_prioritize(
            {"finance_tax": result}, budgets, max_total=10
        )

        assert len(merged) == 0


# ===========================================================================
# GraduatedRetryHandler 테스트
# ===========================================================================


class TestGraduatedRetryHandler:
    """GraduatedRetryHandler.retry() 테스트."""

    def setup_method(self) -> None:
        self.mock_agents = {
            "finance_tax": MagicMock(),
            "hr_labor": MagicMock(),
            "law_common": MagicMock(),
        }
        self.mock_rag_chain = MagicMock()
        self.mock_rag_chain.documents_to_sources.return_value = []

    @patch("agents.retrieval_agent.get_settings")
    def test_already_passed_returns_immediately(self, mock_settings) -> None:
        """이미 통과된 결과는 재시도 없이 즉시 반환."""
        settings = MagicMock()
        settings.enable_multi_query = True
        mock_settings.return_value = settings

        handler = GraduatedRetryHandler(self.mock_agents, self.mock_rag_chain)
        result = _make_result(passed=True)
        budget = DocumentBudget("finance_tax", 5, True, 1)

        output = handler.retry("테스트", "finance_tax", result, budget)

        assert output is result
        self.mock_rag_chain.retrieve.assert_not_called()

    @patch("agents.retrieval_agent.get_settings")
    def test_level1_relax_params_retrieves_with_increased_k(self, mock_settings) -> None:
        """Level 1: K를 +3 증가하여 재검색."""
        settings = MagicMock()
        settings.enable_multi_query = False
        mock_settings.return_value = settings

        new_docs = [_make_doc(f"재검색 문서 {i}", 0.8) for i in range(6)]
        self.mock_rag_chain.retrieve.return_value = new_docs

        handler = GraduatedRetryHandler(self.mock_agents, self.mock_rag_chain)
        result = _make_result(passed=False)
        budget = DocumentBudget("finance_tax", 5, True, 1)

        handler.retry(
            "테스트 쿼리",
            "finance_tax",
            result,
            budget,
            max_level=RetryLevel.RELAX_PARAMS,
        )

        self.mock_rag_chain.retrieve.assert_called_once()
        call_kwargs = self.mock_rag_chain.retrieve.call_args
        assert call_kwargs.kwargs.get("k") == 8

    @patch("agents.retrieval_agent.get_settings")
    def test_level2_multi_query_uses_multi_retriever(self, mock_settings) -> None:
        """Level 2: MultiQueryRetriever 사용."""
        settings = MagicMock()
        settings.enable_multi_query = True
        mock_settings.return_value = settings

        self.mock_rag_chain.retrieve.return_value = []

        handler = GraduatedRetryHandler(self.mock_agents, self.mock_rag_chain)
        result = _make_result(passed=False)
        budget = DocumentBudget("finance_tax", 5, True, 1)

        with patch("utils.query.MultiQueryRetriever") as mock_mq_cls:
            mock_mq = MagicMock()
            mock_mq.retrieve.return_value = (
                [_make_doc("MQ 결과", 0.8)],
                "재작성된 쿼리",
            )
            mock_mq_cls.return_value = mock_mq

            handler.retry(
                "테스트 쿼리",
                "finance_tax",
                result,
                budget,
                max_level=RetryLevel.MULTI_QUERY,
            )

            mock_mq.retrieve.assert_called_once()

    @patch("agents.retrieval_agent.get_settings")
    def test_level3_cross_domain_searches_adjacent(self, mock_settings) -> None:
        """Level 3: 인접 도메인을 검색."""
        settings = MagicMock()
        settings.enable_multi_query = False
        mock_settings.return_value = settings

        self.mock_rag_chain.retrieve.side_effect = [
            [],  # Level 1 재검색 결과
            [_make_doc("인접 도메인 결과", 0.7)],  # Level 3 인접 도메인 결과
        ]

        handler = GraduatedRetryHandler(self.mock_agents, self.mock_rag_chain)
        result = _make_result(
            docs=[_make_doc("원본 문서", 0.5)],
            passed=False,
            domain="hr_labor",
        )
        budget = DocumentBudget("hr_labor", 5, True, 1)

        output = handler.retry(
            "근로 관련 질문",
            "hr_labor",
            result,
            budget,
            max_level=RetryLevel.CROSS_DOMAIN,
        )

        assert "law_common" in ADJACENT_DOMAINS["hr_labor"]
        assert len(output.documents) >= 1

    @patch("agents.retrieval_agent.get_settings")
    def test_max_level_none_returns_original(self, mock_settings) -> None:
        """max_level=NONE이면 재시도 없이 원본 반환."""
        settings = MagicMock()
        settings.enable_multi_query = True
        mock_settings.return_value = settings

        handler = GraduatedRetryHandler(self.mock_agents, self.mock_rag_chain)
        result = _make_result(passed=False)
        budget = DocumentBudget("finance_tax", 5, True, 1)

        output = handler.retry(
            "테스트",
            "finance_tax",
            result,
            budget,
            max_level=RetryLevel.NONE,
        )

        assert output is result
        self.mock_rag_chain.retrieve.assert_not_called()


# ===========================================================================
# ADJACENT_DOMAINS 테스트
# ===========================================================================


class TestAdjacentDomains:
    """인접 도메인 매핑 테스트."""

    def test_startup_funding_adjacent(self) -> None:
        assert ADJACENT_DOMAINS["startup_funding"] == ["finance_tax"]

    def test_finance_tax_adjacent(self) -> None:
        assert ADJACENT_DOMAINS["finance_tax"] == ["startup_funding", "law_common"]

    def test_hr_labor_adjacent(self) -> None:
        assert ADJACENT_DOMAINS["hr_labor"] == ["law_common"]

    def test_law_common_adjacent(self) -> None:
        assert ADJACENT_DOMAINS["law_common"] == ["hr_labor", "finance_tax"]


# ===========================================================================
# QueryCharacteristics / DocumentBudget dataclass 테스트
# ===========================================================================


class TestDataclasses:
    """dataclass 기본 동작 검증."""

    def test_query_characteristics_creation(self) -> None:
        qc = QueryCharacteristics(
            length=30, word_count=5,
            has_legal_citation=True, has_numbers=False,
            is_factual=False, is_complex=False, is_vague=False,
            keyword_density=0.4,
            recommended_mode=SearchMode.EXACT_PLUS_VECTOR,
            recommended_k=5,
        )
        assert qc.has_legal_citation is True
        assert qc.recommended_mode == SearchMode.EXACT_PLUS_VECTOR

    def test_document_budget_creation(self) -> None:
        budget = DocumentBudget(
            domain="finance_tax",
            allocated_k=7,
            is_primary=True,
            priority=1,
        )
        assert budget.domain == "finance_tax"
        assert budget.allocated_k == 7

    def test_retry_level_ordering(self) -> None:
        """RetryLevel 값이 올바른 순서."""
        assert RetryLevel.NONE < RetryLevel.RELAX_PARAMS
        assert RetryLevel.RELAX_PARAMS < RetryLevel.MULTI_QUERY
        assert RetryLevel.MULTI_QUERY < RetryLevel.CROSS_DOMAIN
        assert RetryLevel.CROSS_DOMAIN < RetryLevel.PARTIAL_ANSWER

    def test_search_mode_values(self) -> None:
        """SearchMode 문자열 값 확인."""
        assert SearchMode.HYBRID.value == "hybrid"
        assert SearchMode.VECTOR_HEAVY.value == "vector"
        assert SearchMode.BM25_HEAVY.value == "bm25"
        assert SearchMode.MMR_DIVERSE.value == "mmr"
        assert SearchMode.EXACT_PLUS_VECTOR.value == "exact"


# ===========================================================================
# 엣지 케이스 테스트
# ===========================================================================


class TestEdgeCases:
    """엣지 케이스 검증."""

    def test_empty_query_strategy(self) -> None:
        """빈 쿼리에 대한 전략 선택."""
        selector = SearchStrategySelector()
        result = selector.analyze("", [])
        assert result.length == 0
        assert result.word_count == 0
        assert result.recommended_mode == SearchMode.HYBRID

    @patch("agents.retrieval_agent.get_settings")
    def test_single_domain_list_budget(self, mock_settings) -> None:
        """도메인 리스트가 1개일 때 budget 계산."""
        settings = MagicMock()
        settings.enable_dynamic_k = True
        settings.retrieval_k = 3
        mock_settings.return_value = settings

        calculator = DocumentBudgetCalculator()
        chars = QueryCharacteristics(
            length=10, word_count=2,
            has_legal_citation=False, has_numbers=False,
            is_factual=True, is_complex=False, is_vague=False,
            keyword_density=0.5,
            recommended_mode=SearchMode.BM25_HEAVY,
            recommended_k=3,
        )

        budgets = calculator.calculate(["hr_labor"], chars, max_total=12)
        assert len(budgets) == 1
        assert budgets["hr_labor"].allocated_k == 3

    def test_merger_handles_missing_budget(self) -> None:
        """budgets에 없는 도메인 결과도 처리."""
        merger = DocumentMerger()
        docs = [_make_doc("문서", 0.8)]
        result = _make_result(docs, passed=True, domain="unknown_domain")

        budgets = {
            "finance_tax": DocumentBudget("finance_tax", 5, True, 1),
        }

        merged = merger.merge_and_prioritize(
            {
                "unknown_domain": result,
                "finance_tax": _make_result([], passed=True, domain="finance_tax"),
            },
            budgets,
            max_total=10,
        )

        assert len(merged) >= 1
