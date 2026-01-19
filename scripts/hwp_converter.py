"""
기업마당 지원사업 공고 HWP 파일 스크래핑 및 Markdown 변환 스크립트

게시판에서 최신 게시물의 HWP 첨부파일을 다운로드하고
pywin32를 사용하여 HWP → HTML+ 변환 후
BeautifulSoup4로 정리하고 markdownify로 Markdown 변환

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


# ============================================================
# 스크래핑 설정
# ============================================================
BASE_URL = "https://www.bizinfo.go.kr"
LIST_URL = f"{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/list.do"
OUTPUT_DIR = Path(__file__).parent / "output"


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

    def get_post_list(self, count: int = 5) -> List[Dict]:
        """게시판에서 최신 게시물 목록 추출"""
        response = self.session.get(LIST_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        posts = []

        # 게시물 링크 추출 (view.do?pblancId=PBLN_XXX 패턴)
        links = soup.find_all("a", href=re.compile(r"view\.do\?pblancId=PBLN_"))

        seen_ids = set()
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
                    if len(posts) >= count:
                        break

        return posts

    def get_attachments(self, post_url: str) -> List[Dict]:
        """게시물 상세 페이지에서 본문출력파일 첨부파일 목록 추출"""
        response = self.session.get(post_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        attachments = []
        seen_urls = set()

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
                                hwp_match = re.search(r"([^\s\[\]]+\.hwp)", li_text, re.IGNORECASE)
                                if hwp_match:
                                    attachments.append({
                                        "filename": hwp_match.group(1),
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
                                    hwp_match = re.search(r"([^\s\[\]]+\.hwp)", td_text, re.IGNORECASE)
                                    if hwp_match:
                                        attachments.append({
                                            "filename": hwp_match.group(1),
                                            "url": urljoin(BASE_URL, href)
                                        })
                    break

        # 방법 3: 페이지 전체에서 다운로드 링크와 HWP 파일명 매칭
        if not attachments:
            download_links = soup.find_all("a", href=re.compile(r"getImageFile\.do"))

            for a in download_links:
                href = a.get("href")
                if href in seen_urls:
                    continue

                container = a.find_parent(["li", "div", "td", "p"])
                if container:
                    container_text = container.get_text()
                    hwp_match = re.search(r"([^\s\[\]<>]+\.hwp)", container_text, re.IGNORECASE)
                    if hwp_match:
                        seen_urls.add(href)
                        attachments.append({
                            "filename": hwp_match.group(1),
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
def process_hwp_file(hwp_path: Path, metadata: Dict, output_dir: Path,
                     delete_original: bool = True) -> Optional[Path]:
    """
    HWP 파일을 Markdown으로 변환하고 VectorDB용 메타데이터 추가

    Args:
        hwp_path: HWP 파일 경로
        metadata: 게시물 메타데이터
        output_dir: 출력 디렉토리
        delete_original: 원본 HWP 파일 삭제 여부

    Returns:
        출력 Markdown 파일 경로 (실패시 None)
    """
    try:
        converter = HwpToMarkdownConverter()

        # 출력 파일명 생성 (게시물 ID + 원본 파일명)
        post_id = metadata.get("post_id", "unknown")
        short_id = post_id.replace("PBLN_", "").lstrip("0") or "0"
        base_name = f"{short_id}_{hwp_path.stem}"
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

        output_path = output_dir / f"{base_name}.md"

        # HWP → Markdown 변환
        markdown_content, _ = converter.convert(hwp_path, output_path)

        # VectorDB용 메타데이터를 Markdown 앞에 추가
        metadata_header = f"""---
post_id: {metadata.get('post_id', 'N/A')}
title: {metadata.get('title', '제목 없음')}
original_filename: {metadata.get('original_filename', 'N/A')}
source_url: {metadata.get('source_url', 'N/A')}
---

"""
        # 메타데이터 헤더 추가하여 다시 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(metadata_header + markdown_content)

        print(f"  저장 완료: {output_path}")

        # 원본 HWP 파일 삭제
        if delete_original and hwp_path.exists():
            hwp_path.unlink()
            print(f"  원본 삭제: {hwp_path.name}")

        return output_path

    except Exception as e:
        print(f"  변환 오류: {e}")
        return None


def scrape_and_convert(count: int = 5, output_dir: Optional[Path] = None) -> int:
    """
    기업마당에서 HWP 파일을 스크래핑하고 Markdown으로 변환

    Args:
        count: 처리할 게시물 수
        output_dir: 출력 디렉토리

    Returns:
        처리된 파일 수
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("기업마당 지원사업 공고 HWP → Markdown 변환기")
    print("=" * 60)

    # 스크래퍼 초기화
    print("\n[1] 세션 초기화 중...")
    scraper = BizInfoScraper()

    # 게시물 목록 가져오기
    print("[2] 게시물 목록 조회 중...")
    posts = scraper.get_post_list(count=count)
    print(f"    {len(posts)}개 게시물 발견")

    processed_count = 0

    for i, post in enumerate(posts, 1):
        print(f"\n[{i+2}] 게시물 처리: {post['title'][:40]}...")

        # 첨부파일 목록 가져오기
        attachments = scraper.get_attachments(post['url'])
        hwp_files = [a for a in attachments if a['filename'].lower().endswith('.hwp')]

        if not hwp_files:
            print("    HWP 첨부파일 없음")
            continue

        for attachment in hwp_files:
            print(f"    다운로드: {attachment['filename']}")

            # 임시 파일로 다운로드
            temp_path = output_dir / attachment['filename']

            try:
                downloaded_path = scraper.download_file(attachment['url'], temp_path)

                # HWP 파일 처리
                metadata = {
                    "post_id": post['id'],
                    "title": post['title'],
                    "original_filename": attachment['filename'],
                    "source_url": post['url']
                }

                result = process_hwp_file(downloaded_path, metadata, output_dir)
                if result:
                    processed_count += 1

            except Exception as e:
                print(f"    오류 발생: {e}")
                if temp_path.exists():
                    temp_path.unlink()

    print("\n" + "=" * 60)
    print(f"처리 완료: {processed_count}개 HWP 파일 변환됨")
    print(f"출력 위치: {output_dir}")
    print("=" * 60)

    return processed_count


# ============================================================
# 메인 실행
# ============================================================
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="HWP 파일을 Markdown으로 변환")
    parser.add_argument("--test", action="store_true", help="테스트 파일로 변환 테스트")
    parser.add_argument("--scrape", action="store_true", help="기업마당에서 스크래핑 후 변환")
    parser.add_argument("--count", type=int, default=5, help="스크래핑할 게시물 수 (기본: 5)")
    parser.add_argument("--file", type=str, help="변환할 HWP 파일 경로")
    parser.add_argument("--keep-html", action="store_true", help="중간 HTML 파일 유지")

    args = parser.parse_args()

    # 기본 동작: 테스트 파일 변환
    if args.test or (not args.scrape and not args.file):
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

    elif args.scrape:
        # 스크래핑 모드
        try:
            scrape_and_convert(count=args.count)
        except Exception as e:
            print(f"스크래핑 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.file:
        # 단일 파일 변환 모드
        hwp_path = Path(args.file)
        if not hwp_path.exists():
            print(f"파일을 찾을 수 없습니다: {hwp_path}")
            sys.exit(1)

        try:
            markdown, output_path = convert_hwp_to_markdown(hwp_path, keep_html=args.keep_html)
            print(f"변환 완료: {output_path}")
        except Exception as e:
            print(f"변환 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
