"""Reranker 성능 벤치마크 테스트.

Cross-Encoder와 LLM Reranker의 성능을 비교합니다.
벤치마크 테스트는 pytest -m benchmark로 실행합니다.
"""

import json
import os
import time
from pathlib import Path

import pytest
from langchain_core.documents import Document

from utils.reranker import (
    CrossEncoderReranker,
    LLMReranker,
    get_reranker,
    reset_reranker,
)


# 벤치마크 데이터셋 로드
BENCHMARK_DATA_PATH = Path(__file__).parent / "benchmark" / "benchmark_dataset.jsonl"


def load_benchmark_data():
    """벤치마크 데이터셋을 로드합니다."""
    data = []
    if BENCHMARK_DATA_PATH.exists():
        with open(BENCHMARK_DATA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                data.append(json.loads(line))
    return data


@pytest.fixture
def benchmark_data():
    """벤치마크 데이터셋."""
    return load_benchmark_data()


@pytest.fixture
def sample_documents():
    """샘플 문서 리스트 (10개)."""
    return [
        Document(
            page_content="사업자등록 후 부가가치세 신고를 해야 합니다. 일반과세자는 1년에 2번, 간이과세자는 1년에 1번 신고합니다.",
            metadata={"title": "부가세 신고 안내", "source": "국세청"},
        ),
        Document(
            page_content="법인세는 사업연도 종료일로부터 3개월 이내에 신고해야 합니다. 개인사업자는 종합소득세를 신고합니다.",
            metadata={"title": "법인세 안내", "source": "국세청"},
        ),
        Document(
            page_content="창업 초기에는 세무사 상담을 받는 것이 좋습니다. 세금 신고 기한을 놓치면 가산세가 부과됩니다.",
            metadata={"title": "창업 세무 가이드", "source": "창업진흥원"},
        ),
        Document(
            page_content="근로계약서에는 임금, 근로시간, 휴일 등을 반드시 명시해야 합니다. 서면으로 작성해야 합니다.",
            metadata={"title": "근로계약 안내", "source": "고용노동부"},
        ),
        Document(
            page_content="퇴직금은 계속근로기간 1년에 대해 30일분 이상의 평균임금을 지급해야 합니다.",
            metadata={"title": "퇴직금 계산법", "source": "고용노동부"},
        ),
        Document(
            page_content="4대보험은 국민연금, 건강보험, 고용보험, 산재보험으로 구성됩니다. 사업주와 근로자가 분담합니다.",
            metadata={"title": "4대보험 안내", "source": "국민건강보험공단"},
        ),
        Document(
            page_content="정부 창업 지원사업은 기업마당 홈페이지에서 확인할 수 있습니다. 매년 다양한 지원사업이 공고됩니다.",
            metadata={"title": "지원사업 안내", "source": "중소벤처기업부"},
        ),
        Document(
            page_content="마케팅 전략은 타겟 고객 분석부터 시작해야 합니다. SNS 마케팅이 효과적입니다.",
            metadata={"title": "마케팅 가이드", "source": "창업진흥원"},
        ),
        Document(
            page_content="연차휴가는 1년간 80% 이상 출근한 근로자에게 15일이 부여됩니다. 미사용 시 수당으로 지급 가능합니다.",
            metadata={"title": "연차휴가 안내", "source": "고용노동부"},
        ),
        Document(
            page_content="주52시간제는 주 40시간 근무 + 연장근로 12시간이 상한입니다. 특례업종은 예외가 있습니다.",
            metadata={"title": "근로시간 규정", "source": "고용노동부"},
        ),
    ]


@pytest.fixture(autouse=True)
def cleanup_singleton():
    """각 테스트 전후로 싱글톤 리셋."""
    reset_reranker()
    yield
    reset_reranker()


@pytest.mark.benchmark
class TestCrossEncoderLatency:
    """Cross-Encoder 레이턴시 벤치마크."""

    def test_cross_encoder_latency_single(self, sample_documents):
        """단일 쿼리 레이턴시 측정 (목표: <1초)."""
        reranker = CrossEncoderReranker()
        query = "세금 신고 방법을 알려주세요"

        # 첫 호출은 모델 로딩 포함하므로 웜업
        _ = reranker.rerank(query, sample_documents[:3], top_k=2)

        # 실제 측정
        start = time.time()
        result = reranker.rerank(query, sample_documents, top_k=5)
        elapsed = time.time() - start

        print(f"\n[CrossEncoder] 단일 쿼리 레이턴시: {elapsed:.3f}초")
        assert len(result) == 5
        assert elapsed < 1.0, f"레이턴시 {elapsed:.3f}초가 목표(1초)를 초과"

    def test_cross_encoder_batch_benchmark(self, sample_documents, benchmark_data):
        """배치 쿼리 벤치마크 (10개 쿼리, 목표: 평균 <0.5초)."""
        if not benchmark_data:
            pytest.skip("벤치마크 데이터셋 없음")

        reranker = CrossEncoderReranker()
        queries = [item["question"] for item in benchmark_data[:10]]

        # 웜업
        _ = reranker.rerank(queries[0], sample_documents[:3], top_k=2)

        # 배치 측정
        latencies = []
        for query in queries:
            start = time.time()
            _ = reranker.rerank(query, sample_documents, top_k=5)
            latencies.append(time.time() - start)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)

        print(f"\n[CrossEncoder] 배치 벤치마크 결과:")
        print(f"  - 평균 레이턴시: {avg_latency:.3f}초")
        print(f"  - 최소 레이턴시: {min_latency:.3f}초")
        print(f"  - 최대 레이턴시: {max_latency:.3f}초")

        # GPU 환경: <0.5초, CPU 환경: <2.0초
        assert avg_latency < 2.0, f"평균 레이턴시 {avg_latency:.3f}초가 목표(2.0초)를 초과"


