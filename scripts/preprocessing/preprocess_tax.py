"""
세무 지원 제도 PDF 전처리 (Upstage Document Parse API)

표가 많은 PDF를 Upstage OCR로 추출하여 JSONL로 변환합니다.
"""

import json
import os
import re
import sys
import time
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
UPSTAGE_URL = "https://api.upstage.ai/v1/document-ai/document-parse"


def parse_document(pdf_path: str, output_format: str = "html") -> dict[str, Any]:
    """Upstage Document Parse API로 PDF를 파싱합니다.

    Args:
        pdf_path: PDF 파일 경로
        output_format: 출력 형식 ("html", "markdown", "text")

    Returns:
        API 응답 JSON
    """
    if not UPSTAGE_API_KEY:
        print("ERROR: UPSTAGE_API_KEY가 .env에 설정되지 않았습니다.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}

    with open(pdf_path, "rb") as f:
        files = {"document": (os.path.basename(pdf_path), f, "application/pdf")}
        formats = [output_format] if output_format == "text" else [output_format, "text"]
        data = {
            "ocr": "force",
            "output_formats": json.dumps(formats),
        }

        print(f"  Upstage API 호출 중: {os.path.basename(pdf_path)}...")
        response = httpx.post(
            UPSTAGE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120.0,
        )

    if response.status_code != 200:
        print(f"  API 오류 ({response.status_code}): {response.text[:300]}")
        raise RuntimeError(f"Upstage API 오류: {response.status_code}")

    return response.json()


def parse_large_pdf(
    pdf_path: str, output_format: str = "html", pages_per_batch: int = 10
) -> list[dict[str, Any]]:
    """큰 PDF를 페이지별 배치로 나누어 파싱합니다.

    Args:
        pdf_path: PDF 파일 경로
        output_format: 출력 형식
        pages_per_batch: 배치당 페이지 수

    Returns:
        페이지별 API 응답 리스트
    """
    import pdfplumber

    doc = pdfplumber.open(pdf_path)
    total_pages = len(doc.pages)
    doc.close()

    print(f"  총 {total_pages}페이지 - 배치 크기: {pages_per_batch}")

    results = []
    for start in range(0, total_pages, pages_per_batch):
        end = min(start + pages_per_batch, total_pages)
        print(f"  페이지 {start + 1}-{end} 처리 중...")

        # 페이지 범위 추출을 위해 임시 PDF 생성
        import pdfplumber
        from io import BytesIO

        # pypdf로 페이지 분리
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        buf = BytesIO()
        writer.write(buf)
        buf.seek(0)

        # Upstage API 호출
        headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
        files = {
            "document": (
                f"batch_{start+1}_{end}.pdf",
                buf,
                "application/pdf",
            )
        }
        formats = [output_format] if output_format == "text" else [output_format, "text"]
        data = {
            "ocr": "force",
            "output_formats": json.dumps(formats),
        }

        response = httpx.post(
            UPSTAGE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=180.0,
        )

        if response.status_code != 200:
            print(f"  배치 오류 ({response.status_code}): {response.text[:200]}")
            continue

        result = response.json()
        result["_batch_start"] = start
        result["_batch_end"] = end
        results.append(result)

        # API rate limit 대기
        if end < total_pages:
            time.sleep(1)

    return results


def extract_content_from_result(result: dict[str, Any], output_format: str) -> str:
    """API 결과에서 콘텐츠를 추출합니다."""
    if output_format == "html":
        return result.get("content", {}).get("html", "")
    elif output_format == "markdown":
        return result.get("content", {}).get("markdown", "")
    else:
        return result.get("content", {}).get("text", "")


def move_references_to_end(content: str) -> str:
    """테이블 내 '참고' 행을 추출하여 content 맨 끝으로 이동합니다."""
    lines = content.split("\n")
    ref_notes: list[str] = []

    for line in lines:
        if line.startswith("|") and "참고" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            for cell in cells:
                cleaned = re.sub(r"^참고\s*", "※ 참고: ", cell)
                if cleaned not in ref_notes:
                    ref_notes.append(cleaned)

    result_lines = []
    for line in lines:
        if line.startswith("|") and "참고" in line:
            continue
        result_lines.append(line)

    if ref_notes:
        result_lines.append("")
        for note in ref_notes:
            result_lines.append(note)

    return "\n".join(result_lines)


def remove_garbled_latex(content: str, text_content: str = "") -> str:
    """OCR에서 깨진 LaTeX 수식 블록($$...$$)을 text 출력의 수식으로 대체합니다.

    PDF OCR이 한글이 포함된 수식을 LaTeX로 변환하면 거의 항상 깨집니다.
    text 출력이 제공되면 해당 부분의 원문 수식으로 대체하고,
    없으면 제거합니다.
    """
    def _is_garbled(latex: str) -> bool:
        korean_chars = len(re.findall(r"[가-힣]", latex))
        total_chars = len(re.sub(r"\s", "", latex))
        if total_chars == 0:
            return True
        return korean_chars / total_chars < 0.15

    def _find_text_formula(text_content: str, before_text: str) -> str:
        """text 출력에서 깨진 LaTeX에 대응하는 수식 텍스트를 동적으로 찾습니다."""
        if not text_content:
            return ""

        # 검색 키 후보: LaTeX 앞 텍스트의 마지막 몇 줄에서 추출
        before_lines = [
            l.strip() for l in before_text.strip().split("\n") if l.strip()
        ]
        if not before_lines:
            return ""

        search_keys: list[str] = []
        for line in reversed(before_lines[-5:]):
            cleaned = re.sub(r"[|#*\-]", "", line).strip()
            if len(cleaned) >= 5:
                search_keys.append(cleaned[:50])

        if not search_keys:
            return ""

        for key in search_keys:
            idx = text_content.find(key)
            # 긴 키가 실패하면 앞부분으로 부분 매칭
            if idx < 0 and len(key) > 15:
                idx = text_content.find(key[:15])
            if idx < 0:
                continue

            # 검색 위치 이후 넓은 범위에서 수식 패턴 탐색
            search_start = idx + len(key)
            search_end = min(len(text_content), search_start + 500)
            window = text_content[search_start:search_end]

            formula_lines: list[str] = []
            for wline in window.split("\n"):
                s = wline.strip()
                if not s:
                    if formula_lines:
                        break
                    continue
                # 수식 줄 판별: 연산자 포함 + 테이블 구분선 아님
                if any(op in s for op in ["=", "×", "÷", "/"]) and not s.startswith("|"):
                    formula_lines.append(s)
                elif formula_lines and len(s) < 50 and not s.startswith("*"):
                    formula_lines.append(s)
                elif formula_lines:
                    break

            if formula_lines:
                return " ".join(formula_lines)

        return ""

    def _replace_latex(m: re.Match) -> str:
        if not _is_garbled(m.group()):
            return m.group()
        before = content[: m.start()]
        formula = _find_text_formula(text_content, before)
        if formula:
            return formula
        return ""

    return re.sub(
        r"\$\$.*?\$\$",
        _replace_latex,
        content,
        flags=re.DOTALL,
    )


def _is_structural_line(line: str) -> bool:
    """분수의 분자가 될 수 없는 구조적 줄인지 확인합니다."""
    s = line.strip()
    if not s:
        return True
    if s.startswith("(") and s.endswith(")") and "/" in s:
        return True
    return bool(re.match(r"^[#·\-*|①②③④⑤⑥⑦⑧⑨⑩▶※\[]", s))


def fix_text_fractions(content: str) -> str:
    """OCR에서 텍스트 분수가 별도 줄로 분리된 수식을 복원합니다.

    Pattern 1: '× ×' (이중 곱셈) - 분자/분모가 위/아래 줄에 위치
        감면소득
        감면세액 = 산출세액 × × 감면율
        과세표준
      → 감면세액 = 산출세액 × (감면소득/과세표준) × 감면율

    Pattern 2: 수식 줄 끝이 '= ×'로 끝남 - 분자가 위, 분모가 아래
        해당 과세연도의 고효율제품 등의 매출액
        감면소득 = ×
        제조업에서 발생한 소득 제조업에서 발생한 총매출액
      → 감면소득 = (해당 과세연도의 고효율제품 등의 매출액 / 제조업에서 발생한 총매출액) × 제조업에서 발생한 소득

    Pattern 3: 괄호 안 텍스트 + 분자/분모가 위/아래 줄
        작년 대비 증가한 상시근로자 수
        추가 감면세액 = 산출세액 × (상시근로자 증가율 )
        직전 과세연도 상시근로자 수
      → 추가 감면세액 = 산출세액 × (상시근로자 증가율 = 작년 대비 증가한 상시근로자 수 / 직전 과세연도 상시근로자 수)
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        # Pattern 1: × × (이중 곱셈 - 분수 위치 표시)
        if "=" in stripped and re.search(r"×\s*×", stripped):
            numerator = ""
            num_idx = -1
            # 이전 비구조적 줄 = 분자
            for j in range(len(result) - 1, -1, -1):
                prev = result[j].strip()
                if not prev:
                    continue
                if not _is_structural_line(result[j]) and "=" not in prev:
                    numerator = prev
                    num_idx = j
                    break
                else:
                    break

            # 다음 비구조적 줄 = 분모
            denominator = ""
            denom_skip = False
            if i + 1 < len(lines):
                next_s = lines[i + 1].strip()
                if next_s and not _is_structural_line(lines[i + 1]) and "=" not in next_s:
                    denominator = next_s
                    denom_skip = True

            if numerator and denominator:
                if num_idx >= 0:
                    result.pop(num_idx)
                fixed = re.sub(r"×\s*×", f"× ({numerator}/{denominator}) ×", stripped)
                result.append(fixed)
                if denom_skip:
                    i += 2
                    continue
            else:
                result.append(lines[i])
                i += 1
                continue

        # Pattern 2: 줄이 '= ×' 또는 '×'로 끝나고 = 포함 (분수 분리)
        elif re.match(r".+=\s*×\s*$", stripped):
            numerator = ""
            num_idx = -1
            for j in range(len(result) - 1, -1, -1):
                prev = result[j].strip()
                if not prev:
                    continue
                if not _is_structural_line(result[j]) and "=" not in prev:
                    numerator = prev
                    num_idx = j
                    break
                else:
                    break

            denominator = ""
            denom_skip = False
            if i + 1 < len(lines):
                next_s = lines[i + 1].strip()
                if next_s and not _is_structural_line(lines[i + 1]) and "=" not in next_s:
                    denominator = next_s
                    denom_skip = True

            if numerator and denominator:
                if num_idx >= 0:
                    result.pop(num_idx)
                # '= ×' → '= (분자/분모) ×'
                fixed = re.sub(r"=\s*×\s*$", f"= ({numerator}/{denominator}) ×", stripped)
                result.append(fixed)
                if denom_skip:
                    i += 2
                    continue
            else:
                result.append(lines[i])
                i += 1
                continue

        # Pattern 3: 괄호 안에 공백 + ')' (분수 내용이 위/아래에 분리)
        elif re.search(r"\([^)]+\s+\)\s*$", stripped) and "×" in stripped:
            numerator = ""
            num_idx = -1
            for j in range(len(result) - 1, -1, -1):
                prev = result[j].strip()
                if not prev:
                    continue
                if not _is_structural_line(result[j]) and "=" not in prev:
                    numerator = prev
                    num_idx = j
                    break
                else:
                    break

            denominator = ""
            denom_skip = False
            if i + 1 < len(lines):
                next_s = lines[i + 1].strip()
                if next_s and not _is_structural_line(lines[i + 1]) and "=" not in next_s:
                    denominator = next_s
                    denom_skip = True

            if numerator and denominator:
                if num_idx >= 0:
                    result.pop(num_idx)
                # '(텍스트 )' → '(텍스트 = 분자 / 분모)'
                fixed = re.sub(
                    r"\(([^)]+?)\s+\)",
                    rf"(\1 = {numerator} / {denominator})",
                    stripped,
                )
                result.append(fixed)
                if denom_skip:
                    i += 2
                    continue
            else:
                result.append(lines[i])
                i += 1
                continue

        else:
            result.append(lines[i])
            i += 1
            continue

        i += 1

    return "\n".join(result)


def fix_broken_fractions(content: str) -> str:
    """PDF OCR에서 깨진 분수 수식을 복원합니다.

    예:
        해당 과세연도의 개시일 전부터 소급하여
        3년간 투자한 금액의 합계액
        3
        해당 과세연도의 개월 수
        ×
        12
    →
        (... 3년간 투자한 금액의 합계액 / 3) × (해당 과세연도의 개월 수 / 12)
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        # × 단독 줄 + 다음에 숫자: 분수 곱셈 패턴
        if stripped == "×" and i + 1 < len(lines):
            next_stripped = lines[i + 1].strip()
            if re.match(r"^\d{1,3}$", next_stripped):
                num_parts: list[str] = []
                while result and result[-1].strip() and not _is_structural_line(result[-1]):
                    num_parts.insert(0, result.pop().strip())

                if num_parts:
                    fraction = f" × ({' '.join(num_parts)} / {next_stripped})"
                    while result and not result[-1].strip():
                        result.pop()
                    if result and result[-1].strip().endswith(")"):
                        result[-1] = result[-1].rstrip() + fraction
                    else:
                        result.append(fraction)
                    i += 2
                    continue

        # 단독 숫자 줄: 잠재적 분모
        if re.match(r"^\d{1,3}$", stripped):
            remaining = [line for line in lines[i + 1 :] if line.strip()]
            if not remaining:
                result.append(lines[i])
                i += 1
                continue

            num_parts = []
            while result and result[-1].strip() and not _is_structural_line(result[-1]):
                num_parts.insert(0, result.pop().strip())

            if num_parts:
                result.append(f"({' '.join(num_parts)} / {stripped})")
                i += 1
                continue

        result.append(lines[i])
        i += 1

    return "\n".join(result)


def flatten_html_tables(content: str) -> str:
    """HTML 테이블의 다단 헤더(rowspan/colspan)를 평탄화된 마크다운 테이블로 변환합니다."""
    table_pattern = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
    matches = list(table_pattern.finditer(content))
    if not matches:
        return content

    result = content
    for match in reversed(matches):
        html_table = match.group()
        md_table = _html_table_to_markdown(html_table)
        result = result[: match.start()] + md_table + result[match.end() :]

    return result


def _expand_header_matrix(thead: list) -> list[list[str]]:
    """thead의 tr 목록에서 rowspan/colspan을 해석하여 2D 매트릭스를 구성합니다."""
    if not thead:
        return []

    rows = thead
    max_cols = 0
    for tr in rows:
        cols = 0
        for cell in tr.find_all(["td", "th"]):
            colspan = int(cell.get("colspan", 1))
            cols += colspan
        max_cols = max(max_cols, cols)

    num_rows = len(rows)
    matrix: list[list[str | None]] = [[None] * max_cols for _ in range(num_rows)]

    for r_idx, tr in enumerate(rows):
        col_idx = 0
        for cell in tr.find_all(["td", "th"]):
            while col_idx < max_cols and matrix[r_idx][col_idx] is not None:
                col_idx += 1
            if col_idx >= max_cols:
                break
            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))
            text = cell.get_text(strip=True)
            for dr in range(rowspan):
                for dc in range(colspan):
                    nr, nc = r_idx + dr, col_idx + dc
                    if nr < num_rows and nc < max_cols:
                        matrix[nr][nc] = text
            col_idx += colspan

    for r in range(num_rows):
        for c in range(max_cols):
            if matrix[r][c] is None:
                matrix[r][c] = ""
    return matrix


