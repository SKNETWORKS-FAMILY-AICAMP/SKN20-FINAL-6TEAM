"""CI gate checker for RAG evaluation outputs."""

import argparse
import json
import sys

DEFAULT_MIN_FAITHFULNESS = 0.75
DEFAULT_MIN_ANSWER_RELEVANCY = 0.85
DEFAULT_MIN_CONTEXT_PRECISION = 0.80
DEFAULT_MIN_CONTEXT_RECALL = 0.65
DEFAULT_MAX_TIMEOUT = 10
DEFAULT_MAX_TIMEOUT_RATIO = 0.15

DEFAULT_MIN_DIRECTIVE_COVERAGE = 0.80
DEFAULT_MIN_CONTEXT_ADHERENCE = 0.80
DEFAULT_MIN_CONTEXTUAL_SCORE = 0.80


def _avg_from_results(results: list[dict], key: str, exclude_timeout: bool = True) -> float | None:
    selected = [item for item in results if not (exclude_timeout and item.get("timeout"))]
    values = []
    for item in selected:
        metrics = item.get("metrics", {})
        value = metrics.get(key)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return sum(values) / len(values)


def _avg_contextual_from_results(results: list[dict], key: str, exclude_timeout: bool = True) -> float | None:
    selected = [item for item in results if not (exclude_timeout and item.get("timeout"))]
    values = []
    for item in selected:
        metrics = item.get("contextual_metrics") or {}
        value = metrics.get(key)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return sum(values) / len(values)