@pytest.mark.benchmark
class TestLLMRerankerLatency:
    """LLM Reranker 레이턴시 벤치마크."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-test"),
        reason="실제 OPENAI_API_KEY 필요"
    )
    def test_llm_reranker_latency_single(self, sample_documents):
        """단일 쿼리 LLM 레이턴시 측정."""
        reranker = LLMReranker()
        query = "세금 신고 방법을 알려주세요"

        start = time.time()
        result = reranker.rerank(query, sample_documents[:5], top_k=3)
        elapsed = time.time() - start

        print(f"\n[LLM] 단일 쿼리 레이턴시 (5문서 → top_3): {elapsed:.3f}초")
        assert len(result) == 3


@pytest.mark.benchmark
class TestRerankerComparison:
    """Cross-Encoder vs LLM Reranker 비교."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-test"),
        reason="실제 OPENAI_API_KEY 필요"
    )
    def test_reranker_latency_comparison(self, sample_documents):
        """레이턴시 비교 테스트."""
        query = "퇴직금 계산 방법"
        docs = sample_documents[:5]
        top_k = 3

        # CrossEncoder
        ce_reranker = CrossEncoderReranker()
        _ = ce_reranker.rerank(query, docs[:2], top_k=1)  # 웜업

        ce_start = time.time()
        ce_result = ce_reranker.rerank(query, docs, top_k=top_k)
        ce_elapsed = time.time() - ce_start

        # LLM
        llm_reranker = LLMReranker()

        llm_start = time.time()
        llm_result = llm_reranker.rerank(query, docs, top_k=top_k)
        llm_elapsed = time.time() - llm_start

        speedup = llm_elapsed / ce_elapsed if ce_elapsed > 0 else float('inf')

        print(f"\n[비교] 레이턴시 비교 결과:")
        print(f"  - CrossEncoder: {ce_elapsed:.3f}초")
        print(f"  - LLM Reranker: {llm_elapsed:.3f}초")
        print(f"  - 속도 향상: {speedup:.1f}x")

        assert len(ce_result) == top_k
        assert len(llm_result) == top_k

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-test"),
        reason="실제 OPENAI_API_KEY 필요"
    )
    def test_ranking_consistency(self, sample_documents):
        """순위 일관성 비교 테스트."""
        query = "퇴직금 계산 방법"
        docs = sample_documents
        top_k = 5

        # CrossEncoder
        ce_reranker = CrossEncoderReranker()
        ce_result = ce_reranker.rerank(query, docs, top_k=top_k)
        ce_titles = [doc.metadata.get("title", "") for doc in ce_result]

        # LLM
        llm_reranker = LLMReranker()
        llm_result = llm_reranker.rerank(query, docs, top_k=top_k)
        llm_titles = [doc.metadata.get("title", "") for doc in llm_result]

        # 공통 상위 문서 확인
        common = set(ce_titles[:3]) & set(llm_titles[:3])

        print(f"\n[일관성] 순위 비교:")
        print(f"  - CrossEncoder Top-3: {ce_titles[:3]}")
        print(f"  - LLM Top-3: {llm_titles[:3]}")
        print(f"  - 공통 문서: {common}")

        # 적어도 1개 이상의 공통 문서가 있어야 함 (퇴직금 관련)
        assert len(common) >= 1, "상위 3개 문서 중 공통 문서가 없음"