def _flatten_header_columns(matrix: list[list[str]]) -> list[str]:
    """열 단위로 상위→하위 값을 수집, 중복 제거 후 부모(자식) 형태로 합칩니다."""
    if not matrix:
        return []

    num_cols = len(matrix[0])
    headers = []
    for c in range(num_cols):
        parts: list[str] = []
        for r in range(len(matrix)):
            val = matrix[r][c].strip()
            if val and val not in parts:
                parts.append(val)
        if len(parts) == 0:
            headers.append("")
        elif len(parts) == 1:
            headers.append(parts[0])
        else:
            parent = parts[0]
            children = ", ".join(parts[1:])
            headers.append(f"{parent}({children})")
    return headers


def _expand_body_matrix(tbody_rows: list) -> list[list[str]]:
    """tbody의 tr 목록에서 rowspan/colspan을 해석하여 2D 매트릭스를 구성합니다."""
    if not tbody_rows:
        return []

    max_cols = 0
    for tr in tbody_rows:
        cols = 0
        for cell in tr.find_all(["td", "th"]):
            colspan = int(cell.get("colspan", 1))
            cols += colspan
        max_cols = max(max_cols, cols)

    num_rows = len(tbody_rows)
    matrix: list[list[str | None]] = [[None] * max_cols for _ in range(num_rows)]

    for r_idx, tr in enumerate(tbody_rows):
        col_idx = 0
        for cell in tr.find_all(["td", "th"]):
            while col_idx < max_cols and matrix[r_idx][col_idx] is not None:
                col_idx += 1
            if col_idx >= max_cols:
                break
            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))
            text = cell.get_text(strip=True)
            for dr in range(rowspan):
                for dc in range(colspan):
                    nr, nc = r_idx + dr, col_idx + dc
                    if nr < num_rows and nc < max_cols:
                        matrix[nr][nc] = text
            col_idx += colspan

    for r in range(num_rows):
        for c in range(max_cols):
            if matrix[r][c] is None:
                matrix[r][c] = ""
    return matrix


