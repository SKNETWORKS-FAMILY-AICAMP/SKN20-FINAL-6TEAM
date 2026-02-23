"""RAGAS 평가 결과 분석 모듈.

results/ 디렉토리의 JSON 파일들을 수집하여
버전별 추이, 도메인별 분석, 타임아웃 분석, Markdown 리포트를 생성합니다.

사용법:
    python -m evaluation.results_analyzer
    python -m evaluation.results_analyzer --output report.md
    python -m evaluation.results_analyzer --files results/ragas_v4_improved.json results/ragas_v4_gpu.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
METRIC_KEYS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def load_result_file(path: Path) -> dict | None:
    """결과 JSON 파일을 로드합니다."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "results" not in data:
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def compute_metrics(results: list[dict], exclude_timeout: bool = False) -> dict[str, float | None]:
    """결과 리스트에서 메트릭 평균을 계산합니다."""
    filtered = results
    if exclude_timeout:
        filtered = [r for r in results if not r.get("timeout")]

    averages: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        values = []
        for r in filtered:
            metrics = r.get("metrics", {})
            val = metrics.get(key)
            if val is not None:
                values.append(val)
        averages[key] = round(sum(values) / len(values), 4) if values else None
    return averages


def analyze_single(data: dict) -> dict:
    """단일 결과 파일을 분석합니다."""
    results = data["results"]
    total = len(results)
    timeout_count = sum(1 for r in results if r.get("timeout"))
    valid_count = total - timeout_count

    # 전체 평균
    averages_all = compute_metrics(results, exclude_timeout=False)
    averages_valid = compute_metrics(results, exclude_timeout=True) if timeout_count > 0 else averages_all

    # CR < 0.5 문항 분석
    low_cr_items = []
    for r in results:
        cr = r.get("metrics", {}).get("context_recall")
        if cr is not None and cr < 0.5:
            low_cr_items.append({
                "question": r["question"][:80],
                "context_recall": cr,
                "timeout": r.get("timeout", False),
            })

    # Top 5 최고/최저 문항 (composite score 기준)
    scored_items = []
    for r in results:
        if r.get("timeout"):
            continue
        m = r.get("metrics", {})
        scores = [m.get(k) for k in METRIC_KEYS if m.get(k) is not None]
        if scores:
            scored_items.append({
                "question": r["question"][:80],
                "avg_score": round(sum(scores) / len(scores), 4),
                "metrics": m,
            })

    scored_items.sort(key=lambda x: x["avg_score"], reverse=True)
    top5 = scored_items[:5]
    bottom5 = scored_items[-5:] if len(scored_items) >= 5 else scored_items

    return {
        "total": total,
        "timeout_count": timeout_count,
        "valid_count": valid_count,
        "averages_all": averages_all,
        "averages_valid": averages_valid,
        "low_cr_count": len(low_cr_items),
        "low_cr_items": low_cr_items,
        "top5": top5,
        "bottom5": bottom5,
    }


def generate_comparison_table(file_analyses: list[tuple[str, dict]]) -> str:
    """여러 파일의 분석 결과를 비교 테이블로 생성합니다."""
    lines = []
    lines.append("## 버전별 점수 추이\n")

    # 헤더
    header = "| 메트릭 |"
    separator = "|--------|"
    for name, _ in file_analyses:
        header += f" {name} |"
        separator += "--------|"
    lines.append(header)
    lines.append(separator)

    # 메트릭 행
    for key in METRIC_KEYS:
        row = f"| {key} |"
        for _, analysis in file_analyses:
            val = analysis["averages_all"].get(key)
            row += f" {val:.4f} |" if val is not None else " - |"
        lines.append(row)

    # 타임아웃 행
    row = "| timeout |"
    for _, analysis in file_analyses:
        row += f" {analysis['timeout_count']}/{analysis['total']} |"
    lines.append(row)

    # 타임아웃 제외 평균
    if any(a["timeout_count"] > 0 for _, a in file_analyses):
        lines.append("\n### 타임아웃 제외 평균\n")
        header2 = "| 메트릭 |"
        sep2 = "|--------|"
        for name, _ in file_analyses:
            header2 += f" {name} |"
            sep2 += "--------|"
        lines.append(header2)
        lines.append(sep2)
        for key in METRIC_KEYS:
            row = f"| {key} |"
            for _, analysis in file_analyses:
                val = analysis["averages_valid"].get(key)
                row += f" {val:.4f} |" if val is not None else " - |"
            lines.append(row)

    return "\n".join(lines)


