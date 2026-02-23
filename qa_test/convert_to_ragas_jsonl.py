"""QA 데이터셋(MD) → RAGAS JSONL 변환 스크립트.

사용법:
    py convert_to_ragas_jsonl.py
    py convert_to_ragas_jsonl.py --input bizi_qa_dataset_v3.md --output ragas_v3.jsonl

출력 형식 (JSONL):
    {"id": "W-001", "question": "...", "ground_truth": "...", "domain": "hr", "difficulty": "Easy"}
"""

import argparse
import json
import re
import sys
from pathlib import Path


def extract_qa_pairs(md_path: str) -> list[dict]:
    """MD 파일에서 질문과 기대 답변을 추출합니다.

    2단계 파싱: 먼저 섹션 분할 후 각 섹션에서 필드 추출.
    """
    content = Path(md_path).read_text(encoding="utf-8")

    # 1단계: ### X-NNN 헤더로 섹션 분할
    section_pattern = r'(### ([UVWX])-(\d+)\..+?)(?=\n### [UVWX]-\d+\.|\Z)'
    sections = re.findall(section_pattern, content, re.DOTALL)

    results = []
    for section_text, prefix, num_str in sections:
        # 도메인
        m_domain = re.search(r'- \*\*도메인\*\*: (.+)', section_text)
        if not m_domain:
            continue
        domain = m_domain.group(1).strip()

        # 난이도
        m_diff = re.search(r'- \*\*난이도\*\*: (.+)', section_text)
        difficulty = m_diff.group(1).strip() if m_diff else ""

        # 질문
        m_question = re.search(
            r'\*\*질문\*\*: (.+?)(?=\n\n\*\*기대 답변\*\*:)',
            section_text,
            re.DOTALL,
        )
        if not m_question:
            continue
        question = m_question.group(1).strip()

        # 기대 답변 추출 (여러 형식 지원)
        # v3/v2-Part1: **기대 답변**:\n\n...\n---\n**[답변 근거]**
        # v2-Part2:    **기대 답변**:\n텍스트...\n---\n**[답변 근거]**
        # v2-Part3/4:  **기대 답변**:\n**[관점]**...\n\n**검증 포인트**
        m_gt = re.search(
            r'\*\*기대 답변\*\*:\n+(.+?)\n(?:---\n\*\*\[|\n\*\*검증 포인트\*\*)',
            section_text,
            re.DOTALL,
        )
        if not m_gt:
            continue
        ground_truth = m_gt.group(1).strip()

        results.append({
            "id": f"{prefix}-{int(num_str):03d}",
            "question": question,
            "ground_truth": ground_truth,
            "domain": domain,
            "difficulty": difficulty,
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="QA MD → RAGAS JSONL 변환")
    parser.add_argument(
        "--input", "-i",
        default="bizi_qa_dataset_v3.md",
        help="입력 MD 파일 경로 (기본: bizi_qa_dataset_v3.md)",
    )
    parser.add_argument(
        "--output", "-o",
        default="ragas_dataset_v3.jsonl",
        help="출력 JSONL 파일 경로 (기본: ragas_dataset_v3.jsonl)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    pairs = extract_qa_pairs(str(input_path))
    if not pairs:
        print("Error: no questions extracted. Check MD format.")
        sys.exit(1)

    # JSONL 출력
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        for item in pairs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # 검증
    empty_gt = sum(1 for p in pairs if not p["ground_truth"])
    domains: dict[str, int] = {}
    for p in pairs:
        domains[p["domain"]] = domains.get(p["domain"], 0) + 1

    print(f"Converted: {len(pairs)} items -> {output_path}")
    if empty_gt:
        print(f"  Warning: {empty_gt} items with empty ground_truth")
    print(f"  Domains: {domains}")


if __name__ == "__main__":
    main()
