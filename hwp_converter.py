"""
HWP/PDF 파일 → Markdown 변환 스크립트

hwp5html (pyhwp)를 사용하여 HWP → HTML 변환 후
BeautifulSoup으로 표 복잡도를 판별하여:
- 단순 표: Markdown 표로 변환
- 복잡한 표 (병합/중첩/다이어그램): 텍스트로 풀어쓰기

PDF는 PyMuPDF를 사용하여 텍스트 추출
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# HTML 파싱
try:
    from bs4 import BeautifulSoup, NavigableString, Tag
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("경고: beautifulsoup4가 설치되지 않았습니다. pip install beautifulsoup4")

# Markdown 변환
try:
    from markdownify import markdownify as md, MarkdownConverter
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False
    print("경고: markdownify가 설치되지 않았습니다. pip install markdownify")

# PDF 처리
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("경고: PyMuPDF가 설치되지 않았습니다. pip install pymupdf")

# DOCX 처리
try:
    from docx import Document
    from docx.table import Table as DocxTable
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("경고: python-docx가 설치되지 않았습니다. pip install python-docx")

# HWPX 처리 (ZIP + XML)
import zipfile
from xml.etree import ElementTree as ET


# ============================================================
# 표 복잡도 판별 및 변환
# ============================================================

def is_complex_table(table: Tag) -> bool:
    """
    복잡한 표인지 판별

    복잡한 표 조건:
    - 중첩 표 (table 안에 table)
    - 셀 병합 (rowspan/colspan > 1)
    - 빈 셀 50% 이상 (다이어그램 표)

    Args:
        table: BeautifulSoup table 태그

    Returns:
        복잡한 표이면 True
    """
    # 1. 중첩 표 확인
    if table.find('table'):
        return True

    # 2. 셀 병합 확인
    for cell in table.find_all(['td', 'th']):
        rowspan = int(cell.get('rowspan', 1))
        colspan = int(cell.get('colspan', 1))
        if rowspan > 1 or colspan > 1:
            return True

    # 3. 빈 셀 비율 확인 (50% 이상이면 다이어그램)
    cells = table.find_all(['td', 'th'])
    if cells:
        empty_count = sum(1 for c in cells if not c.get_text(strip=True))
        if empty_count / len(cells) > 0.5:
            return True

    return False


def get_table_title(table: Tag) -> str:
    """
    표 주변에서 제목 추출

    표 바로 앞의 텍스트나 헤딩에서 제목 찾기
    """
    # 이전 형제 요소에서 제목 찾기
    prev = table.find_previous_sibling()
    for _ in range(3):  # 최대 3개 이전 요소까지 확인
        if prev is None:
            break

        if isinstance(prev, Tag):
            # 헤딩 태그
            if prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                return prev.get_text(strip=True)

            # p 태그에 짧은 텍스트 (제목일 가능성)
            if prev.name == 'p':
                text = prev.get_text(strip=True)
                if text and len(text) < 50:
                    return text

        prev = prev.find_previous_sibling()

    # 표의 첫 번째 행이 헤더인 경우
    first_row = table.find('tr')
    if first_row:
        ths = first_row.find_all('th')
        if ths and len(ths) == 1:
            return ths[0].get_text(strip=True)

    return ""


def complex_table_to_text(table: Tag, title: str = "") -> str:
    """
    복잡한 표를 텍스트로 변환

    병합 셀의 그룹 관계를 파악하여 계층적 텍스트로 변환

    Args:
        table: BeautifulSoup table 태그
        title: 표 제목

    Returns:
        텍스트로 변환된 표 내용
    """
    lines = []

    # 제목 추가
    if title:
        lines.append(f"\n### {title}\n")

    rows = table.find_all('tr')
    if not rows:
        return ""

    # 행별로 처리
    current_group = ""

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue

        cell_texts = []
        for cell in cells:
            text = cell.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
            if text:
                cell_texts.append(text)

        if not cell_texts:
            continue

        # 첫 번째 셀이 rowspan이 있으면 그룹 헤더
        first_cell = cells[0]
        rowspan = int(first_cell.get('rowspan', 1))

        if rowspan > 1 and len(cell_texts) >= 1:
            # 새 그룹 시작
            current_group = cell_texts[0]
            lines.append(f"\n**{current_group}:**")
            # 나머지 셀들
            for text in cell_texts[1:]:
                lines.append(f"- {text}")
        elif len(cell_texts) == 1:
            # 단일 셀 - 그룹 헤더일 수 있음
            if first_cell.name == 'th' or (first_cell.get('colspan') and int(first_cell.get('colspan', 1)) > 1):
                current_group = cell_texts[0]
                lines.append(f"\n**{current_group}:**")
            else:
                lines.append(f"- {cell_texts[0]}")
        elif len(cell_texts) == 2:
            # 키-값 쌍
            lines.append(f"- {cell_texts[0]}: {cell_texts[1]}")
        else:
            # 여러 셀 - 첫 번째를 키로, 나머지를 값으로
            key = cell_texts[0]
            values = ", ".join(cell_texts[1:])
            lines.append(f"- {key}: {values}")

    return "\n".join(lines)


def simple_table_to_markdown(table: Tag) -> str:
    """
    단순 표를 Markdown 표로 변환

    Args:
        table: BeautifulSoup table 태그

    Returns:
        Markdown 표 문자열
    """
    rows = table.find_all('tr')
    if not rows:
        return ""

    md_rows = []
    header_done = False

    for row in rows:
        cells = row.find_all(['td', 'th'])
        cell_texts = []

        for cell in cells:
            text = cell.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)
            text = text.replace('|', '\\|')  # 파이프 이스케이프
            cell_texts.append(text if text else " ")

        if not cell_texts:
            continue

        md_row = "| " + " | ".join(cell_texts) + " |"
        md_rows.append(md_row)

        # 첫 행 후 구분선 추가
        if not header_done:
            separator = "|" + "|".join(["---"] * len(cell_texts)) + "|"
            md_rows.append(separator)
            header_done = True

    return "\n".join(md_rows)


# ============================================================
# HWP 변환기 클래스 (hwp5html 사용)
# ============================================================

class HwpToMarkdownConverter:
    """HWP 파일을 Markdown으로 변환하는 클래스 (hwp5html 사용)"""

    def __init__(self):
        """변환기 초기화"""
        self._check_dependencies()

    def _check_dependencies(self):
        """필수 의존성 확인"""
        if not HAS_BS4:
            raise ImportError("beautifulsoup4가 필요합니다: pip install beautifulsoup4")
        if not HAS_MARKDOWNIFY:
            raise ImportError("markdownify가 필요합니다: pip install markdownify")

    def hwp_to_html(self, hwp_path: Path, output_dir: Path) -> Optional[Path]:
        """
        hwp5html로 HWP → HTML 변환

        Args:
            hwp_path: HWP 파일 경로
            output_dir: HTML 출력 디렉토리

        Returns:
            생성된 HTML 파일 경로 (실패시 None)
        """
        hwp_path = Path(hwp_path).resolve()

        if not hwp_path.exists():
            raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {hwp_path}")

        try:
            result = subprocess.run(
                ['hwp5html', '--output', str(output_dir), str(hwp_path)],
                capture_output=True,
                timeout=60
            )

            # xhtml 또는 html 파일 찾기
            html_file = output_dir / 'index.xhtml'
            if not html_file.exists():
                html_file = output_dir / 'index.html'

            if html_file.exists():
                return html_file

            return None

        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None

    def process_html(self, html_content: str) -> str:
        """
        HTML을 파싱하여 표 복잡도에 따라 처리 후 Markdown 변환

        Args:
            html_content: HTML 문자열

        Returns:
            Markdown 문자열
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 불필요한 태그 제거
        for tag_name in ['script', 'style', 'meta', 'link', 'head']:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 표 처리: 복잡도에 따라 변환
        for table in soup.find_all('table'):
            title = get_table_title(table)

            if is_complex_table(table):
                # 복잡한 표 → 텍스트로 변환
                text_content = complex_table_to_text(table, title)
                # 표를 텍스트로 교체
                new_div = soup.new_tag('div')
                new_div['class'] = 'converted-table'
                new_div.string = text_content
                table.replace_with(new_div)
            else:
                # 단순 표 → Markdown 표로 변환
                md_table = simple_table_to_markdown(table)
                new_div = soup.new_tag('div')
                new_div['class'] = 'md-table'
                new_div.string = md_table
                table.replace_with(new_div)

        # body 태그 내용 추출
        body = soup.find('body')
        if body:
            html_str = str(body)
        else:
            html_str = str(soup)

        # markdownify로 나머지 변환
        markdown = md(
            html_str,
            heading_style="ATX",
            bullets="-",
            strip=['a'],
            escape_misc=False,
            escape_asterisks=False,
            escape_underscores=False,
        )

        # 변환된 표 텍스트 복원 (markdownify가 이스케이프한 것 원복)
        # div.converted-table과 div.md-table 내용 복원

        # 후처리
        markdown = self._post_process_markdown(markdown)

        return markdown

    def _post_process_markdown(self, markdown: str) -> str:
        """
        Markdown 후처리
        """
        lines = markdown.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            line = line.rstrip()

            # 연속된 빈 줄 하나로 통합
            if not line.strip():
                if not prev_empty:
                    cleaned_lines.append('')
                    prev_empty = True
                continue

            prev_empty = False

            # 불필요한 특수문자 제거
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)

            # 연속된 공백 하나로
            line = re.sub(r' {2,}', ' ', line)

            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def convert(self, hwp_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """
        HWP 파일을 Markdown으로 변환 (전체 파이프라인)

        1. hwp5html로 HWP → XHTML 변환
        2. BeautifulSoup으로 파싱
        3. 각 표에 대해 복잡도 판별 후 변환
        4. markdownify로 나머지 변환
        5. 후처리

        Args:
            hwp_path: HWP 파일 경로
            output_path: 출력 Markdown 파일 경로

        Returns:
            (Markdown 내용, 출력 파일 경로) 튜플
        """
        hwp_path = Path(hwp_path).resolve()

        if output_path is None:
            output_path = hwp_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 1단계: HWP → HTML
            html_file = self.hwp_to_html(hwp_path, tmpdir)

            if html_file is None:
                raise RuntimeError(f"HWP 변환 실패: {hwp_path}")

            # 2단계: HTML 읽기
            html_content = html_file.read_text(encoding='utf-8', errors='ignore')

            # 3단계: HTML 처리 및 Markdown 변환
            markdown_content = self.process_html(html_content)

            # 4단계: 파일 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

        return markdown_content, output_path


# ============================================================
# PDF 변환기 클래스
# ============================================================

class PdfToMarkdownConverter:
    """PDF 파일을 Markdown으로 변환하는 클래스"""

    def __init__(self):
        """변환기 초기화"""
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 필요합니다: pip install pymupdf")

    def extract_text(self, pdf_path: Path) -> str:
        """PDF에서 텍스트 추출"""
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        text_parts = []

        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, 1):
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text)

        return "\n\n---\n\n".join(text_parts)

    def text_to_markdown(self, text: str) -> str:
        """추출된 텍스트를 Markdown으로 정리"""
        lines = text.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            line = line.rstrip()

            if not line.strip():
                if not prev_empty:
                    cleaned_lines.append('')
                    prev_empty = True
                continue

            prev_empty = False

            # 불필요한 특수문자 제거
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
            line = re.sub(r' {3,}', '  ', line)

            # 제목 감지
            if re.match(r'^[0-9]+\.\s+\S', line) and len(line) < 100:
                line = f"## {line}"
            elif re.match(r'^[가-힣]\.\s+\S', line) and len(line) < 100:
                line = f"### {line}"
            elif re.match(r'^[○●◎◇■□▶▷]\s*', line):
                line = re.sub(r'^[○●◎◇■□▶▷]\s*', '- ', line)

            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def convert(self, pdf_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """PDF 파일을 Markdown으로 변환"""
        pdf_path = Path(pdf_path).resolve()

        if output_path is None:
            output_path = pdf_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        text = self.extract_text(pdf_path)
        markdown_content = self.text_to_markdown(text)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return markdown_content, output_path


# ============================================================
# HWPX 변환기 클래스 (ZIP + XML)
# ============================================================

class HwpxToMarkdownConverter:
    """HWPX 파일을 Markdown으로 변환하는 클래스"""

    # HWPX XML 네임스페이스
    NAMESPACES = {
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
    }

    def __init__(self):
        """변환기 초기화"""
        pass

    def extract_text_from_xml(self, xml_content: bytes) -> Tuple[str, List[List[List[str]]]]:
        """
        HWPX XML에서 텍스트와 표 추출

        Returns:
            (텍스트, 표 리스트) - 표는 [[[셀텍스트]]] 형태
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return "", []

        text_parts = []
        tables = []

        # 모든 텍스트 요소 추출
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            # 텍스트 요소
            if tag == 't' and elem.text:
                text_parts.append(elem.text)
            elif tag == 'linesegarray':
                text_parts.append('\n')
            elif tag == 'p':
                text_parts.append('\n')

            # 표 처리
            if tag == 'tbl':
                table_data = self._extract_table(elem)
                if table_data:
                    tables.append(table_data)
                    # 표 위치 표시
                    text_parts.append(f'\n[[TABLE_{len(tables)-1}]]\n')

        return ''.join(text_parts), tables

    def _extract_table(self, tbl_elem) -> List[List[str]]:
        """표 요소에서 데이터 추출"""
        rows = []

        for elem in tbl_elem.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag == 'tr':
                row = []
                for cell_elem in elem.iter():
                    cell_tag = cell_elem.tag.split('}')[-1] if '}' in cell_elem.tag else cell_elem.tag
                    if cell_tag == 'tc':
                        cell_text = self._get_cell_text(cell_elem)
                        row.append(cell_text)
                if row:
                    rows.append(row)

        return rows

    def _get_cell_text(self, cell_elem) -> str:
        """셀에서 텍스트 추출"""
        texts = []
        for elem in cell_elem.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 't' and elem.text:
                texts.append(elem.text)
        return ' '.join(texts).strip()

    def table_to_markdown(self, table_data: List[List[str]]) -> str:
        """표 데이터를 마크다운 표로 변환"""
        if not table_data:
            return ""

        # 열 수 맞추기
        max_cols = max(len(row) for row in table_data) if table_data else 0
        if max_cols == 0:
            return ""

        md_lines = []
        for i, row in enumerate(table_data):
            # 열 수 맞추기
            while len(row) < max_cols:
                row.append("")

            cells = [cell.replace('|', '\\|') for cell in row]
            md_lines.append("| " + " | ".join(cells) + " |")

            # 첫 행 후 구분선
            if i == 0:
                md_lines.append("|" + "|".join(["---"] * max_cols) + "|")

        return '\n'.join(md_lines)

    def convert(self, hwpx_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """HWPX 파일을 Markdown으로 변환"""
        hwpx_path = Path(hwpx_path).resolve()

        if output_path is None:
            output_path = hwpx_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        if not hwpx_path.exists():
            raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {hwpx_path}")

        all_text = []
        all_tables = []

        try:
            with zipfile.ZipFile(hwpx_path, 'r') as zf:
                # Contents 폴더의 section XML 파일들 찾기
                section_files = sorted([
                    f for f in zf.namelist()
                    if f.startswith('Contents/section') and f.endswith('.xml')
                ])

                for section_file in section_files:
                    xml_content = zf.read(section_file)
                    text, tables = self.extract_text_from_xml(xml_content)

                    # 표 인덱스 조정
                    table_offset = len(all_tables)
                    for i in range(len(tables)):
                        text = text.replace(f'[[TABLE_{i}]]', f'[[TABLE_{table_offset + i}]]')

                    all_text.append(text)
                    all_tables.extend(tables)

        except zipfile.BadZipFile:
            raise RuntimeError(f"잘못된 HWPX 파일: {hwpx_path}")

        # 텍스트 합치기
        full_text = '\n'.join(all_text)

        # 표를 마크다운으로 변환하여 삽입
        for i, table_data in enumerate(all_tables):
            md_table = self.table_to_markdown(table_data)
            full_text = full_text.replace(f'[[TABLE_{i}]]', f'\n{md_table}\n')

        # 후처리
        markdown_content = self._post_process(full_text)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return markdown_content, output_path

    def _post_process(self, text: str) -> str:
        """텍스트 후처리"""
        lines = text.split('\n')
        cleaned = []
        prev_empty = False

        for line in lines:
            line = line.rstrip()

            if not line.strip():
                if not prev_empty:
                    cleaned.append('')
                    prev_empty = True
                continue

            prev_empty = False
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
            line = re.sub(r' {2,}', ' ', line)
            cleaned.append(line)

        result = '\n'.join(cleaned)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result


# ============================================================
# DOCX 변환기 클래스
# ============================================================

class DocxToMarkdownConverter:
    """DOCX 파일을 Markdown으로 변환하는 클래스"""

    def __init__(self):
        """변환기 초기화"""
        if not HAS_DOCX:
            raise ImportError("python-docx가 필요합니다: pip install python-docx")

    def table_to_markdown(self, table: 'DocxTable') -> str:
        """DOCX 표를 마크다운 표로 변환"""
        rows_data = []

        for row in table.rows:
            row_data = []
            for cell in row.cells:
                text = cell.text.strip()
                text = text.replace('|', '\\|')
                text = re.sub(r'\s+', ' ', text)
                row_data.append(text)
            rows_data.append(row_data)

        if not rows_data:
            return ""

        # 열 수 맞추기
        max_cols = max(len(row) for row in rows_data)
        if max_cols == 0:
            return ""

        md_lines = []
        for i, row in enumerate(rows_data):
            while len(row) < max_cols:
                row.append("")
            md_lines.append("| " + " | ".join(row) + " |")
            if i == 0:
                md_lines.append("|" + "|".join(["---"] * max_cols) + "|")

        return '\n'.join(md_lines)

    def convert(self, docx_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """DOCX 파일을 Markdown으로 변환"""
        docx_path = Path(docx_path).resolve()

        if output_path is None:
            output_path = docx_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        if not docx_path.exists():
            raise FileNotFoundError(f"DOCX 파일을 찾을 수 없습니다: {docx_path}")

        doc = Document(docx_path)
        markdown_parts = []

        # 문서의 모든 요소를 순서대로 처리
        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

            if tag == 'p':
                # 문단 처리
                para = element
                text = ''.join(node.text or '' for node in para.iter()
                              if node.tag.endswith('}t'))
                text = text.strip()

                if text:
                    # 스타일에 따라 헤딩 처리
                    style = para.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle')
                    if style is not None:
                        style_val = style.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                        if 'Heading1' in style_val or '제목1' in style_val:
                            text = f"# {text}"
                        elif 'Heading2' in style_val or '제목2' in style_val:
                            text = f"## {text}"
                        elif 'Heading3' in style_val or '제목3' in style_val:
                            text = f"### {text}"

                    markdown_parts.append(text)

            elif tag == 'tbl':
                # 표 처리 - Document의 tables에서 찾기
                for table in doc.tables:
                    if table._element == element:
                        md_table = self.table_to_markdown(table)
                        if md_table:
                            markdown_parts.append(f"\n{md_table}\n")
                        break

        # 후처리
        markdown_content = self._post_process('\n'.join(markdown_parts))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return markdown_content, output_path

    def _post_process(self, text: str) -> str:
        """텍스트 후처리"""
        lines = text.split('\n')
        cleaned = []
        prev_empty = False

        for line in lines:
            line = line.rstrip()

            if not line.strip():
                if not prev_empty:
                    cleaned.append('')
                    prev_empty = True
                continue

            prev_empty = False
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
            cleaned.append(line)

        result = '\n'.join(cleaned)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result


# ============================================================
# 편의 함수
# ============================================================

def convert_hwp_to_markdown(hwp_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
    """HWP 파일을 Markdown으로 변환하는 편의 함수"""
    converter = HwpToMarkdownConverter()
    return converter.convert(hwp_path, output_path)


def convert_pdf_to_markdown(pdf_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
    """PDF 파일을 Markdown으로 변환하는 편의 함수"""
    converter = PdfToMarkdownConverter()
    return converter.convert(pdf_path, output_path)


# ============================================================
# 배치 변환 함수
# ============================================================

def batch_convert(source_dir: Path, output_dir: Path,
                  file_types: List[str] = ['hwp', 'hwpx', 'pdf', 'docx']) -> Dict[str, int]:
    """
    폴더 내 모든 HWP/HWPX/PDF/DOCX 파일을 Markdown으로 변환

    Args:
        source_dir: 원본 파일 폴더
        output_dir: 출력 폴더
        file_types: 변환할 파일 유형 리스트

    Returns:
        {'success': 성공 수, 'fail': 실패 수, 'failed_files': 실패 파일 목록}
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 기존 변환 파일 확인
    existing = {f.stem for f in output_dir.glob('*.md')}

    # 변환 대상 파일 수집
    files = []
    for ft in file_types:
        files.extend(source_dir.glob(f'*.{ft}'))
        files.extend(source_dir.glob(f'*.{ft.upper()}'))

    # 중복 제거 및 정렬
    files = sorted(set(files), key=lambda x: x.name)

    # 미변환 파일 필터링
    todo = [f for f in files if f.stem not in existing]

    print(f"총 파일: {len(files)}개")
    print(f"변환 필요: {len(todo)}개")
    print("=" * 60)

    success = 0
    fail = 0
    failed_files = []

    hwp_converter = HwpToMarkdownConverter()
    hwpx_converter = HwpxToMarkdownConverter()
    pdf_converter = PdfToMarkdownConverter()
    docx_converter = DocxToMarkdownConverter() if HAS_DOCX else None

    for i, file_path in enumerate(todo, 1):
        ext = file_path.suffix.lower()

        if i % 50 == 1 or i <= 5:
            print(f"[{i}/{len(todo)}] {file_path.name[:50]}...")

        try:
            out_path = output_dir / (file_path.stem + '.md')

            if ext == '.hwp':
                hwp_converter.convert(file_path, out_path)
            elif ext == '.hwpx':
                hwpx_converter.convert(file_path, out_path)
            elif ext == '.pdf':
                pdf_converter.convert(file_path, out_path)
            elif ext == '.docx' and docx_converter:
                docx_converter.convert(file_path, out_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {ext}")

            success += 1

        except Exception as e:
            fail += 1
            failed_files.append(f"{file_path.name}: {str(e)[:50]}")

    print("=" * 60)
    print(f"완료: 성공 {success}, 실패 {fail}")

    if failed_files:
        print(f"\n실패한 파일 ({len(failed_files)}개):")
        for f in failed_files[:10]:
            print(f"  - {f}")
        if len(failed_files) > 10:
            print(f"  ... 외 {len(failed_files) - 10}개")

    return {
        'success': success,
        'fail': fail,
        'failed_files': failed_files
    }


# ============================================================
# 메인 실행
# ============================================================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="HWP/PDF 파일을 Markdown으로 변환")
    parser.add_argument("--file", type=str, help="변환할 HWP 또는 PDF 파일 경로")
    parser.add_argument("--source", type=str, help="원본 파일 폴더 (배치 변환)")
    parser.add_argument("--output", type=str, help="출력 폴더")
    parser.add_argument("--types", type=str, nargs="+", default=['hwp', 'hwpx', 'pdf', 'docx'],
                        help="변환할 파일 유형 (기본: hwp hwpx pdf docx)")

    args = parser.parse_args()

    if args.file:
        # 단일 파일 변환
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"파일을 찾을 수 없습니다: {file_path}")
            sys.exit(1)

        ext = file_path.suffix.lower()
        try:
            if ext == '.hwp':
                markdown, out_path = convert_hwp_to_markdown(file_path)
            elif ext == '.hwpx':
                converter = HwpxToMarkdownConverter()
                markdown, out_path = converter.convert(file_path)
            elif ext == '.pdf':
                markdown, out_path = convert_pdf_to_markdown(file_path)
            elif ext == '.docx':
                converter = DocxToMarkdownConverter()
                markdown, out_path = converter.convert(file_path)
            else:
                print(f"지원하지 않는 파일 형식: {ext}")
                sys.exit(1)

            print(f"변환 완료: {out_path}")
            print("\n미리보기 (500자):")
            print(markdown[:500])

        except Exception as e:
            print(f"변환 실패: {e}")
            sys.exit(1)

    elif args.source:
        # 배치 변환
        source_dir = Path(args.source)
        output_dir = Path(args.output) if args.output else source_dir.parent / f"{source_dir.name}-convert"

        if not source_dir.exists():
            print(f"폴더를 찾을 수 없습니다: {source_dir}")
            sys.exit(1)

        result = batch_convert(source_dir, output_dir, args.types)

    else:
        parser.print_help()
