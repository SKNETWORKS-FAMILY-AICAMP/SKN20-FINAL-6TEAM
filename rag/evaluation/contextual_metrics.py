"""Deterministic contextual quality metrics for chat responses.

This module complements RAGAS by checking:
- directive coverage
- context adherence
- conflict-free response
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    return re.sub(r"\s+", " ", lowered)


def _contains_term(text: str, term: str) -> bool:
    return _normalize(term) in _normalize(text)


@dataclass(slots=True)
class ContextualCaseMetrics:
    directive_coverage: float | None
    context_adherence: float | None
    conflict_free: float | None
    score: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "directive_coverage": self.directive_coverage,
            "context_adherence": self.context_adherence,
            "conflict_free": self.conflict_free,
            "score": self.score,
        }


def evaluate_contextual_case(
    answer: str,
    required_directives: list[str] | None = None,
    required_context_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
) -> ContextualCaseMetrics:
    """Evaluate contextual quality from optional deterministic constraints."""
    directives = required_directives or []
    context_terms = required_context_terms or []
    forbidden = forbidden_terms or []

    def _ratio(terms: list[str]) -> float | None:
        if not terms:
            return None
        matched = sum(1 for term in terms if _contains_term(answer, term))
        return matched / len(terms)

    directive_coverage = _ratio(directives)
    context_adherence = _ratio(context_terms)

    if forbidden:
        has_forbidden = any(_contains_term(answer, term) for term in forbidden)
        conflict_free = 0.0 if has_forbidden else 1.0
    else:
        conflict_free = None

    components = [
        metric
        for metric in (directive_coverage, context_adherence, conflict_free)
        if metric is not None
    ]
    score = (sum(components) / len(components)) if components else None

    return ContextualCaseMetrics(
        directive_coverage=directive_coverage,
        context_adherence=context_adherence,
        conflict_free=conflict_free,
        score=score,
    )