def check_thresholds(
    result_path: str,
    min_faithfulness: float = DEFAULT_MIN_FAITHFULNESS,
    min_answer_relevancy: float = DEFAULT_MIN_ANSWER_RELEVANCY,
    min_context_precision: float = DEFAULT_MIN_CONTEXT_PRECISION,
    min_context_recall: float = DEFAULT_MIN_CONTEXT_RECALL,
    max_timeout: int = DEFAULT_MAX_TIMEOUT,
    max_timeout_ratio: float = DEFAULT_MAX_TIMEOUT_RATIO,
    exclude_timeout: bool = True,
    min_directive_coverage: float = DEFAULT_MIN_DIRECTIVE_COVERAGE,
    min_context_adherence: float = DEFAULT_MIN_CONTEXT_ADHERENCE,
    min_contextual_score: float = DEFAULT_MIN_CONTEXTUAL_SCORE,
    require_contextual: bool = False,
) -> bool:
    with open(result_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    results = data.get("results", [])
    total = len(results)
    timeout_count = sum(1 for result in results if result.get("timeout"))

    avg_key = "averages_excluding_timeout" if exclude_timeout else "averages"
    averages = data.get(avg_key) or data.get("averages") or {}
    if not averages:
        averages = {
            "faithfulness": _avg_from_results(results, "faithfulness", exclude_timeout),
            "answer_relevancy": _avg_from_results(results, "answer_relevancy", exclude_timeout),
            "context_precision": _avg_from_results(results, "context_precision", exclude_timeout),
            "context_recall": _avg_from_results(results, "context_recall", exclude_timeout),
        }

    contextual_averages = data.get("averages_contextual") or {
        "directive_coverage": _avg_contextual_from_results(results, "directive_coverage", exclude_timeout),
        "context_adherence": _avg_contextual_from_results(results, "context_adherence", exclude_timeout),
        "score": _avg_contextual_from_results(results, "score", exclude_timeout),
    }

    failures: list[str] = []

    checks = [
        ("faithfulness", averages.get("faithfulness"), min_faithfulness),
        ("answer_relevancy", averages.get("answer_relevancy"), min_answer_relevancy),
        ("context_precision", averages.get("context_precision"), min_context_precision),
        ("context_recall", averages.get("context_recall"), min_context_recall),
    ]

    print(f"result: {result_path}")
    print(f"total: {total}, timeout: {timeout_count}, valid: {total - timeout_count}")
    print("\nmetric checks:")

    for name, actual, threshold in checks:
        if actual is None:
            print(f"  {name}: SKIP (no data)")
            continue
        passed = actual >= threshold
        print(f"  {name}: {actual:.4f} >= {threshold:.4f} -> {'PASS' if passed else 'FAIL'}")
        if not passed:
            failures.append(f"{name}: {actual:.4f} < {threshold:.4f}")

    timeout_ratio = (timeout_count / total) if total > 0 else 0.0
    timeout_passed = timeout_count <= max_timeout and timeout_ratio <= max_timeout_ratio
    print("\ntimeout checks:")
    print(f"  count: {timeout_count} <= {max_timeout} -> {'PASS' if timeout_count <= max_timeout else 'FAIL'}")
    print(f"  ratio: {timeout_ratio:.1%} <= {max_timeout_ratio:.0%} -> {'PASS' if timeout_ratio <= max_timeout_ratio else 'FAIL'}")
    if not timeout_passed:
        failures.append(f"timeout: {timeout_count} ({timeout_ratio:.1%})")

    has_contextual = any(contextual_averages.get(key) is not None for key in ("directive_coverage", "context_adherence", "score"))
    if require_contextual and not has_contextual:
        failures.append("contextual: required but missing")

    if has_contextual:
        print("\ncontextual checks:")
        contextual_checks = [
            ("directive_coverage", contextual_averages.get("directive_coverage"), min_directive_coverage),
            ("context_adherence", contextual_averages.get("context_adherence"), min_context_adherence),
            ("contextual_score", contextual_averages.get("score"), min_contextual_score),
        ]
        for name, actual, threshold in contextual_checks:
            if actual is None:
                print(f"  {name}: SKIP (no data)")
                continue
            passed = actual >= threshold
            print(f"  {name}: {actual:.4f} >= {threshold:.4f} -> {'PASS' if passed else 'FAIL'}")
            if not passed:
                failures.append(f"{name}: {actual:.4f} < {threshold:.4f}")

    timeout_causes = data.get("timeout_causes") or {}
    if timeout_causes:
        print("\ntimeout causes:")
        for cause, count in timeout_causes.items():
            print(f"  {cause}: {count}")

    print("\n" + "=" * 40)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return False

    print("PASSED")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG evaluation CI checker")
    parser.add_argument("--result", "-r", required=True, help="result JSON path")
    parser.add_argument("--min-faithfulness", type=float, default=DEFAULT_MIN_FAITHFULNESS)
    parser.add_argument("--min-relevancy", type=float, default=DEFAULT_MIN_ANSWER_RELEVANCY)
    parser.add_argument("--min-precision", type=float, default=DEFAULT_MIN_CONTEXT_PRECISION)
    parser.add_argument("--min-recall", type=float, default=DEFAULT_MIN_CONTEXT_RECALL)
    parser.add_argument("--max-timeout", type=int, default=DEFAULT_MAX_TIMEOUT)
    parser.add_argument("--include-timeout", action="store_true")

    parser.add_argument("--min-directive-coverage", type=float, default=DEFAULT_MIN_DIRECTIVE_COVERAGE)
    parser.add_argument("--min-context-adherence", type=float, default=DEFAULT_MIN_CONTEXT_ADHERENCE)
    parser.add_argument("--min-contextual-score", type=float, default=DEFAULT_MIN_CONTEXTUAL_SCORE)
    parser.add_argument("--require-contextual", action="store_true")

    args = parser.parse_args()

    passed = check_thresholds(
        result_path=args.result,
        min_faithfulness=args.min_faithfulness,
        min_answer_relevancy=args.min_relevancy,
        min_context_precision=args.min_precision,
        min_context_recall=args.min_recall,
        max_timeout=args.max_timeout,
        exclude_timeout=not args.include_timeout,
        min_directive_coverage=args.min_directive_coverage,
        min_context_adherence=args.min_context_adherence,
        min_contextual_score=args.min_contextual_score,
        require_contextual=args.require_contextual,
    )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
