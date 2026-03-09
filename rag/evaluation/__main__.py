"""Batch RAG evaluation runner.

Usage:
    python -m evaluation --dataset evaluation/ragas_dataset_v4.jsonl
    python -m evaluation --dataset evaluation/ragas_dataset_v4.jsonl --output evaluation/results/run.json
    python -m evaluation --dataset evaluation/ragas_dataset_v4.jsonl --timeout 300
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.router import MainRouter
from evaluation.contextual_metrics import evaluate_contextual_case
from evaluation import RAGAS_METRIC_KEYS
from evaluation.ragas_evaluator import RagasEvaluator, RagasMetrics, strip_system_artifacts
from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

SEPARATOR_LENGTH = 80
QUESTION_PREVIEW_LENGTH = 60
DEFAULT_QUESTION_TIMEOUT = 300


def load_test_dataset(path: str) -> list[dict[str, object]]:
    dataset: list[dict[str, object]] = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                dataset.append(json.loads(line))
    return dataset


def _warmup_runpod() -> None:
    import requests

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    if not api_key or not endpoint_id:
        return

    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payloads = [
        ("embed", {"input": {"task": "embed", "texts": ["warmup"]}}),
        ("rerank", {"input": {"task": "rerank", "query": "warmup", "documents": ["test"]}}),
    ]

    for task_name, payload in payloads:
        started_at = time.time()
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            elapsed = time.time() - started_at
            status = response.json().get("status", "unknown")
            print(f"  RunPod {task_name} warmup: {elapsed:.1f}s ({status})")
        except Exception as exc:
            print(f"  RunPod {task_name} warmup failed: {exc}")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _preview(text: str) -> str:
    if len(text) <= QUESTION_PREVIEW_LENGTH:
        return text
    return text[:QUESTION_PREVIEW_LENGTH] + "..."


def _collect_metric_values(
    results: list[RagasMetrics],
    timeout_flags: list[bool],
    metric_keys: list[str],
) -> dict[str, list[float]]:
    metric_values: dict[str, list[float]] = {key: [] for key in metric_keys}
    for i, metrics in enumerate(results):
        if timeout_flags[i]:
            continue
        if metrics.available:
            for key in metric_keys:
                value = getattr(metrics, key)
                if value is not None:
                    metric_values[key].append(value)
    return metric_values


async def run_batch_evaluation(
    dataset_path: str,
    output_path: str | None = None,
    question_timeout: int = DEFAULT_QUESTION_TIMEOUT,
    compare: bool = False,
) -> None:
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")
    print(f"RAG service init (embedding={embedding_provider})")

    from utils.config import get_settings

    settings = get_settings()
    original_ragas_flag = settings.enable_ragas_evaluation
    original_llm_eval_flag = settings.enable_llm_evaluation
    original_post_eval_flag = settings.enable_post_eval_retry
    original_graduated_retry_flag = settings.enable_graduated_retry

    settings.enable_ragas_evaluation = True
    ragas_eval = RagasEvaluator()
    if not ragas_eval.is_available:
        print("RAGAS is not available. Install with: pip install ragas datasets")
        settings.enable_ragas_evaluation = original_ragas_flag
        return

    settings.enable_ragas_evaluation = False
    settings.enable_llm_evaluation = False
    settings.enable_post_eval_retry = False
    settings.enable_graduated_retry = False
    print("Batch mode: disabled in-pipeline eval/retry")

    if embedding_provider == "runpod":
        print("RunPod warmup...")
        _warmup_runpod()

    vector_store = ChromaVectorStore()
    try:
        print("Chroma warmup...")
        warmup_started_at = time.time()
        try:
            collections = vector_store.list_collections()
            for collection in collections:
                collection_start = time.time()
                vector_store.similarity_search("warmup", collection, k=1)
                print(f"  {collection}: {time.time() - collection_start:.1f}s")
            print(f"  Chroma warmup done: {time.time() - warmup_started_at:.1f}s ({len(collections)} collections)")
        except Exception as exc:
            print(f"  Chroma warmup skipped (non-blocking): {exc}")

        router = MainRouter(vector_store=vector_store)

        dataset = load_test_dataset(dataset_path)
        total_count = len(dataset)
        has_ground_truth = all("ground_truth" in item for item in dataset)

        print(f"Dataset questions: {total_count}")
        print(f"Per-question timeout: {question_timeout}s\n")

        questions: list[str] = []
        answers: list[str] = []
        contexts_list: list[list[str]] = []
        ground_truths: list[str] = []
        timeout_flags: list[bool] = []
        elapsed_times: list[float] = []
        timeout_causes: list[str | None] = []
        contextual_metrics_list: list[dict[str, float | None] | None] = []

        for index, item in enumerate(dataset):
            question = str(item["question"])
            preview = _preview(question)
            started_at = time.time()
            timed_out = False

            try:
                history = item.get("history")
                if not isinstance(history, list):
                    history = None

                response = await asyncio.wait_for(
                    router.aprocess(query=question, history=history),
                    timeout=question_timeout,
                )
                elapsed = time.time() - started_at

                questions.append(question)
                answers.append(response.content)
                contexts = [src.content for src in response.sources if src.content and src.content.strip()]
                contexts_list.append(contexts if contexts else ["NO_CONTEXT"])
                timeout_causes.append(getattr(response.evaluation_data, "timeout_cause", None))

                case_metrics = evaluate_contextual_case(
                    answer=response.content,
                    required_directives=item.get("required_directives"),
                    required_context_terms=item.get("required_context_terms"),
                    forbidden_terms=item.get("forbidden_terms"),
                ).to_dict()
                contextual_metrics_list.append(case_metrics if any(v is not None for v in case_metrics.values()) else None)

                print(f"[{index + 1}/{total_count}] ({elapsed:.1f}s) {preview}")

            except asyncio.TimeoutError:
                elapsed = time.time() - started_at
                timed_out = True
                questions.append(question)
                answers.append("[TIMEOUT]")
                contexts_list.append(["TIMEOUT_NO_CONTEXT"])
                timeout_causes.append("question_timeout")
                contextual_metrics_list.append(None)
                print(f"[{index + 1}/{total_count}] TIMEOUT ({elapsed:.0f}s) {preview}")

            except Exception as exc:
                elapsed = time.time() - started_at
                questions.append(question)
                answers.append(f"[ERROR] {exc}")
                contexts_list.append(["ERROR_NO_CONTEXT"])
                timeout_causes.append("runtime_error")
                contextual_metrics_list.append(None)
                print(f"[{index + 1}/{total_count}] ERROR ({elapsed:.1f}s) {preview}: {exc}")

            timeout_flags.append(timed_out)
            elapsed_times.append(round(elapsed, 2))
            if has_ground_truth:
                ground_truths.append(str(item["ground_truth"]))

        timeout_count = sum(timeout_flags)
        valid_count = total_count - timeout_count
        valid_indices = [i for i, is_timeout in enumerate(timeout_flags) if not is_timeout]

        print(f"\nDone: success={valid_count}/{total_count}, timeout={timeout_count}")

        if not valid_indices:
            print("No valid responses. Skip RAGAS evaluation.")
            return

        valid_questions = [questions[i] for i in valid_indices]
        valid_answers = [answers[i] for i in valid_indices]
        valid_contexts = [contexts_list[i] for i in valid_indices]
        valid_ground_truths = [ground_truths[i] for i in valid_indices] if has_ground_truth else None

        cleaned_answers = [strip_system_artifacts(a) for a in valid_answers]

        print(f"\nRun RAGAS batch ({len(valid_indices)} cases)")
        ragas_results = ragas_eval.evaluate_batch(
            questions=valid_questions,
            answers=cleaned_answers,
            contexts_list=valid_contexts,
            ground_truths=valid_ground_truths,
        )

        raw_ragas_results = None
        if compare:
            print("Run RAGAS batch (raw, no strip)")
            raw_ragas_results = ragas_eval.evaluate_batch(
                questions=valid_questions,
                answers=valid_answers,
                contexts_list=valid_contexts,
                ground_truths=valid_ground_truths,
            )

        all_results: list[RagasMetrics] = []
        all_raw_results: list[RagasMetrics] | None = [] if compare else None
        ragas_index = 0
        for i in range(total_count):
            if timeout_flags[i]:
                all_results.append(RagasMetrics(error="TIMEOUT"))
                if all_raw_results is not None:
                    all_raw_results.append(RagasMetrics(error="TIMEOUT"))
            else:
                all_results.append(ragas_results[ragas_index])
                if all_raw_results is not None and raw_ragas_results:
                    all_raw_results.append(raw_ragas_results[ragas_index])
                ragas_index += 1

        print("\n" + "=" * SEPARATOR_LENGTH)
        print("RAGAS Result" + (" (cleaned vs raw)" if compare else ""))
        print("=" * SEPARATOR_LENGTH)

        metric_keys = [k for k in RAGAS_METRIC_KEYS if k != "context_recall" or has_ground_truth]

        contextual_keys = ["directive_coverage", "context_adherence", "conflict_free", "score"]
        contextual_values: dict[str, list[float]] = {key: [] for key in contextual_keys}

        for i, (question, metrics) in enumerate(zip(questions, all_results)):
            elapsed_str = f" ({elapsed_times[i]:.1f}s)"
            print(f"\n[{i + 1}]{elapsed_str} {_preview(question)}")

            if timeout_flags[i]:
                print(f"  timeout_cause: {timeout_causes[i] or 'unknown'}")
                continue

            if metrics.available:
                for key in metric_keys:
                    value = getattr(metrics, key)
                    if value is not None:
                        print(f"  {key}: {value:.4f}")
            elif metrics.error:
                print(f"  error: {metrics.error}")

            case_contextual = contextual_metrics_list[i]
            if case_contextual:
                for key in contextual_keys:
                    value = case_contextual.get(key)
                    if value is not None:
                        contextual_values[key].append(value)
                        print(f"  {key}: {value:.4f}")

            if timeout_causes[i]:
                print(f"  timeout_cause: {timeout_causes[i]}")

        metric_values = _collect_metric_values(all_results, timeout_flags, metric_keys)
        averages = {key: _avg(values) for key, values in metric_values.items()}
        contextual_averages = {key: _avg(values) for key, values in contextual_values.items()}

        # compare 모드: raw 메트릭 집계
        raw_averages: dict[str, float | None] = {}
        delta_averages: dict[str, float] = {}
        if compare and all_raw_results:
            raw_metric_values = _collect_metric_values(all_raw_results, timeout_flags, metric_keys)
            raw_averages = {key: _avg(values) for key, values in raw_metric_values.items()}
            for key in metric_keys:
                c = averages.get(key)
                r = raw_averages.get(key)
                if c is not None and r is not None:
                    delta_averages[key] = round(c - r, 4)

        print("\n" + "-" * SEPARATOR_LENGTH)
        print(f"Averages (valid={valid_count}, timeout={timeout_count} excluded)")
        for key, value in averages.items():
            print(f"  {key}: {value if value is not None else '-'}")

        if compare and raw_averages:
            print("\nRaw averages (no artifact strip)")
            for key, value in raw_averages.items():
                print(f"  {key}: {value if value is not None else '-'}")
            print("\nDelta (cleaned - raw)")
            for key, value in delta_averages.items():
                sign = "+" if value > 0 else ""
                print(f"  {key}: {sign}{value}")

        has_contextual = any(value is not None for value in contextual_averages.values())
        if has_contextual:
            print("\nContextual averages")
            for key, value in contextual_averages.items():
                print(f"  {key}: {value if value is not None else '-'}")

        timeout_cause_counts = Counter(cause for cause in timeout_causes if cause)
        if timeout_cause_counts:
            print("\nTimeout cause summary")
            for cause, count in timeout_cause_counts.items():
                print(f"  {cause}: {count}")

        if output_path:
            output_data = {
                "dataset": dataset_path,
                "count": total_count,
                "has_ground_truth": has_ground_truth,
                "embedding_provider": embedding_provider,
                "question_timeout": question_timeout,
                "timeout_count": timeout_count,
                "valid_count": valid_count,
                "timeout_causes": dict(timeout_cause_counts),
                "results": [
                    {
                        "question": question,
                        "answer": answers[i],
                        "contexts": contexts_list[i],
                        "timeout": timeout_flags[i],
                        "timeout_cause": timeout_causes[i],
                        "elapsed_seconds": elapsed_times[i],
                        "metrics": all_results[i].to_dict(),
                        "contextual_metrics": contextual_metrics_list[i],
                    }
                    for i, question in enumerate(questions)
                ],
                "averages": averages,
                "averages_contextual": contextual_averages,
            }
            if compare and raw_averages:
                output_data["raw_averages"] = raw_averages
                output_data["delta_averages"] = delta_averages
            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(output_data, file, ensure_ascii=False, indent=2)
            print(f"\nSaved: {output_path}")
    finally:
        settings.enable_ragas_evaluation = original_ragas_flag
        settings.enable_llm_evaluation = original_llm_eval_flag
        settings.enable_post_eval_retry = original_post_eval_flag
        settings.enable_graduated_retry = original_graduated_retry_flag
        vector_store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch RAGAS evaluator")
    parser.add_argument("--dataset", "-d", required=True, help="JSONL dataset path")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path")
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=DEFAULT_QUESTION_TIMEOUT,
        help=f"Per-question timeout in seconds (default: {DEFAULT_QUESTION_TIMEOUT})",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare cleaned vs raw scores (runs RAGAS twice)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_batch_evaluation(args.dataset, args.output, args.timeout, args.compare))


if __name__ == "__main__":
    main()
