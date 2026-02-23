"""토글 조합 최적화 테스트.

11개 토글 기능의 최적 조합을 찾기 위한 체계적 테스트를 수행합니다.

전략:
  Phase 1: 기본값(all ON) 기준 baseline 측정
  Phase 2: 개별 토글 Off (8개 ON→OFF, 3개 OFF→ON) - 각 토글의 독립 영향 측정
  Phase 3: Phase 2에서 효과 있는 조합만 테스트

사용법:
    cd rag
    py -m evaluation.toggle_optimization
    py -m evaluation.toggle_optimization --phase 1      # baseline만
    py -m evaluation.toggle_optimization --phase 1,2    # baseline + 개별
    py -m evaluation.toggle_optimization --queries 5    # 쿼리 수 제한
"""

import argparse
import asyncio
import io
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Windows cp949 인코딩 이슈 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import get_settings, reset_settings

logger = logging.getLogger(__name__)

BENCHMARK_PATH = Path(__file__).parent.parent / "tests" / "benchmark" / "benchmark_dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


# ──────────────────────────────────────────────────────────────
# 토글 정의
# ──────────────────────────────────────────────────────────────

# 기본 ON (OFF로 테스트) - 8개
TOGGLES_DEFAULT_ON: dict[str, str] = {
    "enable_fixed_doc_limit": "Fixed Doc Limit",
    "enable_cross_domain_rerank": "Cross-Domain Rerank",
    "enable_legal_supplement": "Legal Supplement",
    "enable_adaptive_search": "Adaptive Search",
    "enable_dynamic_k": "Dynamic K",
    "enable_post_eval_retry": "Post-Eval Retry",
    "enable_graduated_retry": "Graduated Retry",
    "enable_action_aware_generation": "Action-Aware Generation",
}

# 기본 OFF (ON으로 테스트) - 3개
TOGGLES_DEFAULT_OFF: dict[str, str] = {
    "enable_context_compression": "Context Compression",
    "enable_llm_domain_classification": "LLM Domain Classification",
    "enable_ragas_evaluation": "RAGAS Evaluation",
}

# Weight 테스트값
WEIGHT_VARIANTS: list[tuple[str, float]] = [
    ("weight_0.3_bm25_heavy", 0.3),
    ("weight_0.5_balanced", 0.5),
    ("weight_0.7_default", 0.7),
    ("weight_0.9_vector_heavy", 0.9),
]


@dataclass
class TestResult:
    """개별 테스트 결과."""
    config_name: str
    overrides: dict[str, Any]
    avg_score: float
    avg_time: float
    scores: list[float]
    times: list[float]
    query_details: list[dict[str, Any]] = field(default_factory=list)


def _print(msg: str) -> None:
    print(msg, flush=True)


def _load_benchmark() -> list[dict[str, Any]]:
    """벤치마크 데이터셋 로드."""
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"벤치마크 데이터셋 없음: {BENCHMARK_PATH}")
    items: list[dict[str, Any]] = []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _select_queries(benchmark: list[dict], max_per_domain: int = 2) -> list[dict]:
    """도메인별 균등 선택."""
    selected: list[dict] = []
    domain_counts: dict[str, int] = {}
    for item in benchmark:
        d = item["domain"]
        if domain_counts.get(d, 0) < max_per_domain:
            selected.append(item)
            domain_counts[d] = domain_counts.get(d, 0) + 1
    return selected


async def _run_config(
    config_name: str,
    overrides: dict[str, Any],
    queries: list[dict],
) -> TestResult:
    """단일 설정으로 테스트 실행."""
    from agents.router import MainRouter
    from vectorstores.chroma import ChromaVectorStore

    # 설정 오버라이드
    reset_settings()
    settings = get_settings()
    for k, v in overrides.items():
        settings.override(**{k: v})

    vs = ChromaVectorStore()
    router = MainRouter(vector_store=vs)

    scores: list[float] = []
    times: list[float] = []
    details: list[dict[str, Any]] = []

    for item in queries:
        question = item["question"]
        domain = item["domain"]
        try:
            start = time.time()
            response = await router.aprocess(query=question)
            elapsed = time.time() - start

            llm_score = response.evaluation.total_score if response.evaluation else 0
            scores.append(llm_score)
            times.append(elapsed)

            details.append({
                "question": question,
                "domain": domain,
                "score": llm_score,
                "time": round(elapsed, 2),
                "detected_domain": response.domain,
            })

            _print(f"    {question[:40]:40s} score={llm_score:3.0f} time={elapsed:.1f}s domain={response.domain}")
        except Exception as e:
            logger.error(f"테스트 실패 [{config_name}]: {e}")
            scores.append(0)
            times.append(0)
            details.append({
                "question": question,
                "domain": domain,
                "score": 0,
                "time": 0,
                "error": str(e),
            })
            _print(f"    {question[:40]:40s} ERROR: {e}")

    avg_score = sum(scores) / len(scores) if scores else 0
    avg_time = sum(times) / len(times) if times else 0

    return TestResult(
        config_name=config_name,
        overrides=overrides,
        avg_score=round(avg_score, 2),
        avg_time=round(avg_time, 2),
        scores=[round(s, 2) for s in scores],
        times=[round(t, 2) for t in times],
        query_details=details,
    )


async def phase1_baseline(queries: list[dict]) -> TestResult:
    """Phase 1: 기본 설정(모든 기본값) baseline."""
    _print("\n" + "=" * 70)
    _print("Phase 1: Baseline (all defaults)")
    _print("=" * 70)

    result = await _run_config("baseline", {}, queries)
    _print(f"\n  >>> Baseline: avg_score={result.avg_score:.1f}, avg_time={result.avg_time:.1f}s")
    return result


