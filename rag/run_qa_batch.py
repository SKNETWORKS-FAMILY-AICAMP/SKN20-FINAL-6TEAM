"""QA 배치 테스트 실행기.

QA 데이터셋 MD에서 질문을 추출하여 순차 실행하고 결과를 로그로 기록합니다.

사용법:
    cd rag
    py run_qa_batch.py                        # v1 전체 실행 (기본)
    py run_qa_batch.py --dataset v2           # v2 전체 실행
    py run_qa_batch.py --dataset v2 --start 1 --end 10  # V-001 ~ V-010만
    py run_qa_batch.py --start 30             # U-030부터 이어서 실행
    py run_qa_batch.py --dataset v4           # v4 전체 실행
    py run_qa_batch.py --dataset v4 --start 1 --end 10  # X-001 ~ X-010만
"""

import asyncio
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows cp949 인코딩 이슈 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))


def _print(msg: str) -> None:
    """즉시 flush되는 print."""
    print(msg, flush=True)


def extract_questions(md_path: str) -> list[dict]:
    """통합 QA 데이터셋 MD 파일에서 질문을 추출합니다. U-NNN / V-NNN / W-NNN / X-NNN 모두 지원."""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # U-NNN, V-NNN, W-NNN, X-NNN 헤더와 질문 추출 (페르소나/소스 줄 수 유연 처리)
    pattern = r'### (([UVWX])-(\d+)\..+?)\n\n- \*\*도메인\*\*: (.+?)\n- \*\*난이도\*\*: (.+?)\n(?:- \*\*.+?\n)*\n\*\*질문\*\*: (.+?)(?:\n\n)'
    matches = re.findall(pattern, content, re.DOTALL)

    questions = []
    for match in matches:
        header = match[0].strip()
        prefix = match[1]  # "U" or "V"
        q_num = int(match[2])
        domain = match[3].strip()
        difficulty = match[4].strip()
        question = match[5].strip()
        questions.append({
            "id": f"{prefix}-{q_num:03d}",
            "num": q_num,
            "header": header,
            "domain": domain,
            "difficulty": difficulty,
            "question": question,
        })

    return questions


