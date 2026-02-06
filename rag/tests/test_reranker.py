"""Reranker 모듈 단위 테스트."""

import os

import pytest
from langchain_core.documents import Document

from utils.reranker import (
    BaseReranker,
    CrossEncoderReranker,
    LLMReranker,
    get_reranker,
    reset_reranker,
)


@pytest.fixture
def sample_documents():
    """샘플 문서 리스트 (10개)."""
    return [
        Document(
            page_content="사업자등록 후 부가가치세 신고를 해야 합니다.",
            metadata={"title": "부가세 신고", "source": "국세청"},
        ),
        Document(
            page_content="법인세는 사업연도 종료일로부터 3개월 이내에 신고해야 합니다.",
            metadata={"title": "법인세 안내", "source": "국세청"},
        ),
        Document(
            page_content="창업 초기에는 세무사 상담을 받는 것이 좋습니다.",
            metadata={"title": "창업 세무 가이드", "source": "창업진흥원"},
        ),
        Document(
            page_content="근로계약서에는 임금, 근로시간, 휴일 등을 명시해야 합니다.",
            metadata={"title": "근로계약 안내", "source": "고용노동부"},
        ),
        Document(
            page_content="퇴직금은 계속근로기간 1년에 대해 30일분 이상의 평균임금을 지급합니다.",
            metadata={"title": "퇴직금 계산", "source": "고용노동부"},
        ),
        Document(
            page_content="4대보험은 국민연금, 건강보험, 고용보험, 산재보험으로 구성됩니다.",
            metadata={"title": "4대보험 안내", "source": "국민건강보험공단"},
        ),
        Document(
            page_content="정부 창업 지원사업은 기업마당에서 확인할 수 있습니다.",
            metadata={"title": "지원사업 안내", "source": "중소벤처기업부"},
        ),
        Document(
            page_content="마케팅 전략은 타겟 고객 분석부터 시작해야 합니다.",
            metadata={"title": "마케팅 가이드", "source": "창업진흥원"},
        ),
        Document(
            page_content="연차휴가는 1년간 80% 이상 출근한 근로자에게 15일이 부여됩니다.",
            metadata={"title": "연차휴가 안내", "source": "고용노동부"},
        ),
        Document(
            page_content="주52시간제는 주 40시간 + 연장근로 12시간이 상한입니다.",
            metadata={"title": "근로시간 규정", "source": "고용노동부"},
        ),
    ]


@pytest.fixture(autouse=True)
def cleanup_singleton():
    """각 테스트 전후로 싱글톤 리셋."""
    reset_reranker()
    yield
    reset_reranker()


class TestCrossEncoderReranker:
    """CrossEncoderReranker 테스트."""

    def test_rerank_basic(self, sample_documents):
        """기본 재정렬 기능 테스트."""
        reranker = CrossEncoderReranker()
        query = "세금 신고 방법"

        result = reranker.rerank(query, sample_documents, top_k=3)

        assert len(result) == 3
        assert all(isinstance(doc, Document) for doc in result)

    def test_rerank_returns_all_when_less_than_top_k(self):
        """top_k보다 문서 수가 적으면 전체 반환."""
        reranker = CrossEncoderReranker()
        docs = [
            Document(page_content="테스트 문서 1", metadata={}),
            Document(page_content="테스트 문서 2", metadata={}),
        ]

        result = reranker.rerank("쿼리", docs, top_k=5)

        assert len(result) == 2

    def test_rerank_relevance_order(self, sample_documents):
        """관련성 높은 문서가 상위로 정렬되는지 테스트."""
        reranker = CrossEncoderReranker()
        query = "퇴직금 계산 방법"

        result = reranker.rerank(query, sample_documents, top_k=3)

        # 퇴직금 관련 문서가 상위에 있어야 함
        top_contents = [doc.page_content for doc in result]
        assert any("퇴직금" in content for content in top_contents)

    def test_rerank_with_empty_documents(self):
        """빈 문서 리스트 처리."""
        reranker = CrossEncoderReranker()

        result = reranker.rerank("쿼리", [], top_k=3)

        assert result == []

    @pytest.mark.asyncio
    async def test_arerank_basic(self, sample_documents):
        """비동기 재정렬 기능 테스트."""
        reranker = CrossEncoderReranker()
        query = "세금 신고 방법"

        result = await reranker.arerank(query, sample_documents, top_k=3)

        assert len(result) == 3
        assert all(isinstance(doc, Document) for doc in result)


