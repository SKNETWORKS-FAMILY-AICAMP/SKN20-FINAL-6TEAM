"""JSONL 데이터 정제 스크립트.

data/preprocessed/ 하위 모든 JSONL 파일을 순회하며 다음 정제를 수행합니다:
1. domain 필드 정규화 (DOMAIN_LABELS 키와 일치시킴)
2. type 필드 정규화
3. 불필요 메타데이터 제거 (filter_method, filter_reason, page, page_range, qa_count)
4. HTML 잔재 정리 (court_cases의 reference 필드)
5. 화이트리스트 기반 메타데이터 정리 (파일별 유지할 키만 남기고 나머지 제거)
6. court_cases의 reference → content 이동 (검색 가능화)

사용법:
    py scripts/preprocessing/clean_jsonl.py                # 실행 (원본 .bak 백업)
    py scripts/preprocessing/clean_jsonl.py --dry-run      # 변경 사항만 리포트
    py scripts/preprocessing/clean_jsonl.py --no-backup    # 백업 없이 실행
"""

import argparse
import json
import re
import shutil
from pathlib import Path

# 프로젝트 루트 기준 경로
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "preprocessed"

# --- 1. domain 정규화 매핑 ---
DOMAIN_NORMALIZE: dict[str, str] = {
    "funding": "startup_funding",
    "startup": "startup_funding",
    "labor": "hr_labor",
}

# --- 2. type 정규화 매핑 (파일별) ---
TYPE_NORMALIZE: dict[str, dict[str, str]] = {
    "labor_interpretation.jsonl": {"labor": "interpretation"},
}

# --- 3. 제거할 메타데이터 키 (파일별) — 기존 호환 ---
METADATA_REMOVE: dict[str, list[str]] = {
    "laws_full.jsonl": ["filter_method", "filter_reason"],
    "interpretations.jsonl": ["filter_method", "filter_reason"],
    "tax_support.jsonl": ["page"],
    "hr_insurance_edu.jsonl": ["page_range"],
    "labor_interpretation.jsonl": ["qa_count"],
}

# --- 4. HTML 정리 대상 파일 (metadata.reference) ---
HTML_CLEAN_FILES: set[str] = {
    "court_cases_tax.jsonl",
    "court_cases_labor.jsonl",
}

# --- 5. 화이트리스트 기반 메타데이터 정리 ---
# 파일별 유지할 메타데이터 키만 정의. 여기에 없는 키는 제거됨.
# None이면 화이트리스트 적용하지 않음 (기존 동작 유지).
METADATA_WHITELIST: dict[str, set[str] | None] = {
    "announcements.jsonl": {"region", "support_type", "original_id"},
    "court_cases_tax.jsonl": {"case_no", "court_name"},
    "court_cases_labor.jsonl": {"case_no", "court_name"},
    "laws_full.jsonl": {"law_id"},
    "interpretations.jsonl": {"case_no"},
    "labor_interpretation.jsonl": set(),  # 모든 메타데이터 제거
    "hr_insurance_edu.jsonl": set(),
    "tax_support.jsonl": set(),
    "industry_startup_guide_filtered.jsonl": {"industry_code", "license_type"},
    "startup_procedures_filtered.jsonl": set(),
}

# --- 6. reference → content 이동 대상 ---
REFERENCE_TO_CONTENT_FILES: set[str] = {
    "court_cases_tax.jsonl",
    "court_cases_labor.jsonl",
}

# HTML 태그 제거 정규식
HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_html(text: str) -> str:
    """HTML 잔재를 정리합니다.

    - <br/>, <br>, <br /> → \\n
    - 기타 HTML 태그 제거
    - 연속 줄바꿈 정리
    """
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_record(record: dict, filename: str) -> tuple[dict, list[str]]:
    """단일 레코드를 정제하고 변경 내역을 반환합니다.

    Args:
        record: JSONL 레코드 (dict)
        filename: 파일명 (e.g. "announcements.jsonl")

    Returns:
        (정제된 레코드, 변경 내역 리스트)
    """
    changes: list[str] = []

    # 1. domain 정규화
    old_domain = record.get("domain", "")
    if old_domain in DOMAIN_NORMALIZE:
        record["domain"] = DOMAIN_NORMALIZE[old_domain]
        changes.append(f"domain: {old_domain} → {record['domain']}")

    # 2. type 정규화
    if filename in TYPE_NORMALIZE:
        old_type = record.get("type", "")
        mapping = TYPE_NORMALIZE[filename]
        if old_type in mapping:
            record["type"] = mapping[old_type]
            changes.append(f"type: {old_type} → {record['type']}")

    # 3. 기존 메타데이터 제거 (레거시 호환)
    if filename in METADATA_REMOVE:
        metadata = record.get("metadata", {})
        for key in METADATA_REMOVE[filename]:
            if key in metadata:
                del metadata[key]
                changes.append(f"metadata.{key} removed")

    # 4. HTML 정리 (reference 필드)
    if filename in HTML_CLEAN_FILES:
        metadata = record.get("metadata", {})
        ref = metadata.get("reference", "")
        if ref and ("<" in ref or "&lt;" in ref):
            cleaned = clean_html(ref)
            if cleaned != ref:
                metadata["reference"] = cleaned
                changes.append("metadata.reference: HTML cleaned")

    # 5. reference → content 이동 (HTML 정리 후 수행)
    if filename in REFERENCE_TO_CONTENT_FILES:
        metadata = record.get("metadata", {})
        ref = metadata.get("reference", "")
        if ref and ref.strip():
            content = record.get("content", "")
            ref_marker = "\n\n[참조조문] "
            # 이미 이동된 경우 중복 방지
            if ref_marker not in content:
                record["content"] = content + ref_marker + ref.strip()
                changes.append("metadata.reference → content 이동")

    # 6. 화이트리스트 기반 메타데이터 정리 (가장 마지막에 수행)
    whitelist = METADATA_WHITELIST.get(filename)
    if whitelist is not None:
        metadata = record.get("metadata", {})
        keys_to_remove = [k for k in metadata if k not in whitelist]
        for key in keys_to_remove:
            del metadata[key]
            changes.append(f"metadata.{key} whitelist-removed")

    return record, changes


