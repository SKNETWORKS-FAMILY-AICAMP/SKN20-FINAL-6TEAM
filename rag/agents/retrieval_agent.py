"""검색 전략 에이전트 모듈.

쿼리 특성 분석 → 검색 전략 결정 → 도메인별 검색 → 평가 → 재시도 → 문서 병합
파이프라인의 3번 검색(retrieve) 파트를 전담합니다.

핵심 원칙: LLM 호출 없이 규칙 기반으로 전략 결정 (비용 0, 지연 0)
"""

import asyncio
import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document

from agents.base import RetrievalResult, RetrievalStatus, RetrievalEvaluationResult
from utils.config import get_settings
from utils.legal_supplement import LEGAL_SUPPLEMENT_KEYWORDS, needs_legal_supplement

if TYPE_CHECKING:
    from agents.base import BaseAgent
    from chains.rag_chain import RAGChain
    from utils.query import MultiQueryRetriever
    from utils.question_decomposer import SubQuery
    from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator
    from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SearchMode(str, Enum):
    """검색 모드."""

    HYBRID = "hybrid"  # BM25 + Vector + RRF (기본)
    VECTOR_HEAVY = "vector"  # 벡터 중심 검색
    BM25_HEAVY = "bm25"  # 키워드(BM25) 중심 검색
    MMR_DIVERSE = "mmr"  # MMR로 다양성 극대화
    EXACT_PLUS_VECTOR = "exact"  # 법조문 인용 등 정확 매칭 우선


class RetryLevel(int, Enum):
    """재시도 단계."""

    NONE = 0  # 재시도 안함 (성공)
    RELAX_PARAMS = 1  # 평가 기준 완화 + K 증가
    MULTI_QUERY = 2  # 기본 Multi-Query 검색 강화
    CROSS_DOMAIN = 3  # 인접 도메인 검색
    PARTIAL_ANSWER = 4  # 부분 답변 허용 (포기)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QueryCharacteristics:
    """쿼리 분석 결과."""

    length: int
    word_count: int
    has_legal_citation: bool
    has_numbers: bool
    is_factual: bool
    is_complex: bool
    is_vague: bool
    keyword_density: float
    recommended_mode: SearchMode
    recommended_k: int


@dataclass
class DocumentBudget:
    """도메인별 문서 할당량."""

    domain: str
    allocated_k: int
    is_primary: bool
    priority: int  # 1=최고


@dataclass
class RetryContext:
    """재시도 상태 추적."""

    level: RetryLevel = RetryLevel.NONE
    attempts: int = 0
    relaxed_keyword_threshold: float = 0.0
    relaxed_similarity_threshold: float = 0.0
    extra_k: int = 0
    cross_domains_tried: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 인접 도메인 매핑
# ---------------------------------------------------------------------------

ADJACENT_DOMAINS: dict[str, list[str]] = {
    "startup_funding": ["finance_tax"],
    "finance_tax": ["startup_funding", "law_common"],
    "hr_labor": ["law_common"],
    "law_common": ["hr_labor", "finance_tax"],
}

# ---------------------------------------------------------------------------
# 법조문 인용 패턴
# ---------------------------------------------------------------------------

_LEGAL_CITATION_PATTERN = re.compile(
    r"제\s*\d+\s*조|법\s+제\s*\d+|시행령|시행규칙|동법|같은\s*법"
)

# 도메인 키워드 (쿼리 밀도 계산용)
_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "startup_funding": {
        "창업", "사업자등록", "법인설립", "업종", "지원사업",
        "보조금", "정책자금", "공고", "마케팅", "광고", "홍보",
    },
    "finance_tax": {
        "세금", "부가세", "법인세", "회계", "세무", "재무",
        "결산", "세무조정", "소득세", "원천징수",
    },
    "hr_labor": {
        "근로", "채용", "해고", "급여", "퇴직금", "연차",
        "인사", "노무", "4대보험", "근로계약",
    },
    "law_common": {
        "법률", "법령", "조문", "판례", "규정", "상법", "민법",
        "소송", "분쟁", "손해배상", "특허", "상표", "저작권",
    },
}

# 모든 도메인 키워드 합집합
_ALL_DOMAIN_KEYWORDS: set[str] = set()
for _kw_set in _DOMAIN_KEYWORDS.values():
    _ALL_DOMAIN_KEYWORDS.update(_kw_set)


# ---------------------------------------------------------------------------
# SearchStrategySelector
# ---------------------------------------------------------------------------


