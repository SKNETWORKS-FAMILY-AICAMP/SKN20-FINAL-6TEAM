"""
기업마당 지원사업 공고 HWP 파일 스크래핑 및 변환 스크립트

게시판에서 최신 5개 게시물의 HWP 첨부파일을 다운로드하고
JSON/MD 형식으로 변환 후 원본 HWP 파일을 삭제합니다.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import subprocess
import tempfile
import shutil


BASE_URL = "https://www.bizinfo.go.kr"
LIST_URL = f"{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/list.do"
OUTPUT_DIR = Path(__file__).parent / "output"


def get_session():
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


def get_post_list(session, count=5):
    """게시판에서 최신 게시물 목록 추출"""
    response = session.get(LIST_URL)
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


def get_attachments(session, post_url):
    """게시물 상세 페이지에서 본문출력파일 첨부파일 목록 추출"""
    response = session.get(post_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    attachments = []
    seen_urls = set()

    # 방법 1: "본문출력파일" 섹션 찾기 (h3 또는 th 태그)
    # h3 태그에서 "본문출력파일" 텍스트를 찾고 그 다음 형제 요소에서 링크 추출
    for heading in soup.find_all(["h3", "h4", "strong", "th"]):
        heading_text = heading.get_text(strip=True)
        if "본문출력파일" in heading_text:
            # 다음 형제 요소들에서 다운로드 링크 찾기
            parent = heading.find_parent()
            if parent:
                for a in parent.find_all("a", href=True):
                    href = a.get("href")
                    if "getImageFile.do" in href and href not in seen_urls:
                        seen_urls.add(href)
                        # 파일명 추출 - 링크 주변 텍스트에서
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
        # 모든 다운로드 링크 수집
        download_links = soup.find_all("a", href=re.compile(r"getImageFile\.do"))

        for a in download_links:
            href = a.get("href")
            if href in seen_urls:
                continue

            # 링크의 부모 li 또는 div에서 파일명 추출
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

    # 방법 4: 링크 텍스트가 "다운로드"인 경우 이전 텍스트에서 파일명 추출
    if not attachments:
        for a in soup.find_all("a", string=re.compile(r"다운로드|다운")):
            href = a.get("href", "")
            if "getImageFile.do" in href and href not in seen_urls:
                # 이전 형제 텍스트 노드에서 파일명 찾기
                prev = a.find_previous_sibling(string=True)
                if prev:
                    hwp_match = re.search(r"([^\s\[\]]+\.hwp)", str(prev), re.IGNORECASE)
                    if hwp_match:
                        seen_urls.add(href)
                        attachments.append({
                            "filename": hwp_match.group(1),
                            "url": urljoin(BASE_URL, href)
                        })

    return attachments


def download_file(session, url, save_path):
    """파일 다운로드"""
    from urllib.parse import unquote

    response = session.get(url, stream=True)
    response.raise_for_status()

    # Content-Disposition 헤더에서 실제 파일명 추출
    content_disp = response.headers.get("Content-Disposition", "")
    real_filename = None

    if content_disp:
        # filename*=UTF-8''인코딩된파일명 형식 (RFC 5987)
        match = re.search(r"filename\*=(?:UTF-8''|utf-8'')(.+?)(?:;|$)", content_disp, re.IGNORECASE)
        if match:
            real_filename = unquote(match.group(1).strip('"\''))
        else:
            # filename="파일명" 형식
            match = re.search(r'filename="?([^";]+)"?', content_disp, re.IGNORECASE)
            if match:
                raw_filename = match.group(1).strip()
                # URL 인코딩된 경우 디코딩
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


def convert_hwp_to_text(hwp_path):
    """
    HWP 파일을 텍스트로 변환
    pyhwp의 hwp5txt 명령어 또는 olefile을 사용하여 텍스트 추출
    """
    text_content = ""

    # 방법 1: pyhwp의 hwp5txt 사용 시도
    try:
        result = subprocess.run(
            ["hwp5txt", str(hwp_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 방법 2: olefile을 사용한 직접 추출
    try:
        import olefile

        if olefile.isOleFile(str(hwp_path)):
            ole = olefile.OleFileIO(str(hwp_path))

            # HWP 파일의 텍스트 스트림들
            text_streams = []
            for stream in ole.listdir():
                stream_path = "/".join(stream)
                if "BodyText" in stream_path or "Section" in stream_path:
                    text_streams.append(stream)

            for stream in text_streams:
                try:
                    data = ole.openstream(stream).read()
                    # HWP 텍스트는 압축되어 있을 수 있음
                    try:
                        import zlib
                        decompressed = zlib.decompress(data, -15)
                        # 유니코드 텍스트 추출 시도
                        text = extract_text_from_hwp_stream(decompressed)
                        text_content += text + "\n"
                    except:
                        # 압축되지 않은 경우
                        text = extract_text_from_hwp_stream(data)
                        text_content += text + "\n"
                except:
                    continue

            ole.close()
    except ImportError:
        pass
    except Exception as e:
        print(f"olefile 처리 오류: {e}")

    # 방법 3: python-hwp 라이브러리 사용 시도
    if not text_content:
        try:
            from hwp5.hwp5txt import hwp5txt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                tmp_path = tmp.name

            hwp5txt(str(hwp_path), tmp_path)

            with open(tmp_path, 'r', encoding='utf-8') as f:
                text_content = f.read()

            os.unlink(tmp_path)
        except:
            pass

    return text_content


def extract_text_from_hwp_stream(data):
    """HWP 스트림에서 텍스트 추출"""
    text = ""
    try:
        # HWP 5.0 형식의 텍스트 레코드 파싱
        # 텍스트는 UTF-16LE로 인코딩되어 있음
        i = 0
        while i < len(data) - 4:
            # 레코드 헤더 읽기
            header = int.from_bytes(data[i:i+4], 'little')
            tag_id = header & 0x3FF
            level = (header >> 10) & 0x3FF
            size = (header >> 20) & 0xFFF

            if size == 0xFFF:
                # 확장 크기
                if i + 8 <= len(data):
                    size = int.from_bytes(data[i+4:i+8], 'little')
                    i += 8
                else:
                    break
            else:
                i += 4

            # 텍스트 태그 (67 = HWPTAG_PARA_TEXT)
            if tag_id == 67 and i + size <= len(data):
                try:
                    # 텍스트 데이터 추출
                    text_data = data[i:i+size]
                    # 컨트롤 문자 제거하고 텍스트만 추출
                    decoded = ""
                    j = 0
                    while j < len(text_data) - 1:
                        char_code = int.from_bytes(text_data[j:j+2], 'little')
                        if char_code == 0:
                            break
                        elif char_code < 32:
                            # 컨트롤 문자
                            if char_code == 10 or char_code == 13:
                                decoded += "\n"
                            j += 2
                        # surrogate 문자 범위 제외 (0xD800-0xDFFF)
                        elif 0xD800 <= char_code <= 0xDFFF:
                            j += 2
                        else:
                            try:
                                decoded += chr(char_code)
                            except:
                                pass
                            j += 2
                    text += decoded + "\n"
                except:
                    pass

            i += size
    except:
        # 실패 시 단순 유니코드 디코딩 시도
        try:
            text = data.decode('utf-16le', errors='ignore')
            # 출력 불가능한 문자 및 surrogate 문자 제거
            text = ''.join(c for c in text if (c.isprintable() or c in '\n\r\t') and not (0xD800 <= ord(c) <= 0xDFFF))
        except:
            pass

    return text


def sanitize_text(text):
    """텍스트에서 HWP 컨트롤 코드를 의미 있는 마커로 치환 (표 구조 유지)"""
    if not text:
        return ""

    # 1단계: HWP 컨트롤 코드를 의미 있는 마커로 치환
    replacements = [
        # 표/셀 관련 마커 - 구조 유지
        ('\u6364\u7365', '\n<<<TABLE>>>\n'),   # 捤獥 → 표 시작
        ('\u6C20\u7462', ' | '),                # 氠瑢 → 셀 구분
        ('\u7462\u6C20', ' | '),                # 瑢氠 → 셀 구분 (역순)
        ('\u6364', ' | '),                      # 단독 → 셀 구분
        ('\u7365', ''),
        ('\u6C20', ' '),
        ('\u7462', ' '),
        ('\u6573', ''),
        ('\u0063', ''),
        ('\u2074', ''),
        ('\u6C62', ''),
    ]

    result = text
    for old, new in replacements:
        result = result.replace(old, new)

    # 2단계: 남은 HWP 컨트롤 코드 범위를 셀 구분자로 치환
    cleaned_chars = []
    prev_was_control = False

    for c in result:
        code = ord(c)

        # surrogate 문자 제거
        if 0xD800 <= code <= 0xDFFF:
            continue

        # HWP 컨트롤 코드 범위 → 셀 구분자로 치환
        if (0x6200 <= code <= 0x67FF) or (0x7000 <= code <= 0x77FF):
            if not prev_was_control:
                cleaned_chars.append(' | ')
                prev_was_control = True
            continue

        # 제어 문자 (줄바꿈, 탭 제외)
        if code < 32 and c not in '\n\r\t':
            continue

        cleaned_chars.append(c)
        prev_was_control = False

    cleaned = ''.join(cleaned_chars)

    # 3단계: 표 마커를 마크다운 형식으로 변환
    # <<<TABLE>>> 을 보기 좋게 변환
    cleaned = cleaned.replace('<<<TABLE>>>', '\n\n---[표 시작]---\n')

    # 4단계: 연속된 구분자 정리
    while ' |  | ' in cleaned:
        cleaned = cleaned.replace(' |  | ', ' | ')
    while '| |' in cleaned:
        cleaned = cleaned.replace('| |', '|')
    while '|  |' in cleaned:
        cleaned = cleaned.replace('|  |', ' | ')

    # 줄 시작/끝의 | 정리
    lines = cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # 빈 줄이나 구분자만 있는 줄 스킵
        if not line or line == '|' or line == '| |':
            continue
        # 줄 시작/끝 | 정리
        if line.startswith('| '):
            line = line[2:]
        if line.endswith(' |'):
            line = line[:-2]
        cleaned_lines.append(line)

    cleaned = '\n'.join(cleaned_lines)

    # 5단계: 연속된 줄바꿈 정리
    while '\n\n\n' in cleaned:
        cleaned = cleaned.replace('\n\n\n', '\n\n')

    return cleaned.strip()


def convert_hwp_with_hwplib(hwp_path):
    """hwplib을 사용한 HWP 변환 (Java 기반 - 대안)"""
    # 이 방법은 Java가 설치되어 있어야 함
    pass


def save_as_json(content, metadata, output_path):
    """JSON 형식으로 저장"""
    # 텍스트 정리 (JSON 호환되지 않는 문자 제거)
    clean_content = sanitize_text(content)
    data = {
        "metadata": metadata,
        "content": clean_content
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_as_markdown(content, metadata, output_path):
    """마크다운 형식으로 저장"""
    clean_content = sanitize_text(content)
    md_content = f"""# {metadata.get('title', '제목 없음')}

