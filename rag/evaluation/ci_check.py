"""RAGAS CI 회귀 방지 스크립트.

평가 결과 JSON 파일의 메트릭이 임계값을 충족하는지 검증합니다.
임계값 미달 시 exit code 1을 반환하여 CI 파이프라인에서 실패 처리합니다.

사용법:
    python -m evaluation.ci_check --result results/ragas_v4_gpu.json
    python -m evaluation.ci_check --result results/ragas_v4_gpu.json --min-faithfulness 0.80 --min-recall 0.70
    python -m evaluation.ci_check --result results/ragas_v4_gpu.json --max-timeout 5
"""

import argparse
import json
import sys
from pathlib import Path

# 기본 임계값
DEFAULT_MIN_FAITHFULNESS = 0.75
DEFAULT_MIN_ANSWER_RELEVANCY = 0.85
DEFAULT_MIN_CONTEXT_PRECISION = 0.80
DEFAULT_MIN_CONTEXT_RECALL = 0.65
DEFAULT_MAX_TIMEOUT = 10
DEFAULT_MAX_TIMEOUT_RATIO = 0.15  # 15%


def check_thresholds(
    result_path: str,
    min_faithfulness: float = DEFAULT_MIN_FAITHFULNESS,
    min_answer_relevancy: float = DEFAULT_MIN_ANSWER_RELEVANCY,
    min_context_precision: float = DEFAULT_MIN_CONTEXT_PRECISION,
    min_context_recall: float = DEFAULT_MIN_CONTEXT_RECALL,
    max_timeout: int = DEFAULT_MAX_TIMEOUT,
    max_timeout_ratio: float = DEFAULT_MAX_TIMEOUT_RATIO,
    exclude_timeout: bool = True,
) -> bool:
    """결과 파일의 메트릭이 임계값을 충족하는지 검증합니다.

    Args:
        result_path: 결과 JSON 파일 경로
        min_faithfulness: 최소 Faithfulness 점수
        min_answer_relevancy: 최소 Answer Relevancy 점수
        min_context_precision: 최소 Context Precision 점수
        min_context_recall: 최소 Context Recall 점수
        max_timeout: 최대 허용 타임아웃 건수
        max_timeout_ratio: 최대 허용 타임아웃 비율
        exclude_timeout: True면 타임아웃 제외 평균으로 검증

    Returns:
        True면 모든 임계값 충족, False면 하나 이상 미달
    """
    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data["results"]
    total = len(results)
    timeout_count = sum(1 for r in results if r.get("timeout"))

    # 평균 계산
    if exclude_timeout:
        avg_key = "averages_excluding_timeout"
    else:
        avg_key = "averages"

    # 새 포맷에서는 averages_excluding_timeout이 있음, 없으면 직접 계산
    if avg_key in data and data[avg_key]:
        averages = data[avg_key]
    else:
        filtered = [r for r in results if not r.get("timeout")] if exclude_timeout else results
        averages = {}
        for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            values = [r["metrics"].get(key) for r in filtered if r["metrics"].get(key) is not None]
            averages[key] = sum(values) / len(values) if values else None

    # 검증
    failures: list[str] = []
    checks = [
        ("faithfulness", averages.get("faithfulness"), min_faithfulness),
        ("answer_relevancy", averages.get("answer_relevancy"), min_answer_relevancy),
        ("context_precision", averages.get("context_precision"), min_context_precision),
        ("context_recall", averages.get("context_recall"), min_context_recall),
    ]

    print(f"결과 파일: {result_path}")
    print(f"전체: {total}건, 타임아웃: {timeout_count}건, 유효: {total - timeout_count}건")
    timeout_label = " (타임아웃 제외)" if exclude_timeout else ""
    print(f"\n메트릭 검증{timeout_label}:")

    for name, actual, threshold in checks:
        if actual is None:
            status = "SKIP (데이터 없음)"
            print(f"  {name}: {status}")
            continue

        passed = actual >= threshold
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {actual:.4f} >= {threshold:.4f} → {status}")
        if not passed:
            failures.append(f"{name}: {actual:.4f} < {threshold:.4f}")

    # 타임아웃 검증
    timeout_ratio = timeout_count / total if total > 0 else 0
    timeout_passed = timeout_count <= max_timeout and timeout_ratio <= max_timeout_ratio
    timeout_status = "PASS" if timeout_passed else "FAIL"
    print(f"\n타임아웃 검증:")
    print(f"  건수: {timeout_count} <= {max_timeout} → {'PASS' if timeout_count <= max_timeout else 'FAIL'}")
    print(f"  비율: {timeout_ratio:.1%} <= {max_timeout_ratio:.0%} → {'PASS' if timeout_ratio <= max_timeout_ratio else 'FAIL'}")
    if not timeout_passed:
        failures.append(f"timeout: {timeout_count}건 ({timeout_ratio:.1%})")

    # 결과
    print(f"\n{'='*40}")
    if failures:
        print(f"FAILED -{len(failures)}개 임계값 미달:")
        for f in failures:
            print(f"  - {f}")
        return False
    else:
        print("PASSED -모든 임계값 충족")
        return True


def main() -> None:
    """CI 검증 CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="RAGAS CI 회귀 방지 -메트릭 임계값 검증"
    )
    parser.add_argument(
        "--result",
        "-r",
        required=True,
        help="결과 JSON 파일 경로",
    )
    parser.add_argument(
        "--min-faithfulness",
        type=float,
        default=DEFAULT_MIN_FAITHFULNESS,
        help=f"최소 Faithfulness (기본: {DEFAULT_MIN_FAITHFULNESS})",
    )
    parser.add_argument(
        "--min-relevancy",
        type=float,
        default=DEFAULT_MIN_ANSWER_RELEVANCY,
        help=f"최소 Answer Relevancy (기본: {DEFAULT_MIN_ANSWER_RELEVANCY})",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=DEFAULT_MIN_CONTEXT_PRECISION,
        help=f"최소 Context Precision (기본: {DEFAULT_MIN_CONTEXT_PRECISION})",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=DEFAULT_MIN_CONTEXT_RECALL,
        help=f"최소 Context Recall (기본: {DEFAULT_MIN_CONTEXT_RECALL})",
    )
    parser.add_argument(
        "--max-timeout",
        type=int,
        default=DEFAULT_MAX_TIMEOUT,
        help=f"최대 허용 타임아웃 건수 (기본: {DEFAULT_MAX_TIMEOUT})",
    )
    parser.add_argument(
        "--include-timeout",
        action="store_true",
        help="타임아웃 포함 전체 평균으로 검증 (기본: 타임아웃 제외)",
    )

    args = parser.parse_args()

    passed = check_thresholds(
        result_path=args.result,
        min_faithfulness=args.min_faithfulness,
        min_answer_relevancy=args.min_relevancy,
        min_context_precision=args.min_precision,
        min_context_recall=args.min_recall,
        max_timeout=args.max_timeout,
        exclude_timeout=not args.include_timeout,
    )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