class SearchStrategySelector:
    """쿼리를 분석하여 검색 전략을 추천합니다. LLM 호출 없음."""

    def analyze(self, query: str, domains: list[str]) -> QueryCharacteristics:
        """쿼리를 분석하여 검색 전략 추천.

        Args:
            query: 사용자 질문
            domains: 분류된 도메인 리스트

        Returns:
            QueryCharacteristics (모드, 추천 K 포함)
        """
        length = len(query)
        words = re.findall(r"[가-힣a-zA-Z0-9]+", query)
        word_count = len(words)

        has_legal_citation = bool(_LEGAL_CITATION_PATTERN.search(query))
        has_numbers = bool(re.search(r"\d+", query))

        # 키워드 밀도: 쿼리 단어 중 도메인 키워드 비율
        domain_kw_count = sum(1 for w in words if w in _ALL_DOMAIN_KEYWORDS)
        keyword_density = domain_kw_count / max(word_count, 1)

        # 쿼리 유형 판별
        is_factual = length <= 20 and keyword_density >= 0.3
        is_complex = length >= 50 or word_count >= 10
        is_vague = length >= 15 and keyword_density < 0.1

        # 전략 결정
        if has_legal_citation:
            mode = SearchMode.EXACT_PLUS_VECTOR
            k = 5
        elif is_factual:
            mode = SearchMode.BM25_HEAVY
            k = 3
        elif is_complex:
            mode = SearchMode.VECTOR_HEAVY
            k = 7
        elif is_vague:
            mode = SearchMode.MMR_DIVERSE
            k = 7
        else:
            mode = SearchMode.HYBRID
            k = 5

        return QueryCharacteristics(
            length=length,
            word_count=word_count,
            has_legal_citation=has_legal_citation,
            has_numbers=has_numbers,
            is_factual=is_factual,
            is_complex=is_complex,
            is_vague=is_vague,
            keyword_density=keyword_density,
            recommended_mode=mode,
            recommended_k=k,
        )


# ---------------------------------------------------------------------------
# DocumentBudgetCalculator
# ---------------------------------------------------------------------------


