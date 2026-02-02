"""업종코드(KSIC 기반) 및 지역코드 SQL/TS 생성 스크립트.

입력:
  - data/origin/startup_funding/(붙임2)업종코드_표준산업분류연계표_홈페이지게시.xlsx
  - data/국토교통부_법정동코드_20250805.csv

출력:
  - --format sql (기본): SQL INSERT 문
  - --format ts: TypeScript 상수 (INDUSTRY_MAJOR, INDUSTRY_MINOR)

사용법:
  python backend/scripts/generate_code_sql.py
  python backend/scripts/generate_code_sql.py --format ts
  python backend/scripts/generate_code_sql.py --output output.sql
"""

import argparse
import csv
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("openpyxl 패키지가 필요합니다: pip install openpyxl", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

XLSX_PATH = PROJECT_ROOT / "data" / "origin" / "startup_funding" / "(붙임2)업종코드_표준산업분류연계표_홈페이지게시.xlsx"
CSV_PATH = PROJECT_ROOT / "data" / "국토교통부_법정동코드_20250805.csv"

# 대분류 letter → B-코드 매핑 (A~U → BA~BU)
MAJOR_LETTER_MAP = {
    "A": "BA", "B": "BB", "C": "BC", "D": "BD", "E": "BE",
    "F": "BF", "G": "BG", "H": "BH", "I": "BI", "J": "BJ",
    "K": "BK", "L": "BL", "M": "BM", "N": "BN", "O": "BO",
    "P": "BP", "Q": "BQ", "R": "BR", "S": "BS", "T": "BT",
    "U": "BU",
}


def escape_sql(s: str) -> str:
    """SQL 문자열에서 특수문자를 이스케이프하고 앞뒤 공백을 제거합니다.

    Note: strip()은 앞뒤 공백만 제거하며, 이름 내부 공백(예: '건 설 업')은 보존됩니다.
    """
    return s.replace("'", "''").strip()


def extract_industry_codes() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """XLSX에서 KSIC(한국표준산업분류) 기반 업종 대분류/소분류 추출.

    KSIC 소분류(3자리)는 이름 중복이 없어 드롭다운 표시에 적합합니다.

    Returns:
        (majors, minors) 각각 (name, main_code, code) 튜플 리스트
    """
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb["연계표"]

    majors_dict: dict[str, str] = {}
    minors_dict: dict[tuple[str, str], str] = {}

    for row in ws.iter_rows(min_row=6, values_only=True):
        major_letter = row[16]  # column Q: KSIC 대분류 letter (A~U)
        major_name = row[17]    # column R: KSIC 대분류 이름
        minor_code = row[20]    # column U: KSIC 소분류 코드 (3자리 숫자)
        minor_name = row[21]    # column V: KSIC 소분류 이름

        if major_letter and major_name and major_letter not in majors_dict:
            majors_dict[major_letter] = str(major_name).strip()

        if major_letter and minor_code and minor_name:
            key = (str(major_letter), str(minor_code).zfill(3))
            if key not in minors_dict:
                minors_dict[key] = str(minor_name).strip()

    wb.close()

    majors = []
    for letter in sorted(majors_dict.keys()):
        prefix = MAJOR_LETTER_MAP[letter]
        code = f"{prefix}000000"
        majors.append((majors_dict[letter], "B", code))

    minors = []
    for (letter, minor_num), name in sorted(minors_dict.items()):
        prefix = MAJOR_LETTER_MAP[letter]
        code = f"{prefix}{minor_num}000"
        minors.append((name, "B", code))

    return majors, minors


def extract_region_codes() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """CSV에서 지역 시도/시군구 추출.

    Returns:
        (sidos, sigungus) 각각 (name, main_code, code) 튜플 리스트
    """
    sidos_dict: dict[str, str] = {}
    sigungus_dict: dict[str, str] = {}

    with open(CSV_PATH, encoding="euc-kr") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            raw_code = row[0]
            name = row[1].strip()
            status = row[2].strip()

            if status != "존재":
                continue

            # 시도: XX00000000
            if raw_code[2:] == "00000000":
                sido_code = raw_code[:2]
                r_code = f"R{sido_code}00000"
                sidos_dict[r_code] = name

            # 시군구: XXXXX00000 (5th digit not 000)
            elif raw_code[5:] == "00000" and raw_code[2:5] != "000":
                sg_code5 = raw_code[:5]
                r_code = f"R{sg_code5}00"
                # 시군구 이름: 풀네임에서 마지막 부분
                parts = name.split()
                sg_name = parts[-1] if len(parts) > 1 else name
                sigungus_dict[r_code] = sg_name

    # 세종특별자치시 수동 추가 (법정동코드에 시도 레벨만 있고 시군구가 없음)
    sejong_sido = "R3600000"
    if sejong_sido not in sidos_dict:
        sidos_dict[sejong_sido] = "세종특별자치시"

    sidos = [(name, "R", code) for code, name in sorted(sidos_dict.items())]
    sigungus = [(name, "R", code) for code, name in sorted(sigungus_dict.items())]

    return sidos, sigungus


def generate_sql(output_file: str | None = None) -> None:
    """SQL INSERT 문 생성."""
    if not XLSX_PATH.exists():
        print(f"Error: XLSX file not found: {XLSX_PATH}", file=sys.stderr)
        sys.exit(1)
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    majors, minors = extract_industry_codes()
    sidos, sigungus = extract_region_codes()

    lines: list[str] = []
    lines.append("-- ============================================")
    lines.append("-- 업종코드 (대분류)")
    lines.append("-- ============================================")
    for name, main_code, code in majors:
        lines.append(
            f"    UNION ALL SELECT '{escape_sql(name)}', '{main_code}', '{code}'"
        )

    lines.append("")
    lines.append("-- ============================================")
    lines.append("-- 업종코드 (소분류)")
    lines.append("-- ============================================")
    for name, main_code, code in minors:
        lines.append(
            f"    UNION ALL SELECT '{escape_sql(name)}', '{main_code}', '{code}'"
        )

    lines.append("")
    lines.append("-- ============================================")
    lines.append("-- 지역코드 (시도)")
    lines.append("-- ============================================")
    for name, main_code, code in sidos:
        lines.append(
            f"    UNION ALL SELECT '{escape_sql(name)}', '{main_code}', '{code}'"
        )

    lines.append("")
    lines.append("-- ============================================")
    lines.append("-- 지역코드 (시군구)")
    lines.append("-- ============================================")
    for name, main_code, code in sigungus:
        lines.append(
            f"    UNION ALL SELECT '{escape_sql(name)}', '{main_code}', '{code}'"
        )

    output = "\n".join(lines)

    if output_file:
        Path(output_file).write_text(output, encoding="utf-8")
        print(f"SQL 생성 완료: {output_file}", file=sys.stderr)
    else:
        print(output)

    # Summary
    print(f"\n-- 통계:", file=sys.stderr)
    print(f"--   업종 대분류: {len(majors)}건", file=sys.stderr)
    print(f"--   업종 소분류: {len(minors)}건", file=sys.stderr)
    print(f"--   지역 시도: {len(sidos)}건", file=sys.stderr)
    print(f"--   지역 시군구: {len(sigungus)}건", file=sys.stderr)
    print(f"--   총: {len(majors) + len(minors) + len(sidos) + len(sigungus)}건", file=sys.stderr)


def generate_ts(output_file: str | None = None) -> None:
    """TypeScript 업종코드 상수 생성."""
    if not XLSX_PATH.exists():
        print(f"Error: XLSX file not found: {XLSX_PATH}", file=sys.stderr)
        sys.exit(1)

    majors, minors = extract_industry_codes()

    lines: list[str] = []

    # INDUSTRY_MAJOR
    lines.append("// Industry codes - Major categories (대분류 %d개)" % len(majors))
    lines.append("export const INDUSTRY_MAJOR: Record<string, string> = {")
    for name, _main_code, code in majors:
        lines.append(f"  {code}: '{name}',")
    lines.append("};")
    lines.append("")

    # INDUSTRY_MINOR grouped by major
    lines.append(
        "// Industry codes - Minor categories grouped by major (소분류 %d개)"
        % len(minors)
    )
    lines.append(
        "export const INDUSTRY_MINOR: Record<string, Record<string, string>> = {"
    )

    # Group minors by major code
    groups: dict[str, list[tuple[str, str]]] = {}
    for name, _main_code, code in minors:
        major_key = code[:2] + "000000"
        if major_key not in groups:
            groups[major_key] = []
        groups[major_key].append((code, name))

    for major_key in sorted(groups.keys()):
        lines.append(f"  {major_key}: {{")
        for code, name in groups[major_key]:
            lines.append(f"    {code}: '{name}',")
        lines.append("  },")

    lines.append("};")

    output = "\n".join(lines)

    if output_file:
        Path(output_file).write_text(output, encoding="utf-8")
        print(f"TS 생성 완료: {output_file}", file=sys.stderr)
    else:
        print(output)

    # Summary
    print(f"\n-- 통계:", file=sys.stderr)
    print(f"--   업종 대분류: {len(majors)}건", file=sys.stderr)
    print(f"--   업종 소분류: {len(minors)}건", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="업종코드/지역코드 SQL/TS 생성")
    parser.add_argument("--output", "-o", help="출력 파일 경로 (미지정 시 stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["sql", "ts"],
        default="sql",
        help="출력 포맷 (기본: sql)",
    )
    args = parser.parse_args()

    if args.format == "ts":
        generate_ts(args.output)
    else:
        generate_sql(args.output)