def _merge_body_categories(matrix: list[list[str]]) -> list[list[str]]:
    """Body matrix에서 빈 카테고리 셀을 상위 행에서 채우고, 부모(자식) 형태로 합칩니다."""
    if len(matrix) <= 1:
        return matrix

    for r in range(1, len(matrix)):
        for c in range(len(matrix[r])):
            if matrix[r][c] == "":
                matrix[r][c] = matrix[r - 1][c]
            else:
                break

        match_end = 0
        while match_end < len(matrix[r]) and match_end < len(matrix[r - 1]):
            if matrix[r][match_end] == matrix[r - 1][match_end] and matrix[r][match_end] != "":
                match_end += 1
            else:
                break

        if match_end > 0 and match_end < len(matrix[r]):
            parent = matrix[r][match_end - 1]
            child = matrix[r][match_end]
            if parent and child and parent != child:
                matrix[r][match_end] = f"{parent}({child})"

    return matrix


def _html_table_to_markdown(html_table: str) -> str:
    """단일 HTML 테이블을 평탄화된 마크다운 테이블로 변환합니다."""
    soup = BeautifulSoup(html_table, "html.parser")
    table = soup.find("table")
    if not table:
        return html_table

    thead = table.find("thead")
    if thead:
        header_rows = thead.find_all("tr")
    else:
        all_trs = table.find_all("tr")
        header_rows = [all_trs[0]] if all_trs else []

    header_matrix = _expand_header_matrix(header_rows)
    flat_headers = _flatten_header_columns(header_matrix)

    if not flat_headers:
        return html_table

    tbody = table.find("tbody")
    if tbody:
        body_rows = tbody.find_all("tr")
    else:
        all_trs = table.find_all("tr")
        if thead:
            body_rows = [tr for tr in all_trs if tr.parent != thead]
        else:
            body_rows = all_trs[1:] if len(all_trs) > 1 else []

    body_matrix = _expand_body_matrix(body_rows)
    body_matrix = _merge_body_categories(body_matrix)

    lines = []
    header_line = "| " + " | ".join(flat_headers) + " |"
    lines.append(header_line)
    separator = "| " + " | ".join("---" for _ in flat_headers) + " |"
    lines.append(separator)

    for row in body_matrix:
        while len(row) < len(flat_headers):
            row.append("")
        row_line = "| " + " | ".join(row[: len(flat_headers)]) + " |"
        lines.append(row_line)

    return "\n".join(lines)


