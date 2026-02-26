"""Tests for deterministic contextual metrics."""

from evaluation.contextual_metrics import evaluate_contextual_case


def test_contextual_metrics_full_match():
    metrics = evaluate_contextual_case(
        answer="세무 신고는 3월 말까지 하시고, 서울 기준으로 지원사업 신청하세요.",
        required_directives=["세무 신고", "3월 말"],
        required_context_terms=["서울", "지원사업"],
        forbidden_terms=["부산"],
    )
    result = metrics.to_dict()

    assert result["directive_coverage"] == 1.0
    assert result["context_adherence"] == 1.0
    assert result["conflict_free"] == 1.0
    assert result["score"] == 1.0


def test_contextual_metrics_partial_match():
    metrics = evaluate_contextual_case(
        answer="세무 신고를 준비하세요.",
        required_directives=["세무 신고", "3월 말"],
        required_context_terms=["서울"],
        forbidden_terms=["부산"],
    )
    result = metrics.to_dict()

    assert result["directive_coverage"] == 0.5
    assert result["context_adherence"] == 0.0
    assert result["conflict_free"] == 1.0
    assert result["score"] is not None


def test_contextual_metrics_forbidden_hit():
    metrics = evaluate_contextual_case(
        answer="부산 기준으로 안내드립니다.",
        forbidden_terms=["부산"],
    )
    result = metrics.to_dict()

    assert result["conflict_free"] == 0.0
    assert result["score"] == 0.0