@pytest.mark.benchmark
class TestDomainSpecificBenchmark:
    """도메인별 키워드 적중률 벤치마크."""

    def test_domain_keyword_hit_rate(self, benchmark_data):
        """도메인별 키워드 적중률 테스트."""
        if not benchmark_data:
            pytest.skip("벤치마크 데이터셋 없음")

        reranker = CrossEncoderReranker()

        # 도메인별 테스트 케이스 그룹화
        domain_cases = {}
        for item in benchmark_data[:30]:
            domain = item.get("domain", "unknown")
            if domain not in domain_cases:
                domain_cases[domain] = []
            domain_cases[domain].append(item)

        # 각 도메인별로 테스트
        results = {}
        for domain, cases in domain_cases.items():
            # 해당 도메인에 맞는 가상 문서 생성
            docs = self._create_domain_docs(domain)
            if not docs:
                continue

            hits = 0
            total = len(cases)

            for case in cases:
                query = case["question"]
                expected_keywords = case.get("expected_keywords", [])

                top_docs = reranker.rerank(query, docs, top_k=3)
                top_content = " ".join(doc.page_content for doc in top_docs)

                # 키워드 적중 확인
                keyword_found = any(kw in top_content for kw in expected_keywords)
                if keyword_found:
                    hits += 1

            hit_rate = hits / total if total > 0 else 0
            results[domain] = {
                "total": total,
                "hits": hits,
                "hit_rate": hit_rate,
            }

        print("\n[도메인별 키워드 적중률]")
        for domain, stats in results.items():
            print(f"  - {domain}: {stats['hit_rate']:.1%} ({stats['hits']}/{stats['total']})")

        # 전체 적중률이 50% 이상이어야 함
        total_hits = sum(r["hits"] for r in results.values())
        total_cases = sum(r["total"] for r in results.values())
        overall_rate = total_hits / total_cases if total_cases > 0 else 0

        assert overall_rate >= 0.5, f"전체 적중률 {overall_rate:.1%}이 50% 미만"

    def _create_domain_docs(self, domain: str) -> list[Document]:
        """도메인별 테스트용 문서 생성."""
        domain_docs = {
            "startup_funding": [
                Document(
                    page_content="사업자등록은 홈택스 또는 세무서에서 신청할 수 있습니다. 사업자등록증은 약 3일 내 발급됩니다.",
                    metadata={"title": "사업자등록 안내", "source": "국세청"},
                ),
                Document(
                    page_content="법인 설립에는 정관, 등기신청서, 법인인감이 필요합니다. 등기 후 사업자등록을 진행합니다.",
                    metadata={"title": "법인설립 가이드", "source": "법원"},
                ),
                Document(
                    page_content="정부 지원사업은 예비창업자와 창업기업을 대상으로 합니다. 지원자격은 공고마다 다릅니다.",
                    metadata={"title": "지원사업 안내", "source": "중기부"},
                ),
                Document(
                    page_content="보조금, 정책자금, 지원사업 등 다양한 창업 지원 프로그램이 있습니다.",
                    metadata={"title": "창업지원 총정리", "source": "창업진흥원"},
                ),
                Document(
                    page_content="마케팅은 타겟 고객 분석, 홍보 전략, 브랜딩이 핵심입니다.",
                    metadata={"title": "마케팅 전략", "source": "창업진흥원"},
                ),
            ],
            "finance_tax": [
                Document(
                    page_content="부가세 신고는 분기별로 다음 달 25일까지 해야 합니다.",
                    metadata={"title": "부가세 신고", "source": "국세청"},
                ),
                Document(
                    page_content="법인세는 세율과 과세표준에 따라 계산됩니다.",
                    metadata={"title": "법인세 계산", "source": "국세청"},
                ),
                Document(
                    page_content="원천징수는 소득세를 원천에서 징수하여 납부하는 것입니다.",
                    metadata={"title": "원천징수 안내", "source": "국세청"},
                ),
                Document(
                    page_content="절세를 위해 공제와 감면 항목을 활용하세요.",
                    metadata={"title": "절세 가이드", "source": "국세청"},
                ),
                Document(
                    page_content="재무제표에는 손익계산서와 대차대조표가 포함됩니다.",
                    metadata={"title": "재무제표 안내", "source": "금융감독원"},
                ),
            ],
            "hr_labor": [
                Document(
                    page_content="퇴직금은 평균임금과 계속근로기간을 기준으로 계산합니다.",
                    metadata={"title": "퇴직금 계산", "source": "고용노동부"},
                ),
                Document(
                    page_content="연차휴가는 근속기간에 따라 발생하며 최대 25일까지 부여됩니다.",
                    metadata={"title": "연차휴가 안내", "source": "고용노동부"},
                ),
                Document(
                    page_content="근로계약서에는 임금, 근로시간 등을 명시해야 합니다.",
                    metadata={"title": "근로계약 안내", "source": "고용노동부"},
                ),
                Document(
                    page_content="해고는 정당사유가 있어야 하며 해고예고를 해야 합니다.",
                    metadata={"title": "해고 규정", "source": "고용노동부"},
                ),
                Document(
                    page_content="4대보험은 국민연금, 건강보험, 고용보험, 산재보험입니다.",
                    metadata={"title": "4대보험 안내", "source": "건강보험공단"},
                ),
            ],
        }
        return domain_docs.get(domain, [])


@pytest.mark.benchmark
@pytest.mark.asyncio
class TestAsyncBenchmark:
    """비동기 벤치마크 테스트."""

    async def test_async_cross_encoder_latency(self, sample_documents):
        """비동기 CrossEncoder 레이턴시 측정."""
        reranker = CrossEncoderReranker()
        query = "세금 신고 방법"

        # 웜업
        await reranker.arerank(query, sample_documents[:3], top_k=2)

        # 측정
        start = time.time()
        result = await reranker.arerank(query, sample_documents, top_k=5)
        elapsed = time.time() - start

        print(f"\n[Async CrossEncoder] 레이턴시: {elapsed:.3f}초")
        assert len(result) == 5
        assert elapsed < 1.0
