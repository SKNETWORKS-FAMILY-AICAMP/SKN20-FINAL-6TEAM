"""
K-Startup 창업지원포털 첨부파일 다운로드 및 HWP/PDF → Markdown 변환 스크립트

기능:
1. K-Startup 사업공고 페이지에서 모든 게시물의 첨부파일 일괄 다운로드
2. 다운로드된 HWP/PDF 파일을 Markdown으로 변환

사용법:
    # 첨부파일 다운로드만
    python hwp_converter2.py --download --output ./downloads

    # 다운로드 후 변환까지
    python hwp_converter2.py --download --convert --output ./downloads

    # 기존 파일 변환만
    python hwp_converter2.py --convert --source ./downloads
"""

import os
import re
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# HTML 파싱
try:
    from bs4 import BeautifulSoup, Tag
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("경고: beautifulsoup4가 설치되지 않았습니다. pip install beautifulsoup4")

# Markdown 변환
try:
    from markdownify import markdownify as md
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


# ============================================================
# 설정
# ============================================================

BASE_URL = "https://www.k-startup.go.kr"
LIST_URL = f"{BASE_URL}/web/contents/bizpbanc-ongoing.do"
DEFAULT_PARAMS = {
    "pbancClssCd": "PBC020",  # 민간기관·교육기관 (PBC010: 중앙부처·지자체·공공기관)
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL,
}


# ============================================================
# 데이터 클래스
# ============================================================

@dataclass
class Announcement:
    """공고 정보"""
    id: str
    title: str
    url: str
    deadline: str = ""
    organization: str = ""


@dataclass
class AttachmentFile:
    """첨부파일 정보"""
    file_id: str
    filename: str
    download_url: str
    announcement_id: str


# ============================================================
# K-Startup 크롤러
# ============================================================