def process_file(
    filepath: Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> dict[str, int]:
    """단일 JSONL 파일을 정제합니다.

    Args:
        filepath: JSONL 파일 경로
        dry_run: True면 변경 사항만 리포트
        backup: True면 원본을 .bak으로 백업

    Returns:
        변경 통계 dict
    """
    filename = filepath.name
    stats: dict[str, int] = {
        "total": 0,
        "modified": 0,
        "domain_changed": 0,
        "type_changed": 0,
        "metadata_removed": 0,
        "metadata_whitelist_removed": 0,
        "html_cleaned": 0,
        "reference_moved": 0,
    }

    cleaned_lines: list[str] = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["total"] += 1

            record = json.loads(line)
            record, changes = clean_record(record, filename)

            if changes:
                stats["modified"] += 1
                for c in changes:
                    if c.startswith("domain:"):
                        stats["domain_changed"] += 1
                    elif c.startswith("type:"):
                        stats["type_changed"] += 1
                    elif "whitelist-removed" in c:
                        stats["metadata_whitelist_removed"] += 1
                    elif "removed" in c:
                        stats["metadata_removed"] += 1
                    elif "HTML" in c:
                        stats["html_cleaned"] += 1
                    elif "content 이동" in c:
                        stats["reference_moved"] += 1

            cleaned_lines.append(json.dumps(record, ensure_ascii=False))

    if not dry_run and stats["modified"] > 0:
        if backup:
            bak_path = filepath.with_suffix(".jsonl.bak")
            shutil.copy2(filepath, bak_path)

        with open(filepath, "w", encoding="utf-8") as f:
            for line in cleaned_lines:
                f.write(line + "\n")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JSONL 데이터 정제 스크립트",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 사항만 리포트 (파일 수정 안함)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="백업(.bak) 없이 실행",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY-RUN] 변경 사항만 리포트합니다.\n")

    total_files = 0
    total_modified = 0

    # data/preprocessed/ 하위 모든 JSONL 순회
    for filepath in sorted(DATA_DIR.rglob("*.jsonl")):
        # .bak, _etc 파일 스킵
        if ".bak" in str(filepath) or "_etc" in filepath.name:
            continue

        stats = process_file(
            filepath,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
        total_files += 1

        if stats["modified"] > 0:
            total_modified += 1
            action = "[DRY-RUN]" if args.dry_run else "[CLEANED]"
            print(f"{action} {filepath.relative_to(BASE_DIR)}")
            print(f"  총 {stats['total']}건 중 {stats['modified']}건 수정")
            if stats["domain_changed"]:
                print(f"  - domain 정규화: {stats['domain_changed']}건")
            if stats["type_changed"]:
                print(f"  - type 정규화: {stats['type_changed']}건")
            if stats["metadata_removed"]:
                print(f"  - 메타데이터 제거: {stats['metadata_removed']}건")
            if stats["metadata_whitelist_removed"]:
                print(f"  - 메타데이터 화이트리스트 정리: {stats['metadata_whitelist_removed']}건")
            if stats["html_cleaned"]:
                print(f"  - HTML 정리: {stats['html_cleaned']}건")
            if stats["reference_moved"]:
                print(f"  - reference→content 이동: {stats['reference_moved']}건")
            print()
        else:
            print(f"[SKIP] {filepath.relative_to(BASE_DIR)} (변경 없음)")

    print(f"\n{'='*50}")
    print(f"총 {total_files}개 파일 검사, {total_modified}개 파일 수정")
    if args.dry_run:
        print("(dry-run 모드: 실제 파일은 수정되지 않았습니다)")


if __name__ == "__main__":
    main()