async def phase2_individual(queries: list[dict]) -> list[TestResult]:
    """Phase 2: 개별 토글 영향 측정."""
    _print("\n" + "=" * 70)
    _print("Phase 2: Individual Toggle Tests")
    _print("=" * 70)

    results: list[TestResult] = []

    # 기본 ON → OFF 테스트 (8개)
    for toggle_key, label in TOGGLES_DEFAULT_ON.items():
        _print(f"\n  [{label}] OFF")
        result = await _run_config(
            f"{label}_OFF",
            {toggle_key: False},
            queries,
        )
        results.append(result)
        _print(f"  >>> {label} OFF: avg_score={result.avg_score:.1f}, avg_time={result.avg_time:.1f}s")

    # 기본 OFF → ON 테스트 (3개)
    for toggle_key, label in TOGGLES_DEFAULT_OFF.items():
        _print(f"\n  [{label}] ON")
        result = await _run_config(
            f"{label}_ON",
            {toggle_key: True},
            queries,
        )
        results.append(result)
        _print(f"  >>> {label} ON: avg_score={result.avg_score:.1f}, avg_time={result.avg_time:.1f}s")

    # Weight 변형 테스트
    for name, weight in WEIGHT_VARIANTS:
        _print(f"\n  [Vector Weight = {weight}]")
        result = await _run_config(
            name,
            {"vector_search_weight": weight},
            queries,
        )
        results.append(result)
        _print(f"  >>> weight={weight}: avg_score={result.avg_score:.1f}, avg_time={result.avg_time:.1f}s")

    return results


def _print_summary(baseline: TestResult, individual: list[TestResult]) -> None:
    """결과 요약 표 출력."""
    _print("\n" + "=" * 70)
    _print("SUMMARY: Toggle Impact Analysis")
    _print("=" * 70)

    _print(f"\n  {'설정':<30s} {'점수':>6s} {'차이':>6s} {'시간':>7s} {'시간차':>7s}")
    _print(f"  {'-' * 56}")
    _print(f"  {'BASELINE (defaults)':<30s} {baseline.avg_score:>6.1f} {'':>6s} {baseline.avg_time:>6.1f}s {'':>7s}")

    for r in individual:
        score_diff = r.avg_score - baseline.avg_score
        time_diff = r.avg_time - baseline.avg_time
        score_mark = "+" if score_diff > 0 else ""
        time_mark = "+" if time_diff > 0 else ""
        _print(
            f"  {r.config_name:<30s} {r.avg_score:>6.1f} {score_mark}{score_diff:>5.1f} "
            f"{r.avg_time:>6.1f}s {time_mark}{time_diff:>5.1f}s"
        )

    # 점수 기준 정렬
    _print(f"\n{'=' * 70}")
    _print("RANKING (by score)")
    _print(f"{'=' * 70}")

    all_results = [baseline] + individual
    ranked = sorted(all_results, key=lambda r: r.avg_score, reverse=True)
    for i, r in enumerate(ranked, 1):
        _print(f"  {i:2d}. {r.config_name:<30s} score={r.avg_score:.1f}  time={r.avg_time:.1f}s")


def _save_results(
    baseline: TestResult,
    individual: list[TestResult],
) -> Path:
    """결과를 JSON으로 저장."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"toggle_optimization_{ts}.json"

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "config_name": baseline.config_name,
            "avg_score": baseline.avg_score,
            "avg_time": baseline.avg_time,
            "query_details": baseline.query_details,
        },
        "individual_tests": [
            {
                "config_name": r.config_name,
                "overrides": r.overrides,
                "avg_score": r.avg_score,
                "avg_time": r.avg_time,
                "score_diff": round(r.avg_score - baseline.avg_score, 2),
                "time_diff": round(r.avg_time - baseline.avg_time, 2),
                "query_details": r.query_details,
            }
            for r in individual
        ],
        "ranking": [
            {"rank": i + 1, "config": r.config_name, "score": r.avg_score, "time": r.avg_time}
            for i, r in enumerate(
                sorted([baseline] + individual, key=lambda r: r.avg_score, reverse=True)
            )
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    _print(f"\n결과 저장: {path}")
    return path


async def main() -> None:
    """메인 실행."""
    parser = argparse.ArgumentParser(description="Toggle Optimization Test")
    parser.add_argument(
        "--phase", type=str, default="1,2",
        help="실행할 Phase (1=baseline, 2=individual, 3=combination). 예: 1,2",
    )
    parser.add_argument(
        "--queries", type=int, default=2,
        help="도메인별 쿼리 수 (기본 2, 총 8개)",
    )
    args = parser.parse_args()

    phases = [int(p.strip()) for p in args.phase.split(",")]

    # 로깅 설정 (WARNING만)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    benchmark = _load_benchmark()
    queries = _select_queries(benchmark, max_per_domain=args.queries)
    _print(f"테스트 쿼리: {len(queries)}개 (도메인별 {args.queries}개)")

    baseline: TestResult | None = None
    individual: list[TestResult] = []

    if 1 in phases:
        baseline = await phase1_baseline(queries)

    if 2 in phases:
        if baseline is None:
            baseline = await phase1_baseline(queries)
        individual = await phase2_individual(queries)

    if baseline and individual:
        _print_summary(baseline, individual)
        _save_results(baseline, individual)
    elif baseline:
        _print(f"\nBaseline만 실행 완료: score={baseline.avg_score:.1f}, time={baseline.avg_time:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
