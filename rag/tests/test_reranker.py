"""Unit tests for reranker module."""

import os

import pytest
from langchain_core.documents import Document

from utils.reranker import (
    BaseReranker,
    CrossEncoderReranker,
    LLMReranker,
    RunPodReranker,
    get_reranker,
    reset_reranker,
)


@pytest.fixture
def sample_documents():
    """Sample documents for reranking tests."""
    return [
        Document(page_content="부가가치세 신고는 정기적으로 해야 합니다.", metadata={"title": "부가세 신고", "source": "국세청"}),
        Document(page_content="법인은 사업연도 종료 후 3개월 이내 신고해야 합니다.", metadata={"title": "법인세 안내", "source": "국세청"}),
        Document(page_content="창업 초기에는 세무 상담을 받는 것이 좋습니다.", metadata={"title": "창업 세무 가이드", "source": "창업진흥원"}),
        Document(page_content="근로계약서에는 임금, 근로시간, 휴일을 명시해야 합니다.", metadata={"title": "근로계약 안내", "source": "고용노동부"}),
        Document(page_content="Retirement pay is calculated from average wages.", metadata={"title": "retirement_pay", "source": "고용노동부"}),
        Document(page_content="4대보험은 국민연금, 건강보험, 고용보험, 산재보험으로 구성됩니다.", metadata={"title": "4대보험 안내", "source": "국민건강보험공단"}),
        Document(page_content="정책 창업 지원사업은 기업마당에서 확인할 수 있습니다.", metadata={"title": "지원사업 안내", "source": "중소벤처기업부"}),
        Document(page_content="마케팅 전략은 타겟 고객 분석부터 시작해야 합니다.", metadata={"title": "마케팅 가이드", "source": "창업진흥원"}),
        Document(page_content="연차휴가는 1년간 80% 이상 출근한 근로자에게 15일이 부여됩니다.", metadata={"title": "연차휴가 안내", "source": "고용노동부"}),
        Document(page_content="주 2시간은 주 40시간 + 연장근로 12시간을 상한합니다.", metadata={"title": "근로시간 규정", "source": "고용노동부"}),
    ]


@pytest.fixture(autouse=True)
def cleanup_singleton():
    reset_reranker()
    yield
    reset_reranker()


class TestCrossEncoderReranker:
    def test_rerank_basic(self, sample_documents):
        reranker = CrossEncoderReranker()
        result = reranker.rerank("세금 신고 방법", sample_documents, top_k=3)
        assert len(result) == 3
        assert all(isinstance(doc, Document) for doc in result)

    def test_rerank_returns_all_when_less_than_top_k(self):
        reranker = CrossEncoderReranker()
        docs = [Document(page_content="테스트 문서1", metadata={}), Document(page_content="테스트 문서2", metadata={})]
        result = reranker.rerank("쿼리", docs, top_k=5)
        assert len(result) == 2

    def test_rerank_relevance_order(self, sample_documents):
        reranker = CrossEncoderReranker()
        result = reranker.rerank("retirement pay calculation", sample_documents, top_k=3)
        assert any(doc.metadata.get("title") == "retirement_pay" for doc in result)

    def test_rerank_with_empty_documents(self):
        reranker = CrossEncoderReranker()
        assert reranker.rerank("쿼리", [], top_k=3) == []

    @pytest.mark.asyncio
    async def test_arerank_basic(self, sample_documents):
        reranker = CrossEncoderReranker()
        result = await reranker.arerank("세금 신고 방법", sample_documents, top_k=3)
        assert len(result) == 3


class TestLLMReranker:
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-test"),
        reason="real OPENAI_API_KEY required",
    )
    def test_rerank_basic(self, sample_documents):
        reranker = LLMReranker()
        result = reranker.rerank("세금 신고 방법", sample_documents[:5], top_k=3)
        assert len(result) == 3

    def test_rerank_returns_all_when_less_than_top_k(self):
        reranker = LLMReranker()
        docs = [Document(page_content="테스트 문서1", metadata={}), Document(page_content="테스트 문서2", metadata={})]
        result = reranker.rerank("쿼리", docs, top_k=5)
        assert len(result) == 2

    def test_parse_score_valid(self):
        reranker = LLMReranker()
        assert reranker._parse_score("8") == 8.0
        assert reranker._parse_score("점수: 9") == 9.0
        assert reranker._parse_score("7.5점") == 7.5

    def test_parse_score_clamping(self):
        reranker = LLMReranker()
        assert reranker._parse_score("15") == 10.0
        assert reranker._parse_score("-5") == 5.0
        assert reranker._parse_score("abc") == 5.0

    def test_parse_score_invalid(self):
        reranker = LLMReranker()
        assert reranker._parse_score("관련 없음") == 5.0
        assert reranker._parse_score("") == 5.0


class TestGetReranker:
    def test_get_cross_encoder_reranker(self):
        assert isinstance(get_reranker("cross-encoder"), CrossEncoderReranker)

    def test_get_llm_reranker(self):
        assert isinstance(get_reranker("llm"), LLMReranker)

    def test_singleton_pattern(self):
        r1 = get_reranker("cross-encoder")
        r2 = get_reranker("cross-encoder")
        assert r1 is r2

    def test_singleton_type_change(self):
        r1 = get_reranker("cross-encoder")
        r2 = get_reranker("llm")
        assert r1 is not r2
        assert isinstance(r1, CrossEncoderReranker)
        assert isinstance(r2, LLMReranker)

    def test_invalid_reranker_type(self):
        with pytest.raises(ValueError, match="reranker_type"):
            get_reranker("invalid-type")

    def test_reset_reranker(self):
        r1 = get_reranker("cross-encoder")
        reset_reranker()
        r2 = get_reranker("cross-encoder")
        assert r1 is not r2

    def test_default_type_from_settings(self):
        reranker = get_reranker()
        from utils.config import get_settings
        settings = get_settings()
        if settings.embedding_provider == "runpod":
            assert isinstance(reranker, RunPodReranker)
        else:
            assert isinstance(reranker, CrossEncoderReranker)


class TestBaseReranker:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseReranker()

    def test_subclass_must_implement_methods(self):
        class IncompleteReranker(BaseReranker):
            pass

        with pytest.raises(TypeError):
            IncompleteReranker()