def flatten_markdown_multi_headers(content: str) -> str:
    """마크다운 테이블의 다단 헤더(2행 이상)를 부모(자식) 형태로 병합합니다.

    Upstage OCR이 HTML 대신 마크다운으로 반환한 테이블에서,
    헤더 행이 2행이고 상위 행에 동일 값이 반복되면 하위 행의 값을 자식으로 병합합니다.

    예:
        | 요 건 | 요 건 | 요 건 |
        | --- | --- | --- |
        | 규모 | 소재지 | 업종 |
      →
        | 요건(규모) | 요건(소재지) | 요건(업종) |
        | --- | --- | --- |
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 마크다운 테이블 시작 감지: | ... | 형태
        if not line.startswith("|") or not line.endswith("|"):
            result.append(lines[i])
            i += 1
            continue

        # 3행 연속 (헤더1, 구분선, 헤더2/데이터) 확인
        if i + 2 >= len(lines):
            result.append(lines[i])
            i += 1
            continue

        next1 = lines[i + 1].strip()
        next2 = lines[i + 2].strip()

        # 구분선 확인 (| --- | --- | 형태)
        is_separator = (
            next1.startswith("|")
            and next1.endswith("|")
            and all(c.strip().replace("-", "") == "" for c in next1.split("|") if c.strip())
        )

        if not is_separator:
            result.append(lines[i])
            i += 1
            continue

        # 다음 행이 데이터 행인지 확인
        if not next2.startswith("|") or not next2.endswith("|"):
            result.append(lines[i])
            i += 1
            continue

        # 헤더1, 헤더2 셀 파싱
        header1_cells = [c.strip() for c in line.split("|")[1:-1]]
        header2_cells = [c.strip() for c in next2.split("|")[1:-1]]

        if len(header1_cells) != len(header2_cells):
            result.append(lines[i])
            i += 1
            continue

        # 상위 헤더에 중복 값이 있는지 확인 (다단 헤더 패턴)
        has_duplicates = len(header1_cells) != len(set(header1_cells))
        # 상위/하위가 동일하지 않은 셀이 있는지 (하위가 자식 값인 경우)
        has_children = any(
            h1 != h2 and h2 != ""
            for h1, h2 in zip(header1_cells, header2_cells)
        )

        if not (has_duplicates and has_children):
            result.append(lines[i])
            i += 1
            continue

        # 병합: 상위==하위면 그대로, 상위!=하위면 "상위(하위)"
        merged = []
        for h1, h2 in zip(header1_cells, header2_cells):
            h1_clean = re.sub(r"\s+", "", h1)
            h2_clean = re.sub(r"\s+", "", h2)
            if h1_clean == h2_clean or h2_clean == "":
                merged.append(h1_clean)
            else:
                merged.append(f"{h1_clean}({h2_clean})")

        merged_header = "| " + " | ".join(merged) + " |"
        result.append(merged_header)
        result.append(lines[i + 1])  # 구분선 유지
        # 헤더2 행(i+2)은 스킵
        i += 3
        continue

    return "\n".join(result)


def build_documents(
    contents: list[dict[str, str]],
    source_filename: str,
) -> list[dict[str, Any]]:
    """추출된 콘텐츠를 통합 스키마 문서로 변환합니다.

    Args:
        contents: [{"page": int, "title": str, "content": str}, ...]
        source_filename: 원본 파일명

    Returns:
        통합 스키마 문서 리스트
    """
    collected_at = datetime.now().isoformat(timespec="seconds")
    documents = []

    for idx, item in enumerate(contents, 1):
        processed_content = flatten_html_tables(item["content"])
        processed_content = flatten_markdown_multi_headers(processed_content)
        processed_content = fix_text_fractions(processed_content)
        processed_content = fix_broken_fractions(processed_content)
        processed_content = remove_garbled_latex(
            processed_content, item.get("text_content", "")
        )
        processed_content = move_references_to_end(processed_content)
        doc = {
            "id": f"TAX_SUPPORT_{idx:03d}",
            "type": "tax",
            "domain": "tax",
            "title": "2025 중소기업세제 세정지원 제도",
            "content": processed_content,
            "source": {
                "name": "중소기업 세제·세정지원 제도",
                "url": "",
                "collected_at": collected_at,
            },
            "effective_date": "",
            "metadata": {
                "category": "세무 가이드",
                "chapter": "세제·세정지원",
                "page": item.get("page", 0),
                "source_file": source_filename,
            },
        }
        documents.append(doc)

    return documents


def save_jsonl(
    documents: list[dict[str, Any]], output_path: str
) -> str:
    """JSONL 파일로 저장합니다."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"  JSONL 저장: {output_path} ({len(documents)}건)")
    return output_path