class KStartupCrawler:
    """K-Startup 사업공고 크롤러"""

    def __init__(self, output_dir: Path):
        """
        크롤러 초기화

        Args:
            output_dir: 다운로드 파일 저장 경로
        """
        if not HAS_BS4:
            raise ImportError("beautifulsoup4가 필요합니다: pip install beautifulsoup4")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_total_pages(self) -> int:
        """전체 페이지 수 확인"""
        try:
            response = self.session.get(LIST_URL, params={**DEFAULT_PARAMS, "page": 1})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 페이지네이션에서 마지막 페이지 번호 찾기
            pagination = soup.select('.paging a, .pagination a, [class*="page"] a')
            if pagination:
                page_nums = []
                for a in pagination:
                    href = a.get('href', '')
                    text = a.get_text(strip=True)
                    # 숫자만 추출
                    if text.isdigit():
                        page_nums.append(int(text))

                if page_nums:
                    return max(page_nums)

            # 기본값
            return 10

        except Exception as e:
            print(f"페이지 수 확인 실패: {e}")
            return 10

    def get_announcements_from_page(self, page: int) -> List[Announcement]:
        """
        특정 페이지에서 공고 목록 추출

        Args:
            page: 페이지 번호

        Returns:
            공고 목록
        """
        announcements = []

        try:
            response = self.session.get(LIST_URL, params={**DEFAULT_PARAMS, "page": page})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # go_view(ID) 패턴에서 공고 ID 추출
            pattern = re.compile(r'go_view\((\d+)\)')

            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                match = pattern.search(href)

                if match:
                    ann_id = match.group(1)

                    # 제목 추출
                    title_elem = link.select_one('p, .tit, .title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    else:
                        title = link.get_text(strip=True)

                    # 제목이 너무 짧으면 스킵
                    if len(title) < 5:
                        continue

                    # 중복 제거
                    if any(a.id == ann_id for a in announcements):
                        continue

                    url = f"{LIST_URL}?pbancClssCd=PBC010&schM=view&pbancSn={ann_id}"

                    announcements.append(Announcement(
                        id=ann_id,
                        title=title[:100],  # 제목 길이 제한
                        url=url
                    ))

        except Exception as e:
            print(f"페이지 {page} 공고 목록 추출 실패: {e}")

        return announcements

    def get_all_announcements(self, max_pages: Optional[int] = None) -> List[Announcement]:
        """
        모든 페이지에서 공고 목록 추출

        Args:
            max_pages: 최대 페이지 수 (None이면 전체)

        Returns:
            전체 공고 목록
        """
        total_pages = self.get_total_pages()
        if max_pages:
            total_pages = min(total_pages, max_pages)

        print(f"총 {total_pages} 페이지에서 공고 수집 중...")

        all_announcements = []
        seen_ids = set()

        for page in range(1, total_pages + 1):
            print(f"  페이지 {page}/{total_pages} 처리 중...")
            announcements = self.get_announcements_from_page(page)

            for ann in announcements:
                if ann.id not in seen_ids:
                    all_announcements.append(ann)
                    seen_ids.add(ann.id)

            # 요청 간 딜레이
            time.sleep(0.5)

        print(f"총 {len(all_announcements)}개 공고 수집 완료")
        return all_announcements

    def get_attachments_from_announcement(self, announcement: Announcement) -> List[AttachmentFile]:
        """
        공고 상세 페이지에서 첨부파일 목록 추출

        Args:
            announcement: 공고 정보

        Returns:
            첨부파일 목록
        """
        attachments = []

        try:
            response = self.session.get(announcement.url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 첨부파일 다운로드 링크 찾기
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                if 'fileDownload' in href:
                    # 파일 ID 추출
                    file_id = href.split('/')[-1]

                    # 파일명 추출 (title 속성 또는 부모 요소에서)
                    filename = ""

                    # 같은 li 내의 파일명 요소 찾기
                    parent_li = link.find_parent('li')
                    if parent_li:
                        file_elem = parent_li.select_one('a.file_bg, [class*="file"]')
                        if file_elem:
                            filename = file_elem.get('title', '') or file_elem.get_text(strip=True)
                            # [첨부파일] 접두사 제거
                            filename = re.sub(r'^\[첨부파일\]\s*', '', filename)

                    if not filename:
                        filename = f"file_{file_id}"

                    # 다운로드 URL 생성
                    if href.startswith('/'):
                        download_url = BASE_URL + href
                    else:
                        download_url = href

                    # 중복 체크
                    if not any(a.file_id == file_id for a in attachments):
                        attachments.append(AttachmentFile(
                            file_id=file_id,
                            filename=filename,
                            download_url=download_url,
                            announcement_id=announcement.id
                        ))

        except Exception as e:
            print(f"공고 {announcement.id} 첨부파일 추출 실패: {e}")

        return attachments

    def download_file(self, attachment: AttachmentFile, subfolder: str = "") -> Optional[Path]:
        """
        첨부파일 다운로드

        Args:
            attachment: 첨부파일 정보
            subfolder: 하위 폴더명

        Returns:
            저장된 파일 경로 (실패 시 None)
        """
        try:
            # 저장 경로 설정
            if subfolder:
                save_dir = self.output_dir / subfolder
            else:
                save_dir = self.output_dir

            save_dir.mkdir(parents=True, exist_ok=True)

            # 다운로드
            response = self.session.get(attachment.download_url, stream=True)
            response.raise_for_status()

            # Content-Disposition에서 실제 파일명 추출
            content_disposition = response.headers.get('Content-Disposition', '')
            real_filename = None

            if 'filename' in content_disposition:
                match = re.search(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', content_disposition)
                if match:
                    raw_filename = match.group(1).strip('"\'')
                    # ISO-8859-1로 인코딩된 경우 EUC-KR로 디코딩 시도
                    try:
                        real_filename = raw_filename.encode('iso-8859-1').decode('euc-kr')
                    except:
                        try:
                            real_filename = urllib.parse.unquote(raw_filename)
                        except:
                            real_filename = raw_filename

            if not real_filename:
                real_filename = f"file_{attachment.file_id}"

            # 문서 파일만 저장 (HWP, HWPX, PDF, DOC, DOCX)
            target_extensions = {'.hwp', '.hwpx', '.pdf', '.doc', '.docx'}
            ext = Path(real_filename).suffix.lower()
            if ext not in target_extensions:
                return None  # 문서가 아니면 스킵

            # 파일명 정리 (특수문자 제거)
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', real_filename)
            save_path = save_dir / safe_filename

            # 이미 존재하는 파일 스킵
            if save_path.exists():
                print(f"  이미 존재: {safe_filename}")
                return save_path

            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  다운로드 완료: {save_path.name}")
            return save_path

        except Exception as e:
            print(f"  다운로드 실패 ({attachment.filename}): {e}")
            return None

    def download_all_attachments(self, max_pages: Optional[int] = None,
                                  max_workers: int = 3) -> Dict[str, int]:
        """
        모든 공고의 첨부파일 일괄 다운로드

        Args:
            max_pages: 최대 페이지 수
            max_workers: 동시 다운로드 수

        Returns:
            {'success': 성공 수, 'fail': 실패 수, 'skip': 스킵 수}
        """
        # 1. 공고 목록 수집
        announcements = self.get_all_announcements(max_pages)

        if not announcements:
            print("수집된 공고가 없습니다.")
            return {'success': 0, 'fail': 0, 'skip': 0}

        # 2. 각 공고의 첨부파일 수집
        print("\n첨부파일 정보 수집 중...")
        all_attachments = []

        for i, ann in enumerate(announcements, 1):
            if i % 10 == 1:
                print(f"  공고 {i}/{len(announcements)} 처리 중...")

            attachments = self.get_attachments_from_announcement(ann)
            all_attachments.extend(attachments)

            # 요청 간 딜레이
            time.sleep(0.3)

        print(f"총 {len(all_attachments)}개 첨부파일 발견")

        # 모든 첨부파일 다운로드 (Content-Disposition에서 실제 파일명 확인)
        # 기존 필터링 제거 - 다운로드 시 실제 파일명 확인 후 필터링
        filtered = all_attachments
        print(f"다운로드 대상 첨부파일: {len(filtered)}개")

        # 3. 파일 다운로드
        print("\n파일 다운로드 중...")
        success = 0
        fail = 0
        skip = 0

        for i, att in enumerate(filtered, 1):
            print(f"[{i}/{len(filtered)}] {att.filename[:50]}...")
            result = self.download_file(att)

            if result:
                if result.stat().st_size > 0:
                    success += 1
                else:
                    skip += 1
            else:
                fail += 1

            # 다운로드 간 딜레이
            time.sleep(0.5)

        print("\n" + "=" * 60)
        print(f"다운로드 완료: 성공 {success}, 실패 {fail}, 스킵 {skip}")
        print(f"저장 경로: {self.output_dir}")

        return {'success': success, 'fail': fail, 'skip': skip}


# ============================================================
# 표 복잡도 판별 및 변환 (hwp_converter.py에서 가져옴)
# ============================================================

def is_complex_table(table: Tag) -> bool:
    """복잡한 표인지 판별"""
    if table.find('table'):
        return True

    for cell in table.find_all(['td', 'th']):
        rowspan = int(cell.get('rowspan', 1))
        colspan = int(cell.get('colspan', 1))
        if rowspan > 1 or colspan > 1:
            return True

    cells = table.find_all(['td', 'th'])
    if cells:
        empty_count = sum(1 for c in cells if not c.get_text(strip=True))
        if empty_count / len(cells) > 0.5:
            return True

    return False


def complex_table_to_text(table: Tag, title: str = "") -> str:
    """복잡한 표를 텍스트로 변환"""
    lines = []

    if title:
        lines.append(f"\n### {title}\n")

    rows = table.find_all('tr')
    if not rows:
        return ""

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue

        cell_texts = []
        for cell in cells:
            text = cell.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)
            if text:
                cell_texts.append(text)

        if not cell_texts:
            continue

        first_cell = cells[0]
        rowspan = int(first_cell.get('rowspan', 1))

        if rowspan > 1 and len(cell_texts) >= 1:
            lines.append(f"\n**{cell_texts[0]}:**")
            for text in cell_texts[1:]:
                lines.append(f"- {text}")
        elif len(cell_texts) == 1:
            if first_cell.name == 'th' or (first_cell.get('colspan') and int(first_cell.get('colspan', 1)) > 1):
                lines.append(f"\n**{cell_texts[0]}:**")
            else:
                lines.append(f"- {cell_texts[0]}")
        elif len(cell_texts) == 2:
            lines.append(f"- {cell_texts[0]}: {cell_texts[1]}")
        else:
            key = cell_texts[0]
            values = ", ".join(cell_texts[1:])
            lines.append(f"- {key}: {values}")

    return "\n".join(lines)


def simple_table_to_markdown(table: Tag) -> str:
    """단순 표를 Markdown 표로 변환"""
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
            text = text.replace('|', '\\|')
            cell_texts.append(text if text else " ")

        if not cell_texts:
            continue

        md_row = "| " + " | ".join(cell_texts) + " |"
        md_rows.append(md_row)

        if not header_done:
            separator = "|" + "|".join(["---"] * len(cell_texts)) + "|"
            md_rows.append(separator)
            header_done = True

    return "\n".join(md_rows)


# ============================================================
# HWP/PDF 변환기 (hwp_converter.py에서 가져옴)
# ============================================================

class HwpToMarkdownConverter:
    """HWP 파일을 Markdown으로 변환하는 클래스"""

    def __init__(self):
        if not HAS_BS4:
            raise ImportError("beautifulsoup4가 필요합니다: pip install beautifulsoup4")
        if not HAS_MARKDOWNIFY:
            raise ImportError("markdownify가 필요합니다: pip install markdownify")

    def hwp_to_html(self, hwp_path: Path, output_dir: Path) -> Optional[Path]:
        """hwp5html로 HWP → HTML 변환"""
        hwp_path = Path(hwp_path).resolve()

        if not hwp_path.exists():
            raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {hwp_path}")

        try:
            result = subprocess.run(
                ['hwp5html', '--output', str(output_dir), str(hwp_path)],
                capture_output=True,
                timeout=60
            )

            html_file = output_dir / 'index.xhtml'
            if not html_file.exists():
                html_file = output_dir / 'index.html'

            if html_file.exists():
                return html_file

            return None

        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

    def process_html(self, html_content: str) -> str:
        """HTML을 파싱하여 Markdown 변환"""
        soup = BeautifulSoup(html_content, 'html.parser')

        for tag_name in ['script', 'style', 'meta', 'link', 'head']:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for table in soup.find_all('table'):
            if is_complex_table(table):
                text_content = complex_table_to_text(table)
                new_div = soup.new_tag('div')
                new_div['class'] = 'converted-table'
                new_div.string = text_content
                table.replace_with(new_div)
            else:
                md_table = simple_table_to_markdown(table)
                new_div = soup.new_tag('div')
                new_div['class'] = 'md-table'
                new_div.string = md_table
                table.replace_with(new_div)

        body = soup.find('body')
        html_str = str(body) if body else str(soup)

        markdown = md(
            html_str,
            heading_style="ATX",
            bullets="-",
            strip=['a'],
            escape_misc=False,
            escape_asterisks=False,
            escape_underscores=False,
        )

        return self._post_process_markdown(markdown)

    def _post_process_markdown(self, markdown: str) -> str:
        """Markdown 후처리"""
        lines = markdown.split('\n')
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
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
            line = re.sub(r' {2,}', ' ', line)
            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def convert(self, hwp_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """HWP 파일을 Markdown으로 변환"""
        hwp_path = Path(hwp_path).resolve()

        if output_path is None:
            output_path = hwp_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            html_file = self.hwp_to_html(hwp_path, tmpdir)

            if html_file is None:
                raise RuntimeError(f"HWP 변환 실패: {hwp_path}")

            html_content = html_file.read_text(encoding='utf-8', errors='ignore')
            markdown_content = self.process_html(html_content)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

        return markdown_content, output_path


class PdfToMarkdownConverter:
    """PDF 파일을 Markdown으로 변환하는 클래스"""

    def __init__(self):
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 필요합니다: pip install pymupdf")

    def extract_text(self, pdf_path: Path) -> str:
        """PDF에서 텍스트 추출"""
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        text_parts = []

        with fitz.open(str(pdf_path)) as doc:
            for page in doc:
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
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
            line = re.sub(r' {3,}', '  ', line)

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
# 배치 변환 함수
# ============================================================

def batch_convert(source_dir: Path, output_dir: Optional[Path] = None,
                  file_types: List[str] = None) -> Dict[str, int]:
    """
    폴더 내 모든 HWP/PDF 파일을 Markdown으로 변환

    Args:
        source_dir: 원본 파일 폴더
        output_dir: 출력 폴더 (None이면 source_dir 사용)
        file_types: 변환할 파일 유형 리스트

    Returns:
        {'success': 성공 수, 'fail': 실패 수, 'failed_files': 실패 파일 목록}
    """
    if file_types is None:
        file_types = ['hwp', 'hwpx', 'pdf']

    source_dir = Path(source_dir)
    if output_dir is None:
        output_dir = source_dir
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 기존 변환 파일 확인
    existing = {f.stem for f in output_dir.glob('*.md')}

    # 변환 대상 파일 수집
    files = []
    for ft in file_types:
        files.extend(source_dir.glob(f'*.{ft}'))
        files.extend(source_dir.glob(f'*.{ft.upper()}'))

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
    pdf_converter = PdfToMarkdownConverter()

    for i, file_path in enumerate(todo, 1):
        ext = file_path.suffix.lower()

        if i % 10 == 1 or i <= 5:
            print(f"[{i}/{len(todo)}] {file_path.name[:50]}...")

        try:
            out_path = output_dir / (file_path.stem + '.md')

            if ext in ['.hwp', '.hwpx']:
                hwp_converter.convert(file_path, out_path)
            elif ext == '.pdf':
                pdf_converter.convert(file_path, out_path)

            success += 1

        except Exception as e:
            fail += 1
            failed_files.append(f"{file_path.name}: {str(e)[:50]}")

    print("=" * 60)
    print(f"변환 완료: 성공 {success}, 실패 {fail}")

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

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="K-Startup 첨부파일 다운로드 및 HWP/PDF → Markdown 변환",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 첨부파일 다운로드만
  python hwp_converter2.py --download --output ./downloads

  # 처음 5페이지만 다운로드
  python hwp_converter2.py --download --max-pages 5 --output ./downloads

  # 다운로드 후 변환까지
  python hwp_converter2.py --download --convert --output ./downloads

  # 기존 파일 변환만
  python hwp_converter2.py --convert --source ./downloads

  # 단일 파일 변환
  python hwp_converter2.py --file ./document.hwp
        """
    )

    parser.add_argument("--download", action="store_true",
                        help="K-Startup에서 첨부파일 다운로드")
    parser.add_argument("--convert", action="store_true",
                        help="다운로드된 파일을 Markdown으로 변환")
    parser.add_argument("--file", type=str,
                        help="단일 파일 변환")
    parser.add_argument("--source", type=str,
                        help="변환할 파일이 있는 폴더 (--convert와 함께 사용)")
    parser.add_argument("--output", type=str, default="./kstartup_downloads",
                        help="출력 폴더 (기본: ./kstartup_downloads)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="다운로드할 최대 페이지 수")
    parser.add_argument("--types", type=str, nargs="+", default=['hwp', 'hwpx', 'pdf'],
                        help="변환할 파일 유형 (기본: hwp hwpx pdf)")

    args = parser.parse_args()

    # 단일 파일 변환
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"파일을 찾을 수 없습니다: {file_path}")
            return 1

        ext = file_path.suffix.lower()
        try:
            if ext in ['.hwp', '.hwpx']:
                converter = HwpToMarkdownConverter()
                markdown, out_path = converter.convert(file_path)
            elif ext == '.pdf':
                converter = PdfToMarkdownConverter()
                markdown, out_path = converter.convert(file_path)
            else:
                print(f"지원하지 않는 파일 형식: {ext}")
                return 1

            print(f"변환 완료: {out_path}")
            print("\n미리보기 (500자):")
            print(markdown[:500])

        except Exception as e:
            print(f"변환 실패: {e}")
            return 1

        return 0

    # 다운로드
    if args.download:
        output_dir = Path(args.output)
        crawler = KStartupCrawler(output_dir)
        result = crawler.download_all_attachments(max_pages=args.max_pages)

        if args.convert:
            print("\n" + "=" * 60)
            print("파일 변환 시작...")
            batch_convert(output_dir, output_dir, args.types)

        return 0

    # 변환만
    if args.convert:
        source_dir = Path(args.source) if args.source else Path(args.output)
        if not source_dir.exists():
            print(f"폴더를 찾을 수 없습니다: {source_dir}")
            return 1

        batch_convert(source_dir, source_dir, args.types)
        return 0

    # 아무 옵션도 없으면 도움말 출력
    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
