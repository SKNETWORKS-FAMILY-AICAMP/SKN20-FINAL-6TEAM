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
import io
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

# 신청서/양식 파일 키워드 (공고문 정보 추출에서는 제외하지만 별도 저장)
APPLICATION_FORM_KEYWORDS = [
    "신청서", "지원서", "신청양식", "지원양식",
    "신청서류", "지원서류", "제출서류",
    "접수서", "참가신청", "응모신청",
    "서식", "양식", "첨부서류", "제출양식",
    "동의서", "위임장", "확약서", "이력서",
    "사업계획서", "자기소개서", "추천서",
]


# gpt-4o-mini 가격 (USD per 1M tokens)
OPENAI_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """OpenAI API 호출 비용 계산"""
    pricing = OPENAI_PRICING.get(model, {"input": 0.15, "output": 0.60})
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]


def _is_application_form(filename: str) -> bool:
    """신청서/양식 파일인지 확인"""
    filename_lower = filename.lower()
    for keyword in APPLICATION_FORM_KEYWORDS:
        if keyword in filename_lower:
            return True
    return False


def _should_skip_file(filename: str) -> bool:
    """정보 추출에서 스킵해야 할 파일인지 확인 (신청서/양식)"""
    return _is_application_form(filename)


@dataclass
class Config:
    """설정 클래스"""
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    output_dir: Path = field(default=None)
    temp_dir: Path = field(default=None)
    forms_dir: Path = field(default=None)  # 신청서/양식 저장 디렉토리

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
        if self.forms_dir is None:
            self.forms_dir = self.base_dir / "forms"  # 신청서/양식 저장

        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        self.forms_dir.mkdir(exist_ok=True)

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

