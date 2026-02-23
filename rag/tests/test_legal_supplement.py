"""법률 보충 검색 필요성 판단 모듈 단위 테스트."""

import pytest
from langchain_core.documents import Document

from utils.legal_supplement import needs_legal_supplement


def _make_doc(content: str) -> Document:
    """테스트용 Document를 생성합니다."""
    return Document(page_content=content, metadata={})


class TestNeedsLegalSupplement:
    """needs_legal_supplement() 함수 테스트."""

    def test_law_common_as_primary_domain_returns_false(self) -> None:
        """law_common이 주 도메인이면 보충 불필요."""
        result = needs_legal_supplement(
            query="상법에 따른 법인 설립 절차",
            documents=[_make_doc("법인 설립 관련 내용")],
            classified_domains=["law_common"],
        )
        assert result is False

    def test_law_common_in_multi_domains_returns_false(self) -> None:
        """law_common이 복합 도메인에 포함되어도 보충 불필요."""
        result = needs_legal_supplement(
            query="법률 관련 세무 질문",
            documents=[],
            classified_domains=["finance_tax", "law_common"],
        )
        assert result is False

    def test_query_with_legal_keyword_returns_true(self) -> None:
        """쿼리에 법률 키워드가 있으면 보충 필요."""
        result = needs_legal_supplement(
            query="직원 해고 시 손해배상 책임이 있나요?",
            documents=[],
            classified_domains=["hr_labor"],
        )
        assert result is True

    def test_query_with_multiple_legal_keywords_returns_true(self) -> None:
        """쿼리에 법률 키워드가 여러 개 있으면 보충 필요."""
        result = needs_legal_supplement(
            query="특허 출원 후 소송 절차가 궁금합니다",
            documents=[],
            classified_domains=["startup_funding"],
        )
        assert result is True

    def test_documents_with_legal_keywords_returns_true(self) -> None:
        """문서에 법률 키워드가 2개 이상이면 보충 필요."""
        docs = [
            _make_doc("사업자등록 시 상법 규정에 따라 법인을 설립해야 합니다."),
            _make_doc("부가세 신고 시 세법에 따른 판례를 참고하세요."),
        ]
        result = needs_legal_supplement(
            query="사업자등록 방법 알려주세요",
            documents=docs,
            classified_domains=["startup_funding"],
        )
        assert result is True

    def test_no_keywords_returns_false(self) -> None:
        """법률 키워드가 없으면 보충 불필요."""
        docs = [
            _make_doc("창업 지원금 신청 절차를 안내합니다."),
            _make_doc("중소기업 마케팅 전략에 대해 설명합니다."),
        ]
        result = needs_legal_supplement(
            query="창업 지원금 신청하려면 어떻게 해야 하나요?",
            documents=docs,
            classified_domains=["startup_funding"],
        )
        assert result is False

    def test_single_doc_keyword_not_enough(self) -> None:
        """문서에 법률 키워드가 1개만 있으면 보충 불필요 (임계값 2)."""
        docs = [
            _make_doc("창업 시 상법을 참고하면 좋습니다."),
            _make_doc("마케팅 전략을 세워보세요."),
        ]
        result = needs_legal_supplement(
            query="창업 절차 알려주세요",
            documents=docs,
            classified_domains=["startup_funding"],
        )
        assert result is False

    def test_empty_documents_no_query_keywords(self) -> None:
        """문서가 비어있고 쿼리에도 키워드가 없으면 보충 불필요."""
        result = needs_legal_supplement(
            query="사업 시작하고 싶어요",
            documents=[],
            classified_domains=["startup_funding"],
        )
        assert result is False

    def test_empty_domains_with_legal_query(self) -> None:
        """도메인 리스트가 비어있어도 쿼리에 법률 키워드가 있으면 보충 필요."""
        result = needs_legal_supplement(
            query="소송 절차가 궁금합니다",
            documents=[],
            classified_domains=[],
        )
        assert result is True

    def test_doc_content_limit_respected(self) -> None:
        """문서 내용 검사가 800자로 제한되는지 확인."""
        # 법률 키워드가 800자 이후에만 있는 문서
        padding = "가" * 900
        docs = [
            _make_doc(padding + "상법 규정에 따르면"),
            _make_doc(padding + "판례를 참고하세요"),
        ]
        result = needs_legal_supplement(
            query="세금 신고 방법",
            documents=docs,
            classified_domains=["finance_tax"],
        )
        assert result is False

    def test_finance_tax_domain_with_legal_query(self) -> None:
        """재무/세무 도메인에서 법률 키워드가 있으면 보충 필요."""
        result = needs_legal_supplement(
            query="세금 체납 시 벌금과 과태료는 얼마인가요?",
            documents=[],
            classified_domains=["finance_tax"],
        )
        assert result is True
