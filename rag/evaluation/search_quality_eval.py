"""5단계 검색 품질 평가 시스템.

VectorDB 재구축 후 검색 품질을 체계적으로 검증합니다.

Stage 1: 컬렉션 통계 검증 (API 불필요)
Stage 2: 검색 정확도 테스트 (API 불필요)
Stage 3: 노이즈 제거 검증 (API 불필요)
Stage 4: RAGAS 정량 평가 (OpenAI API 필요)
Stage 5: A/B 기능 비교 (OpenAI API 필요)

사용법:
    cd rag
    py -m evaluation.search_quality_eval --stage all
    py -m evaluation.search_quality_eval --stage 1,2,3
    py -m evaluation.search_quality_eval --stage 4 --quiet
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

# 상수
BENCHMARK_PATH = Path(__file__).parent.parent / "tests" / "benchmark" / "benchmark_dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
SEPARATOR = "=" * 80
SUBSEP = "-" * 80


# ──────────────────────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────────────────────

@dataclass
class StageResult:
    """개별 단계 평가 결과."""

    stage: int
    name: str
    passed: bool
    score: float  # 0.0 ~ 1.0
    duration: float  # 초
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    """전체 평가 보고서."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stages: list[StageResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        return all(s.passed for s in self.stages)

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_passed": self.overall_passed,
            "stages": [
                {
                    "stage": s.stage,
                    "name": s.name,
                    "passed": s.passed,
                    "score": round(s.score, 4),
                    "duration": round(s.duration, 2),
                }
                for s in self.stages
            ],
        }


# ──────────────────────────────────────────────────────────────
# 메인 평가 클래스
# ──────────────────────────────────────────────────────────────