class FileDownloader:
    """문서 파일 다운로더 (HWP/HWPX/PPT/PPTX 지원)"""

    # OLE Compound Document 매직 바이트 (HWP, PPT 등)
    OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(config.headers)

    def _detect_file_type(self, content: bytes, filename: str = "") -> tuple[bool, str]:
        """
        파일 타입 감지 (HWP/HWPX/PPT/PPTX)

        Returns:
            tuple[bool, str]: (지원 파일 여부, 확장자)
        """
        if not content:
            return False, ""

        filename_lower = filename.lower()

        # ZIP 기반 파일 (HWPX, PPTX, DOCX 등)
        if content[:2] == b'PK':
            # 파일명으로 타입 판별
            if filename_lower.endswith('.pptx'):
                return True, ".pptx"
            elif filename_lower.endswith('.hwpx'):
                return True, ".hwpx"
            # 파일명이 없으면 내부 구조로 판별
            try:
                import io
                with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                    namelist = zf.namelist()
                    if any(name.startswith('ppt/') for name in namelist):
                        return True, ".pptx"
                    elif any(name.startswith('Contents/') for name in namelist):
                        return True, ".hwpx"
                    # 일반 ZIP (내부에 문서 파일 있을 수 있음)
                    return True, ".zip"
            except:
                return True, ".hwpx"  # 기본값

        # OLE 기반 파일 (HWP, PPT)
        if content[:8] == self.OLE_MAGIC:
            # 파일명으로 타입 판별
            if filename_lower.endswith('.ppt'):
                return True, ".ppt"
            elif filename_lower.endswith('.hwp'):
                return True, ".hwp"
            # 파일명이 없으면 내부 구조로 판별
            try:
                ole = olefile.OleFileIO(io.BytesIO(content))
                entries = ['/'.join(e) for e in ole.listdir()]
                ole.close()
                if any('PowerPoint' in e for e in entries):
                    return True, ".ppt"
                else:
                    return True, ".hwp"  # 기본값
            except:
                return True, ".hwp"  # 기본값

        return False, ""

    def _is_hwp(self, content: bytes) -> tuple[bool, str]:
        """하위 호환성을 위한 래퍼 (deprecated)"""
        return self._detect_file_type(content)

    def _safe_filename(self, filename: str, ann_id: str, ext: str) -> str:
        """안전한 파일명 생성"""
        safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
        base = safe.rsplit('.', 1)[0] if '.' in safe else safe
        return f"{ann_id}_{base}{ext}"

    def save_form_file(self, content: bytes, filename: str, ann_id: str, ext: str) -> Path:
        """
        신청서/양식 파일을 forms_dir에 저장

        Args:
            content: 파일 내용
            filename: 원본 파일명
            ann_id: 공고 ID
            ext: 확장자

        Returns:
            Path: 저장된 파일 경로
        """
        safe_filename = self._safe_filename(filename, ann_id, ext)
        output_path = self.config.forms_dir / safe_filename
        output_path.write_bytes(content)
        self.logger.info(f"  📋 신청양식 저장: {output_path.name}")
        return output_path

    def iter_files_bizinfo(self, ann_id: str, ann_data: dict = None, form_files: list = None):
        """
        기업마당 문서 파일들을 순회하는 제너레이터

        Args:
            ann_id: 공고 ID
            ann_data: API 응답 데이터
            form_files: 신청서/양식 파일 경로를 저장할 리스트 (외부에서 전달)

        Yields:
            Path: 다운로드된 파일 경로 (정보 추출용, 신청서/양식 제외)
        """
        if form_files is None:
            form_files = []

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

                    try:
                        resp = self.session.get(url, timeout=self.config.timeout)
                        is_valid, ext = self._detect_file_type(resp.content, display_name)

                        if is_valid:
                            # 신청서/양식 파일인지 확인
                            if _is_application_form(display_name):
                                form_path = self.save_form_file(resp.content, display_name, ann_id, ext)
                                form_files.append(str(form_path))
                                continue  # 정보 추출에서는 스킵

                            filename = self._safe_filename(display_name or f"{file_type}", ann_id, ext)
                            output_path = self.config.temp_dir / filename
                            output_path.write_bytes(resp.content)
                            self.logger.info(f"  문서 다운로드 ({file_type}): {output_path.name}")
                            yield output_path
                    except Exception as e:
                        self.logger.warning(f"  파일 다운로드 실패 ({file_type}): {e}")
                        continue

            # 2. 웹페이지에서 추가 파일 다운로드
            yield from self._iter_files_bizinfo_from_web(ann_id, form_files)

        except Exception as e:
            self.logger.error(f"  문서 다운로드 실패 [{ann_id}]: {e}")

    def download_bizinfo(self, ann_id: str, ann_data: dict = None) -> Path | None:
        """기업마당 문서 다운로드 (첫 번째 파일만 반환, 하위 호환성)"""
        for file_path in self.iter_files_bizinfo(ann_id, ann_data):
            return file_path
        return None

    def _iter_files_bizinfo_from_web(self, ann_id: str, form_files: list = None):
        """기업마당 웹페이지에서 문서 파일들을 순회하는 제너레이터"""
        if form_files is None:
            form_files = []

        view_url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do"
        file_url = "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do"

        try:
            resp = self.session.get(view_url, params={"pblancId": ann_id}, timeout=self.config.timeout)
            soup = BeautifulSoup(resp.text, 'html.parser')

            file_idx = 0
            for a in soup.select("a[href*='getImageFile.do']"):
                href = a.get("href", "")
                link_text = a.get_text(strip=True)
                file_id_match = re.search(r"atchFileId=([A-Z_0-9]+)", href)
                file_sn_match = re.search(r"fileSn=(\d+)", href)

                if file_id_match:
                    try:
                        file_resp = self.session.get(
                            file_url,
                            params={
                                "atchFileId": file_id_match.group(1),
                                "fileSn": file_sn_match.group(1) if file_sn_match else "0"
                            },
                            timeout=self.config.timeout
                        )

                        is_valid, ext = self._detect_file_type(file_resp.content, link_text)
                        if is_valid:
                            # 신청서/양식 파일인지 확인
                            if _is_application_form(link_text):
                                form_path = self.save_form_file(file_resp.content, link_text, ann_id, ext)
                                form_files.append(str(form_path))
                                continue  # 정보 추출에서는 스킵

                            output_path = self.config.temp_dir / f"{ann_id}_file{file_idx}{ext}"
                            output_path.write_bytes(file_resp.content)
                            self.logger.info(f"  문서 다운로드: {output_path.name}")
                            file_idx += 1
                            yield output_path
                    except Exception as e:
                        self.logger.warning(f"  파일 다운로드 실패: {e}")
                        continue
        except Exception as e:
            self.logger.error(f"  웹페이지 접근 실패 [{ann_id}]: {e}")

    def _download_bizinfo_from_web(self, ann_id: str) -> Path | None:
        """기업마당 웹페이지에서 문서 다운로드 (첫 번째 파일만, 하위 호환성)"""
        for file_path in self._iter_files_bizinfo_from_web(ann_id):
            return file_path
        return None

    def iter_files_kstartup(self, ann_id: str, ann_data: dict = None, form_files: list = None):
        """
        K-Startup 문서 파일들을 순회하는 제너레이터

        Args:
            ann_id: 공고 ID
            ann_data: API 응답 데이터
            form_files: 신청서/양식 파일 경로를 저장할 리스트 (외부에서 전달)

        Yields:
            Path: 다운로드된 파일 경로 (정보 추출용, 신청서/양식 제외)
        """
        if form_files is None:
            form_files = []

        self.session.headers["Referer"] = "https://www.k-startup.go.kr/"
        list_url = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"

        try:
            resp = self.session.get(list_url, params={"schM": "view", "pbancSn": ann_id}, timeout=self.config.timeout)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for a in soup.select("a[href*='fileDownload']"):
                href = a.get("href", "")
                match = re.search(r"/afile/fileDownload/([A-Za-z0-9]+)", href)

                if match:
                    try:
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

                        is_valid, ext = self._detect_file_type(file_resp.content, filename)
                        if is_valid:
                            # 신청서/양식 파일인지 확인
                            if _is_application_form(filename):
                                form_path = self.save_form_file(file_resp.content, filename, ann_id, ext)
                                form_files.append(str(form_path))
                                continue  # 정보 추출에서는 스킵

                            safe_filename = self._safe_filename(filename, ann_id, ext)
                            output_path = self.config.temp_dir / safe_filename
                            output_path.write_bytes(file_resp.content)
                            self.logger.info(f"  문서 다운로드: {output_path.name}")
                            yield output_path
                    except Exception as e:
                        self.logger.warning(f"  파일 다운로드 실패: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"  문서 다운로드 실패 [{ann_id}]: {e}")

    def download_kstartup(self, ann_id: str, ann_data: dict = None) -> Path | None:
        """K-Startup 문서 다운로드 (첫 번째 파일만 반환, 하위 호환성)"""
        for file_path in self.iter_files_kstartup(ann_id, ann_data):
            return file_path
        return None


# 하위 호환성을 위한 별칭
HWPDownloader = FileDownloader


# =============================================================================
# 텍스트 추출기
# =============================================================================

class TextExtractor:
    """HWP/HWPX/PPT/PPTX/PDF/ZIP 텍스트 추출기"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def extract(self, file_path: Path) -> str:
        """파일에서 텍스트 추출"""
        suffix = file_path.suffix.lower()

        if suffix == '.hwp':
            text = self._extract_hwp(file_path)
        elif suffix == '.hwpx':
            text = self._extract_hwpx(file_path)
        elif suffix == '.pptx':
            text = self._extract_pptx(file_path)
        elif suffix == '.ppt':
            text = self._extract_ppt(file_path)
        elif suffix == '.pdf':
            text = self._extract_pdf(file_path)
        elif suffix == '.zip':
            text = self._extract_zip(file_path)
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
                    # ZIP 압축 파일: 내부 문서 파일들에서 텍스트 추출
                    self.logger.info("  ZIP 압축 파일 감지, 내부 문서 추출 시도")
                    import tempfile
                    supported_extensions = ('.hwp', '.hwpx', '.ppt', '.pptx', '.pdf')

                    for name in namelist:
                        name_lower = name.lower()
                        if not any(name_lower.endswith(ext) for ext in supported_extensions):
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
                            suffix = Path(name_lower).suffix
                            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                                tmp.write(file_data)
                                tmp_path = Path(tmp.name)

                            # 파일 타입에 따라 텍스트 추출
                            extracted_text = ""
                            if suffix == '.hwp':
                                extracted_text = self._extract_hwp(tmp_path)
                            elif suffix == '.hwpx':
                                extracted_text = self._extract_hwpx(tmp_path)
                            elif suffix == '.pptx':
                                extracted_text = self._extract_pptx(tmp_path)
                            elif suffix == '.ppt':
                                extracted_text = self._extract_ppt(tmp_path)
                            elif suffix == '.pdf':
                                extracted_text = self._extract_pdf(tmp_path)

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

    def extract_form_pages_from_pdf(self, pdf_path: Path, output_dir: Path, ann_id: str) -> Path | None:
        """
        PDF에서 신청서/양식 페이지를 감지하고 분리하여 별도 PDF로 저장

        Args:
            pdf_path: 원본 PDF 경로
            output_dir: 출력 디렉토리
            ann_id: 공고 ID (파일명에 사용)

        Returns:
            Path | None: 분리된 신청서 PDF 경로 (없으면 None)
        """
        try:
            import fitz
            doc = fitz.open(pdf_path)
            form_pages = []

            # 각 페이지에서 신청서/양식 키워드 검색
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # 신청서/양식 페이지인지 확인
                is_form_page = False
                for keyword in PDF_FORM_PAGE_KEYWORDS:
                    if keyword in text:
                        is_form_page = True
                        break

                if is_form_page:
                    form_pages.append(page_num)

            # 신청서/양식 페이지가 있으면 별도 PDF로 저장
            if form_pages:
                output_path = output_dir / f"{ann_id}_신청양식.pdf"
                form_doc = fitz.open()

                for page_num in form_pages:
                    form_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

                form_doc.save(output_path)
                form_doc.close()
                doc.close()

                self.logger.info(f"  신청양식 분리: {len(form_pages)}페이지 → {output_path.name}")
                return output_path

            doc.close()
            return None

        except Exception as e:
            self.logger.warning(f"  PDF 신청양식 분리 오류: {e}")
            return None

    def _extract_pptx(self, pptx_path: Path) -> str:
        """PPTX에서 텍스트 추출 (ZIP/XML 기반)"""
        try:
            text_parts = []
            with zipfile.ZipFile(pptx_path, 'r') as zf:
                namelist = zf.namelist()

                # ppt/slides/slide*.xml 에서 텍스트 추출
                slide_files = sorted([
                    name for name in namelist
                    if name.startswith('ppt/slides/slide') and name.endswith('.xml')
                ])

                for slide_file in slide_files:
                    try:
                        content = zf.read(slide_file).decode('utf-8')
                        root = ET.fromstring(content)

                        # DrawingML 네임스페이스의 텍스트 요소 추출
                        # a:t 태그 (텍스트 내용)
                        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                        for text_elem in root.findall('.//a:t', ns):
                            if text_elem.text and text_elem.text.strip():
                                text_parts.append(text_elem.text.strip())
                    except Exception as e:
                        self.logger.warning(f"  슬라이드 파싱 오류 ({slide_file}): {e}")
                        continue

            combined = ' '.join(text_parts)
            return re.sub(r'\s+', ' ', combined).strip()

        except Exception as e:
            self.logger.warning(f"  PPTX 추출 오류: {e}")
            return ""

    def _extract_ppt(self, ppt_path: Path) -> str:
        """PPT에서 텍스트 추출 (OLE Compound 기반)"""
        try:
            ole = olefile.OleFileIO(str(ppt_path))
            text_parts = []

            # PowerPoint Document 스트림에서 텍스트 추출
            if ole.exists('PowerPoint Document'):
                try:
                    ppt_stream = ole.openstream('PowerPoint Document').read()
                    # 텍스트 레코드 패턴 찾기 (간단한 방식)
                    # PPT 바이너리에서 유니코드 텍스트 추출
                    text = ppt_stream.decode('utf-16le', errors='ignore')
                    # 출력 가능한 문자만 필터링
                    text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t ')
                    if text.strip():
                        text_parts.append(text)
                except Exception as e:
                    self.logger.warning(f"  PPT Document 스트림 추출 오류: {e}")

            # Current User 등 다른 스트림에서도 텍스트 시도
            for entry in ole.listdir():
                entry_name = '/'.join(entry)
                if 'Text' in entry_name or 'text' in entry_name:
                    try:
                        stream_data = ole.openstream(entry).read()
                        text = stream_data.decode('utf-16le', errors='ignore')
                        text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t ')
                        if text.strip() and len(text) > 10:
                            text_parts.append(text)
                    except:
                        continue

            ole.close()
            combined = '\n'.join(text_parts)
            return re.sub(r'\s+', ' ', combined).strip()

        except Exception as e:
            self.logger.warning(f"  PPT 추출 오류: {e}")
            return ""

    def _extract_zip(self, zip_path: Path) -> str:
        """ZIP 파일 내부의 문서 파일들에서 텍스트 추출"""
        try:
            text_parts = []
            import tempfile

            with zipfile.ZipFile(zip_path, 'r') as zf:
                namelist = zf.namelist()
                self.logger.info(f"  ZIP 파일 내부 탐색: {len(namelist)}개 파일")

                for name in namelist:
                    name_lower = name.lower()
                    filename = Path(name).name

                    # 지원하는 파일 형식 확인
                    supported_extensions = ('.hwp', '.hwpx', '.ppt', '.pptx', '.pdf')
                    if not any(name_lower.endswith(ext) for ext in supported_extensions):
                        continue

                    # 신청서/양식 등 스킵
                    if _should_skip_file(filename):
                        self.logger.info(f"    스킵 (양식/서식): {filename}")
                        continue

                    try:
                        # 임시 파일로 추출
                        file_data = zf.read(name)
                        suffix = Path(name_lower).suffix
                        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                            tmp.write(file_data)
                            tmp_path = Path(tmp.name)

                        # 파일 타입에 따라 텍스트 추출
                        extracted_text = ""
                        if suffix == '.hwp':
                            extracted_text = self._extract_hwp(tmp_path)
                        elif suffix == '.hwpx':
                            extracted_text = self._extract_hwpx(tmp_path)
                        elif suffix == '.pptx':
                            extracted_text = self._extract_pptx(tmp_path)
                        elif suffix == '.ppt':
                            extracted_text = self._extract_ppt(tmp_path)
                        elif suffix == '.pdf':
                            extracted_text = self._extract_pdf(tmp_path)

                        if extracted_text:
                            text_parts.append(extracted_text)
                            self.logger.info(f"    추출 성공: {filename} ({len(extracted_text)}자)")

                        # 임시 파일 삭제
                        tmp_path.unlink(missing_ok=True)

                    except Exception as e:
                        self.logger.warning(f"  내부 파일 추출 실패 ({filename}): {e}")
                        continue

            return ' '.join(text_parts).strip()

        except Exception as e:
            self.logger.warning(f"  ZIP 추출 오류: {e}")
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

        # 토큰 사용량 누적
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0

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

            # 토큰 사용량 추출 및 로깅
            if response.usage:
                input_t = response.usage.prompt_tokens
                output_t = response.usage.completion_tokens
                total_t = response.usage.total_tokens
                cost = _calculate_cost("gpt-4o-mini", input_t, output_t)

                self.total_input_tokens += input_t
                self.total_output_tokens += output_t
                self.total_tokens += total_t
                self.total_cost += cost
                self.call_count += 1

                self.logger.info(
                    "  [토큰] 입력=%s / 출력=%s / 합계=%s / 비용=$%.6f",
                    f"{input_t:,}", f"{output_t:,}", f"{total_t:,}", cost,
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

    def log_total_usage(self) -> None:
        """토큰 사용량 총합 로깅"""
        if self.call_count == 0:
            return
        self.logger.info(
            "[토큰 총합] %d회 호출 / 입력=%s / 출력=%s / 합계=%s / 비용=$%.6f",
            self.call_count,
            f"{self.total_input_tokens:,}",
            f"{self.total_output_tokens:,}",
            f"{self.total_tokens:,}",
            self.total_cost,
        )


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
        self.downloader = FileDownloader(self.config, self.logger)
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
                    self.downloader.iter_files_bizinfo,
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
                    self.downloader.iter_files_kstartup,
                    source="kstartup"
                )
                self._save_results("kstartup", results["kstartup"], timestamp)

        self.logger.info("\n" + "=" * 60)
        self.logger.info("처리 완료!")
        self.logger.info(f"기업마당: {len(results['bizinfo'])}개, K-Startup: {len(results['kstartup'])}개")
        self.logger.info(f"결과 파일: {self.config.output_dir}")
        self.logger.info("=" * 60)

        self.analyzer.log_total_usage()

        return results

    def _is_info_complete(self, 지원대상: str, 제외대상: str, 지원금액: str, is_kstartup: bool) -> bool:
        """필요한 정보가 모두 추출되었는지 확인"""
        no_info = "정보 없음"

        if is_kstartup:
            # K-Startup: 지원대상은 API에서 가져오므로, 제외대상과 지원금액만 확인
            return 제외대상 != no_info and 지원금액 != no_info
        else:
            # 기업마당: 지원대상, 제외대상, 지원금액 모두 확인
            return 지원대상 != no_info and 제외대상 != no_info and 지원금액 != no_info

    def _merge_info(self, current: str, new: str) -> str:
        """정보 병합 - 새 정보가 유효하면 사용"""
        if new and new != "정보 없음":
            return new
        return current

    def _process_announcements(
        self,
        announcements: list[dict],
        iter_files_func: Callable,
        source: str = "bizinfo"
    ) -> list[dict]:
        """공고 목록 처리 (여러 파일 순회, 정보 완성 시 중단, 신청양식 분리)"""
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

            제외대상 = "정보 없음"
            지원금액 = "정보 없음"

            # 신청서/양식 파일 경로 저장 리스트
            form_files = []

            # 파일들을 순회하면서 정보 추출
            file_count = 0
            for file_path in iter_files_func(ann_id, ann, form_files):
                if not file_path or not file_path.exists():
                    continue

                file_count += 1

                # PDF인 경우 신청서/양식 페이지 분리 시도
                if file_path.suffix.lower() == '.pdf':
                    form_pdf_path = self.extractor.extract_form_pages_from_pdf(
                        file_path, self.config.forms_dir, ann_id
                    )
                    if form_pdf_path:
                        form_files.append(str(form_pdf_path))

                # 텍스트 추출
                text = self.extractor.extract(file_path)

                if text:
                    # OpenAI 분석 (K-Startup은 지원대상 제외)
                    extracted_info = self.analyzer.analyze(text, extract_target=not is_kstartup)

                    # 기업마당인 경우 지원대상도 LLM에서 추출
                    if not is_kstartup:
                        지원대상 = self._merge_info(지원대상, extracted_info.get("지원대상", ""))

                    제외대상 = self._merge_info(제외대상, extracted_info.get("제외대상", ""))
                    지원금액 = self._merge_info(지원금액, extracted_info.get("지원금액", ""))

                # 임시 파일 정리
                self._cleanup_temp_files(file_path)

                # 필요한 정보가 모두 추출되면 나머지 파일은 스킵
                if self._is_info_complete(지원대상, 제외대상, 지원금액, is_kstartup):
                    self.logger.info(f"  ✓ 정보 추출 완료 (파일 {file_count}개 처리)")
                    break

            if file_count == 0:
                self.logger.warning("  문서 파일 없음")

            # 신청양식 파일 로그
            if form_files:
                self.logger.info(f"  📋 신청양식 {len(form_files)}개 저장됨")

            # 결과 병합 (신청양식 파일 경로 포함)
            result = {
                **ann,
                "지원대상": 지원대상,
                "제외대상": 제외대상,
                "지원금액": 지원금액,
                "신청양식_파일": form_files,  # 신청서/양식 파일 경로 리스트
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