async def run_batch(start: int = 1, end: int | None = None, dataset: str = "v1") -> None:
    """배치 테스트를 실행합니다."""
    import logging
    from agents.router import MainRouter
    from schemas.request import UserContext
    from utils.config import get_settings, init_db, load_domain_config
    from utils.token_tracker import RequestTokenTracker
    from vectorstores.chroma import ChromaVectorStore

    # 로깅 설정 (WARNING만 콘솔 출력)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 질문 추출
    dataset_files = {
        "v1": "bizi_qa_dataset_unified.md",
        "v2": "bizi_qa_dataset_v2.md",
        "v3": "bizi_qa_dataset_v3.md",
        "v4": "bizi_qa_dataset_v4.md",
    }
    dataset_file = dataset_files.get(dataset, dataset_files["v1"])
    qa_path = Path(__file__).parent.parent / "qa_test" / dataset_file
    if not qa_path.exists():
        _print(f"ERROR: 데이터셋 파일을 찾을 수 없습니다: {qa_path}")
        return
    questions = extract_questions(str(qa_path))
    prefix = questions[0]["id"][0] if questions else "V"
    _print(f"데이터셋: {dataset_file} ({len(questions)}개 질문)")

    # 범위 필터
    if end is None:
        end = max(q["num"] for q in questions) if questions else 0
    filtered = [q for q in questions if start <= q["num"] <= end]
    _print(f"실행 범위: {prefix}-{start:03d} ~ {prefix}-{end:03d} ({len(filtered)}건)")

    # 설정: .env 값 그대로 사용 (서버/프론트와 동일 조건)
    settings = get_settings()
    _print(f"Hybrid Search: ON (vector_weight={settings.vector_search_weight})")
    _print(f"Re-ranking: {settings.reranker_type if settings.enable_reranking else 'OFF'}")
    _print(f"Total Timeout: {settings.total_timeout}s")

    # 초기화
    _print("RAG 서비스 초기화 중...")
    init_db()
    load_domain_config()

    from utils.config import get_settings
    _embedding_provider = get_settings().embedding_provider
    _print(f"임베딩 프로바이더: {_embedding_provider}")

    vector_store = ChromaVectorStore()
    router = MainRouter(vector_store=vector_store)
    user_context = UserContext(user_type="prospective")
    _print("초기화 완료.\n")

    # 결과 로그 파일
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"qa_batch_{timestamp}.jsonl"
    summary_file = log_dir / f"qa_batch_{timestamp}_summary.md"

    results = []
    pass_count = 0
    fail_count = 0
    reject_count = 0
    error_count = 0

    for i, q in enumerate(filtered, 1):
        qid = q["id"]
        _print(f"\n[{i}/{len(filtered)}] {qid}: {q['header']}")
        _print(f"  도메인: {q['domain']} | 난이도: {q['difficulty']}")
        _print(f"  질문: {q['question'][:80]}...")

        start_time = time.time()
        result = {
            "id": qid,
            "header": q["header"],
            "domain_expected": q["domain"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            async with RequestTokenTracker() as tracker:
                response = await router.aprocess(
                    query=q["question"],
                    user_context=user_context,
                )
                token_usage = tracker.get_usage()

            elapsed = time.time() - start_time
            result["elapsed_sec"] = round(elapsed, 2)
            result["domains_actual"] = response.domains
            result["content"] = response.content
            result["retry_count"] = response.retry_count
            result["source_count"] = len(response.sources)
            result["sources"] = [
                {"title": s.title, "source": s.source}
                for s in response.sources
                if s.content and s.content.strip()
            ]

            if response.evaluation:
                result["eval_score"] = response.evaluation.total_score
                result["eval_passed"] = response.evaluation.passed
                result["eval_scores"] = response.evaluation.scores
                result["eval_feedback"] = response.evaluation.feedback
            else:
                result["eval_score"] = None
                result["eval_passed"] = None

            if response.timing_metrics:
                result["timing"] = {
                    "classify": response.timing_metrics.classify_time,
                    "integrate": response.timing_metrics.integrate_time,
                    "evaluate": response.timing_metrics.evaluate_time,
                    "total": response.timing_metrics.total_time,
                }

            if token_usage and token_usage.get("total_tokens", 0) > 0:
                result["tokens"] = token_usage

            # 통계
            is_rejection = "상담 범위" in response.content or "전문 상담 영역" in response.content
            if is_rejection:
                result["status"] = "REJECTED"
                reject_count += 1
                _print(f"  -> REJECTED (도메인 외 거부) | {elapsed:.1f}초")
            elif result.get("eval_passed"):
                result["status"] = "PASS"
                pass_count += 1
                score = result.get("eval_score", "?")
                _print(f"  -> PASS ({score}/100) | {elapsed:.1f}초")
            else:
                result["status"] = "FAIL"
                fail_count += 1
                score = result.get("eval_score", "?")
                _print(f"  -> FAIL ({score}/100) | {elapsed:.1f}초")

        except Exception as e:
            elapsed = time.time() - start_time
            result["elapsed_sec"] = round(elapsed, 2)
            result["status"] = "ERROR"
            result["error"] = str(e)
            error_count += 1
            _print(f"  -> ERROR: {e} | {elapsed:.1f}초")

        results.append(result)

        # 실시간 JSONL 기록
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # 최종 통계
    total = len(filtered)
    _print("\n" + "=" * 80)
    _print("QA 배치 테스트 완료")
    _print("=" * 80)
    _print(f"총 {total}건 | PASS: {pass_count} | FAIL: {fail_count} | REJECTED: {reject_count} | ERROR: {error_count}")
    if pass_count + fail_count > 0:
        avg_score = sum(
            r.get("eval_score", 0) or 0
            for r in results
            if r["status"] in ("PASS", "FAIL")
        ) / (pass_count + fail_count)
        _print(f"평균 점수: {avg_score:.1f}/100")
    _print(f"결과 파일: {log_file}")

    # Summary MD 생성
    _write_summary(summary_file, results, settings, pass_count, fail_count, reject_count, error_count)
    _print(f"요약 파일: {summary_file}")

    # 분석 보고서 생성
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"{datetime.now().strftime('%Y-%m-%d')}_qa_batch_analysis.md"
    _write_analysis_report(report_file, results, settings, pass_count, fail_count, reject_count, error_count, log_file, summary_file, dataset_file)
    _print(f"분석 보고서: {report_file}")

    vector_store.close()


def _write_summary(
    path: Path,
    results: list[dict],
    settings,
    pass_count: int,
    fail_count: int,
    reject_count: int,
    error_count: int,
) -> None:
    """테스트 결과 요약 MD를 생성합니다."""
    total = len(results)
    scored = [r for r in results if r["status"] in ("PASS", "FAIL")]
    avg_score = sum(r.get("eval_score", 0) or 0 for r in scored) / len(scored) if scored else 0
    avg_time = sum(r.get("elapsed_sec", 0) for r in results) / total if total else 0

    lines = [
        "# Bizi QA 배치 테스트 결과",
        "",
        f"> **테스트 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> **Hybrid Search**: ON (weight={settings.vector_search_weight})",
        f"> **Re-ranking**: {settings.reranker_type if settings.enable_reranking else 'OFF'}",
        f"> **Multi-Query**: ON (count={settings.multi_query_count})",
        "",
        "---",
        "",
        "## 전체 통계",
        "",
        f"| 항목 | 값 |",
        f"|------|-----|",
        f"| 총 건수 | {total} |",
        f"| PASS | {pass_count} ({pass_count/total*100:.1f}%) |" if total else f"| PASS | 0 |",
        f"| FAIL | {fail_count} |",
        f"| REJECTED | {reject_count} |",
        f"| ERROR | {error_count} |",
        f"| 평균 점수 | {avg_score:.1f}/100 |",
        f"| 평균 처리시간 | {avg_time:.1f}초 |",
        "",
        "---",
        "",
        "## 난이도별 통계",
        "",
    ]

    # 난이도별
    for diff in ["Easy", "Medium", "Hard", "N/A"]:
        subset = [r for r in results if r.get("difficulty") == diff]
        if not subset:
            continue
        s_pass = sum(1 for r in subset if r["status"] == "PASS")
        s_fail = sum(1 for r in subset if r["status"] == "FAIL")
        s_rej = sum(1 for r in subset if r["status"] == "REJECTED")
        s_err = sum(1 for r in subset if r["status"] == "ERROR")
        s_scored = [r for r in subset if r["status"] in ("PASS", "FAIL")]
        s_avg = sum(r.get("eval_score", 0) or 0 for r in s_scored) / len(s_scored) if s_scored else 0
        lines.append(f"### {diff} ({len(subset)}건)")
        lines.append(f"- PASS: {s_pass}, FAIL: {s_fail}, REJECTED: {s_rej}, ERROR: {s_err}")
        lines.append(f"- 평균 점수: {s_avg:.1f}/100")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 개별 결과",
        "",
        "| # | ID | 도메인(기대) | 도메인(실제) | 난이도 | 점수 | 상태 | 시간 |",
        "|---|-----|-------------|-------------|--------|------|------|------|",
    ])

    for i, r in enumerate(results, 1):
        domains_actual = ", ".join(r.get("domains_actual", [])) if r.get("domains_actual") else "-"
        score = r.get("eval_score", "-") if r.get("eval_score") is not None else "-"
        status = r["status"]
        elapsed = r.get("elapsed_sec", "-")
        lines.append(
            f"| {i} | {r['id']} | {r.get('domain_expected', '-')} | {domains_actual} | "
            f"{r.get('difficulty', '-')} | {score} | {status} | {elapsed}s |"
        )

    lines.extend(["", "---", ""])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_analysis_report(
    path: Path,
    results: list[dict],
    settings,
    pass_count: int,
    fail_count: int,
    reject_count: int,
    error_count: int,
    log_file: Path,
    summary_file: Path,
    dataset_file: str = "bizi_qa_dataset_unified.md",
) -> None:
    """테스트 분석 보고서 MD를 생성합니다. 문제점/개선방안 포함."""
    from collections import Counter

    total = len(results)
    scored = [r for r in results if r["status"] in ("PASS", "FAIL")]
    avg_score = sum(r.get("eval_score", 0) or 0 for r in scored) / len(scored) if scored else 0
    avg_time = sum(r.get("elapsed_sec", 0) for r in results) / total if total else 0

    pass_items = [r for r in results if r["status"] == "PASS"]
    fail_items = [r for r in results if r["status"] == "FAIL"]
    reject_items = [r for r in results if r["status"] == "REJECTED"]
    error_items = [r for r in results if r["status"] == "ERROR"]

    avg_pass_time = sum(r["elapsed_sec"] for r in pass_items) / len(pass_items) if pass_items else 0
    total_cost = sum(r.get("tokens", {}).get("cost", 0) for r in results)
    total_tokens = sum(r.get("tokens", {}).get("total_tokens", 0) for r in results)

    now = datetime.now()
    lines = [
        "# QA 배치 테스트 분석 보고서",
        "",
        f"> **테스트 일시**: {now.strftime('%Y-%m-%d %H:%M')}",
        f"> **데이터셋**: `qa_test/{dataset_file}` ({total}건)",
        f"> **로그 파일**: `{log_file.relative_to(log_file.parent.parent)}`",
        f"> **요약 파일**: `{summary_file.relative_to(summary_file.parent.parent)}`",
        "",
        "---",
        "",
        "## 1. 테스트 환경",
        "",
        "| 항목 | 설정값 |",
        "|------|--------|",
        f"| Hybrid Search | ON (weight={settings.vector_search_weight}) |",
        f"| Re-ranking | {settings.reranker_type if settings.enable_reranking else 'OFF'} |",
        f"| Multi-Query | ON (count={settings.multi_query_count}) |",
        f"| LLM Evaluation | {'ON' if settings.enable_llm_evaluation else 'OFF'} |",
        f"| Total Timeout | {settings.total_timeout}초 |",
        f"| Domain Threshold | {settings.domain_classification_threshold} |",
        "",
        "---",
        "",
        "## 2. 전체 결과 요약",
        "",
        "| 항목 | 값 |",
        "|------|-----|",
        f"| 총 건수 | {total} |",
        f"| PASS | {pass_count} ({pass_count/total*100:.1f}%) |" if total else "| PASS | 0 |",
        f"| FAIL | {fail_count} ({fail_count/total*100:.1f}%) |" if total else "| FAIL | 0 |",
        f"| REJECTED | {reject_count} ({reject_count/total*100:.1f}%) |" if total else "| REJECTED | 0 |",
        f"| ERROR | {error_count} |",
        f"| 평균 점수 (PASS+FAIL) | {avg_score:.1f}/100 |",
        f"| PASS 평균 처리시간 | {avg_pass_time:.1f}초 |",
        f"| 전체 평균 처리시간 | {avg_time:.1f}초 |",
        f"| 총 토큰 | {total_tokens:,} |",
        f"| 총 API 비용 | ${total_cost:.4f} |",
        "",
        "### 난이도별",
        "",
        "| 난이도 | 총 | PASS | FAIL | REJECTED | ERROR | 평균점수 |",
        "|--------|-----|------|------|----------|-------|---------|",
    ]

    for diff in ["Easy", "Medium", "Hard", "N/A"]:
        subset = [r for r in results if r.get("difficulty") == diff]
        if not subset:
            continue
        s_pass = sum(1 for r in subset if r["status"] == "PASS")
        s_fail = sum(1 for r in subset if r["status"] == "FAIL")
        s_rej = sum(1 for r in subset if r["status"] == "REJECTED")
        s_err = sum(1 for r in subset if r["status"] == "ERROR")
        s_scored = [r for r in subset if r["status"] in ("PASS", "FAIL")]
        s_avg = sum(r.get("eval_score", 0) or 0 for r in s_scored) / len(s_scored) if s_scored else 0
        lines.append(
            f"| {diff} | {len(subset)} | {s_pass} | {s_fail} | {s_rej} | {s_err} | {s_avg:.1f} |"
        )

    lines.extend(["", "---", "", "## 3. 발견된 문제점", ""])

    # --- 문제점 자동 분석 ---
    problem_num = 0

    # 문제점: REJECTED 비율이 높을 때
    if total > 0 and reject_count / total > 0.3:
        problem_num += 1
        reject_pct = reject_count / total * 100
        lines.extend([
            f"### 문제 {problem_num}: 도메인 분류 거부율 과다 ({reject_pct:.1f}%) — CRITICAL",
            "",
            f"78건 중 {reject_count}건이 '상담 범위 외'로 즉시 거부됨 (평균 응답시간 ~0.3초).",
            "",
            "**REJECTED 도메인별 분포:**",
            "",
            "| 기대 도메인 | 거부 건수 |",
            "|------------|----------|",
        ])
        domain_counts = Counter(r["domain_expected"] for r in reject_items)
        for d, c in domain_counts.most_common():
            lines.append(f"| {d} | {c} |")
        lines.extend([
            "",
            "**거부 원인 분석:**",
            f"- 벡터 유사도 임계값({settings.domain_classification_threshold})이 너무 높음",
            "- 도메인별 대표 쿼리(DOMAIN_REPRESENTATIVE_QUERIES) 수 부족",
            "- 키워드 매칭 커버리지 부족 (동의어/유의어 미지원)",
            "- 멀티도메인 질문의 구조적 불이익 (유사도 분산)",
            f"- LLM 보조 분류 {'비활성' if not settings.enable_llm_domain_classification else '활성'}",
            "",
            "**거부된 질문 샘플:**",
            "",
            "| ID | 도메인 | 난이도 | 질문 (앞 60자) |",
            "|----|--------|--------|---------------|",
        ])
        for r in reject_items[:10]:
            q_short = r["question"][:60].replace("|", "/") + "..."
            lines.append(f"| {r['id']} | {r['domain_expected']} | {r['difficulty']} | {q_short} |")
        lines.append("")

    # 문제점: ERROR 발생
    if error_items:
        problem_num += 1
        lines.extend([
            f"### 문제 {problem_num}: ERROR {len(error_items)}건",
            "",
        ])
        for r in error_items:
            lines.extend([
                f"- **{r['id']}** ({r['domain_expected']}, {r['difficulty']}): `{r.get('error', 'N/A')}`",
                f"  - 처리시간: {r['elapsed_sec']}초",
            ])
        lines.append("")

    # 문제점: FAIL 발생
    if fail_items:
        problem_num += 1
        lines.extend([
            f"### 문제 {problem_num}: FAIL {len(fail_items)}건 (점수 미달)",
            "",
            "| ID | 도메인 | 점수 | 피드백 |",
            "|----|--------|------|--------|",
        ])
        for r in fail_items:
            fb = (r.get("eval_feedback") or "-")[:80].replace("|", "/")
            lines.append(f"| {r['id']} | {r['domain_expected']} | {r.get('eval_score', '-')} | {fb} |")
        lines.append("")

    # 문제점: 첫 질문 처리시간 과다
    if pass_items and pass_items[0]["elapsed_sec"] > avg_pass_time * 2:
        problem_num += 1
        first = results[0] if results[0]["status"] == "PASS" else None
        if first:
            lines.extend([
                f"### 문제 {problem_num}: 첫 질문 처리시간 과다 ({first['id']}: {first['elapsed_sec']}초)",
                "",
                f"- PASS 평균 처리시간: {avg_pass_time:.1f}초의 {first['elapsed_sec']/avg_pass_time:.1f}배",
                "- 원인: cross-encoder reranker 모델 초기 로딩 시간 포함",
                "",
            ])

    # 문제점: 낮은 점수 항목
    low_score_items = [r for r in scored if (r.get("eval_score") or 0) < 80]
    if low_score_items:
        problem_num += 1
        lines.extend([
            f"### 문제 {problem_num}: 낮은 평가 점수 ({len(low_score_items)}건, <80점)",
            "",
            "| ID | 점수 | 약점 항목 |",
            "|----|------|----------|",
        ])
        for r in low_score_items:
            scores = r.get("eval_scores", {})
            weak = [k for k, v in scores.items() if v and v < 16]
            lines.append(f"| {r['id']} | {r.get('eval_score', '-')} | {', '.join(weak) if weak else '-'} |")
        lines.append("")

    if problem_num == 0:
        lines.extend(["문제점이 발견되지 않았습니다.", ""])

    # --- 긍정적 발견 ---
    lines.extend(["---", "", "## 4. 긍정적 발견", ""])

    positives = []
    if fail_count == 0 and pass_count > 0:
        positives.append(f"FAIL 0건: 도메인 분류를 통과한 질문은 모두 PASS ({pass_count}/{pass_count+fail_count} = 100%)")
    if avg_score >= 90:
        positives.append(f"높은 평균 점수: {avg_score:.1f}/100")
    perfect = [r for r in pass_items if r.get("eval_score") == 100]
    if perfect:
        ids = ", ".join(r["id"] for r in perfect)
        positives.append(f"만점 {len(perfect)}건: {ids}")
    multi_pass = [r for r in pass_items if r.get("domains_actual") and len(r["domains_actual"]) >= 3]
    if multi_pass:
        positives.append(f"복합 도메인(3+) 처리 성공: {len(multi_pass)}건")
    if total_cost < 1.0:
        positives.append(f"비용 효율적: 총 ${total_cost:.4f}")

    for p in positives:
        lines.append(f"- {p}")
    if not positives:
        lines.append("- 특별한 긍정적 발견 없음")
    lines.append("")

    # --- PASS 상세 ---
    lines.extend([
        "---",
        "",
        "## 5. PASS 질문 상세",
        "",
        "| ID | 기대 도메인 | 실제 도메인 | 점수 | 시간 | 비용 |",
        "|----|------------|-----------|------|------|------|",
    ])
    for r in pass_items:
        domains = ", ".join(r.get("domains_actual", []))
        cost = r.get("tokens", {}).get("cost", 0)
        lines.append(
            f"| {r['id']} | {r['domain_expected']} | {domains} | "
            f"{r.get('eval_score', '-')} | {r['elapsed_sec']}s | ${cost:.4f} |"
        )

    if pass_items:
        lines.extend(["", "### 평가 항목별 평균", ""])
        eval_keys = ["retrieval_quality", "accuracy", "completeness", "relevance", "citation"]
        labels = {"retrieval_quality": "검색 품질", "accuracy": "정확성", "completeness": "완성도", "relevance": "관련성", "citation": "출처 명시"}
        lines.append("| 항목 | 평균 | 최저 | 최고 |")
        lines.append("|------|------|------|------|")
        for key in eval_keys:
            vals = [r.get("eval_scores", {}).get(key, 0) or 0 for r in pass_items]
            if vals:
                lines.append(f"| {labels.get(key, key)} | {sum(vals)/len(vals):.1f} | {min(vals)} | {max(vals)} |")
    lines.append("")

    # --- 개선 방안 ---
    lines.extend(["---", "", "## 6. 개선 방안", ""])
    suggestion_num = 0

    if total > 0 and reject_count / total > 0.3:
        suggestion_num += 1
        lines.extend([
            f"### {suggestion_num}. [P0] 도메인 분류 임계값 하향 조정",
            "",
            f"- 현재: `domain_classification_threshold = {settings.domain_classification_threshold}`",
            "- 제안: `0.35 ~ 0.45` 범위로 단계적 테스트",
            "- 너무 낮추면 무관한 질문도 통과하므로 균형 필요",
            "",
        ])
        suggestion_num += 1
        lines.extend([
            f"### {suggestion_num}. [P0] 도메인별 대표 쿼리 확충",
            "",
            "- 현재 도메인당 15~20개 → 50~100개로 확충",
            "- 특히 `finance_tax`, `hr_labor` 도메인 커버리지 부족",
            "- 실제 사용자 질문 패턴을 반영한 다양한 표현 추가",
            "",
        ])
        suggestion_num += 1
        lines.extend([
            f"### {suggestion_num}. [P1] 키워드 사전 확장",
            "",
            '- "세액감면", "공제", "절세" → finance_tax 매핑 추가',
            '- "면허", "인허가", "개업" → startup_funding 매핑 추가',
            "- 동의어/유의어 처리 로직 강화",
            "",
        ])

    if not settings.enable_llm_domain_classification:
        suggestion_num += 1
        lines.extend([
            f"### {suggestion_num}. [P1] LLM 보조 분류 활성화 검토",
            "",
            "- `enable_llm_domain_classification = True`",
            "- 벡터 유사도가 임계값 근처(±0.15)인 경우에만 LLM 2차 검증",
            "- 추가 비용 발생하나 정확도 향상 예상",
            "",
        ])

    if error_items:
        suggestion_num += 1
        errors_summary = "; ".join(f"{r['id']}: {r.get('error', '')[:50]}" for r in error_items)
        lines.extend([
            f"### {suggestion_num}. [P2] ERROR 수정",
            "",
            f"- {errors_summary}",
            "- 에러 핸들링 경로의 잔여 코드 정리 필요",
            "",
        ])

    if not suggestion_num:
        lines.append("특별한 개선 방안 없음.")
        lines.append("")

    # --- 다음 단계 ---
    lines.extend([
        "---",
        "",
        "## 7. 다음 단계",
        "",
        "1. 임계값을 조정 후 동일 데이터셋 재테스트",
        "2. 대표 쿼리 확충 후 재테스트",
        "3. 최적 설정 확정 후 `.env` 반영",
        "",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QA 배치 테스트")
    parser.add_argument("--dataset", type=str, default="v1", choices=["v1", "v2", "v3", "v4"], help="데이터셋 버전 (기본: v1)")
    parser.add_argument("--start", type=int, default=1, help="시작 번호 (기본: 1)")
    parser.add_argument("--end", type=int, default=None, help="종료 번호 (기본: 마지막)")
    args = parser.parse_args()

    asyncio.run(run_batch(start=args.start, end=args.end, dataset=args.dataset))
