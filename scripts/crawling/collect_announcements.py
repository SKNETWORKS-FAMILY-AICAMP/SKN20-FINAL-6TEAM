# -*- coding: utf-8 -*-
"""
공고문 처리 모듈
- 기업마당/K-Startup API에서 공고 정보 조회
- HWP 첨부파일 다운로드 및 텍스트 추출
- OpenAI API로 지원대상/제외대상/지원금액 추출
- 최종 JSON 파일 생성

Usage:
    from announcement_processor import AnnouncementProcessor

    processor = AnnouncementProcessor()
    results = processor.process(count=10, vrf_str='b')  # 기업마당 10개
    results = processor.process(count=0, vrf_str='k')   # K-Startup 전체
    results = processor.process(count=5)                # 둘 다 5개씩
"""

import os
import re
import json
import time
import logging
import zlib
import zipfile
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable

import requests
from bs4 import BeautifulSoup
import olefile

# =============================================================================
# 설정
# =============================================================================

# 스킵할 파일명 키워드 (신청서류, 양식 등 공고문이 아닌 파일)
SKIP_KEYWORDS = [
    "신청서", "지원서", "신청양식", "지원양식",
    "신청서류", "지원서류", "제출서류",
    "접수서", "참가신청", "응모신청",
    "서식", "양식", "첨부서류", "제출양식",
    "동의서", "위임장", "확약서", "이력서",
    "사업계획서", "자기소개서", "추천서",
]


def _should_skip_file(filename: str) -> bool:
    """스킵해야 할 파일인지 확인"""
    filename_lower = filename.lower()
    for keyword in SKIP_KEYWORDS:
        if keyword in filename_lower:
            return True
    return False


@dataclass
class Config:
    """설정 클래스"""
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    output_dir: Path = field(default=None)
    temp_dir: Path = field(default=None)

    # API 키
    kstartup_api_key: str = ""
    bizinfo_api_key: str = ""
    openai_api_key: str = ""

    # HTTP 설정
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    timeout: int = 30

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.base_dir / "output"
        if self.temp_dir is None:
            self.temp_dir = self.base_dir / "temp"

        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        # .env 파일 로드
        self._load_env()

    def _load_env(self):
        """환경 변수 로드"""
        env_path = self.base_dir.parent.parent / ".env"
        if env_path.exists():
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value and not os.getenv(key):
                            os.environ[key] = value

        self.kstartup_api_key = os.getenv("K-STARTUP_API_KEY", "") or os.getenv("KSTARTUP_API_KEY", "")
        self.bizinfo_api_key = os.getenv("BIZINFO_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")


# =============================================================================
# 로거 설정
# =============================================================================

