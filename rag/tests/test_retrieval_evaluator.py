"""규칙 기반 검색 평가기 테스트."""

from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from utils.retrieval_evaluator import RuleBasedRetrievalEvaluator


def _settings(
    min_doc_count: int = 1,
    min_keyword_match_ratio: float = 0.0,
    min_avg_similarity_score: float = 0.5,
) -> SimpleNamespace:
    """테스트용 settings 객체 생성."""
    return SimpleNamespace(
        min_retrieval_doc_count=min_doc_count,
        min_keyword_match_ratio=min_keyword_match_ratio,
        min_avg_similarity_score=min_avg_similarity_score,
    )


def test_evaluator_prefers_embedding_similarity_over_legacy_scores():
    """embedding_similarity가 있으면 legacy score보다 우선 사용해야 한다."""
    docs = [
        Document(
            page_content="세무 신고 관련 문서",
            metadata={"score": 0.95, "embedding_similarity": 0.2},
        ),
        Document(
            page_content="부가세 신고 안내",
            metadata={"score": 0.9, "embedding_similarity": 0.2},
        ),
    ]

    with patch("utils.retrieval_evaluator.get_settings", return_value=_settings()):
        evaluator = RuleBasedRetrievalEvaluator()
        result = evaluator.evaluate(
            query="세무 신고",
            documents=docs,
            scores=[0.95, 0.9],  # embedding 우선이면 무시되어야 함
        )

    assert result.passed is False
    assert result.details is not None
    assert result.details["quality_score_source"] == "embedding_similarity"
    assert result.avg_similarity_score == 0.2


def test_evaluator_pass_fail_based_on_embedding_similarity():
    """embedding_similarity 기반으로 PASS/FAIL이 갈려야 한다."""
    pass_docs = [
        Document(
            page_content="근로계약서 작성 안내",
            metadata={"embedding_similarity": 0.82},
        ),
    ]
    fail_docs = [
        Document(
            page_content="근로계약서 작성 안내",
            metadata={"embedding_similarity": 0.18},
        ),
    ]

    with patch("utils.retrieval_evaluator.get_settings", return_value=_settings()):
        evaluator = RuleBasedRetrievalEvaluator()
        pass_result = evaluator.evaluate("근로계약서", pass_docs)
        fail_result = evaluator.evaluate("근로계약서", fail_docs)

    assert pass_result.passed is True
    assert pass_result.details is not None
    assert pass_result.details["quality_score_source"] == "embedding_similarity"
    assert fail_result.passed is False
    assert fail_result.details is not None
    assert fail_result.details["quality_score_source"] == "embedding_similarity"


def test_evaluator_falls_back_to_legacy_score_when_embedding_missing():
    """embedding 정보가 없으면 기존 score 경로를 사용해야 한다."""
    docs = [
        Document(
            page_content="법인세 신고 안내",
            metadata={"score": 0.8},
        ),
    ]

    with patch("utils.retrieval_evaluator.get_settings", return_value=_settings()):
        evaluator = RuleBasedRetrievalEvaluator()
        result = evaluator.evaluate(
            query="법인세 신고",
            documents=docs,
            scores=[0.8],
        )

    assert result.passed is True
    assert result.details is not None
    assert result.details["quality_score_source"] == "legacy_score"
    assert result.avg_similarity_score == 0.8