## 메타데이터
- **게시물 ID**: {metadata.get('post_id', 'N/A')}
- **원본 파일**: {metadata.get('original_filename', 'N/A')}
- **다운로드 URL**: {metadata.get('source_url', 'N/A')}

---

## 본문 내용

{clean_content}
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)


def process_hwp_file(hwp_path, metadata, output_format="json"):
    """HWP 파일 처리: 변환 후 저장, 원본 삭제"""
    content = convert_hwp_to_text(hwp_path)

    if not content.strip():
        print(f"  경고: {hwp_path.name}에서 텍스트를 추출할 수 없습니다.")
        content = "(텍스트 추출 실패 - HWP 파일 형식이 지원되지 않거나 암호화되어 있을 수 있습니다)"

    # 출력 파일명 생성 (게시물 ID + 원본 파일명으로 고유성 확보)
    post_id = metadata.get("post_id", "unknown")
    # PBLN_000000000117608 -> 117608
    short_id = post_id.replace("PBLN_", "").lstrip("0") or "0"
    base_name = f"{short_id}_{hwp_path.stem}"
    # 파일명에 사용할 수 없는 문자 제거
    base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

    if output_format == "json":
        output_path = OUTPUT_DIR / f"{base_name}.json"
        save_as_json(content, metadata, output_path)
    else:
        output_path = OUTPUT_DIR / f"{base_name}.md"
        save_as_markdown(content, metadata, output_path)

    print(f"  저장 완료: {output_path}")

    # 원본 HWP 파일 삭제
    hwp_path.unlink()
    print(f"  원본 삭제: {hwp_path.name}")

    return output_path


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("기업마당 지원사업 공고 HWP 스크래퍼")
    print("=" * 60)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 세션 생성
    print("\n[1] 세션 초기화 중...")
    session = get_session()

    # 게시물 목록 가져오기
    print("[2] 게시물 목록 조회 중...")
    posts = get_post_list(session, count=5)
    print(f"    {len(posts)}개 게시물 발견")

    processed_count = 0

    for i, post in enumerate(posts, 1):
        print(f"\n[{i+2}] 게시물 처리: {post['title'][:40]}...")

        # 첨부파일 목록 가져오기
        attachments = get_attachments(session, post['url'])

        hwp_files = [a for a in attachments if a['filename'].lower().endswith('.hwp')]

        if not hwp_files:
            print("    HWP 첨부파일 없음")
            continue

        for attachment in hwp_files:
            print(f"    다운로드: {attachment['filename']}")

            # 임시 파일로 다운로드
            temp_path = OUTPUT_DIR / attachment['filename']

            try:
                downloaded_path = download_file(session, attachment['url'], temp_path)

                # HWP 파일 처리
                metadata = {
                    "post_id": post['id'],
                    "title": post['title'],
                    "original_filename": attachment['filename'],
                    "source_url": post['url']
                }

                process_hwp_file(downloaded_path, metadata, output_format="json")
                processed_count += 1

            except Exception as e:
                print(f"    오류 발생: {e}")
                # 실패 시 임시 파일 정리
                if temp_path.exists():
                    temp_path.unlink()

    print("\n" + "=" * 60)
    print(f"처리 완료: {processed_count}개 HWP 파일 변환됨")
    print(f"출력 위치: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