def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """로거 설정"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# =============================================================================
# API 클라이언트
# =============================================================================

class BizinfoClient:
    """기업마당 API 클라이언트"""

    API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"

    def __init__(self, api_key: str, logger: logging.Logger):
        self.api_key = api_key
        self.logger = logger

    def _is_recruiting(self, date_range: str) -> bool:
        """모집중인지 확인 (접수기간 기준) - 확실한 것만"""
        if not date_range:
            return False

        today = datetime.now().strftime("%Y%m%d")

        # "YYYYMMDD ~ YYYYMMDD" 형식만 허용 (확실한 날짜)
        if "~" in date_range:
            try:
                parts = date_range.replace(" ", "").split("~")
                if len(parts) == 2:
                    start_date = parts[0].strip()
                    end_date = parts[1].strip()
                    # 8자리 숫자인지 확인
                    if len(start_date) == 8 and len(end_date) == 8 and start_date.isdigit() and end_date.isdigit():
                        return start_date <= today <= end_date
            except:
                pass

        return False

    def fetch(self, count: int = 0, recruiting_only: bool = True) -> list[dict]:
        """공고 목록 조회 (count=0이면 전체, recruiting_only=True면 모집중만)"""
        if not self.api_key:
            self.logger.error("BIZINFO_API_KEY가 설정되지 않았습니다.")
            return []

        # 전체 조회 후 필터링
        params = {
            "crtfcKey": self.api_key,
            "dataType": "json",
        }

        try:
            resp = requests.get(self.API_URL, params=params, timeout=60)
            data = resp.json()
            items = data.get("jsonArray", [])

            announcements = []
            for item in items:
                # 모집중 필터링
                if recruiting_only:
                    date_range = item.get("reqstBeginEndDe", "")
                    if not self._is_recruiting(date_range):
                        continue

                ann = dict(item)
                ann["id"] = item.get("pblancId", "")
                announcements.append(ann)

                # count 제한
                if count > 0 and len(announcements) >= count:
                    break

            self.logger.info(f"기업마당 API: {len(announcements)}개 공고 조회 (모집중)")
            return announcements

        except Exception as e:
            self.logger.error(f"기업마당 API 호출 실패: {e}")
            return []


class KstartupClient:
    """K-Startup API 클라이언트"""

    API_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"

    def __init__(self, api_key: str, logger: logging.Logger):
        self.api_key = api_key
        self.logger = logger

    def _parse_xml_items(self, content: bytes) -> list[dict]:
        """XML 응답에서 item 파싱"""
        items = []
        try:
            root = ET.fromstring(content)
            for item in root.findall(".//item"):
                item_dict = {}
                for col in item.findall("col"):
                    name = col.get("name")
                    value = col.text.strip() if col.text else ""
                    item_dict[name] = value
                if item_dict:
                    items.append(item_dict)
        except ET.ParseError as e:
            self.logger.warning(f"  XML 파싱 오류: {e}")
        return items

    def fetch(self, count: int = 0, recruiting_only: bool = True) -> list[dict]:
        """공고 목록 조회 (count=0이면 전체, recruiting_only=True면 모집중만)"""
        if not self.api_key:
            self.logger.error("KSTARTUP_API_KEY가 설정되지 않았습니다.")
            return []

        announcements = []
        page = 1
        per_page = 500  # 한 번에 500개씩 요청
        max_pages = 100  # 최대 100페이지 (5만개)

        self.logger.info("K-Startup API 조회 중...")

        while page <= max_pages:
            params = {
                "serviceKey": self.api_key,
                "page": page,
                "perPage": per_page
            }

            try:
                resp = requests.get(self.API_URL, params=params, timeout=60)

                # 응답 상태 확인
                if resp.status_code != 200:
                    self.logger.error(f"  HTTP 오류: {resp.status_code}")
                    break

                # 응답 내용 확인 (JSON인지 XML인지)
                content = resp.content
                if not content or len(content) < 50:
                    self.logger.info(f"  페이지 {page}: 데이터 없음, 종료")
                    break

                # XML 파싱 시도
                items = self._parse_xml_items(content)

                if not items:
                    # JSON 형식일 수도 있음
                    try:
                        data = resp.json()
                        if "data" in data:
                            items = data.get("data", [])
                        elif isinstance(data, list):
                            items = data
                    except:
                        pass

                if not items:
                    self.logger.info(f"  페이지 {page}: 더 이상 데이터 없음")
                    break

                # 모집중 필터링 및 결과 추가
                for item_dict in items:
                    # 모집중 필터링 (rcrt_prgs_yn = "Y")
                    if recruiting_only:
                        if item_dict.get("rcrt_prgs_yn") != "Y":
                            continue

                    pbanc_sn = item_dict.get("pbanc_sn", "")
                    if pbanc_sn:
                        item_dict["id"] = pbanc_sn
                        announcements.append(item_dict)

                        # count 제한
                        if count > 0 and len(announcements) >= count:
                            self.logger.info(f"K-Startup API: {len(announcements)}개 공고 조회 완료 (모집중)")
                            return announcements

                self.logger.info(f"  페이지 {page}: {len(items)}개 조회, 모집중 누적 {len(announcements)}개")

                # 다음 페이지로
                if len(items) < per_page:
                    break  # 마지막 페이지

                page += 1
                time.sleep(0.5)  # API 부하 방지

            except requests.exceptions.Timeout:
                self.logger.error(f"  페이지 {page}: 타임아웃")
                break
            except Exception as e:
                self.logger.error(f"  페이지 {page} 조회 실패: {e}")
                break

        self.logger.info(f"K-Startup API: 총 {len(announcements)}개 공고 조회 (모집중)")
        return announcements


# =============================================================================
# HWP 다운로더
# =============================================================================

class HWPDownloader:
    """HWP 파일 다운로더"""

    HWP_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(config.headers)

    def _is_hwp(self, content: bytes) -> tuple[bool, str]:
        """HWP/HWPX 파일 여부 확인"""
        if not content:
            return False, ""
        if content[:8] == self.HWP_MAGIC:
            return True, ".hwp"
        if content[:2] == b'PK':
            return True, ".hwpx"
        return False, ""

    def _safe_filename(self, filename: str, ann_id: str, ext: str) -> str:
        """안전한 파일명 생성"""
        safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
        base = safe.rsplit('.', 1)[0] if '.' in safe else safe
        return f"{ann_id}_{base}{ext}"

    def download_bizinfo(self, ann_id: str, ann_data: dict = None) -> Path | None:
        """기업마당 HWP 다운로드 (공고문 우선)"""
        try:
            # 1. API 데이터에서 파일 URL 사용
            if ann_data:
                file_urls = []
                if ann_data.get("printFlpthNm"):
                    file_urls.append(("공고문", ann_data["printFlpthNm"], ann_data.get("printFileNm", "")))
                if ann_data.get("flpthNm"):
                    file_urls.append(("첨부", ann_data["flpthNm"], ann_data.get("fileNm", "")))

                for file_type, url, display_name in file_urls:
                    if not url:
                        continue

                    resp = self.session.get(url, timeout=self.config.timeout)
                    is_hwp, ext = self._is_hwp(resp.content)

                    if is_hwp:
                        filename = self._safe_filename(display_name or f"{file_type}", ann_id, ext)
                        output_path = self.config.temp_dir / filename
                        output_path.write_bytes(resp.content)
                        self.logger.info(f"  HWP 다운로드 ({file_type}): {output_path.name}")
                        return output_path

            # 2. 웹페이지에서 다운로드 (폴백)
            return self._download_bizinfo_from_web(ann_id)

        except Exception as e:
            self.logger.error(f"  HWP 다운로드 실패 [{ann_id}]: {e}")
            return None

    def _download_bizinfo_from_web(self, ann_id: str) -> Path | None:
        """기업마당 웹페이지에서 HWP 다운로드"""
        view_url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do"
        file_url = "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do"

        resp = self.session.get(view_url, params={"pblancId": ann_id}, timeout=self.config.timeout)
        soup = BeautifulSoup(resp.text, 'html.parser')

        for a in soup.select("a[href*='getImageFile.do']"):
            href = a.get("href", "")
            file_id_match = re.search(r"atchFileId=([A-Z_0-9]+)", href)
            file_sn_match = re.search(r"fileSn=(\d+)", href)

            if file_id_match:
                file_resp = self.session.get(
                    file_url,
                    params={
                        "atchFileId": file_id_match.group(1),
                        "fileSn": file_sn_match.group(1) if file_sn_match else "0"
                    },
                    timeout=self.config.timeout
                )

                is_hwp, ext = self._is_hwp(file_resp.content)
                if is_hwp:
                    output_path = self.config.temp_dir / f"{ann_id}_file{ext}"
                    output_path.write_bytes(file_resp.content)
                    self.logger.info(f"  HWP 다운로드: {output_path.name}")
                    return output_path

        return None

    def download_kstartup(self, ann_id: str, ann_data: dict = None) -> Path | None:
        """K-Startup HWP 다운로드"""
        self.session.headers["Referer"] = "https://www.k-startup.go.kr/"
        list_url = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"

        try:
            resp = self.session.get(list_url, params={"schM": "view", "pbancSn": ann_id}, timeout=self.config.timeout)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for a in soup.select("a[href*='fileDownload']"):
                href = a.get("href", "")
                match = re.search(r"/afile/fileDownload/([A-Za-z0-9]+)", href)

                if match:
                    file_code = match.group(1)
                    download_url = f"https://www.k-startup.go.kr/afile/fileDownload/{file_code}"
                    file_resp = self.session.get(download_url, timeout=self.config.timeout)

                    # 파일명 추출
                    filename = a.get_text(strip=True) or f"file_{file_code}"
                    content_disp = file_resp.headers.get("Content-Disposition", "")
                    if "filename" in content_disp:
                        fn_match = re.search(r"filename\*=(?:UTF-8''|utf-8'')([^;\n]+)", content_disp)
                        if fn_match:
                            filename = unquote(fn_match.group(1))

                    is_hwp, ext = self._is_hwp(file_resp.content)
                    if is_hwp:
                        safe_filename = self._safe_filename(filename, ann_id, ext)
                        output_path = self.config.temp_dir / safe_filename
                        output_path.write_bytes(file_resp.content)
                        self.logger.info(f"  HWP 다운로드: {output_path.name}")
                        return output_path

        except Exception as e:
            self.logger.error(f"  HWP 다운로드 실패 [{ann_id}]: {e}")

        return None


# =============================================================================
# 텍스트 추출기
# =============================================================================

class TextExtractor:
    """HWP/HWPX/PDF 텍스트 추출기"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def extract(self, file_path: Path) -> str:
        """파일에서 텍스트 추출"""
        suffix = file_path.suffix.lower()

        if suffix == '.hwp':
            text = self._extract_hwp(file_path)
        elif suffix == '.hwpx':
            text = self._extract_hwpx(file_path)
        elif suffix == '.pdf':
            text = self._extract_pdf(file_path)
        else:
            self.logger.warning(f"  지원하지 않는 파일 형식: {suffix}")
            return ""

        if text and len(text) > 100:
            self.logger.info(f"  텍스트 추출 완료: {len(text)}자")
            return text

        self.logger.warning(f"  텍스트 추출 실패 또는 내용 부족: {file_path.name}")
        return ""

    def _extract_hwp(self, hwp_path: Path) -> str:
        """HWP에서 텍스트 추출 (olefile)"""
        try:
            ole = olefile.OleFileIO(str(hwp_path))
            header = ole.openstream('FileHeader').read()
            is_compressed = header[36] & 1

            text_parts = []

            # PrvText 스트림
            if ole.exists('PrvText'):
                prv_text = ole.openstream('PrvText').read()
                try:
                    text = prv_text.decode('utf-16le', errors='ignore')
                    text_parts.append(text)
                except:
                    pass

            # BodyText 섹션
            for entry in ole.listdir():
                if entry[0] == 'BodyText':
                    stream_data = ole.openstream(entry).read()
                    if is_compressed:
                        try:
                            stream_data = zlib.decompress(stream_data, -15)
                        except:
                            continue
                    try:
                        text = stream_data.decode('utf-16le', errors='ignore')
                        text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t ')
                        if text.strip():
                            text_parts.append(text)
                    except:
                        pass

            ole.close()
            combined = '\n'.join(text_parts)
            return re.sub(r'\s+', ' ', combined).strip()

        except Exception as e:
            self.logger.warning(f"  HWP 추출 오류: {e}")
            return ""

    def _extract_hwpx(self, hwpx_path: Path) -> str:
        """HWPX에서 텍스트 추출 (ZIP/XML)"""
        try:
            text_parts = []
            with zipfile.ZipFile(hwpx_path, 'r') as zf:
                namelist = zf.namelist()

                # 진짜 HWPX인지 확인 (Contents/ 폴더 존재)
                has_contents = any(name.startswith('Contents/') for name in namelist)

                if has_contents:
                    # 진짜 HWPX: Contents/*.xml에서 텍스트 추출
                    for name in namelist:
                        if name.startswith('Contents/') and name.endswith('.xml'):
                            try:
                                content = zf.read(name).decode('utf-8')
                                root = ET.fromstring(content)
                                for elem in root.iter():
                                    if elem.text and elem.text.strip():
                                        text_parts.append(elem.text.strip())
                            except:
                                continue
                else:
                    # ZIP 압축 파일: 내부 HWP/HWPX 파일들에서 텍스트 추출
                    self.logger.info("  ZIP 압축 파일 감지, 내부 HWP 추출 시도")
                    import tempfile
                    for name in namelist:
                        name_lower = name.lower()
                        if not (name_lower.endswith('.hwp') or name_lower.endswith('.hwpx')):
                            continue

                        # 파일명만 추출 (경로 제외)
                        filename = Path(name).name

                        # 신청서/양식 등 스킵
                        if _should_skip_file(filename):
                            self.logger.info(f"    스킵 (양식/서식): {filename}")
                            continue

                        try:
                            # 임시 파일로 추출
                            file_data = zf.read(name)
                            suffix = '.hwpx' if name_lower.endswith('.hwpx') else '.hwp'
                            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                                tmp.write(file_data)
                                tmp_path = Path(tmp.name)

                            # 텍스트 추출
                            if suffix == '.hwp':
                                extracted_text = self._extract_hwp(tmp_path)
                            else:
                                # 내부 HWPX는 재귀 호출 (진짜 HWPX일 수 있음)
                                extracted_text = self._extract_hwpx(tmp_path)

                            if extracted_text:
                                text_parts.append(extracted_text)
                                self.logger.info(f"    추출 성공: {filename} ({len(extracted_text)}자)")

                            # 임시 파일 삭제
                            tmp_path.unlink(missing_ok=True)
                        except Exception as e:
                            self.logger.warning(f"  내부 파일 추출 실패: {e}")
                            continue

            return ' '.join(text_parts).strip()

        except Exception as e:
            self.logger.warning(f"  HWPX 추출 오류: {e}")
            return ""

    def _extract_pdf(self, pdf_path: Path) -> str:
        """PDF에서 텍스트 추출 (PyMuPDF)"""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text.strip()
        except Exception as e:
            self.logger.warning(f"  PDF 추출 오류: {e}")
            return ""


