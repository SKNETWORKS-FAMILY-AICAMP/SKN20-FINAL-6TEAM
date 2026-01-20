"""
기업마당 지원사업 공고 HWP/PDF 파일 스크래핑 및 Markdown 변환 스크립트

게시판에서 최신 게시물의 HWP/PDF 첨부파일을 다운로드하고
- HWP: pywin32를 사용하여 HWP → HTML 변환 후 markdownify로 Markdown 변환
- PDF: PyMuPDF를 사용하여 텍스트 추출 후 Markdown 변환

VectorDB에 사용할 Markdown 파일 생성을 목표로 함
"""

import os
import re
import json
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from urllib.parse import urljoin, unquote

# HTTP 요청
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("경고: requests가 설치되지 않았습니다. pip install requests")

# Windows COM 인터페이스
try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False
    print("경고: pywin32가 설치되지 않았습니다. pip install pywin32")

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


# ============================================================
# 스크래핑 설정
# ============================================================
BASE_URL = "https://www.bizinfo.go.kr"
LIST_URL = f"{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/list.do"
RAW_DIR = Path(__file__).parent / "raw"       # HWP/PDF 원본 저장 폴더
OUTPUT_DIR = Path(__file__).parent / "output"  # MD 변환 결과 저장 폴더

# Markdown 변환 시 제외할 파일명 키워드 (신청서류, 지원서류, 서식 등)
# 다운로드는 모두 진행하고, 변환 시에만 제외
EXCLUDE_KEYWORDS_FOR_CONVERT = [
    "신청서", "지원서", "신청양식", "지원양식",
    "신청서류", "지원서류", "제출서류",
    "접수서", "참가신청", "응모신청",
    "서식", "양식", "첨부서류", "제출양식",
]


