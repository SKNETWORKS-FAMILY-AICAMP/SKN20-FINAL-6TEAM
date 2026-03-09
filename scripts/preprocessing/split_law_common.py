"""law_common JSONL을 도메인별로 분할하는 스크립트.

laws_full.jsonl과 interpretations.jsonl에 포함된 domain 필드를 기준으로
각 도메인 컬렉션 디렉토리에 분산 적재합니다.

분배 규칙:
  - finance_tax  → finance_tax (재무·세무)/laws_finance_tax.jsonl  (법+해석 병합)
  - hr_labor     → hr_labor (인사·노무)/laws_hr_labor.jsonl        (법+해석 병합)
  - startup_funding → startup_support (창업·지원)/laws_startup.jsonl (법+해석 병합)
  - general      → law_common (...)/laws_general.jsonl             (법만)
                   law_common (...)/interpretations_general.jsonl  (해석만)

원본 파일은 삭제하지 않습니다.

사용법:
    python scripts/preprocessing/split_law_common.py
    python scripts/preprocessing/split_law_common.py --dry-run
"""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "preprocessed"

LAW_COMMON_DIR = DATA_DIR / "law_common"

DOMAIN_OUTPUT: dict[str, Path] = {
    "finance_tax": DATA_DIR / "finance_tax",
    "hr_labor": DATA_DIR / "hr_labor",
    "startup_funding": DATA_DIR / "startup_support",
    "general": LAW_COMMON_DIR,
}

# 비-general 도메인: 법+해석례 단일 파일로 병합
MERGED_OUTPUT_FILENAME: dict[str, str] = {
    "finance_tax": "laws_finance_tax.jsonl",
    "hr_labor": "laws_hr_labor.jsonl",
    "startup_funding": "laws_startup.jsonl",
}

# general 도메인: 파일 유형별 분리
GENERAL_LAWS_FILENAME = "laws_general.jsonl"
GENERAL_INTERP_FILENAME = "interpretations_general.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning("파싱 실패 [%s:%d]: %s", path.name, line_num, e)
    return records


def _write_jsonl(path: Path, records: list[dict], dry_run: bool = False) -> None:
    if dry_run:
        logger.info("[DRY-RUN] 쓰기 생략: %s (%d건)", path, len(records))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("작성 완료: %s (%d건)", path, len(records))


def split(dry_run: bool = False) -> None:
    laws_path = LAW_COMMON_DIR / "laws_full.jsonl"
    interp_path = LAW_COMMON_DIR / "interpretations.jsonl"

    for p in [laws_path, interp_path]:
        if not p.exists():
            raise FileNotFoundError(f"파일 없음: {p}")

    logger.info("laws_full.jsonl 읽는 중...")
    laws_records = _read_jsonl(laws_path)
    logger.info("interpretations.jsonl 읽는 중...")
    interp_records = _read_jsonl(interp_path)

    # 도메인별 버킷: {domain: {"laws": [...], "interpretations": [...]}}
    buckets: dict[str, dict[str, list]] = defaultdict(lambda: {"laws": [], "interpretations": []})

    for rec in laws_records:
        domain = rec.get("domain", "general")
        buckets[domain]["laws"].append(rec)

    for rec in interp_records:
        domain = rec.get("domain", "general")
        buckets[domain]["interpretations"].append(rec)

    # 통계 출력
    logger.info("\n=== 도메인별 분배 현황 ===")
    for domain, data in sorted(buckets.items()):
        laws_cnt = len(data["laws"])
        interp_cnt = len(data["interpretations"])
        logger.info("  %-20s laws=%d, interpretations=%d (합계=%d)", domain, laws_cnt, interp_cnt, laws_cnt + interp_cnt)

    # 비-general 도메인: 법+해석례 병합 후 단일 파일 출력
    for domain, filename in MERGED_OUTPUT_FILENAME.items():
        merged = buckets[domain]["laws"] + buckets[domain]["interpretations"]
        if not merged:
            logger.warning("  [SKIP] %s: 데이터 없음", domain)
            continue
        out_path = DOMAIN_OUTPUT[domain] / filename
        _write_jsonl(out_path, merged, dry_run=dry_run)

    # general 도메인: 법/해석례 각각 분리 저장
    general_laws = buckets["general"]["laws"]
    general_interp = buckets["general"]["interpretations"]

    if general_laws:
        _write_jsonl(DOMAIN_OUTPUT["general"] / GENERAL_LAWS_FILENAME, general_laws, dry_run=dry_run)
    if general_interp:
        _write_jsonl(DOMAIN_OUTPUT["general"] / GENERAL_INTERP_FILENAME, general_interp, dry_run=dry_run)

    logger.info("\n완료. 원본 파일은 보존됩니다.")
    logger.info("  %s", laws_path)
    logger.info("  %s", interp_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="law_common JSONL 도메인별 분할")
    parser.add_argument("--dry-run", action="store_true", help="실제 파일 쓰기 없이 통계만 출력")
    args = parser.parse_args()
    split(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
