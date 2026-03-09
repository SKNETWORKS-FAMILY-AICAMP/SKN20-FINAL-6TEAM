"""ground_truth 코퍼스 정렬 검증 도구.

각 ground_truth의 주장(claim)이 VectorDB에서 검색 가능한지 진단합니다.

Usage:
    cd rag
    python -m evaluation.ground_truth_alignment -d eval_0301/ragas_dataset_0301.jsonl
    python -m evaluation.ground_truth_alignment -d eval_0301/ragas_dataset_0301.jsonl --threshold 1.5 --output alignment.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

# 데이터셋의 domain 필드 → ChromaDB 컬렉션 매핑
DOMAIN_COLLECTION_MAP = {
    "startup": "startup_funding",
    "finance": "finance_tax",
    "hr": "hr_labor",
    "law": "law_common",
    # 이미 컬렉션명인 경우도 지원
    "startup_funding": "startup_funding",
    "finance_tax": "finance_tax",
    "hr_labor": "hr_labor",
    "law_common": "law_common",
}

DEFAULT_THRESHOLD = 1.0


def extract_claims(ground_truth: str) -> list[str]:
    """ground_truth에서 개별 claim을 추출합니다.

    '- ' 또는 줄바꿈으로 구분된 항목을 분리합니다.
    """
    claims = []
    for line in ground_truth.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if line:
            claims.append(line)
    return claims if claims else [ground_truth.strip()]


def check_alignment(
    dataset_path: str,
    threshold: float = DEFAULT_THRESHOLD,
    output_path: str | None = None,
) -> None:
    """ground_truth의 각 claim에 대해 VectorDB 검색 가능 여부를 진단합니다."""
    # 데이터셋 로드
    dataset: list[dict] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                dataset.append(json.loads(line))

    if not dataset:
        print("Empty dataset.")
        return

    has_ground_truth = all("ground_truth" in item for item in dataset)
    if not has_ground_truth:
        print("Dataset has no ground_truth field. Exiting.")
        return

    vector_store = ChromaVectorStore()

    total_claims = 0
    retrievable_claims = 0
    question_results: list[dict] = []
    zero_coverage_questions: list[str] = []

    for idx, item in enumerate(dataset):
        question = str(item["question"])
        ground_truth = str(item["ground_truth"])
        domain_raw = str(item.get("domain", ""))
        domain = DOMAIN_COLLECTION_MAP.get(domain_raw, domain_raw)

        if not domain:
            print(f"[{idx + 1}] No domain for: {question[:60]}... (skipped)")
            continue

        claims = extract_claims(ground_truth)
        claim_results = []
        q_retrievable = 0

        for claim in claims:
            total_claims += 1
            try:
                results = vector_store.similarity_search_with_score(
                    claim, domain, k=3
                )
                best_score = results[0][1] if results else float("inf")
                is_retrievable = best_score <= threshold
            except Exception as e:
                logger.warning("Search failed for claim '%s': %s", claim[:50], e)
                best_score = float("inf")
                is_retrievable = False

            if is_retrievable:
                retrievable_claims += 1
                q_retrievable += 1

            claim_results.append({
                "claim": claim,
                "best_distance": round(best_score, 4) if best_score != float("inf") else None,
                "retrievable": is_retrievable,
            })

        coverage = q_retrievable / len(claims) if claims else 0.0
        if coverage == 0.0:
            zero_coverage_questions.append(question)

        question_results.append({
            "question": question,
            "domain": domain,
            "claims_count": len(claims),
            "retrievable_count": q_retrievable,
            "coverage": round(coverage, 4),
            "claims": claim_results,
        })

        status = "OK" if coverage >= 0.5 else "LOW"
        print(
            f"[{idx + 1}/{len(dataset)}] {status} coverage={coverage:.0%} "
            f"({q_retrievable}/{len(claims)}) {question[:60]}"
        )

    vector_store.close()

    # 전체 요약
    overall_coverage = retrievable_claims / total_claims if total_claims else 0.0
    print(f"\n{'=' * 70}")
    print(f"Overall: {retrievable_claims}/{total_claims} claims retrievable ({overall_coverage:.1%})")
    print(f"Threshold: {threshold} (L2 distance)")
    print(f"Questions: {len(dataset)}, Zero-coverage: {len(zero_coverage_questions)}")

    if zero_coverage_questions:
        print("\nZero-coverage questions:")
        for q in zero_coverage_questions:
            print(f"  - {q[:80]}")

    if output_path:
        output_data = {
            "dataset": dataset_path,
            "threshold": threshold,
            "total_claims": total_claims,
            "retrievable_claims": retrievable_claims,
            "overall_coverage": round(overall_coverage, 4),
            "zero_coverage_count": len(zero_coverage_questions),
            "questions": question_results,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ground_truth-VectorDB alignment checker"
    )
    parser.add_argument("--dataset", "-d", required=True, help="JSONL dataset path")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"L2 distance threshold for retrievable (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument("--output", "-o", default=None, help="Output JSON path")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    check_alignment(args.dataset, args.threshold, args.output)


if __name__ == "__main__":
    main()