def generate_report(file_analyses: list[tuple[str, dict, dict]]) -> str:
    """Markdown 리포트를 생성합니다.

    Args:
        file_analyses: [(파일명, 원본데이터, 분석결과)] 리스트
    """
    lines = ["# RAGAS 평가 결과 분석 리포트\n"]

    # 비교 테이블
    comparisons = [(name, analysis) for name, _, analysis in file_analyses]
    lines.append(generate_comparison_table(comparisons))

    # 개별 파일 상세 분석
    for name, data, analysis in file_analyses:
        lines.append(f"\n---\n\n## {name}\n")
        lines.append(f"- 데이터셋: {data.get('dataset', 'N/A')}")
        lines.append(f"- 전체 문항: {analysis['total']}건")
        lines.append(f"- 타임아웃: {analysis['timeout_count']}건 ({analysis['timeout_count']/analysis['total']*100:.1f}%)")
        lines.append(f"- 유효 문항: {analysis['valid_count']}건")
        lines.append(f"- CR < 0.5 문항: {analysis['low_cr_count']}건\n")

        # Top 5 문항
        if analysis["top5"]:
            lines.append("### Top 5 문항 (평균 점수 기준)\n")
            lines.append("| # | 질문 | 평균 |")
            lines.append("|---|------|------|")
            for i, item in enumerate(analysis["top5"], 1):
                lines.append(f"| {i} | {item['question']} | {item['avg_score']:.4f} |")

        # Bottom 5 문항
        if analysis["bottom5"]:
            lines.append("\n### Bottom 5 문항\n")
            lines.append("| # | 질문 | 평균 |")
            lines.append("|---|------|------|")
            for i, item in enumerate(analysis["bottom5"], 1):
                lines.append(f"| {i} | {item['question']} | {item['avg_score']:.4f} |")

        # Low CR 문항 상세
        if analysis["low_cr_items"]:
            lines.append(f"\n### Context Recall < 0.5 문항 ({analysis['low_cr_count']}건)\n")
            lines.append("| # | 질문 | CR | 타임아웃 |")
            lines.append("|---|------|----|----|")
            for i, item in enumerate(analysis["low_cr_items"], 1):
                timeout_str = "Y" if item["timeout"] else ""
                lines.append(f"| {i} | {item['question']} | {item['context_recall']:.4f} | {timeout_str} |")

    return "\n".join(lines)


def main() -> None:
    """결과 분석 CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="RAGAS 평가 결과 분석 -버전별 추이, 도메인별 분석, Markdown 리포트"
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="분석할 JSON 파일 경로 (미지정 시 results/ 디렉토리 전체 스캔)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Markdown 리포트 저장 경로",
    )
    args = parser.parse_args()

    # 파일 수집
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        if not RESULTS_DIR.exists():
            print(f"결과 디렉토리가 없습니다: {RESULTS_DIR}")
            return
        paths = sorted(RESULTS_DIR.glob("ragas_*.json"))

    if not paths:
        print("분석할 결과 파일이 없습니다.")
        return

    # 파일 로드 및 분석
    file_analyses: list[tuple[str, dict, dict]] = []
    for path in paths:
        data = load_result_file(path)
        if data is None:
            print(f"  건너뜀 (파싱 실패): {path.name}")
            continue
        analysis = analyze_single(data)
        name = path.stem
        file_analyses.append((name, data, analysis))
        print(f"  로드 완료: {name} ({analysis['total']}건, timeout={analysis['timeout_count']})")

    if not file_analyses:
        print("유효한 결과 파일이 없습니다.")
        return

    # 리포트 생성
    report = generate_report(file_analyses)

    # 콘솔 출력
    print("\n" + report)

    # 파일 저장
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n리포트 저장됨: {args.output}")


if __name__ == "__main__":
    main()
