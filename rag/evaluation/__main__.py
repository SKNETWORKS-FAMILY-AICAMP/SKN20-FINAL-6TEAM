"""RAGAS 배치 평가 실행 모듈.

테스트 데이터셋을 사용하여 RAG 시스템의 RAGAS 메트릭을 배치로 평가합니다.

사용법:
    python -m evaluation --dataset tests/test_dataset.jsonl
    python -m evaluation --dataset tests/test_dataset.jsonl --output results.json
    python -m evaluation --dataset tests/test_dataset.jsonl --timeout 300

테스트 데이터셋 형식 (JSONL):
    {"question": "퇴직금 계산은 어떻게 하나요?", "ground_truth": "퇴직금은..."}
    {"question": "사업자등록 절차는?"}
    (ground_truth는 선택사항)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.router import MainRouter
from evaluation.ragas_evaluator import RagasEvaluator
from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

# 출력 구분선 길이
SEPARATOR_LENGTH = 80
# 질문 미리보기 최대 길이
QUESTION_PREVIEW_LENGTH = 60
# 질문별 기본 타임아웃 (초)
DEFAULT_QUESTION_TIMEOUT = 300


def load_test_dataset(path: str) -> list[dict[str, str]]:
    """테스트 데이터셋을 로드합니다.

    Args:
        path: JSONL 파일 경로

    Returns:
        질문/정답 딕셔너리 리스트

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        json.JSONDecodeError: JSON 파싱 실패 시
    """
    dataset: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                dataset.append(json.loads(line))
    return dataset


def _warmup_runpod() -> None:
    """RunPod 워커를 사전 예열합니다 (cold start 방지)."""
    import requests

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    if not api_key or not endpoint_id:
        return

    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for task_name, payload in [
        ("embed", {"input": {"task": "embed", "texts": ["warmup"]}}),
        ("rerank", {"input": {"task": "rerank", "query": "warmup", "documents": ["test"]}}),
    ]:
        start = time.time()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            elapsed = time.time() - start
            status = resp.json().get("status", "unknown")
            print(f"  RunPod {task_name} warmup: {elapsed:.1f}s ({status})")
        except Exception as e:
            print(f"  RunPod {task_name} warmup failed: {e}")


async def run_batch_evaluation(
    dataset_path: str,
    output_path: str | None = None,
    question_timeout: int = DEFAULT_QUESTION_TIMEOUT,
) -> None:
    """배치 평가를 실행합니다.

    Args:
        dataset_path: 테스트 데이터셋 파일 경로
        output_path: 결과 저장 경로 (선택)
        question_timeout: 질문별 타임아웃 초 (기본 300초)
    """
    # 초기화
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")
    print(f"RAG 서비스 초기화 중... (embedding: {embedding_provider})")

    # Settings 수정 — 파이프라인 내부 평가 비활성화 (Router 생성 전에 적용)
    from utils.config import get_settings

    settings = get_settings()
    original_ragas_flag = settings.enable_ragas_evaluation
    original_llm_eval_flag = settings.enable_llm_evaluation

    # RAGAS 평가기를 먼저 생성 (enable_ragas_evaluation=True 필요)
    settings.enable_ragas_evaluation = True
    ragas_eval = RagasEvaluator()

    if not ragas_eval.is_available:
        print(
            "RAGAS 라이브러리가 설치되지 않았습니다.\n"
            "설치: pip install ragas datasets"
        )
        settings.enable_ragas_evaluation = original_ragas_flag
        return

    # 파이프라인 내부 평가/보충검색/재시도 비활성화 (배치 속도 최적화)
    settings.enable_ragas_evaluation = False
    settings.enable_llm_evaluation = False
    original_legal_supp_flag = settings.enable_legal_supplement
    settings.enable_legal_supplement = False
    original_post_eval_flag = settings.enable_post_eval_retry
    settings.enable_post_eval_retry = False
    original_graduated_retry_flag = settings.enable_graduated_retry
    settings.enable_graduated_retry = False
    print("배치 모드: 내부평가/법률보충/재시도/단계적재시도 비활성화")

    # RunPod 워커 사전 예열
    if embedding_provider == "runpod":
        print("RunPod 워커 예열 중...")
        _warmup_runpod()

    # ChromaDB + Router 초기화
    vector_store = ChromaVectorStore()

    # ChromaDB 연결 pre-warm — 모든 컬렉션에 더미 검색으로 BM25 인덱스 초기화
    print("ChromaDB 연결 예열 중...")
    warmup_start = time.time()
    try:
        collections = vector_store.list_collections()
        for coll in collections:
            coll_start = time.time()
            vector_store.similarity_search("테스트", coll, k=1)
            print(f"  {coll}: {time.time() - coll_start:.1f}s")
        print(f"  ChromaDB 예열 완료: {time.time() - warmup_start:.1f}s ({len(collections)} 컬렉션)")
    except Exception as e:
        print(f"  ChromaDB 예열 실패 (계속 진행): {e}")

    router = MainRouter(vector_store=vector_store)

    # 데이터셋 로드
    dataset = load_test_dataset(dataset_path)
    total_count = len(dataset)
    print(f"테스트 데이터: {total_count}개 질문")
    print(f"질문별 타임아웃: {question_timeout}초\n")

    # 모든 질문에 대해 RAG 실행
    questions: list[str] = []
    answers: list[str] = []
    contexts_list: list[list[str]] = []
    ground_truths: list[str] = []
    timeout_flags: list[bool] = []
    elapsed_times: list[float] = []
    has_ground_truth = all("ground_truth" in item for item in dataset)

    for i, item in enumerate(dataset):
        question = item["question"]
        preview = question[:QUESTION_PREVIEW_LENGTH]
        if len(question) > QUESTION_PREVIEW_LENGTH:
            preview += "..."

        start_time = time.time()
        timed_out = False

        try:
            response = await asyncio.wait_for(
                router.aprocess(query=question),
                timeout=question_timeout,
            )
            elapsed = time.time() - start_time

            questions.append(question)
            answers.append(response.content)
            contexts = [
                s.content
                for s in response.sources
                if s.content and s.content.strip()
            ]
            contexts_list.append(contexts if contexts else ["컨텍스트 없음"])
            print(f"[{i + 1}/{total_count}] ({elapsed:.1f}s) {preview}")

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            timed_out = True
            questions.append(question)
            answers.append("[TIMEOUT]")
            contexts_list.append(["타임아웃으로 컨텍스트 없음"])
            print(f"[{i + 1}/{total_count}] TIMEOUT ({elapsed:.0f}s) {preview}")

        except Exception as e:
            elapsed = time.time() - start_time
            questions.append(question)
            answers.append(f"[ERROR] {e}")
            contexts_list.append(["오류로 컨텍스트 없음"])
            print(f"[{i + 1}/{total_count}] ERROR ({elapsed:.1f}s) {preview}: {e}")

        timeout_flags.append(timed_out)
        elapsed_times.append(round(elapsed, 2))

        if has_ground_truth:
            ground_truths.append(item["ground_truth"])

    # 타임아웃 통계
    timeout_count = sum(timeout_flags)
    valid_count = total_count - timeout_count
    print(f"\n완료: {valid_count}/{total_count} 성공, {timeout_count} 타임아웃")

    # RAGAS 배치 평가 — 타임아웃 제외한 유효 질문만
    valid_indices = [i for i, t in enumerate(timeout_flags) if not t]

    if not valid_indices:
        print("유효한 응답이 없어 RAGAS 평가를 건너뜁니다.")
        settings.enable_ragas_evaluation = original_ragas_flag
        vector_store.close()
        return

    valid_questions = [questions[i] for i in valid_indices]
    valid_answers = [answers[i] for i in valid_indices]
    valid_contexts = [contexts_list[i] for i in valid_indices]
    valid_ground_truths = (
        [ground_truths[i] for i in valid_indices] if has_ground_truth else None
    )

    print(f"\nRAGAS 배치 평가 실행 중... ({len(valid_indices)}건)")
    ragas_results = ragas_eval.evaluate_batch(
        questions=valid_questions,
        answers=valid_answers,
        contexts_list=valid_contexts,
        ground_truths=valid_ground_truths,
    )

    # 유효 결과를 전체 인덱스에 매핑
    from evaluation.ragas_evaluator import RagasMetrics

    all_results: list[RagasMetrics] = []
    ragas_idx = 0
    for i in range(total_count):
        if timeout_flags[i]:
            all_results.append(RagasMetrics(error="TIMEOUT"))
        else:
            all_results.append(ragas_results[ragas_idx])
            ragas_idx += 1

    # 결과 출력
    print("\n" + "=" * SEPARATOR_LENGTH)
    print("RAGAS 배치 평가 결과")
    print("=" * SEPARATOR_LENGTH)

    metric_keys = ["faithfulness", "answer_relevancy", "context_precision"]
    if has_ground_truth:
        metric_keys.append("context_recall")

    total_metrics: dict[str, list[float]] = {key: [] for key in metric_keys}

    for i, (q, metrics) in enumerate(zip(questions, all_results)):
        preview = q[:QUESTION_PREVIEW_LENGTH]
        if len(q) > QUESTION_PREVIEW_LENGTH:
            preview += "..."
        elapsed_str = f" ({elapsed_times[i]:.1f}s)"
        if timeout_flags[i]:
            print(f"\n[{i + 1}] TIMEOUT{elapsed_str} {preview}")
            continue
        print(f"\n[{i + 1}]{elapsed_str} {preview}")
        if metrics.available:
            for key in metric_keys:
                val = getattr(metrics, key)
                if val is not None:
                    total_metrics[key].append(val)
                    print(f"  {key}: {val:.4f}")
        elif metrics.error:
            print(f"  오류: {metrics.error}")

    # 전체 평균 출력
    print("\n" + "-" * SEPARATOR_LENGTH)
    print(f"평균 메트릭 (유효 {valid_count}건, 타임아웃 {timeout_count}건 제외):")
    averages: dict[str, float | None] = {}
    for key, values in total_metrics.items():
        if values:
            avg = sum(values) / len(values)
            averages[key] = round(avg, 4)
            print(f"  {key}: {avg:.4f} (n={len(values)})")
        else:
            averages[key] = None
            print(f"  {key}: (데이터 없음)")

    # 결과 저장
    if output_path:
        output_data = {
            "dataset": dataset_path,
            "count": total_count,
            "has_ground_truth": has_ground_truth,
            "embedding_provider": embedding_provider,
            "question_timeout": question_timeout,
            "timeout_count": timeout_count,
            "valid_count": valid_count,
            "results": [
                {
                    "question": q,
                    "timeout": timeout_flags[i],
                    "elapsed_seconds": elapsed_times[i],
                    "metrics": all_results[i].to_dict(),
                }
                for i, q in enumerate(questions)
            ],
            "averages": averages,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장됨: {output_path}")

    # 정리
    settings.enable_ragas_evaluation = original_ragas_flag
    settings.enable_llm_evaluation = original_llm_eval_flag
    settings.enable_legal_supplement = original_legal_supp_flag
    settings.enable_post_eval_retry = original_post_eval_flag
    settings.enable_graduated_retry = original_graduated_retry_flag
    vector_store.close()


def main() -> None:
    """배치 평가 CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="RAGAS 배치 평가 - 테스트 데이터셋 기반 RAG 정량 평가"
    )
    parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        help="테스트 데이터셋 경로 (JSONL 형식)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="결과 저장 경로 (JSON 형식)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=DEFAULT_QUESTION_TIMEOUT,
        help=f"질문별 타임아웃 초 (기본: {DEFAULT_QUESTION_TIMEOUT})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_batch_evaluation(args.dataset, args.output, args.timeout))


if __name__ == "__main__":
    main()