class TestLLMReranker:
    """LLMReranker 테스트."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-test"),
        reason="실제 OPENAI_API_KEY 필요"
    )
    def test_rerank_basic(self, sample_documents):
        """기본 재정렬 기능 테스트 (실제 API 호출)."""
        reranker = LLMReranker()
        query = "세금 신고 방법"

        result = reranker.rerank(query, sample_documents[:5], top_k=3)

        assert len(result) == 3
        assert all(isinstance(doc, Document) for doc in result)

    def test_rerank_returns_all_when_less_than_top_k(self):
        """top_k보다 문서 수가 적으면 전체 반환 (API 호출 없음)."""
        reranker = LLMReranker()
        docs = [
            Document(page_content="테스트 문서 1", metadata={}),
            Document(page_content="테스트 문서 2", metadata={}),
        ]

        result = reranker.rerank("쿼리", docs, top_k=5)

        assert len(result) == 2

    def test_parse_score_valid(self):
        """점수 파싱 테스트 - 유효한 입력."""
        reranker = LLMReranker()

        assert reranker._parse_score("8") == 8.0
        assert reranker._parse_score("점수: 9") == 9.0
        assert reranker._parse_score("7.5점입니다") == 7.5

    def test_parse_score_clamping(self):
        """점수 파싱 테스트 - 범위 클램핑."""
        reranker = LLMReranker()

        assert reranker._parse_score("15") == 10.0
        assert reranker._parse_score("-5") == 5.0  # 정규식이 5 추출
        assert reranker._parse_score("abc") == 5.0  # 숫자 없음, 기본값

    def test_parse_score_invalid(self):
        """점수 파싱 테스트 - 유효하지 않은 입력."""
        reranker = LLMReranker()

        assert reranker._parse_score("관련 없음") == 5.0  # 기본값
        assert reranker._parse_score("") == 5.0


class TestGetReranker:
    """get_reranker 팩토리 함수 테스트."""

    def test_get_cross_encoder_reranker(self):
        """Cross-Encoder Reranker 생성."""
        reranker = get_reranker("cross-encoder")

        assert isinstance(reranker, CrossEncoderReranker)

    def test_get_llm_reranker(self):
        """LLM Reranker 생성."""
        reranker = get_reranker("llm")

        assert isinstance(reranker, LLMReranker)

    def test_singleton_pattern(self):
        """싱글톤 패턴 검증."""
        reranker1 = get_reranker("cross-encoder")
        reranker2 = get_reranker("cross-encoder")

        assert reranker1 is reranker2

    def test_singleton_type_change(self):
        """타입 변경 시 새 인스턴스 생성."""
        reranker1 = get_reranker("cross-encoder")
        reranker2 = get_reranker("llm")

        assert reranker1 is not reranker2
        assert isinstance(reranker1, CrossEncoderReranker)
        assert isinstance(reranker2, LLMReranker)

    def test_invalid_reranker_type(self):
        """유효하지 않은 타입 에러 처리."""
        with pytest.raises(ValueError, match="지원하지 않는 reranker_type"):
            get_reranker("invalid-type")

    def test_reset_reranker(self):
        """싱글톤 리셋 테스트."""
        reranker1 = get_reranker("cross-encoder")
        reset_reranker()
        reranker2 = get_reranker("cross-encoder")

        # 리셋 후에는 새 인스턴스가 생성됨
        assert reranker1 is not reranker2

    def test_default_type_from_settings(self):
        """설정에서 기본 타입 가져오기."""
        # 설정의 기본값은 cross-encoder
        reranker = get_reranker()

        assert isinstance(reranker, CrossEncoderReranker)


class TestBaseReranker:
    """BaseReranker 추상 클래스 테스트."""

    def test_is_abstract(self):
        """추상 클래스는 인스턴스화 불가."""
        with pytest.raises(TypeError):
            BaseReranker()

    def test_subclass_must_implement_methods(self):
        """서브클래스는 필수 메서드 구현 필요."""

        class IncompleteReranker(BaseReranker):
            pass

        with pytest.raises(TypeError):
            IncompleteReranker()