class SearchQualityEvaluator:
    """5단계 검색 품질 평가 오케스트레이터."""

    # Stage 1 기대값
    EXPECTED_COLLECTIONS = {
        "startup_funding": (1_000, 5_000),
        "finance_tax": (10_000, 30_000),
        "hr_labor": (5_000, 20_000),
        "law_common": (140_000, 180_000),
    }

    # Stage 2 합격 기준
    KEYWORD_MATCH_THRESHOLD = 0.50
    DOMAIN_ALIGNMENT_THRESHOLD = 0.80

    # Stage 3 합격 기준
    NOISE_REMOVAL_THRESHOLD = 0.85
    ESSENTIAL_INCLUSION_THRESHOLD = 0.70

    # Stage 4 합격 기준
    LLM_SCORE_THRESHOLD = 70

    def __init__(self, quiet: bool = False) -> None:
        self._quiet = quiet
        self._vector_store: ChromaVectorStore | None = None

    def _get_vector_store(self) -> ChromaVectorStore:
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore()
        return self._vector_store

    def _print(self, msg: str = "") -> None:
        if not self._quiet:
            print(msg)

    def _load_benchmark(self) -> list[dict[str, Any]]:
        """벤치마크 데이터셋을 로드합니다."""
        if not BENCHMARK_PATH.exists():
            raise FileNotFoundError(f"벤치마크 데이터셋 없음: {BENCHMARK_PATH}")
        items: list[dict[str, Any]] = []
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    async def run(self, stages: list[int]) -> EvalReport:
        """지정된 단계들을 실행하고 보고서를 반환합니다.

        Args:
            stages: 실행할 단계 번호 리스트 (예: [1, 2, 3])

        Returns:
            전체 평가 보고서
        """
        report = EvalReport()

        stage_map = {
            1: ("컬렉션 통계 검증", self._stage1_collection_stats),
            2: ("검색 정확도 테스트", self._stage2_search_accuracy),
            3: ("노이즈 제거 검증", self._stage3_noise_removal),
            4: ("RAGAS 정량 평가", self._stage4_ragas_evaluation),
            5: ("A/B 기능 비교", self._stage5_ab_comparison),
        }

        for stage_num in sorted(stages):
            if stage_num not in stage_map:
                self._print(f"[SKIP] Stage {stage_num}: 알 수 없는 단계")
                continue

            name, func = stage_map[stage_num]
            self._print(f"\n{SEPARATOR}")
            self._print(f"  Stage {stage_num}: {name}")
            self._print(SEPARATOR)

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()
                report.stages.append(result)
                status = "PASS" if result.passed else "FAIL"
                self._print(
                    f"\n  => [{status}] score={result.score:.2%}, "
                    f"time={result.duration:.1f}s"
                )
            except Exception as e:
                logger.error(f"Stage {stage_num} 오류: {e}", exc_info=True)
                report.stages.append(
                    StageResult(
                        stage=stage_num,
                        name=name,
                        passed=False,
                        score=0.0,
                        duration=0.0,
                        errors=[str(e)],
                    )
                )
                self._print(f"\n  => [ERROR] {e}")

        # 결과 요약
        self._print(f"\n{SEPARATOR}")
        self._print("  평가 결과 요약")
        self._print(SEPARATOR)
        for s in report.stages:
            status = "PASS" if s.passed else "FAIL"
            self._print(f"  Stage {s.stage}: [{status}] {s.name} ({s.score:.2%})")
        overall = "PASS" if report.overall_passed else "FAIL"
        self._print(f"\n  전체: [{overall}]")

        # 정리
        if self._vector_store:
            self._vector_store.close()
            self._vector_store = None

        return report

    # ──────────────────────────────────────────────────────────
    # Stage 1: 컬렉션 통계 검증
    # ──────────────────────────────────────────────────────────

    def _stage1_collection_stats(self) -> StageResult:
        """컬렉션별 문서 수가 기대 범위 안인지 검증합니다."""
        start = time.time()
        vs = self._get_vector_store()
        stats = vs.get_all_stats()

        checks: list[dict[str, Any]] = []
        pass_count = 0
        total_docs = 0

        for domain, (low, high) in self.EXPECTED_COLLECTIONS.items():
            info = stats.get(domain, {})
            count = info.get("count", 0)
            total_docs += count
            ok = low <= count <= high

            check = {
                "domain": domain,
                "collection": info.get("name", "?"),
                "count": count,
                "expected_range": [low, high],
                "passed": ok,
            }
            checks.append(check)
            if ok:
                pass_count += 1

            status = "OK" if ok else "FAIL"
            self._print(
                f"  {domain:20s}: {count:>8,} 문서  "
                f"(기대: {low:,}~{high:,})  [{status}]"
            )

        score = pass_count / len(self.EXPECTED_COLLECTIONS) if self.EXPECTED_COLLECTIONS else 0
        self._print(f"\n  총 문서 수: {total_docs:,}")

        return StageResult(
            stage=1,
            name="컬렉션 통계 검증",
            passed=score == 1.0,
            score=score,
            duration=time.time() - start,
            details={"checks": checks, "total_docs": total_docs},
        )

    # ──────────────────────────────────────────────────────────
    # Stage 2: 검색 정확도 테스트
    # ──────────────────────────────────────────────────────────

    def _stage2_search_accuracy(self) -> StageResult:
        """벤치마크 30개 쿼리의 키워드 매칭률과 유사도 거리를 측정합니다."""
        start = time.time()
        vs = self._get_vector_store()
        benchmark = self._load_benchmark()

        results: list[dict[str, Any]] = []
        domain_scores: dict[str, list[float]] = {}
        total_keyword_match = 0.0
        total_domain_aligned = 0

        for item in benchmark:
            qid = item["id"]
            question = item["question"]
            expected_domain = item["domain"]
            expected_keywords = item.get("expected_keywords", [])

            # law_common에서 검색 (공통 법령 DB)
            search_results = vs.similarity_search_with_score(
                query=question, domain="law_common", k=5
            )

            # 키워드 매칭률
            if expected_keywords:
                matched = 0
                combined_text = " ".join(
                    doc.page_content + " " + doc.metadata.get("title", "")
                    for doc, _ in search_results
                )
                for kw in expected_keywords:
                    if kw in combined_text:
                        matched += 1
                kw_ratio = matched / len(expected_keywords)
            else:
                kw_ratio = 0.0

            total_keyword_match += kw_ratio

            # 평균 유사도 거리 (cosine distance, 낮을수록 좋음)
            distances = [score for _, score in search_results]
            avg_distance = sum(distances) / len(distances) if distances else 1.0

            # 도메인 정렬: 도메인 전용 DB에서도 검색하여 결과 존재 여부 확인
            domain_results = vs.similarity_search_with_score(
                query=question, domain=expected_domain, k=3
            )
            domain_aligned = len(domain_results) > 0
            if domain_aligned:
                total_domain_aligned += 1

            result = {
                "id": qid,
                "question": question[:50],
                "domain": expected_domain,
                "keyword_match_ratio": round(kw_ratio, 4),
                "avg_distance": round(avg_distance, 4),
                "domain_aligned": domain_aligned,
                "result_count": len(search_results),
            }
            results.append(result)

            if expected_domain not in domain_scores:
                domain_scores[expected_domain] = []
            domain_scores[expected_domain].append(kw_ratio)

            self._print(
                f"  [{qid:2d}] kw={kw_ratio:.0%} dist={avg_distance:.4f} "
                f"domain={'OK' if domain_aligned else 'MISS'} "
                f"| {question[:40]}"
            )

        n = len(benchmark)
        avg_keyword = total_keyword_match / n if n else 0
        domain_alignment = total_domain_aligned / n if n else 0

        # 도메인별 평균
        domain_avg = {}
        for d, scores in domain_scores.items():
            domain_avg[d] = round(sum(scores) / len(scores), 4) if scores else 0

        self._print(f"\n  평균 키워드 매칭률: {avg_keyword:.2%}")
        self._print(f"  도메인 정렬률: {domain_alignment:.2%}")
        for d, avg in domain_avg.items():
            self._print(f"    {d}: {avg:.2%}")

        passed = (
            avg_keyword >= self.KEYWORD_MATCH_THRESHOLD
            and domain_alignment >= self.DOMAIN_ALIGNMENT_THRESHOLD
        )
        score = (avg_keyword + domain_alignment) / 2

        return StageResult(
            stage=2,
            name="검색 정확도 테스트",
            passed=passed,
            score=score,
            duration=time.time() - start,
            details={
                "query_count": n,
                "avg_keyword_match": round(avg_keyword, 4),
                "domain_alignment": round(domain_alignment, 4),
                "domain_averages": domain_avg,
                "results": results,
            },
        )

    # ──────────────────────────────────────────────────────────
    # Stage 3: 노이즈 제거 검증
    # ──────────────────────────────────────────────────────────

    def _stage3_noise_removal(self) -> StageResult:
        """Part A: 무관한 법률이 제거되었는지, Part B: 필수 법령이 포함되는지 검증합니다."""
        from evaluation.negative_test_cases import (
            ESSENTIAL_LAW_TEST_CASES,
            NOISE_TEST_CASES,
        )

        start = time.time()
        vs = self._get_vector_store()

        # Part A: 노이즈 제거 확인
        self._print("\n  [Part A] 노이즈 제거 검증")
        noise_clean_count = 0
        noise_total = len(NOISE_TEST_CASES)
        noise_details: list[dict[str, Any]] = []

        for tc in NOISE_TEST_CASES:
            search_results = vs.similarity_search_with_score(
                query=tc["query"], domain=tc["domain"], k=10
            )

            found_noise = []
            for doc, _ in search_results:
                title = doc.metadata.get("title", "")
                content = doc.page_content[:200]
                combined = title + " " + content
                for kw in tc["noise_keywords"]:
                    if kw in combined:
                        found_noise.append(f"{kw} (in: {title[:30]})")

            is_clean = len(found_noise) == 0
            if is_clean:
                noise_clean_count += 1

            noise_details.append({
                "query": tc["query"][:40],
                "clean": is_clean,
                "found_noise": found_noise,
            })

            status = "CLEAN" if is_clean else "NOISE"
            self._print(f"    [{status}] {tc['query'][:50]}")
            if found_noise:
                for n in found_noise[:3]:
                    self._print(f"           -> {n}")

        noise_rate = noise_clean_count / noise_total if noise_total else 0

        # Part B: 필수 법령 포함 확인
        self._print(f"\n  [Part B] 필수 법령 포함 검증")
        essential_found_count = 0
        essential_total = len(ESSENTIAL_LAW_TEST_CASES)
        essential_details: list[dict[str, Any]] = []

        for tc in ESSENTIAL_LAW_TEST_CASES:
            search_results = vs.similarity_search_with_score(
                query=tc["query"], domain=tc["domain"], k=10
            )

            found_essential = []
            for doc, _ in search_results:
                title = doc.metadata.get("title", "")
                for kw in tc["essential_keywords"]:
                    if kw in title:
                        found_essential.append(title[:40])
                        break

            is_found = len(found_essential) > 0
            if is_found:
                essential_found_count += 1

            essential_details.append({
                "query": tc["query"][:40],
                "found": is_found,
                "matched_titles": found_essential,
            })

            status = "FOUND" if is_found else "MISS"
            self._print(f"    [{status}] {tc['query'][:50]}")
            if is_found:
                self._print(f"           -> {found_essential[0]}")

        essential_rate = essential_found_count / essential_total if essential_total else 0

        self._print(f"\n  노이즈 제거율: {noise_rate:.2%} (기준: {self.NOISE_REMOVAL_THRESHOLD:.0%})")
        self._print(f"  필수법령 포함률: {essential_rate:.2%} (기준: {self.ESSENTIAL_INCLUSION_THRESHOLD:.0%})")

        passed = (
            noise_rate >= self.NOISE_REMOVAL_THRESHOLD
            and essential_rate >= self.ESSENTIAL_INCLUSION_THRESHOLD
        )
        score = (noise_rate + essential_rate) / 2

        return StageResult(
            stage=3,
            name="노이즈 제거 검증",
            passed=passed,
            score=score,
            duration=time.time() - start,
            details={
                "noise_removal_rate": round(noise_rate, 4),
                "essential_inclusion_rate": round(essential_rate, 4),
                "noise_details": noise_details,
                "essential_details": essential_details,
            },
        )

    # ──────────────────────────────────────────────────────────
    # Stage 4: RAGAS 정량 평가
    # ──────────────────────────────────────────────────────────

    async def _stage4_ragas_evaluation(self) -> StageResult:
        """벤치마크 30개 쿼리를 MainRouter로 실행하고 LLM + RAGAS 평가합니다."""
        from agents.router import MainRouter
        from evaluation.ragas_evaluator import RagasEvaluator
        from utils.config import get_settings

        start = time.time()
        benchmark = self._load_benchmark()

        # 설정: RAGAS 활성화
        settings = get_settings()
        settings.override(enable_ragas_evaluation=True)

        vs = self._get_vector_store()
        router = MainRouter(vector_store=vs)
        ragas_eval = RagasEvaluator()

        query_results: list[dict[str, Any]] = []
        domain_llm_scores: dict[str, list[float]] = {}
        ragas_metrics_all: dict[str, list[float]] = {
            "faithfulness": [],
            "answer_relevancy": [],
            "context_precision": [],
        }

        n = len(benchmark)
        for i, item in enumerate(benchmark):
            question = item["question"]
            expected_domain = item["domain"]
            self._print(f"  [{i + 1}/{n}] {question[:50]}")

            try:
                response = await router.aprocess(query=question)

                # LLM 평가 점수
                llm_score = 0
                if response.evaluation:
                    llm_score = response.evaluation.total_score

                # RAGAS 메트릭
                ragas = response.ragas_metrics or {}

                # RAGAS가 파이프라인에서 비활성화된 경우 수동 평가
                if not ragas and ragas_eval.is_available:
                    contexts = [
                        s.content for s in response.sources if s.content and s.content.strip()
                    ]
                    if contexts:
                        ragas = await ragas_eval.aevaluate_answer_quality(
                            question=question,
                            answer=response.content,
                            contexts=contexts,
                        )

                result = {
                    "id": item["id"],
                    "question": question[:50],
                    "domain": expected_domain,
                    "detected_domain": response.domain,
                    "llm_score": llm_score,
                    "ragas": {k: round(v, 4) if v else None for k, v in ragas.items() if k != "error"},
                    "response_time": round(
                        response.timing_metrics.total_time if response.timing_metrics else 0, 2
                    ),
                }
                query_results.append(result)

                # 집계
                if expected_domain not in domain_llm_scores:
                    domain_llm_scores[expected_domain] = []
                domain_llm_scores[expected_domain].append(llm_score)

                for key in ragas_metrics_all:
                    val = ragas.get(key)
                    if val is not None:
                        ragas_metrics_all[key].append(val)

                self._print(
                    f"         LLM={llm_score}/100, "
                    f"faith={ragas.get('faithfulness', '-')}, "
                    f"relev={ragas.get('answer_relevancy', '-')}"
                )

            except Exception as e:
                logger.error(f"Query 실패: {question[:30]}: {e}")
                query_results.append({
                    "id": item["id"],
                    "question": question[:50],
                    "error": str(e),
                })

        # 전체 LLM 평균
        all_llm = [r.get("llm_score", 0) for r in query_results if "llm_score" in r]
        avg_llm = sum(all_llm) / len(all_llm) if all_llm else 0

        # 도메인별 평균
        domain_avg = {}
        for d, scores in domain_llm_scores.items():
            domain_avg[d] = round(sum(scores) / len(scores), 2) if scores else 0

        # RAGAS 평균
        ragas_avg = {}
        for k, vals in ragas_metrics_all.items():
            ragas_avg[k] = round(sum(vals) / len(vals), 4) if vals else None

        self._print(f"\n  LLM 평균 점수: {avg_llm:.1f}/100 (기준: {self.LLM_SCORE_THRESHOLD})")
        for d, avg in domain_avg.items():
            self._print(f"    {d}: {avg:.1f}")
        self._print(f"  RAGAS 평균:")
        for k, v in ragas_avg.items():
            self._print(f"    {k}: {v}")

        passed = avg_llm >= self.LLM_SCORE_THRESHOLD
        score = avg_llm / 100

        return StageResult(
            stage=4,
            name="RAGAS 정량 평가",
            passed=passed,
            score=score,
            duration=time.time() - start,
            details={
                "query_count": n,
                "avg_llm_score": round(avg_llm, 2),
                "domain_averages": domain_avg,
                "ragas_averages": ragas_avg,
                "results": query_results,
            },
        )

    # ──────────────────────────────────────────────────────────
    # Stage 5: A/B 기능 비교
    # ──────────────────────────────────────────────────────────

    async def _stage5_ab_comparison(self) -> StageResult:
        """4가지 설정으로 비교 테스트합니다."""
        from agents.router import MainRouter
        from utils.config import get_settings

        start = time.time()
        benchmark = self._load_benchmark()

        # 도메인별 2개씩 = 6개 쿼리 선택
        selected: list[dict[str, Any]] = []
        domain_counts: dict[str, int] = {}
        for item in benchmark:
            d = item["domain"]
            if domain_counts.get(d, 0) < 2:
                selected.append(item)
                domain_counts[d] = domain_counts.get(d, 0) + 1
            if len(selected) >= 6:
                break

        configs = {
            "A_all_on": {"enable_hybrid_search": True, "enable_reranking": True, "enable_query_rewrite": True},
            "B_no_hybrid": {"enable_hybrid_search": False, "enable_reranking": True, "enable_query_rewrite": True},
            "C_no_rerank": {"enable_hybrid_search": True, "enable_reranking": False, "enable_query_rewrite": True},
            "D_no_rewrite": {"enable_hybrid_search": True, "enable_reranking": True, "enable_query_rewrite": False},
        }

        config_results: dict[str, dict[str, Any]] = {}

        for config_name, overrides in configs.items():
            self._print(f"\n  [{config_name}] {overrides}")

            settings = get_settings()
            for k, v in overrides.items():
                settings.override(**{k: v})

            vs = self._get_vector_store()
            router = MainRouter(vector_store=vs)

            scores: list[float] = []
            times: list[float] = []

            for item in selected:
                question = item["question"]
                try:
                    response = await router.aprocess(query=question)
                    llm_score = response.evaluation.total_score if response.evaluation else 0
                    resp_time = response.timing_metrics.total_time if response.timing_metrics else 0
                    scores.append(llm_score)
                    times.append(resp_time)
                    self._print(f"    {question[:35]} => score={llm_score}, time={resp_time:.1f}s")
                except Exception as e:
                    logger.error(f"A/B 실패 [{config_name}]: {e}")
                    scores.append(0)
                    times.append(0)

            avg_score = sum(scores) / len(scores) if scores else 0
            avg_time = sum(times) / len(times) if times else 0
            config_results[config_name] = {
                "avg_score": round(avg_score, 2),
                "avg_time": round(avg_time, 2),
                "scores": [round(s, 2) for s in scores],
                "times": [round(t, 2) for t in times],
            }

        # 비교표 출력
        self._print(f"\n  {'설정':<20s} {'평균점수':>8s} {'평균시간':>8s}")
        self._print(f"  {SUBSEP[:40]}")
        for name, data in config_results.items():
            self._print(f"  {name:<20s} {data['avg_score']:>8.1f} {data['avg_time']:>7.1f}s")

        # A_all_on 대비 점수 차이
        baseline_score = config_results.get("A_all_on", {}).get("avg_score", 0)
        score = baseline_score / 100 if baseline_score else 0

        return StageResult(
            stage=5,
            name="A/B 기능 비교",
            passed=True,  # 비교 테스트는 항상 PASS (정보 제공 목적)
            score=score,
            duration=time.time() - start,
            details={
                "query_count": len(selected),
                "configs": config_results,
                "baseline": "A_all_on",
            },
        )

    # ──────────────────────────────────────────────────────────
    # 보고서 저장
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def save_json(report: EvalReport, path: Path) -> None:
        """평가 결과를 JSON으로 저장합니다."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": report.timestamp,
            "overall_passed": report.overall_passed,
            "stages": [],
        }
        for s in report.stages:
            data["stages"].append({
                "stage": s.stage,
                "name": s.name,
                "passed": s.passed,
                "score": round(s.score, 4),
                "duration": round(s.duration, 2),
                "details": s.details,
                "errors": s.errors,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장됨: {path}")

    @staticmethod
    def save_markdown(report: EvalReport, path: Path) -> None:
        """평가 결과를 마크다운 보고서로 저장합니다."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []

        lines.append("# 검색 품질 평가 보고서\n")
        lines.append(f"**생성일시**: {report.timestamp}\n")
        overall = "PASS" if report.overall_passed else "FAIL"
        lines.append(f"**전체 결과**: **{overall}**\n")

        # 요약표
        lines.append("\n## 요약\n")
        lines.append("| Stage | 이름 | 결과 | 점수 | 소요시간 |")
        lines.append("|-------|------|------|------|----------|")
        for s in report.stages:
            status = "PASS" if s.passed else "FAIL"
            lines.append(
                f"| {s.stage} | {s.name} | {status} | {s.score:.2%} | {s.duration:.1f}s |"
            )

        # 단계별 상세
        for s in report.stages:
            lines.append(f"\n## Stage {s.stage}: {s.name}\n")
            status = "PASS" if s.passed else "FAIL"
            lines.append(f"**결과**: {status} ({s.score:.2%})\n")

            if s.stage == 1:
                checks = s.details.get("checks", [])
                lines.append("| 도메인 | 컬렉션 | 문서 수 | 기대 범위 | 결과 |")
                lines.append("|--------|--------|---------|-----------|------|")
                for c in checks:
                    lo, hi = c["expected_range"]
                    st = "OK" if c["passed"] else "FAIL"
                    lines.append(
                        f"| {c['domain']} | {c['collection']} | "
                        f"{c['count']:,} | {lo:,}~{hi:,} | {st} |"
                    )
                total = s.details.get("total_docs", 0)
                lines.append(f"\n**총 문서 수**: {total:,}\n")

            elif s.stage == 2:
                lines.append(
                    f"- 평균 키워드 매칭률: {s.details.get('avg_keyword_match', 0):.2%}\n"
                    f"- 도메인 정렬률: {s.details.get('domain_alignment', 0):.2%}\n"
                )
                domain_avg = s.details.get("domain_averages", {})
                if domain_avg:
                    lines.append("**도메인별 키워드 매칭률**:\n")
                    for d, avg in domain_avg.items():
                        lines.append(f"- {d}: {avg:.2%}")

            elif s.stage == 3:
                lines.append(
                    f"- 노이즈 제거율: {s.details.get('noise_removal_rate', 0):.2%}\n"
                    f"- 필수법령 포함률: {s.details.get('essential_inclusion_rate', 0):.2%}\n"
                )

            elif s.stage == 4:
                lines.append(
                    f"- LLM 평균 점수: {s.details.get('avg_llm_score', 0):.1f}/100\n"
                )
                domain_avg = s.details.get("domain_averages", {})
                if domain_avg:
                    lines.append("**도메인별 LLM 점수**:\n")
                    for d, avg in domain_avg.items():
                        lines.append(f"- {d}: {avg:.1f}")
                ragas_avg = s.details.get("ragas_averages", {})
                if ragas_avg:
                    lines.append("\n**RAGAS 메트릭 평균**:\n")
                    for k, v in ragas_avg.items():
                        lines.append(f"- {k}: {v}")

            elif s.stage == 5:
                configs = s.details.get("configs", {})
                if configs:
                    lines.append("| 설정 | 평균점수 | 평균시간 |")
                    lines.append("|------|---------|---------|")
                    for name, data in configs.items():
                        lines.append(
                            f"| {name} | {data['avg_score']:.1f} | {data['avg_time']:.1f}s |"
                        )

            if s.errors:
                lines.append("\n**오류**:\n")
                for e in s.errors:
                    lines.append(f"- {e}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"마크다운 저장됨: {path}")


# ──────────────────────────────────────────────────────────────
# CLI 진입점
# ──────────────────────────────────────────────────────────────

def parse_stages(stage_arg: str) -> list[int]:
    """--stage 인자를 파싱합니다.

    Args:
        stage_arg: "all" 또는 "1,2,3" 형식

    Returns:
        단계 번호 리스트
    """
    if stage_arg.strip().lower() == "all":
        return [1, 2, 3, 4, 5]
    return [int(s.strip()) for s in stage_arg.split(",") if s.strip()]


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="5단계 검색 품질 평가 시스템"
    )
    parser.add_argument(
        "--stage",
        "-s",
        default="all",
        help="실행할 단계 (all 또는 1,2,3 형식, 기본값: all)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="로그 최소화 (WARNING만 출력)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="결과 저장 디렉토리 (기본값: evaluation/results/)",
    )
    args = parser.parse_args()

    # 로깅 설정
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # 벡터 검색 로그 억제 (Stage 2, 3에서 대량 출력 방지)
    logging.getLogger("vectorstores.chroma").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    stages = parse_stages(args.stage)
    print(f"\n검색 품질 평가 시작 (Stage: {stages})")

    evaluator = SearchQualityEvaluator(quiet=args.quiet)
    report = asyncio.run(evaluator.run(stages))

    # 결과 저장
    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR
    SearchQualityEvaluator.save_json(
        report, output_dir / "search_quality_results.json"
    )
    SearchQualityEvaluator.save_markdown(
        report, output_dir / "search_quality_report.md"
    )


if __name__ == "__main__":
    main()
