"""RAGAS 배치 평가 실행 모듈.

테스트 데이터셋을 사용하여 RAG 시스템의 RAGAS 메트릭을 배치로 평가합니다.

사용법:
    python -m evaluation --dataset tests/test_dataset.jsonl
    python -m evaluation --dataset tests/test_dataset.jsonl --output results.json

테스트 데이터셋 형식 (JSONL):
    {"question": "퇴직금 계산은 어떻게 하나요?", "ground_truth": "퇴직금은..."}
    {"question": "사업자등록 절차는?"}
    (ground_truth는 선택사항)
"""

import argparse
import asyncio
import json
import logging
import sys
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


async def run_batch_evaluation(
    dataset_path: str,
    output_path: str | None = None,
) -> None:
    """배치 평가를 실행합니다.

    Args:
        dataset_path: 테스트 데이터셋 파일 경로
        output_path: 결과 저장 경로 (선택)
    """
    # 초기화
    print("RAG 서비스 초기화 중...")
    vector_store = ChromaVectorStore()
    router = MainRouter(vector_store=vector_store)
    ragas_eval = RagasEvaluator()

    if not ragas_eval.is_available:
        print(
            "RAGAS 라이브러리가 설치되지 않았거나 비활성화되어 있습니다.\n"
            "설치: pip install ragas datasets\n"
            "활성화: .env에 ENABLE_RAGAS_EVALUATION=true 추가"
        )
        vector_store.close()
        return

    # 데이터셋 로드
    dataset = load_test_dataset(dataset_path)
    total_count = len(dataset)
    print(f"테스트 데이터: {total_count}개 질문\n")

    # 모든 질문에 대해 RAG 실행
    questions: list[str] = []
    answers: list[str] = []
    contexts_list: list[list[str]] = []
    ground_truths: list[str] = []
    has_ground_truth = all("ground_truth" in item for item in dataset)

    for i, item in enumerate(dataset):
        question = item["question"]
        preview = question[:QUESTION_PREVIEW_LENGTH]
        if len(question) > QUESTION_PREVIEW_LENGTH:
            preview += "..."
        print(f"[{i + 1}/{total_count}] {preview}")

        response = await router.aprocess(query=question)

        questions.append(question)
        answers.append(response.content)
        contexts = [
            s.content
            for s in response.sources
            if s.content and s.content.strip()
        ]
        contexts_list.append(contexts if contexts else ["컨텍스트 없음"])

        if has_ground_truth:
            ground_truths.append(item["ground_truth"])

    # RAGAS 배치 평가
    print("\nRAGAS 배치 평가 실행 중...")
    results = ragas_eval.evaluate_batch(
        questions=questions,
        answers=answers,
        contexts_list=contexts_list,
        ground_truths=ground_truths if has_ground_truth else None,
    )

    # 결과 출력
    print("\n" + "=" * SEPARATOR_LENGTH)
    print("RAGAS 배치 평가 결과")
    print("=" * SEPARATOR_LENGTH)

    metric_keys = ["faithfulness", "answer_relevancy", "context_precision"]
    if has_ground_truth:
        metric_keys.append("context_recall")

    total_metrics: dict[str, list[float]] = {key: [] for key in metric_keys}

    for i, (q, metrics) in enumerate(zip(questions, results)):
        preview = q[:QUESTION_PREVIEW_LENGTH]
        if len(q) > QUESTION_PREVIEW_LENGTH:
            preview += "..."
        print(f"\n[{i + 1}] {preview}")
        if metrics.available:
            for key in metric_keys:
                val = getattr(metrics, key)
                if val is not None:
                    total_metrics[key].append(val)
                    print(f"  {key}: {val:.4f}")
        elif metrics.error:
            print(f"  오류: {metrics.error}")

    # 평균 출력
    print("\n" + "-" * SEPARATOR_LENGTH)
    print("평균 메트릭:")
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
            "results": [
                {"question": q, "metrics": m.to_dict()}
                for q, m in zip(questions, results)
            ],
            "averages": averages,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장됨: {output_path}")

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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_batch_evaluation(args.dataset, args.output))


if __name__ == "__main__":
    main()