def save_raw_result(result: Any, output_path: str) -> str:
    """Upstage API 원본 결과를 JSON으로 저장합니다."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  원본 결과 저장: {output_path}")
    return output_path


def process_large_pdf(pdf_path: str, output_dir: str) -> list[dict[str, Any]]:
    """대용량(134페이지) PDF를 배치로 처리합니다."""
    filename = os.path.basename(pdf_path)

    results = parse_large_pdf(pdf_path, output_format="markdown", pages_per_batch=10)

    # 원본 결과 저장
    raw_path = os.path.join(output_dir, f"{Path(filename).stem}_upstage_raw.json")
    save_raw_result(results, raw_path)

    # 페이지별 콘텐츠 수집
    all_contents = []
    for batch_result in results:
        batch_start = batch_result.get("_batch_start", 0)
        elements = batch_result.get("elements", [])

        if elements:
            # 페이지별로 markdown/text 각각 그룹핑
            page_md: dict[int, list[str]] = {}
            page_txt: dict[int, list[str]] = {}
            for elem in elements:
                cat = elem.get("category", "")
                if cat == "figure":
                    continue
                page = elem.get("page", batch_start + 1)
                md = elem.get("content", {}).get("markdown", "")
                txt = elem.get("content", {}).get("text", "")
                # equation 카테고리는 LaTeX가 깨지므로 text 출력을 markdown으로 사용
                if cat == "equation" and txt.strip():
                    md = txt
                if md.strip():
                    page_md.setdefault(page, []).append(md)
                if txt.strip():
                    page_txt.setdefault(page, []).append(txt)

            for page_num in sorted(page_md.keys()):
                combined = "\n\n".join(page_md[page_num])
                combined_text = "\n\n".join(page_txt.get(page_num, []))
                if len(combined) > 50:
                    # 첫 줄을 제목으로
                    lines = combined.strip().split("\n")
                    title = lines[0].strip()[:100] if lines else f"세무 지원 제도 - 페이지 {page_num}"
                    all_contents.append({
                        "page": page_num,
                        "title": title,
                        "content": combined,
                        "text_content": combined_text,
                    })
        else:
            # elements가 없으면 content에서 직접 추출
            md = extract_content_from_result(batch_result, "markdown")
            if md and len(md.strip()) > 50:
                all_contents.append({
                    "page": batch_start + 1,
                    "title": f"세무 지원 제도 - 페이지 {batch_start + 1}-{batch_result.get('_batch_end', '')}",
                    "content": md,
                })

    documents = build_documents(all_contents, filename)
    return documents


def reprocess_from_raw(output_dir: str) -> list[dict[str, Any]]:
    """저장된 raw JSON에서 개선된 후처리 로직으로 JSONL을 재생성합니다.

    API 재호출 없이 이전에 저장한 Upstage API 원본 결과를 다시 처리합니다.

    Args:
        output_dir: raw JSON과 출력 JSONL이 저장되는 디렉토리

    Returns:
        변환된 문서 리스트
    """
    raw_path = os.path.join(output_dir, "세무 지원 제도_upstage_raw.json")
    if not os.path.exists(raw_path):
        print(f"  ERROR: raw JSON 없음: {raw_path}")
        return []

    print(f"  raw JSON 로드: {raw_path}")
    with open(raw_path, encoding="utf-8") as f:
        results = json.load(f)

    all_contents: list[dict[str, str]] = []
    for batch_result in results:
        batch_start = batch_result.get("_batch_start", 0)
        elements = batch_result.get("elements", [])

        if elements:
            page_md: dict[int, list[str]] = {}
            page_txt: dict[int, list[str]] = {}
            for elem in elements:
                cat = elem.get("category", "")
                if cat == "figure":
                    continue
                page = elem.get("page", batch_start + 1)
                md = elem.get("content", {}).get("markdown", "")
                txt = elem.get("content", {}).get("text", "")
                # equation 카테고리는 LaTeX가 깨지므로 text 출력을 markdown으로 사용
                if cat == "equation" and txt.strip():
                    md = txt
                if md.strip():
                    page_md.setdefault(page, []).append(md)
                if txt.strip():
                    page_txt.setdefault(page, []).append(txt)

            for page_num in sorted(page_md.keys()):
                combined = "\n\n".join(page_md[page_num])
                combined_text = "\n\n".join(page_txt.get(page_num, []))
                if len(combined) > 50:
                    lines = combined.strip().split("\n")
                    title = (
                        lines[0].strip()[:100]
                        if lines
                        else f"세무 지원 제도 - 페이지 {page_num}"
                    )
                    all_contents.append(
                        {
                            "page": page_num,
                            "title": title,
                            "content": combined,
                            "text_content": combined_text,
                        }
                    )
        else:
            md = extract_content_from_result(batch_result, "markdown")
            if md and len(md.strip()) > 50:
                all_contents.append(
                    {
                        "page": batch_start + 1,
                        "title": f"세무 지원 제도 - 페이지 {batch_start + 1}-{batch_result.get('_batch_end', '')}",
                        "content": md,
                    }
                )

    print(f"  페이지별 콘텐츠: {len(all_contents)}건")
    documents = build_documents(all_contents, "2025 중소기업세제 세정지원 제도.pdf")
    return documents


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="세무 지원 제도 PDF 전처리")
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="저장된 raw JSON에서 JSONL 재생성 (API 재호출 없음)",
    )
    args = parser.parse_args()

    output_dir = str(PROJECT_ROOT / "data" / "preprocessed" / "finance")

    if args.reprocess:
        print("=" * 60)
        print("세무 지원 제도 - raw JSON에서 JSONL 재생성")
        print("=" * 60)

        documents = reprocess_from_raw(output_dir)
        if documents:
            jsonl_path = os.path.join(output_dir, "tax_support.jsonl")
            save_jsonl(documents, jsonl_path)
            print(f"\n{'=' * 60}")
            print(f"완료! 총 {len(documents)}건 재생성")
            print(f"{'=' * 60}")
        else:
            print("\n재처리할 raw JSON이 없습니다.")
        return

    pdf_path = str(PROJECT_ROOT / "scripts" / "2025 중소기업세제 세정지원 제도.pdf")

    print("=" * 60)
    print("세무 지원 제도 PDF 전처리 (Upstage Document Parse)")
    print("=" * 60)

    if not os.path.exists(pdf_path):
        print(f"\n  ERROR: PDF 파일 없음: {pdf_path}")
        return

    print(f"\n  대상: {os.path.basename(pdf_path)}")
    documents = process_large_pdf(pdf_path, output_dir)

    if documents:
        jsonl_path = os.path.join(output_dir, "tax_support.jsonl")
        save_jsonl(documents, jsonl_path)

        print(f"\n{'=' * 60}")
        print(f"완료! 총 {len(documents)}건 저장")
        print(f"{'=' * 60}")
    else:
        print("\n추출된 문서가 없습니다.")


if __name__ == "__main__":
    main()