class DocumentBudgetCalculator:
    """도메인별 문서 할당량(K값)을 계산합니다."""

    def calculate(
        self,
        domains: list[str],
        query_chars: QueryCharacteristics,
        max_total: int = 12,
        primary_ratio: float = 0.6,
    ) -> dict[str, DocumentBudget]:
        """도메인별 문서 할당량 계산.

        Args:
            domains: 분류된 도메인 리스트
            query_chars: 쿼리 분석 결과
            max_total: 전체 문서 예산
            primary_ratio: 주 도메인 예산 비율

        Returns:
            도메인 → DocumentBudget 매핑
        """
        settings = get_settings()
        if settings.enable_dynamic_k:
            recommended_k = query_chars.recommended_k
        else:
            recommended_k = settings.retrieval_k

        # enable_fixed_doc_limit ON: 도메인당 최대 retrieval_k개 제한
        if settings.enable_fixed_doc_limit:
            logger.debug(
                "[DocumentBudget] bounded 방식 (retrieval_k=%d, recommended_k=%d)",
                settings.retrieval_k,
                recommended_k,
            )
            return self._calculate_bounded(domains, recommended_k, settings.retrieval_k)

        # enable_fixed_doc_limit OFF: 기존 Dynamic K 방식
        logger.debug(
            "[DocumentBudget] dynamic 방식 (max_total=%d, recommended_k=%d)",
            max_total,
            recommended_k,
        )
        return self._calculate_dynamic(
            domains, recommended_k, max_total, primary_ratio
        )

    def _calculate_bounded(
        self,
        domains: list[str],
        recommended_k: int,
        retrieval_k: int,
    ) -> dict[str, DocumentBudget]:
        """도메인당 retrieval_k를 상한으로 하는 문서 할당 방식.

        Args:
            domains: 분류된 도메인 리스트
            recommended_k: Dynamic K 추천값
            retrieval_k: 도메인당 상한값

        Returns:
            도메인 → DocumentBudget 매핑
        """
        k = min(recommended_k, retrieval_k)

        if len(domains) == 1:
            return {
                domains[0]: DocumentBudget(
                    domain=domains[0],
                    allocated_k=k,
                    is_primary=True,
                    priority=1,
                )
            }

        # 복합 도메인: 각 도메인에 균등 할당하되, 총량이 max_retrieval_docs를 초과하지 않도록 조정
        settings = get_settings()
        total = k * len(domains)
        if total > settings.max_retrieval_docs:
            k = max(2, settings.max_retrieval_docs // len(domains))

        budgets: dict[str, DocumentBudget] = {}
        for i, domain in enumerate(domains):
            budgets[domain] = DocumentBudget(
                domain=domain,
                allocated_k=k,
                is_primary=(i == 0),
                priority=i + 1,
            )
        return budgets

    def _calculate_dynamic(
        self,
        domains: list[str],
        recommended_k: int,
        max_total: int,
        primary_ratio: float,
    ) -> dict[str, DocumentBudget]:
        """기존 Dynamic K 방식 (max_total 비례 분배).

        Args:
            domains: 분류된 도메인 리스트
            recommended_k: Dynamic K 추천값
            max_total: 전체 문서 예산
            primary_ratio: 주 도메인 예산 비율

        Returns:
            도메인 → DocumentBudget 매핑
        """
        if len(domains) == 1:
            k = min(recommended_k, max_total)
            return {
                domains[0]: DocumentBudget(
                    domain=domains[0],
                    allocated_k=k,
                    is_primary=True,
                    priority=1,
                )
            }

        # 복합 도메인
        budgets: dict[str, DocumentBudget] = {}
        primary = domains[0]

        if len(domains) == 2:
            primary_k = math.ceil(max_total * primary_ratio)
            secondary_k = max_total - primary_k
            budgets[primary] = DocumentBudget(
                domain=primary,
                allocated_k=primary_k,
                is_primary=True,
                priority=1,
            )
            budgets[domains[1]] = DocumentBudget(
                domain=domains[1],
                allocated_k=secondary_k,
                is_primary=False,
                priority=2,
            )
        else:
            # 3+ 도메인
            primary_k = math.ceil(max_total * 0.5)
            remaining = max_total - primary_k
            secondary_count = len(domains) - 1
            per_secondary = max(1, remaining // secondary_count)

            budgets[primary] = DocumentBudget(
                domain=primary,
                allocated_k=primary_k,
                is_primary=True,
                priority=1,
            )
            for i, d in enumerate(domains[1:], start=2):
                budgets[d] = DocumentBudget(
                    domain=d,
                    allocated_k=per_secondary,
                    is_primary=False,
                    priority=i,
                )

        return budgets


# ---------------------------------------------------------------------------
# GraduatedRetryHandler
# ---------------------------------------------------------------------------


class GraduatedRetryHandler:
    """평가 실패 시 단계적 재시도를 수행합니다."""

    def __init__(
        self,
        agents: dict[str, "BaseAgent"],
        rag_chain: "RAGChain",
    ):
        self.agents = agents
        self.rag_chain = rag_chain
        self.settings = get_settings()

    def retry(
        self,
        query: str,
        domain: str,
        current_result: RetrievalResult,
        budget: DocumentBudget,
        max_level: RetryLevel = RetryLevel.MULTI_QUERY,
    ) -> RetrievalResult:
        """단계적 재시도. 각 단계 실패 시 다음 단계로.

        Args:
            query: 사용자 질문
            domain: 검색 도메인
            current_result: 현재 검색 결과
            budget: 문서 할당량
            max_level: 최대 재시도 단계

        Returns:
            개선된 RetrievalResult
        """
        if current_result.evaluation.passed:
            return current_result

        ctx = RetryContext()
        result = current_result

        # Level 1: RELAX_PARAMS
        if max_level >= RetryLevel.RELAX_PARAMS:
            result = self._retry_relax_params(query, domain, result, budget, ctx)
            if result.evaluation.passed:
                return result

        # Level 2: MULTI_QUERY
        if max_level >= RetryLevel.MULTI_QUERY:
            result = self._retry_multi_query(query, domain, result, budget, ctx)
            if result.evaluation.passed:
                return result

        # Level 3: CROSS_DOMAIN
        if max_level >= RetryLevel.CROSS_DOMAIN:
            result = self._retry_cross_domain(query, domain, result, ctx)
            if result.evaluation.passed:
                return result

        # Level 4: PARTIAL_ANSWER - 현재 문서로 진행
        if max_level >= RetryLevel.PARTIAL_ANSWER:
            logger.info(
                "[재시도] Level 4 (PARTIAL_ANSWER): %s - 현재 문서로 진행",
                domain,
            )

        return result

    async def aretry(
        self,
        query: str,
        domain: str,
        current_result: RetrievalResult,
        budget: DocumentBudget,
        max_level: RetryLevel = RetryLevel.MULTI_QUERY,
    ) -> RetrievalResult:
        """비동기 단계적 재시도."""
        return await asyncio.to_thread(
            self.retry, query, domain, current_result, budget, max_level
        )

    def _multi_query_retrieve(
        self,
        query: str,
        domain: str,
        k: int,
        include_common: bool,
        use_mmr: bool | None = None,
        use_hybrid: bool | None = None,
    ) -> tuple[list[Document], str]:
        """도메인별 Multi-Query 검색 공통 헬퍼."""
        from utils.query import MultiQueryRetriever

        multi_retriever = MultiQueryRetriever(self.rag_chain)
        return multi_retriever.retrieve(
            query=query,
            domain=domain,
            k=k,
            include_common=include_common,
            use_mmr=use_mmr,
            use_hybrid=use_hybrid,
        )

    def _retry_relax_params(
        self,
        query: str,
        domain: str,
        result: RetrievalResult,
        budget: DocumentBudget,
        ctx: RetryContext,
    ) -> RetrievalResult:
        """Level 1: 파라미터 완화 + K 증가."""
        from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator

        logger.info("[재시도] Level 1 (RELAX_PARAMS): %s", domain)
        ctx.level = RetryLevel.RELAX_PARAMS
        ctx.attempts += 1

        # K를 +3 증가하여 재검색
        new_k = budget.allocated_k + 3
        if domain in self.agents:
            try:
                documents, expanded_queries = self._multi_query_retrieve(
                    query=query,
                    domain=domain,
                    k=new_k,
                    include_common=False,
                )
                scores = [doc.metadata.get("score", 0.0) for doc in documents]

                # 완화된 기준으로 평가
                evaluator = RuleBasedRetrievalEvaluator()
                orig_keyword = evaluator.min_keyword_match_ratio
                orig_similarity = evaluator.min_avg_similarity

                evaluator.min_keyword_match_ratio = max(0.15, orig_keyword - 0.15)
                evaluator.min_avg_similarity = max(0.35, orig_similarity - 0.15)

                evaluation = evaluator.evaluate(query, documents, scores)

                # 원래 기준 복원
                evaluator.min_keyword_match_ratio = orig_keyword
                evaluator.min_avg_similarity = orig_similarity

                new_result = RetrievalResult(
                    documents=documents,
                    scores=scores,
                    sources=self.rag_chain.documents_to_sources(documents),
                    evaluation=evaluation,
                    used_multi_query=True,
                    retrieve_time=result.retrieve_time,
                    domain=domain,
                    query=query,
                    rewritten_query=expanded_queries,
                )

                logger.info(
                    "[재시도] Level 1 결과: %d건, 평가=%s",
                    len(documents),
                    "PASS" if evaluation.passed else "FAIL",
                )
                return new_result

            except Exception as e:
                logger.warning("[재시도] Level 1 실패: %s", e)

        return result

    def _retry_multi_query(
        self,
        query: str,
        domain: str,
        result: RetrievalResult,
        budget: DocumentBudget,
        ctx: RetryContext,
    ) -> RetrievalResult:
        """Level 2: Multi-Query 재검색."""
        from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator

        logger.info("[재시도] Level 2 (MULTI_QUERY): %s", domain)
        ctx.level = RetryLevel.MULTI_QUERY
        ctx.attempts += 1

        try:
            documents, rewritten_query = self._multi_query_retrieve(
                query=query,
                domain=domain,
                k=budget.allocated_k,
                include_common=True,
            )
            scores = [doc.metadata.get("score", 0.0) for doc in documents]

            evaluator = RuleBasedRetrievalEvaluator()
            evaluation = evaluator.evaluate(query, documents, scores)

            new_result = RetrievalResult(
                documents=documents,
                scores=scores,
                sources=self.rag_chain.documents_to_sources(documents),
                evaluation=evaluation,
                used_multi_query=True,
                retrieve_time=result.retrieve_time,
                domain=domain,
                query=query,
                rewritten_query=rewritten_query,
            )

            logger.info(
                "[재시도] Level 2 결과: %d건, 평가=%s",
                len(documents),
                "PASS" if evaluation.passed else "FAIL",
            )
            return new_result

        except Exception as e:
            logger.warning("[재시도] Level 2 실패: %s", e)
            return result

    def _retry_cross_domain(
        self,
        query: str,
        domain: str,
        result: RetrievalResult,
        ctx: RetryContext,
    ) -> RetrievalResult:
        """Level 3: 인접 도메인 검색."""
        from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator

        adjacent = ADJACENT_DOMAINS.get(domain, [])
        if not adjacent:
            return result

        logger.info("[재시도] Level 3 (CROSS_DOMAIN): %s → %s", domain, adjacent)
        ctx.level = RetryLevel.CROSS_DOMAIN
        ctx.attempts += 1

        combined_docs = list(result.documents)

        for adj_domain in adjacent:
            if adj_domain in ctx.cross_domains_tried:
                continue
            ctx.cross_domains_tried.append(adj_domain)

            if adj_domain not in self.agents:
                continue

            try:
                adj_docs, _ = self._multi_query_retrieve(
                    query=query,
                    domain=adj_domain,
                    k=3,
                    include_common=False,
                )
                combined_docs.extend(adj_docs)
                logger.info(
                    "[재시도] 인접 도메인 %s: %d건 추가",
                    adj_domain,
                    len(adj_docs),
                )
            except Exception as e:
                logger.warning("[재시도] 인접 도메인 %s 실패: %s", adj_domain, e)

        if len(combined_docs) > len(result.documents):
            scores = [doc.metadata.get("score", 0.0) for doc in combined_docs]
            evaluator = RuleBasedRetrievalEvaluator()
            evaluation = evaluator.evaluate(query, combined_docs, scores)

            return RetrievalResult(
                documents=combined_docs,
                scores=scores,
                sources=self.rag_chain.documents_to_sources(combined_docs),
                evaluation=evaluation,
                used_multi_query=True,
                retrieve_time=result.retrieve_time,
                domain=domain,
                query=query,
                rewritten_query=result.rewritten_query,
            )

        return result


# ---------------------------------------------------------------------------
# DocumentMerger
# ---------------------------------------------------------------------------


class DocumentMerger:
    """복합 도메인 문서를 병합, 중복 제거, 우선순위 정렬합니다."""

    @staticmethod
    def _content_hash(doc: Document) -> str:
        """문서 앞 500자 기반 해시."""
        content = doc.page_content[:500]
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def merge_and_prioritize(
        self,
        retrieval_results: dict[str, RetrievalResult],
        budgets: dict[str, DocumentBudget],
        max_total: int = 12,
    ) -> list[Document]:
        """복합 도메인 문서를 병합, 중복 제거, 우선순위 정렬.

        Args:
            retrieval_results: 도메인별 검색 결과
            budgets: 도메인별 문서 할당량
            max_total: 최대 전체 문서 수

        Returns:
            병합된 문서 리스트
        """
        seen_hashes: set[str] = set()
        domain_docs: dict[str, list[Document]] = {}

        # 1. 중복 제거하며 도메인별 분류
        for domain, result in retrieval_results.items():
            domain_docs[domain] = []
            for doc in result.documents:
                h = self._content_hash(doc)
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    domain_docs[domain].append(doc)

        # 2. 도메인별 예산 적용 + 점수순 정렬
        for domain, docs in domain_docs.items():
            # 점수 내림차순 정렬
            docs.sort(
                key=lambda d: d.metadata.get("score", 0.0),
                reverse=True,
            )
            budget = budgets.get(domain)
            if budget:
                domain_docs[domain] = docs[: budget.allocated_k]

        # 3. 우선순위 정렬하여 병합
        sorted_domains = sorted(
            domain_docs.keys(),
            key=lambda d: budgets[d].priority if d in budgets else 99,
        )

        merged: list[Document] = []
        for domain in sorted_domains:
            merged.extend(domain_docs[domain])

        # 4. 총 예산 적용
        if len(merged) > max_total:
            merged = merged[:max_total]

        return merged


# ---------------------------------------------------------------------------
# RetrievalAgent
# ---------------------------------------------------------------------------


class RetrievalAgent:
    """검색 파이프라인 오케스트레이터.

    쿼리 분석 → 예산 할당 → 도메인별 검색 → 평가/재시도 → 법률 보충 → 문서 병합.
    """

    def __init__(
        self,
        agents: dict[str, "BaseAgent"],
        rag_chain: "RAGChain",
        vector_store: "ChromaVectorStore",
        settings: Any | None = None,
    ):
        self.agents = agents
        self.rag_chain = rag_chain
        self.vector_store = vector_store
        self.settings = settings or get_settings()

        self.strategy_selector = SearchStrategySelector()
        self.budget_calculator = DocumentBudgetCalculator()
        self.retry_handler = GraduatedRetryHandler(agents, rag_chain)
        self.merger = DocumentMerger()

    # ----- 메인 엔트리포인트 (동기) ----------------------------------------

    def retrieve(self, state: dict) -> dict:
        """동기 검색 오케스트레이션.

        Args:
            state: RouterState dict

        Returns:
            업데이트된 RouterState dict
        """
        start = time.time()
        sub_queries: list = state["sub_queries"]
        query: str = state["query"]
        domains: list[str] = state["domains"]

        # 1. 쿼리 분석
        query_chars = self.strategy_selector.analyze(query, domains)
        logger.info(
            "[RetrievalAgent] 쿼리 분석: mode=%s, K=%d, length=%d",
            query_chars.recommended_mode.value,
            query_chars.recommended_k,
            query_chars.length,
        )

        # 2. 예산 할당
        budgets = self.budget_calculator.calculate(
            domains=domains,
            query_chars=query_chars,
            max_total=self.settings.max_retrieval_docs,
            primary_ratio=self.settings.primary_domain_budget_ratio,
        )
        logger.info(
            "[RetrievalAgent] 예산 할당: %s",
            {d: b.allocated_k for d, b in budgets.items()},
        )

        # 3. 도메인별 검색
        retrieval_results: dict[str, RetrievalResult] = {}
        all_documents: list[Document] = []
        agent_timings: list[dict] = []

        for sq in sub_queries:
            if sq.domain not in self.agents:
                continue

            agent = self.agents[sq.domain]
            budget = budgets.get(sq.domain)
            k_value = budget.allocated_k if budget else self.settings.retrieval_k

            logger.info("[RetrievalAgent] 에이전트 [%s] 검색 시작 (K=%d)", sq.domain, k_value)
            agent_start = time.time()

            # 적응형 검색 모드 적용
            result = self._retrieve_with_strategy(
                agent=agent,
                query=sq.query,
                domain=sq.domain,
                k=k_value,
                query_chars=query_chars,
            )

            # 평가 실패 시 단계적 재시도
            if (
                not result.evaluation.passed
                and self.settings.enable_graduated_retry
                and budget
            ):
                max_retry = RetryLevel(
                    min(self.settings.max_retry_level, RetryLevel.PARTIAL_ANSWER.value)
                )
                result = self.retry_handler.retry(
                    query=sq.query,
                    domain=sq.domain,
                    current_result=result,
                    budget=budget,
                    max_level=max_retry,
                )

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
                "[RetrievalAgent] 에이전트 [%s] 완료: %d건, 평가=%s (%.3fs)",
                sq.domain,
                len(result.documents),
                "PASS" if result.evaluation.passed else "FAIL",
                agent_elapsed,
            )

        # 4. 법률 보충 검색
        self._perform_legal_supplement(
            query=query,
            documents=all_documents,
            domains=domains,
            retrieval_results=retrieval_results,
            all_documents=all_documents,
            agent_timings=agent_timings,
            sub_queries=sub_queries,
        )

        # 5. 복합 도메인 문서 병합 (2+ 도메인)
        if len(retrieval_results) > 1:
            # supplement 제외한 본 검색 결과만 병합 대상
            main_results = {
                d: r for d, r in retrieval_results.items()
                if d != "law_common_supplement"
            }
            if len(main_results) > 1:
                merged = self._merge_with_optional_rerank(
                    query=query,
                    main_results=main_results,
                    budgets=budgets,
                )
                # supplement 문서 뒤에 추가
                supplement = retrieval_results.get("law_common_supplement")
                if supplement:
                    merged.extend(supplement.documents)
                all_documents = merged

        state["retrieval_results"] = retrieval_results
        state["documents"] = all_documents

        retrieve_time = time.time() - start
        state["timing_metrics"]["retrieve_time"] = retrieve_time
        state["timing_metrics"]["agents"] = agent_timings

        logger.info(
            "[RetrievalAgent] 전체 완료: %d건, %.3fs",
            len(all_documents),
            retrieve_time,
        )

        return state

    # ----- 메인 엔트리포인트 (비동기) --------------------------------------

    async def aretrieve(self, state: dict) -> dict:
        """비동기 검색 오케스트레이션 (asyncio.gather로 병렬).

        Args:
            state: RouterState dict

        Returns:
            업데이트된 RouterState dict
        """
        start = time.time()
        sub_queries: list = state["sub_queries"]
        query: str = state["query"]
        domains: list[str] = state["domains"]

        # 1. 쿼리 분석
        query_chars = self.strategy_selector.analyze(query, domains)
        logger.info(
            "[RetrievalAgent] 쿼리 분석: mode=%s, K=%d",
            query_chars.recommended_mode.value,
            query_chars.recommended_k,
        )

        # 2. 예산 할당
        budgets = self.budget_calculator.calculate(
            domains=domains,
            query_chars=query_chars,
            max_total=self.settings.max_retrieval_docs,
            primary_ratio=self.settings.primary_domain_budget_ratio,
        )

        # 3. 도메인별 병렬 검색
        async def retrieve_for_domain(sq: "SubQuery"):
            if sq.domain not in self.agents:
                return None

            agent = self.agents[sq.domain]
            budget = budgets.get(sq.domain)
            k_value = budget.allocated_k if budget else self.settings.retrieval_k

            logger.info("[RetrievalAgent] 에이전트 [%s] 비동기 검색 시작 (K=%d)", sq.domain, k_value)
            agent_start = time.time()

            # 적응형 검색
            result = await asyncio.to_thread(
                self._retrieve_with_strategy,
                agent,
                sq.query,
                sq.domain,
                k_value,
                query_chars,
            )

            # 평가 실패 시 재시도
            if (
                not result.evaluation.passed
                and self.settings.enable_graduated_retry
                and budget
            ):
                max_retry = RetryLevel(
                    min(self.settings.max_retry_level, RetryLevel.PARTIAL_ANSWER.value)
                )
                result = await self.retry_handler.aretry(
                    query=sq.query,
                    domain=sq.domain,
                    current_result=result,
                    budget=budget,
                    max_level=max_retry,
                )

            agent_elapsed = time.time() - agent_start
            return sq.domain, result, agent_elapsed

        tasks = [retrieve_for_domain(sq) for sq in sub_queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        retrieval_results: dict[str, RetrievalResult] = {}
        all_documents: list[Document] = []
        agent_timings: list[dict] = []

        for result in results:
            if isinstance(result, Exception):
                logger.error("[RetrievalAgent] 도메인 에이전트 실패: %s", result)
                continue
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
                    "[RetrievalAgent] 에이전트 [%s] 완료: %d건, 평가=%s (%.3fs)",
                    domain,
                    len(retrieval_result.documents),
                    "PASS" if retrieval_result.evaluation.passed else "FAIL",
                    elapsed,
                )

        # 4. 법률 보충 검색 (비동기)
        await self._aperform_legal_supplement(
            query=query,
            documents=all_documents,
            domains=domains,
            retrieval_results=retrieval_results,
            all_documents=all_documents,
            agent_timings=agent_timings,
            sub_queries=sub_queries,
        )

        # 5. 복합 도메인 문서 병합
        if len(retrieval_results) > 1:
            main_results = {
                d: r for d, r in retrieval_results.items()
                if d != "law_common_supplement"
            }
            if len(main_results) > 1:
                merged = await self._amerge_with_optional_rerank(
                    query=query,
                    main_results=main_results,
                    budgets=budgets,
                )
                supplement = retrieval_results.get("law_common_supplement")
                if supplement:
                    merged.extend(supplement.documents)
                all_documents = merged

        state["retrieval_results"] = retrieval_results
        state["documents"] = all_documents

        retrieve_time = time.time() - start
        state["timing_metrics"]["retrieve_time"] = retrieve_time
        state["timing_metrics"]["agents"] = agent_timings

        logger.info(
            "[RetrievalAgent] 전체 완료: %d건, %.3fs",
            len(all_documents),
            retrieve_time,
        )

        return state

    # ----- 내부 헬퍼 -------------------------------------------------------

    def _merge_with_optional_rerank(
        self,
        query: str,
        main_results: dict[str, RetrievalResult],
        budgets: dict[str, DocumentBudget],
    ) -> list[Document]:
        """복합 도메인 병합 후 선택적 cross-domain reranking (동기).

        Args:
            query: 사용자 질문
            main_results: supplement 제외 도메인별 검색 결과
            budgets: 도메인별 문서 할당량

        Returns:
            병합(+rerank) 된 문서 리스트
        """
        if self.settings.enable_cross_domain_rerank:
            # rerank 후보를 넉넉히 확보
            candidate_total = sum(
                b.allocated_k for b in budgets.values()
                if b.domain in main_results
            )
            merged = self.merger.merge_and_prioritize(
                retrieval_results=main_results,
                budgets=budgets,
                max_total=candidate_total,
            )
            # 모든 도메인 예산 합계를 final_k로 사용 (max_retrieval_docs로 상한)
            final_k = min(
                sum(b.allocated_k for b in budgets.values() if b.domain in main_results),
                self.settings.max_retrieval_docs,
            )
            reranker = self.rag_chain.reranker
            if reranker and len(merged) > final_k:
                logger.info(
                    "[RetrievalAgent] cross-domain rerank: %d건 → %d건",
                    len(merged),
                    final_k,
                )
                merged = reranker.rerank(query, merged, top_k=final_k)
            else:
                if not reranker:
                    logger.warning(
                        "[RetrievalAgent] cross-domain rerank 활성화됐지만 "
                        "reranker 없음 (enable_reranking=False?). 점수순 슬라이스로 대체"
                    )
                merged = merged[:final_k]
            return merged

        # 기존 방식: 우선순위 기반 병합
        return self.merger.merge_and_prioritize(
            retrieval_results=main_results,
            budgets=budgets,
            max_total=self.settings.max_retrieval_docs,
        )

    async def _amerge_with_optional_rerank(
        self,
        query: str,
        main_results: dict[str, RetrievalResult],
        budgets: dict[str, DocumentBudget],
    ) -> list[Document]:
        """복합 도메인 병합 후 선택적 cross-domain reranking (비동기).

        Args:
            query: 사용자 질문
            main_results: supplement 제외 도메인별 검색 결과
            budgets: 도메인별 문서 할당량

        Returns:
            병합(+rerank) 된 문서 리스트
        """
        if self.settings.enable_cross_domain_rerank:
            candidate_total = sum(
                b.allocated_k for b in budgets.values()
                if b.domain in main_results
            )
            merged = self.merger.merge_and_prioritize(
                retrieval_results=main_results,
                budgets=budgets,
                max_total=candidate_total,
            )
            # 모든 도메인 예산 합계를 final_k로 사용 (max_retrieval_docs로 상한)
            final_k = min(
                sum(b.allocated_k for b in budgets.values() if b.domain in main_results),
                self.settings.max_retrieval_docs,
            )
            reranker = self.rag_chain.reranker
            if reranker and len(merged) > final_k:
                logger.info(
                    "[RetrievalAgent] cross-domain rerank: %d건 → %d건",
                    len(merged),
                    final_k,
                )
                merged = await reranker.arerank(query, merged, top_k=final_k)
            else:
                if not reranker:
                    logger.warning(
                        "[RetrievalAgent] cross-domain rerank 활성화됐지만 "
                        "reranker 없음 (enable_reranking=False?). 점수순 슬라이스로 대체"
                    )
                merged = merged[:final_k]
            return merged

        return self.merger.merge_and_prioritize(
            retrieval_results=main_results,
            budgets=budgets,
            max_total=self.settings.max_retrieval_docs,
        )

    def _retrieve_with_strategy(
        self,
        agent: "BaseAgent",
        query: str,
        domain: str,
        k: int,
        query_chars: QueryCharacteristics,
    ) -> RetrievalResult:
        """적응형 검색 모드를 적용하여 검색.

        Args:
            agent: 도메인 에이전트
            query: 검색 쿼리
            domain: 검색 도메인
            k: 검색 결과 개수
            query_chars: 쿼리 분석 결과

        Returns:
            RetrievalResult
        """
        from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator
        from utils.query import MultiQueryRetriever

        start = time.time()

        if not self.settings.enable_adaptive_search:
            # 적응형 검색 비활성화 시 기존 방식
            return agent.retrieve_only(query)

        mode = query_chars.recommended_mode

        # 모드별 파라미터 결정
        use_hybrid = mode in (SearchMode.HYBRID, SearchMode.BM25_HEAVY, SearchMode.VECTOR_HEAVY)
        use_mmr = mode == SearchMode.MMR_DIVERSE

        try:
            multi_retriever = MultiQueryRetriever(self.rag_chain)
            documents, expanded_queries = multi_retriever.retrieve(
                query=query,
                domain=domain,
                k=k,
                include_common=False,
                use_mmr=use_mmr,
                use_hybrid=use_hybrid if mode != SearchMode.MMR_DIVERSE else False,
            )
        except Exception as e:
            logger.error("[RetrievalAgent] 검색 실패 (%s): %s", domain, e)
            documents = []
            expanded_queries = None

        scores = [doc.metadata.get("score", 0.0) for doc in documents]

        evaluator = RuleBasedRetrievalEvaluator()
        evaluation = evaluator.evaluate(query, documents, scores)

        elapsed = time.time() - start

        return RetrievalResult(
            documents=documents,
            scores=scores,
            sources=self.rag_chain.documents_to_sources(documents),
            evaluation=evaluation,
            used_multi_query=True,
            retrieve_time=elapsed,
            domain=domain,
            query=query,
            rewritten_query=expanded_queries,
        )

    @staticmethod
    def _select_legal_query(
        query: str,
        sub_queries: list["SubQuery"],
    ) -> str:
        """법률 보충 검색에 사용할 최적 쿼리를 선택합니다.

        하위 질문 중 법률 키워드가 가장 많이 포함된 질문을 선택합니다.
        복합 질문 전체가 아닌 법률 특화 하위 질문을 사용하여 검색 정밀도를 높입니다.

        Args:
            query: 원본 복합 질문
            sub_queries: 분해된 하위 질문 리스트

        Returns:
            법률 보충 검색에 사용할 쿼리 문자열
        """
        if not sub_queries or len(sub_queries) <= 1:
            return query

        best_query = query
        best_count = 0

        for sq in sub_queries:
            count = sum(1 for kw in LEGAL_SUPPLEMENT_KEYWORDS if kw in sq.query)
            if count > best_count:
                best_count = count
                best_query = sq.query

        if best_count > 0 and best_query != query:
            logger.info(
                "[법률 보충] 하위 질문 선택: '%s' (법률 키워드 %d개)",
                best_query[:50],
                best_count,
            )

        return best_query

    def _perform_legal_supplement(
        self,
        query: str,
        documents: list[Document],
        domains: list[str],
        retrieval_results: dict[str, RetrievalResult],
        all_documents: list[Document],
        agent_timings: list[dict],
        sub_queries: list["SubQuery"] | None = None,
    ) -> None:
        """법률 보충 검색을 수행합니다 (동기).

        Args:
            query: 사용자 질문
            documents: 도메인 에이전트가 검색한 전체 문서
            domains: 분류된 도메인 리스트
            retrieval_results: 검색 결과 딕셔너리 (in-place 수정)
            all_documents: 전체 문서 리스트 (in-place 수정)
            agent_timings: 에이전트 타이밍 리스트 (in-place 수정)
            sub_queries: 분해된 하위 질문 리스트 (법률 특화 쿼리 선택용)
        """
        if not self.settings.enable_legal_supplement:
            return

        if not needs_legal_supplement(query, documents, domains):
            return

        logger.info("[법률 보충] 법률 보충 검색 시작")
        legal_agent = self.agents.get("law_common")
        if not legal_agent:
            return

        # 복합 질문 시 법률 특화 하위 질문 선택
        search_query = self._select_legal_query(query, sub_queries or [])

        agent_start = time.time()

        try:
            result = legal_agent.retrieve_only(search_query)
            if len(result.documents) > self.settings.legal_supplement_k:
                result.documents = result.documents[: self.settings.legal_supplement_k]
                result.sources = result.sources[: self.settings.legal_supplement_k]

            retrieval_results["law_common_supplement"] = result
            all_documents.extend(result.documents)

            agent_elapsed = time.time() - agent_start
            agent_timings.append({
                "domain": "law_common_supplement",
                "retrieve_time": result.retrieve_time,
                "doc_count": len(result.documents),
                "total_time": agent_elapsed,
            })

            logger.info(
                "[법률 보충] 완료: %d건 (%.3fs)",
                len(result.documents),
                agent_elapsed,
            )
        except Exception as e:
            logger.warning("[법률 보충] 검색 실패: %s", e)

    async def _aperform_legal_supplement(
        self,
        query: str,
        documents: list[Document],
        domains: list[str],
        retrieval_results: dict[str, RetrievalResult],
        all_documents: list[Document],
        agent_timings: list[dict],
        sub_queries: list["SubQuery"] | None = None,
    ) -> None:
        """법률 보충 검색을 비동기로 수행합니다 (동기 메서드에 위임)."""
        await asyncio.to_thread(
            self._perform_legal_supplement,
            query, documents, domains,
            retrieval_results, all_documents, agent_timings,
            sub_queries,
        )