class HwpToMarkdownConverter:
    """HWP 파일을 Markdown으로 변환하는 클래스"""

    # 한글 SaveAs 파일 형식 상수
    HWP_FORMAT_HTML = "HTML"

    def __init__(self):
        """변환기 초기화"""
        self._check_dependencies()
        self.hwp = None

    def _check_dependencies(self):
        """필수 의존성 확인"""
        if not HAS_WIN32COM:
            raise ImportError("pywin32가 필요합니다: pip install pywin32")
        if not HAS_BS4:
            raise ImportError("beautifulsoup4가 필요합니다: pip install beautifulsoup4")
        if not HAS_MARKDOWNIFY:
            raise ImportError("markdownify가 필요합니다: pip install markdownify")

    def _init_hwp(self) -> None:
        """한글 COM 객체 초기화"""
        pythoncom.CoInitialize()
        try:
            # 한글 프로그램 COM 객체 생성
            self.hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
            # 보안 모듈 비활성화 (자동화에 필요)
            self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            # 백그라운드 모드로 실행
            self.hwp.XHwpWindows.Item(0).Visible = False
        except Exception as e:
            # gencache 실패 시 Dispatch 사용
            try:
                self.hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
                self.hwp.XHwpWindows.Item(0).Visible = False
            except Exception as e2:
                raise RuntimeError(f"한글 프로그램을 시작할 수 없습니다: {e2}")

    def _close_hwp(self) -> None:
        """한글 COM 객체 종료"""
        if self.hwp:
            try:
                self.hwp.Quit()
            except:
                pass
            self.hwp = None
        pythoncom.CoUninitialize()

    def hwp_to_html(self, hwp_path: Path, html_path: Optional[Path] = None) -> Path:
        """
        HWP 파일을 HTML로 변환

        Args:
            hwp_path: HWP 파일 경로
            html_path: 출력 HTML 파일 경로 (미지정시 임시 파일)

        Returns:
            HTML 파일 경로
        """
        hwp_path = Path(hwp_path).resolve()

        if not hwp_path.exists():
            raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {hwp_path}")

        if html_path is None:
            html_path = hwp_path.with_suffix('.html')
        else:
            html_path = Path(html_path).resolve()

        try:
            self._init_hwp()

            # HWP 파일 열기
            self.hwp.Open(str(hwp_path), "HWP", "forceopen:true")

            # HTML로 저장 (HTML+ 형식)
            # SaveAs(path, format, arg) - "HTML" 형식 사용
            self.hwp.SaveAs(str(html_path), "HTML")

            return html_path

        finally:
            self._close_hwp()

    def _read_html_with_encoding(self, html_path: Path) -> str:
        """
        HTML 파일을 올바른 인코딩으로 읽기

        한글 프로그램은 주로 euc-kr로 HTML을 저장함
        charset 메타 태그에서 인코딩을 감지하여 적용
        """
        # 먼저 바이너리로 읽어서 charset 감지
        with open(html_path, 'rb') as f:
            raw_content = f.read()

        # charset 메타 태그에서 인코딩 추출
        encoding = 'utf-8'  # 기본값

        # charset=xxx 패턴 찾기
        charset_match = re.search(rb'charset=([^\s"\'>;]+)', raw_content[:1000])
        if charset_match:
            detected_encoding = charset_match.group(1).decode('ascii', errors='ignore').strip()
            # 일반적인 한글 인코딩 매핑
            encoding_map = {
                'euc-kr': 'euc-kr',
                'euckr': 'euc-kr',
                'ks_c_5601-1987': 'euc-kr',
                'cp949': 'cp949',
                'utf-8': 'utf-8',
                'utf8': 'utf-8',
            }
            encoding = encoding_map.get(detected_encoding.lower(), detected_encoding)

        # 감지된 인코딩으로 디코딩
        try:
            html_content = raw_content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # 실패시 cp949 시도 (euc-kr 확장)
            try:
                html_content = raw_content.decode('cp949')
            except UnicodeDecodeError:
                # 최후의 수단: utf-8 with errors ignore
                html_content = raw_content.decode('utf-8', errors='ignore')

        return html_content

    def clean_html(self, html_content: str) -> str:
        """
        BeautifulSoup을 사용하여 HTML 정리

        VectorDB에 적합하도록 불필요한 태그와 스타일 제거

        Args:
            html_content: 원본 HTML 문자열

        Returns:
            정리된 HTML 문자열
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 불필요한 태그 완전 제거
        tags_to_remove = [
            'script', 'style', 'meta', 'link', 'head',
            'noscript', 'iframe', 'object', 'embed'
        ]
        for tag_name in tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 2. 모든 태그에서 불필요한 속성 제거 (style, class, id 등)
        # 단, href와 src는 유지
        attrs_to_keep = {'href', 'src', 'alt', 'title', 'colspan', 'rowspan'}
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in attrs_to_keep:
                    del tag[attr]

        # 3. 빈 태그 제거 (내용이 없는 div, span, p 등)
        def remove_empty_tags(soup_element):
            for tag in soup_element.find_all(['div', 'span', 'p', 'font', 'b', 'i', 'u']):
                if tag.string is None and not tag.find_all(True):
                    tag.decompose()
                elif tag.string and not tag.string.strip():
                    tag.decompose()

        remove_empty_tags(soup)

        # 4. 연속된 빈 줄/공백 정리
        for br in soup.find_all('br'):
            # 연속된 <br> 태그 하나로 통합
            while br.next_sibling and isinstance(br.next_sibling, Tag) and br.next_sibling.name == 'br':
                br.next_sibling.decompose()

        # 5. 표(table) 구조 정리 - VectorDB에서 표 데이터 활용을 위해 유지
        for table in soup.find_all('table'):
            # 빈 셀에 공백 추가
            for td in table.find_all(['td', 'th']):
                if not td.get_text(strip=True):
                    td.string = " "

        # 6. font 태그를 span으로 대체하거나 제거
        for font in soup.find_all('font'):
            font.unwrap()

        # 7. 불필요한 wrapper div 제거
        for div in soup.find_all('div'):
            # 자식이 하나뿐이고 텍스트가 없으면 unwrap
            children = list(div.children)
            if len(children) == 1 and isinstance(children[0], Tag):
                div.unwrap()

        # body 태그 내용만 반환
        body = soup.find('body')
        if body:
            return str(body)
        return str(soup)

    def html_to_markdown(self, html_content: str) -> str:
        """
        HTML을 Markdown으로 변환

        Args:
            html_content: HTML 문자열

        Returns:
            Markdown 문자열
        """
        # markdownify 옵션 설정
        # - strip: 특정 태그 제거
        # - heading_style: 헤딩 스타일 (ATX = #, SETEXT = underline)
        # - bullets: 리스트 불릿 문자
        markdown = md(
            html_content,
            heading_style="ATX",
            bullets="-",
            strip=['a'],  # 링크 텍스트만 유지, URL 제거 (VectorDB용)
            escape_misc=False,
            escape_asterisks=False,
            escape_underscores=False,
        )

        # 후처리: Markdown 정리
        markdown = self._post_process_markdown(markdown)

        return markdown

    def _post_process_markdown(self, markdown: str) -> str:
        """
        Markdown 후처리

        VectorDB에 적합하도록 추가 정리
        """
        lines = markdown.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            # 앞뒤 공백 제거
            line = line.rstrip()

            # 연속된 빈 줄 하나로 통합
            if not line.strip():
                if not prev_empty:
                    cleaned_lines.append('')
                    prev_empty = True
                continue

            prev_empty = False

            # 불필요한 특수문자 패턴 제거
            # HWP 변환 시 생기는 이상한 문자들
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)

            # 연속된 공백 하나로
            line = re.sub(r' {2,}', ' ', line)

            # 표 구분선 정리 (|---|---|)
            if re.match(r'^[\|\s\-:]+$', line):
                # 표 구분선은 유지하되 정규화
                cells = line.count('|') - 1
                if cells > 0:
                    line = '|' + '|'.join(['---'] * cells) + '|'

            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)

        # 시작과 끝의 빈 줄 제거
        result = result.strip()

        # 연속된 빈 줄 다시 정리 (최대 2개)
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def convert(self, hwp_path: Path, output_path: Optional[Path] = None,
                keep_html: bool = False) -> Tuple[str, Path]:
        """
        HWP 파일을 Markdown으로 변환 (전체 파이프라인)

        Args:
            hwp_path: HWP 파일 경로
            output_path: 출력 Markdown 파일 경로 (미지정시 동일 위치에 .md)
            keep_html: 중간 HTML 파일 유지 여부

        Returns:
            (Markdown 내용, 출력 파일 경로) 튜플
        """
        hwp_path = Path(hwp_path).resolve()

        if output_path is None:
            output_path = hwp_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        # 중간 HTML 파일 경로
        html_path = hwp_path.with_suffix('.html')

        try:
            # 1단계: HWP → HTML
            print(f"  [1/3] HWP → HTML 변환 중...")
            self.hwp_to_html(hwp_path, html_path)

            # 2단계: HTML 읽기 및 정리
            print(f"  [2/3] HTML 정리 중...")

            # HTML 파일의 인코딩 감지 (한글은 주로 euc-kr 또는 utf-8)
            html_content = self._read_html_with_encoding(html_path)

            cleaned_html = self.clean_html(html_content)

            # 3단계: HTML → Markdown
            print(f"  [3/3] Markdown 변환 중...")
            markdown_content = self.html_to_markdown(cleaned_html)

            # Markdown 파일 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            print(f"  완료: {output_path}")

            return markdown_content, output_path

        finally:
            # 중간 HTML 파일 정리
            if not keep_html and html_path.exists():
                html_path.unlink()


class PdfToMarkdownConverter:
    """PDF 파일을 Markdown으로 변환하는 클래스"""

    def __init__(self):
        """변환기 초기화"""
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 필요합니다: pip install pymupdf")

    def extract_text(self, pdf_path: Path) -> str:
        """
        PDF에서 텍스트 추출

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            추출된 텍스트
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        text_parts = []

        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, 1):
                # 페이지 텍스트 추출
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(f"<!-- 페이지 {page_num} -->\n{text}")

        return "\n\n".join(text_parts)

    def text_to_markdown(self, text: str) -> str:
        """
        추출된 텍스트를 Markdown으로 정리

        Args:
            text: 원본 텍스트

        Returns:
            정리된 Markdown 문자열
        """
        lines = text.split('\n')
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
            line = re.sub(r' {3,}', '  ', line)

            # 제목 감지 (짧고 굵은 텍스트, 숫자로 시작하는 항목 등)
            # 간단한 휴리스틱: "1.", "2.", "가.", "나." 등으로 시작하면 헤딩 처리
            if re.match(r'^[0-9]+\.\s+\S', line) and len(line) < 100:
                line = f"## {line}"
            elif re.match(r'^[가-힣]\.\s+\S', line) and len(line) < 100:
                line = f"### {line}"
            elif re.match(r'^[○●◎◇■□▶▷]\s*', line):
                # 불릿 포인트 변환
                line = re.sub(r'^[○●◎◇■□▶▷]\s*', '- ', line)

            cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines)
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def convert(self, pdf_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
        """
        PDF 파일을 Markdown으로 변환 (전체 파이프라인)

        Args:
            pdf_path: PDF 파일 경로
            output_path: 출력 Markdown 파일 경로

        Returns:
            (Markdown 내용, 출력 파일 경로) 튜플
        """
        pdf_path = Path(pdf_path).resolve()

        if output_path is None:
            output_path = pdf_path.with_suffix('.md')
        else:
            output_path = Path(output_path).resolve()

        print(f"  [1/2] PDF 텍스트 추출 중...")
        text = self.extract_text(pdf_path)

        print(f"  [2/2] Markdown 변환 중...")
        markdown_content = self.text_to_markdown(text)

        # Markdown 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"  완료: {output_path}")

        return markdown_content, output_path


def convert_pdf_to_markdown(pdf_path: Path, output_path: Optional[Path] = None) -> Tuple[str, Path]:
    """
    PDF 파일을 Markdown으로 변환하는 편의 함수

    Args:
        pdf_path: PDF 파일 경로
        output_path: 출력 Markdown 파일 경로

    Returns:
        (Markdown 내용, 출력 파일 경로) 튜플
    """
    converter = PdfToMarkdownConverter()
    return converter.convert(pdf_path, output_path)


def convert_hwp_to_markdown(hwp_path: Path, output_path: Optional[Path] = None,
                            keep_html: bool = False) -> Tuple[str, Path]:
    """
    HWP 파일을 Markdown으로 변환하는 편의 함수

    Args:
        hwp_path: HWP 파일 경로
        output_path: 출력 Markdown 파일 경로
        keep_html: 중간 HTML 파일 유지 여부

    Returns:
        (Markdown 내용, 출력 파일 경로) 튜플
    """
    converter = HwpToMarkdownConverter()
    return converter.convert(hwp_path, output_path, keep_html)


# ============================================================
# 스크래핑 클래스
# ============================================================
class BizInfoScraper:
    """기업마당 지원사업 공고 스크래퍼"""

    def __init__(self):
        """스크래퍼 초기화"""
        if not HAS_REQUESTS:
            raise ImportError("requests가 필요합니다: pip install requests")
        if not HAS_BS4:
            raise ImportError("beautifulsoup4가 필요합니다: pip install beautifulsoup4")

        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """세션 생성 및 초기화"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        # 초기 페이지 방문하여 세션 쿠키 획득
        session.get(LIST_URL)
        return session

    def get_post_list(self, count: int = 5, max_pages: int = 50) -> List[Dict]:
        """
        게시판에서 게시물 목록 추출 (페이지네이션 지원)

        Args:
            count: 가져올 게시물 수 (0이면 전체)
            max_pages: 최대 조회 페이지 수

        Returns:
            게시물 정보 리스트
        """
        posts = []
        seen_ids = set()
        page = 1

        while page <= max_pages:
            # 페이지 파라미터 추가
            page_url = f"{LIST_URL}?rows=15&cpage={page}"
            print(f"    페이지 {page} 조회 중...")

            try:
                response = self.session.get(page_url)
                response.raise_for_status()
            except Exception as e:
                print(f"    페이지 {page} 조회 실패: {e}")
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # 게시물 링크 추출 (view.do?pblancId=PBLN_XXX 패턴)
            links = soup.find_all("a", href=re.compile(r"view\.do\?pblancId=PBLN_"))

            if not links:
                print(f"    페이지 {page}: 게시물 없음, 종료")
                break

            page_post_count = 0
            for link in links:
                href = link.get("href")
                match = re.search(r"pblancId=(PBLN_\d+)", href)
                if match:
                    pblanc_id = match.group(1)
                    if pblanc_id not in seen_ids:
                        seen_ids.add(pblanc_id)
                        title = link.get_text(strip=True)
                        posts.append({
                            "id": pblanc_id,
                            "title": title,
                            "url": urljoin(BASE_URL, f"/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}")
                        })
                        page_post_count += 1

                        # count가 0이 아니면 제한 적용
                        if count > 0 and len(posts) >= count:
                            return posts

            print(f"    페이지 {page}: {page_post_count}개 게시물 추가 (총 {len(posts)}개)")

            # 이 페이지에서 새 게시물이 없으면 종료
            if page_post_count == 0:
                break

            page += 1

        return posts

    def get_attachments(self, post_url: str) -> List[Dict]:
        """게시물 상세 페이지에서 본문출력파일 첨부파일 목록 추출 (HWP, PDF)"""
        response = self.session.get(post_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        attachments = []
        seen_urls = set()

        # HWP 또는 PDF 파일 패턴
        file_pattern = r"([^\s\[\]<>]+\.(hwp|pdf))"

        # 방법 1: "본문출력파일" 섹션 찾기
        for heading in soup.find_all(["h3", "h4", "strong", "th"]):
            heading_text = heading.get_text(strip=True)
            if "본문출력파일" in heading_text:
                parent = heading.find_parent()
                if parent:
                    for a in parent.find_all("a", href=True):
                        href = a.get("href")
                        if "getImageFile.do" in href and href not in seen_urls:
                            seen_urls.add(href)
                            li = a.find_parent("li")
                            if li:
                                li_text = li.get_text()
                                file_match = re.search(file_pattern, li_text, re.IGNORECASE)
                                if file_match:
                                    attachments.append({
                                        "filename": file_match.group(1),
                                        "url": urljoin(BASE_URL, href)
                                    })

        # 방법 2: 테이블 구조에서 "본문출력파일" 찾기
        if not attachments:
            for th in soup.find_all("th"):
                if "본문출력파일" in th.get_text():
                    tr = th.find_parent("tr")
                    if tr:
                        td = tr.find("td")
                        if td:
                            for a in td.find_all("a", href=True):
                                href = a.get("href")
                                if "getImageFile.do" in href and href not in seen_urls:
                                    seen_urls.add(href)
                                    td_text = td.get_text()
                                    file_match = re.search(file_pattern, td_text, re.IGNORECASE)
                                    if file_match:
                                        attachments.append({
                                            "filename": file_match.group(1),
                                            "url": urljoin(BASE_URL, href)
                                        })
                    break

        # 방법 3: 페이지 전체에서 다운로드 링크와 파일명 매칭
        if not attachments:
            download_links = soup.find_all("a", href=re.compile(r"getImageFile\.do"))

            for a in download_links:
                href = a.get("href")
                if href in seen_urls:
                    continue

                container = a.find_parent(["li", "div", "td", "p"])
                if container:
                    container_text = container.get_text()
                    file_match = re.search(file_pattern, container_text, re.IGNORECASE)
                    if file_match:
                        seen_urls.add(href)
                        attachments.append({
                            "filename": file_match.group(1),
                            "url": urljoin(BASE_URL, href)
                        })

        return attachments

    def download_file(self, url: str, save_path: Path) -> Path:
        """파일 다운로드"""
        response = self.session.get(url, stream=True)
        response.raise_for_status()

        # Content-Disposition 헤더에서 실제 파일명 추출
        content_disp = response.headers.get("Content-Disposition", "")
        real_filename = None

        if content_disp:
            # filename*=UTF-8''인코딩된파일명 형식 (RFC 5987)
            match = re.search(r"filename\*=(?:UTF-8''|utf-8'')(.+?)(?:;|$)", content_disp, re.IGNORECASE)
            if match:
                real_filename = unquote(match.group(1).strip("\"'"))
            else:
                # filename="파일명" 형식
                match = re.search(r'filename="?([^";]+)"?', content_disp, re.IGNORECASE)
                if match:
                    raw_filename = match.group(1).strip()
                    try:
                        real_filename = unquote(raw_filename)
                    except:
                        real_filename = raw_filename

        if real_filename:
            save_path = save_path.parent / real_filename

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return save_path


# ============================================================
# 통합 처리 함수
# ============================================================
def process_file(file_path: Path, metadata: Dict, output_dir: Path,
                 delete_original: bool = False) -> Optional[Path]:
    """
    HWP 또는 PDF 파일을 Markdown으로 변환하고 VectorDB용 메타데이터 추가

    Args:
        file_path: HWP 또는 PDF 파일 경로
        metadata: 게시물 메타데이터
        output_dir: 출력 디렉토리
        delete_original: 원본 파일 삭제 여부

    Returns:
        출력 Markdown 파일 경로 (실패시 None)
    """
    try:
        file_ext = file_path.suffix.lower()

        # 출력 파일명 생성 (게시물 ID + 원본 파일명)
        post_id = metadata.get("post_id", "unknown")
        short_id = post_id.replace("PBLN_", "").lstrip("0") or "0"
        base_name = f"{short_id}_{file_path.stem}"
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

        output_path = output_dir / f"{base_name}.md"

        # 파일 형식에 따라 적절한 변환기 사용
        if file_ext == '.hwp':
            converter = HwpToMarkdownConverter()
            markdown_content, _ = converter.convert(file_path, output_path)
        elif file_ext == '.pdf':
            converter = PdfToMarkdownConverter()
            markdown_content, _ = converter.convert(file_path, output_path)
        else:
            print(f"  지원하지 않는 파일 형식: {file_ext}")
            return None

        # VectorDB용 메타데이터를 Markdown 앞에 추가
        metadata_header = f"""---
post_id: {metadata.get('post_id', 'N/A')}
title: {metadata.get('title', '제목 없음')}
original_filename: {metadata.get('original_filename', 'N/A')}
source_url: {metadata.get('source_url', 'N/A')}
file_type: {file_ext[1:].upper()}
---

"""
        # 메타데이터 헤더 추가하여 다시 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(metadata_header + markdown_content)

        print(f"  저장 완료: {output_path}")

        # 원본 파일 삭제
        if delete_original and file_path.exists():
            file_path.unlink()
            print(f"  원본 삭제: {file_path.name}")

        return output_path

    except Exception as e:
        print(f"  변환 오류: {e}")
        return None


def should_exclude_for_convert(filename: str) -> bool:
    """
    Markdown 변환 시 제외할 파일인지 확인
    (신청서류, 지원서류, 서식 등)

    Args:
        filename: 파일명

    Returns:
        제외해야 하면 True, 아니면 False
    """
    filename_lower = filename.lower()
    for keyword in EXCLUDE_KEYWORDS_FOR_CONVERT:
        if keyword.lower() in filename_lower:
            return True
    return False


def download_all_files(count: int = 5, raw_dir: Optional[Path] = None,
                       max_pages: int = 50) -> List[Dict]:
    """
    기업마당에서 HWP/PDF 파일을 모두 raw 폴더에 다운로드
    (신청서, 지원서 등 모든 파일 포함)

    Args:
        count: 처리할 게시물 수 (0이면 전체)
        raw_dir: 파일 저장 디렉토리
        max_pages: 최대 조회 페이지 수

    Returns:
        다운로드된 파일 정보 리스트
    """
    if raw_dir is None:
        raw_dir = RAW_DIR

    raw_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("기업마당 지원사업 공고 HWP/PDF 파일 다운로드")
    print("=" * 60)

    # 스크래퍼 초기화
    print("\n[1] 세션 초기화 중...")
    scraper = BizInfoScraper()

    # 게시물 목록 가져오기
    print("[2] 게시물 목록 조회 중..." + (" (전체)" if count == 0 else f" (최대 {count}개)"))
    posts = scraper.get_post_list(count=count, max_pages=max_pages)
    print(f"    총 {len(posts)}개 게시물 발견")

    downloaded_files = []
    hwp_count = 0
    pdf_count = 0

    for i, post in enumerate(posts, 1):
        print(f"\n[{i+2}] 게시물 처리: {post['title'][:40]}...")

        # 첨부파일 목록 가져오기 (HWP, PDF 모두)
        attachments = scraper.get_attachments(post['url'])
        target_files = [a for a in attachments
                        if a['filename'].lower().endswith(('.hwp', '.pdf'))]

        if not target_files:
            print("    HWP/PDF 첨부파일 없음")
            continue

        for attachment in target_files:
            filename = attachment['filename']
            file_ext = Path(filename).suffix.lower()

            print(f"    다운로드: {filename}")

            # raw 폴더에 저장
            save_path = raw_dir / filename

            # 중복 파일 처리: 게시물 ID 추가
            if save_path.exists():
                post_id = post['id'].replace("PBLN_", "").lstrip("0") or "0"
                save_path = raw_dir / f"{post_id}_{filename}"

            try:
                downloaded_path = scraper.download_file(attachment['url'], save_path)

                downloaded_files.append({
                    "file_path": downloaded_path,
                    "post_id": post['id'],
                    "title": post['title'],
                    "original_filename": filename,
                    "source_url": post['url']
                })
                print(f"    저장됨: {downloaded_path.name}")

                if file_ext == '.hwp':
                    hwp_count += 1
                elif file_ext == '.pdf':
                    pdf_count += 1

            except Exception as e:
                print(f"    다운로드 오류: {e}")

    print("\n" + "=" * 60)
    print(f"다운로드 완료: {len(downloaded_files)}개 파일 (HWP: {hwp_count}, PDF: {pdf_count})")
    print(f"저장 위치: {raw_dir}")
    print("=" * 60)

    return downloaded_files


# 이전 버전 호환성을 위한 별칭
download_all_hwp_files = download_all_files


def convert_downloaded_files(downloaded_files: List[Dict],
                             output_dir: Optional[Path] = None,
                             delete_original: bool = False) -> int:
    """
    다운로드된 HWP/PDF 파일들을 Markdown으로 변환
    (신청서류, 지원서류, 서식 파일은 변환에서 제외)

    Args:
        downloaded_files: download_all_files에서 반환된 파일 정보 리스트
        output_dir: MD 파일 출력 디렉토리
        delete_original: 원본 파일 삭제 여부

    Returns:
        변환된 파일 수
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("HWP/PDF → Markdown 변환 시작")
    print("=" * 60)

    converted_count = 0
    skipped_count = 0

    for i, file_info in enumerate(downloaded_files, 1):
        # 호환성: hwp_path 또는 file_path 키 모두 지원
        file_path = file_info.get('file_path') or file_info.get('hwp_path')
        if file_path is None:
            continue

        file_path = Path(file_path)
        filename = file_info.get('original_filename', file_path.name)

        # 변환 시 제외 대상 필터링 (신청서류, 지원서류, 서식 등)
        if should_exclude_for_convert(filename):
            print(f"\n[{i}/{len(downloaded_files)}] 건너뜀 (서식/신청서류): {filename}")
            skipped_count += 1
            continue

        print(f"\n[{i}/{len(downloaded_files)}] 변환 중: {file_path.name}")

        if not file_path.exists():
            print(f"    파일 없음: {file_path}")
            continue

        metadata = {
            "post_id": file_info.get('post_id', 'unknown'),
            "title": file_info.get('title', ''),
            "original_filename": filename,
            "source_url": file_info.get('source_url', '')
        }

        result = process_file(file_path, metadata, output_dir,
                              delete_original=delete_original)
        if result:
            converted_count += 1

    print("\n" + "=" * 60)
    print(f"변환 완료: {converted_count}개 파일")
    print(f"건너뜀 (서식/신청서류): {skipped_count}개 파일")
    print(f"출력 위치: {output_dir}")
    print("=" * 60)

    return converted_count


def scrape_and_convert(count: int = 5, output_dir: Optional[Path] = None,
                       raw_dir: Optional[Path] = None,
                       delete_original: bool = False,
                       max_pages: int = 50) -> int:
    """
    기업마당에서 HWP 파일을 스크래핑하고 Markdown으로 변환

    Args:
        count: 처리할 게시물 수 (0이면 전체)
        output_dir: MD 파일 출력 디렉토리
        raw_dir: HWP 원본 저장 디렉토리
        delete_original: 원본 HWP 파일 삭제 여부
        max_pages: 최대 조회 페이지 수

    Returns:
        처리된 파일 수
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if raw_dir is None:
        raw_dir = RAW_DIR

    # 1단계: HWP 파일 다운로드
    downloaded_files = download_all_hwp_files(count=count, raw_dir=raw_dir, max_pages=max_pages)

    if not downloaded_files:
        print("\n다운로드된 파일이 없습니다.")
        return 0

    # 2단계: Markdown 변환
    converted_count = convert_downloaded_files(
        downloaded_files,
        output_dir=output_dir,
        delete_original=delete_original
    )

    return converted_count


# ============================================================
# 메인 실행
# ============================================================
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="HWP/PDF 파일을 Markdown으로 변환")
    parser.add_argument("--test", action="store_true", help="테스트 파일로 변환 테스트")
    parser.add_argument("--scrape", action="store_true", help="기업마당에서 스크래핑 후 변환")
    parser.add_argument("--download-only", action="store_true", help="HWP/PDF 파일만 다운로드 (변환하지 않음)")
    parser.add_argument("--convert-raw", action="store_true", help="raw 폴더의 HWP/PDF 파일을 변환")
    parser.add_argument("--count", type=int, default=5, help="스크래핑할 게시물 수 (기본: 5)")
    parser.add_argument("--all", action="store_true", help="전체 게시물 스크래핑 (count 무시)")
    parser.add_argument("--max-pages", type=int, default=50, help="최대 페이지 수 (기본: 50)")
    parser.add_argument("--file", type=str, help="변환할 HWP 또는 PDF 파일 경로")
    parser.add_argument("--keep-html", action="store_true", help="중간 HTML 파일 유지 (HWP만 해당)")
    parser.add_argument("--delete-original", action="store_true", help="변환 후 원본 파일 삭제")
    parser.add_argument("--exclude", type=str, nargs="+", help="추가로 변환 제외할 키워드")

    args = parser.parse_args()

    # 추가 제외 키워드 등록 (변환 시 제외)
    if args.exclude:
        EXCLUDE_KEYWORDS_FOR_CONVERT.extend(args.exclude)
        print(f"추가 제외 키워드 (변환 시): {args.exclude}")

    # 기본 동작: 테스트 파일 변환
    if args.test or (not args.scrape and not args.file and not args.download_only and not args.convert_raw):
        script_dir = Path(__file__).parent
        test_hwp = script_dir / "hwp2md_test.hwp"

        if not test_hwp.exists():
            print(f"테스트 파일을 찾을 수 없습니다: {test_hwp}")
            sys.exit(1)

        print(f"테스트 파일: {test_hwp}")
        print("=" * 60)

        try:
            converter = HwpToMarkdownConverter()
            markdown, output_path = converter.convert(test_hwp, keep_html=args.keep_html)

            print("\n" + "=" * 60)
            print("변환 결과 (처음 1000자):")
            print("=" * 60)
            print(markdown[:1000] if len(markdown) > 1000 else markdown)
            print("\n" + "=" * 60)
            print(f"출력 파일: {output_path}")

        except Exception as e:
            print(f"변환 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.download_only:
        # 다운로드만 수행 (모든 HWP/PDF 파일 저장)
        try:
            count = 0 if args.all else args.count
            downloaded = download_all_files(count=count, max_pages=args.max_pages)
            print(f"\n총 {len(downloaded)}개 파일이 raw 폴더에 저장되었습니다.")
        except Exception as e:
            print(f"다운로드 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.convert_raw:
        # raw 폴더의 기존 HWP/PDF 파일 변환
        try:
            raw_dir = RAW_DIR
            if not raw_dir.exists():
                print(f"raw 폴더가 없습니다: {raw_dir}")
                sys.exit(1)

            # HWP와 PDF 파일 모두 수집
            target_files = (
                list(raw_dir.glob("*.hwp")) +
                list(raw_dir.glob("*.HWP")) +
                list(raw_dir.glob("*.pdf")) +
                list(raw_dir.glob("*.PDF"))
            )
            if not target_files:
                print("raw 폴더에 HWP/PDF 파일이 없습니다.")
                sys.exit(1)

            print(f"raw 폴더에서 {len(target_files)}개 HWP/PDF 파일 발견")

            # 파일 정보 구성 (메타데이터 없이)
            # 다운로드된 파일은 모두 포함하고, 변환 시 필터링은 convert_downloaded_files에서 수행
            downloaded_files = []
            for file_path in target_files:
                downloaded_files.append({
                    "file_path": file_path,
                    "post_id": "unknown",
                    "title": file_path.stem,
                    "original_filename": file_path.name,
                    "source_url": "local"
                })

            converted = convert_downloaded_files(
                downloaded_files,
                delete_original=args.delete_original
            )
            print(f"\n총 {converted}개 파일이 변환되었습니다.")

        except Exception as e:
            print(f"변환 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.scrape:
        # 스크래핑 모드 (다운로드 + 변환)
        try:
            count = 0 if args.all else args.count
            scrape_and_convert(count=count, delete_original=args.delete_original,
                               max_pages=args.max_pages)
        except Exception as e:
            print(f"스크래핑 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.file:
        # 단일 파일 변환 모드
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"파일을 찾을 수 없습니다: {file_path}")
            sys.exit(1)

        file_ext = file_path.suffix.lower()
        try:
            if file_ext == '.hwp':
                markdown, output_path = convert_hwp_to_markdown(file_path, keep_html=args.keep_html)
            elif file_ext == '.pdf':
                markdown, output_path = convert_pdf_to_markdown(file_path)
            else:
                print(f"지원하지 않는 파일 형식입니다: {file_ext}")
                print("지원 형식: .hwp, .pdf")
                sys.exit(1)

            print(f"변환 완료: {output_path}")
        except Exception as e:
            print(f"변환 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