# =============================================================================
# OpenAI 분석기
# =============================================================================

class OpenAIAnalyzer:
    """OpenAI를 이용한 공고문 분석"""

    SYSTEM_PROMPT_FULL = """너는 정부 공고문 분석 전문가야.
아래 텍스트에서 '지원대상', '제외대상', '지원금액'을 찾아 요약해줘.
만약 해당 내용이 없다면 '정보 없음'이라고 답해줘.

반드시 아래 JSON 형식으로만 응답해:
{
  "지원대상": "...",
  "제외대상": "...",
  "지원금액": "..."
}"""

    SYSTEM_PROMPT_PARTIAL = """너는 정부 공고문 분석 전문가야.
아래 텍스트에서 '제외대상', '지원금액'을 찾아 요약해줘.
만약 해당 내용이 없다면 '정보 없음'이라고 답해줘.

반드시 아래 JSON 형식으로만 응답해:
{
  "제외대상": "...",
  "지원금액": "..."
}"""

    DEFAULT_RESULT = {"지원대상": "정보 없음", "제외대상": "정보 없음", "지원금액": "정보 없음"}

    def __init__(self, api_key: str, logger: logging.Logger):
        self.api_key = api_key
        self.logger = logger
        self.client = None

        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                self.logger.error("openai 패키지가 설치되지 않았습니다.")

    def analyze(self, text: str, extract_target: bool = True) -> dict:
        """
        텍스트에서 정보 추출

        Args:
            text: 분석할 텍스트
            extract_target: True면 지원대상 포함, False면 제외대상/지원금액만
        """
        if not self.client:
            self.logger.error("OpenAI 클라이언트가 초기화되지 않았습니다.")
            return self.DEFAULT_RESULT.copy()

        if not text or len(text) < 50:
            return self.DEFAULT_RESULT.copy()

        # 토큰 제한을 위해 텍스트 자르기
        max_chars = 15000
        if len(text) > max_chars:
            text = text[:max_chars]

        # 프롬프트 선택
        system_prompt = self.SYSTEM_PROMPT_FULL if extract_target else self.SYSTEM_PROMPT_PARTIAL

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 공고문에서 정보를 추출해줘:\n\n{text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            self.logger.info("  OpenAI 분석 완료")

            if extract_target:
                return {
                    "지원대상": result.get("지원대상", "정보 없음"),
                    "제외대상": result.get("제외대상", "정보 없음"),
                    "지원금액": result.get("지원금액", "정보 없음"),
                }
            else:
                return {
                    "제외대상": result.get("제외대상", "정보 없음"),
                    "지원금액": result.get("지원금액", "정보 없음"),
                }

        except Exception as e:
            self.logger.error(f"  OpenAI API 호출 실패: {e}")
            return self.DEFAULT_RESULT.copy()


# =============================================================================
# 메인 프로세서
# =============================================================================

class AnnouncementProcessor:
    """공고문 처리 메인 클래스"""

    def __init__(self, config: Config = None, logger: logging.Logger = None):
        self.config = config or Config()
        self.logger = logger or setup_logger("AnnouncementProcessor")

        # 컴포넌트 초기화
        self.bizinfo_client = BizinfoClient(self.config.bizinfo_api_key, self.logger)
        self.kstartup_client = KstartupClient(self.config.kstartup_api_key, self.logger)
        self.downloader = HWPDownloader(self.config, self.logger)
        self.extractor = TextExtractor(self.logger)
        self.analyzer = OpenAIAnalyzer(self.config.openai_api_key, self.logger)

    def process(self, count: int = 0, vrf_str: str = None) -> dict:
        """
        공고 처리 메인 함수

        Args:
            count: 처리할 공고 수 (0=전체)
            vrf_str: 'k'=K-Startup, 'b'=기업마당, None=둘 다

        Returns:
            dict: {"bizinfo": [...], "kstartup": [...]} 형식의 결과
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {"bizinfo": [], "kstartup": []}

        self.logger.info("=" * 60)
        self.logger.info("공고문 처리 시작")
        self.logger.info(f"대상: {vrf_str or '전체'}, 개수: {'전체' if count == 0 else count}")
        self.logger.info("=" * 60)

        # 기업마당 처리
        if vrf_str is None or vrf_str.lower() == 'b':
            self.logger.info("\n[기업마당 처리]")
            announcements = self.bizinfo_client.fetch(count)
            if announcements:
                results["bizinfo"] = self._process_announcements(
                    announcements,
                    self.downloader.download_bizinfo,
                    source="bizinfo"
                )
                self._save_results("bizinfo", results["bizinfo"], timestamp)

        # K-Startup 처리
        if vrf_str is None or vrf_str.lower() == 'k':
            self.logger.info("\n[K-Startup 처리]")
            announcements = self.kstartup_client.fetch(count)
            if announcements:
                results["kstartup"] = self._process_announcements(
                    announcements,
                    self.downloader.download_kstartup,
                    source="kstartup"
                )
                self._save_results("kstartup", results["kstartup"], timestamp)

        self.logger.info("\n" + "=" * 60)
        self.logger.info("처리 완료!")
        self.logger.info(f"기업마당: {len(results['bizinfo'])}개, K-Startup: {len(results['kstartup'])}개")
        self.logger.info(f"결과 파일: {self.config.output_dir}")
        self.logger.info("=" * 60)

        return results

    def _process_announcements(
        self,
        announcements: list[dict],
        download_func: Callable,
        source: str = "bizinfo"
    ) -> list[dict]:
        """공고 목록 처리"""
        results = []
        total = len(announcements)
        is_kstartup = source == "kstartup"

        for idx, ann in enumerate(announcements, 1):
            ann_id = ann["id"]
            title = ann.get("pblancNm") or ann.get("biz_pbanc_nm") or ann_id
            self.logger.info(f"[{idx}/{total}] 처리 중: [{ann_id}] {title[:40]}...")

            # K-Startup: API에서 지원대상 가져오기
            if is_kstartup:
                api_target = ann.get("aply_trgt_ctnt", "").strip()
                if not api_target:
                    api_target = ann.get("aply_trgt", "정보 없음")
                지원대상 = api_target if api_target else "정보 없음"
            else:
                지원대상 = "정보 없음"

            # 1. HWP 다운로드
            hwp_path = download_func(ann_id, ann)

            extracted_info = {"제외대상": "정보 없음", "지원금액": "정보 없음"}

            if hwp_path and hwp_path.exists():
                # 2. 텍스트 추출
                text = self.extractor.extract(hwp_path)

                if text:
                    # 3. OpenAI 분석 (K-Startup은 지원대상 제외)
                    extracted_info = self.analyzer.analyze(text, extract_target=not is_kstartup)

                    # 기업마당인 경우 지원대상도 LLM에서 추출
                    if not is_kstartup:
                        지원대상 = extracted_info.get("지원대상", "정보 없음")

                # 임시 파일 정리
                self._cleanup_temp_files(hwp_path)
            else:
                self.logger.warning("  HWP 파일 없음")

            # 4. 결과 병합
            result = {
                **ann,
                "지원대상": 지원대상,
                "제외대상": extracted_info.get("제외대상", "정보 없음"),
                "지원금액": extracted_info.get("지원금액", "정보 없음"),
            }
            results.append(result)

            time.sleep(1)  # API 부하 방지

        return results

    def _cleanup_temp_files(self, hwp_path: Path):
        """임시 파일 정리"""
        try:
            hwp_path.unlink(missing_ok=True)
            hwp_path.with_suffix('.pdf').unlink(missing_ok=True)
        except:
            pass

    def _save_results(self, source: str, data: list[dict], timestamp: str):
        """결과를 JSON 파일로 저장"""
        if not data:
            return

        output_file = self.config.output_dir / f"{source}_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "source": source,
                "generated_at": timestamp,
                "total_count": len(data),
                "data": data
            }, f, ensure_ascii=False, indent=2)

        self.logger.info(f"결과 저장: {output_file}")


# =============================================================================
# CLI 실행
# =============================================================================

def main():
    """CLI 진입점"""
    import argparse

    parser = argparse.ArgumentParser(description="공고문 처리 스크립트")
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=0,
        help="처리할 공고 수 (기본: 0=전체)"
    )
    parser.add_argument(
        "--source", "-s",
        type=str,
        default=None,
        choices=['k', 'b', 'K', 'B'],
        help="데이터 소스 (k=K-Startup, b=기업마당, 미지정=둘 다)"
    )
    args = parser.parse_args()

    processor = AnnouncementProcessor()
    processor.process(count=args.count, vrf_str=args.source)


if __name__ == "__main__":
    main()
