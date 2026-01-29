"""
PDF 질의/회시 추출기 (템플릿 매칭 최적화 버전)
- OCR: 첫 페이지에서 마커 템플릿 1회만 추출
- OpenCV: 나머지 페이지는 템플릿 매칭 (10배 이상 빠름)
- pymupdf: 본문 텍스트 추출
- 출력: 표준화된 JSON 형식 (id, type, domain, content, metadata 등)
"""

import fitz  # pymupdf
import easyocr
import cv2
import numpy as np
from PIL import Image
import io
import re
import json
import pathlib
import bisect
from datetime import datetime
from typing import Optional


# ============================================================
# 설정 상수
# ============================================================
SCALE = 2.0  # 이미지 스케일 (해상도)
TEMPLATE_PADDING = 5  # 템플릿 크롭 시 여유 픽셀
MATCH_THRESHOLD = 0.85  # 템플릿 매칭 임계값 (0.0 ~ 1.0)
DUPLICATE_DISTANCE = 30  # 중복 마커 판정 거리 (px)
TITLE_DISTANCE = 100  # 마커 위 제목 탐색 거리 (px)
PAGE_OFFSET = 10000  # 전역 좌표 계산용 페이지 오프셋

# 문서 타입 상수
DOC_TYPE = "interpretation"
DOC_DOMAIN = "labor"
DOC_CATEGORY = "질의회시"


# ============================================================
# 이미지 변환 유틸리티
# ============================================================
def page_to_image(page, scale: float = SCALE) -> np.ndarray:
    """PDF 페이지를 numpy 배열로 변환"""
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return np.array(img)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """이미지를 그레이스케일로 변환"""
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return img


# ============================================================
# 파일명/메타데이터 파싱
# ============================================================
def extract_chapter_from_filename(filename: str) -> str:
    """
    파일명에서 장 번호 추출
    예: "근로기준법질의회시집(2018-2023)_1장.pdf" → "1"
    """
    match = re.search(r'_(\d+)장\.pdf$', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def parse_admin_info(text: str) -> tuple:
    """
    회시 텍스트에서 행정번호와 날짜 추출
    예: "(근로기준정책과-5076, 2018.8.1.)" → ("근로기준정책과-5076", "2018.8.1")
    예: "(임금근로시간과-309, 2019.5.24.)" → ("임금근로시간과-309", "2019.5.24")
    """
    # 패턴: (부서명-번호, YYYY.M.D.) 또는 (부서명-번호, YYYY.MM.DD.)
    # 부서명: 근로기준정책과, 임금근로시간과, 근로개선정책과 등 모든 한글
    pattern = r'\(([\가-\힣]+-\d+),\s*(\d{4}\.\d{1,2}\.\d{1,2})\.?\)'
    match = re.search(pattern, text)

    if match:
        admin_no = match.group(1)
        admin_date_raw = match.group(2)
        return admin_no, admin_date_raw

    return "", ""


# 행정번호 패턴 (회시 종료 판단용) - 모든 한글 부서명 지원
ADMIN_PATTERN = re.compile(r'\(([\가-\힣]+-\d+),\s*\d{4}\.\d{1,2}\.\d{1,2}\.?\)')


def find_admin_marker_in_text(text: str) -> bool:
    """텍스트에 행정번호 패턴이 포함되어 있는지 확인"""
    return bool(ADMIN_PATTERN.search(text))


def is_endpoint_line(text: str) -> bool:
    """
    텍스트가 엔드포인트 줄인지 확인
    - 행정번호 패턴이 있어야 함
    - 행정번호를 제외한 나머지 텍스트가 없거나 매우 짧아야 함 (공백, 괄호 등만 있는 경우)
    """
    if not find_admin_marker_in_text(text):
        return False
    
    # 행정번호 패턴 제거
    text_without_admin = ADMIN_PATTERN.sub('', text).strip()
    
    # 행정번호 제외하고 남은 텍스트가 10자 이하면 endpoint로 인정
    # (예: 빈 문자열, 괄호, 공백 등만 남은 경우)
    return len(text_without_admin) <= 10


def format_effective_date(date_raw: str) -> str:
    """
    날짜 문자열을 ISO 형식으로 변환
    예: "2018.8.1" → "2018-08-01"
    """
    if not date_raw:
        return ""

    try:
        parts = date_raw.split('.')
        if len(parts) == 3:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        pass

    return ""


def generate_id(admin_no: str, date_raw: str) -> str:
    """
    고유 ID 생성
    예: "INTERP_근로기준정책과-5076_20180801"
    """
    if not admin_no:
        # admin_no가 없으면 타임스탬프 기반 ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"INTERP_{timestamp}"

    # 날짜에서 점 제거
    date_compact = date_raw.replace('.', '') if date_raw else ""
    return f"INTERP_{admin_no}_{date_compact}"


# ============================================================
# 템플릿 추출 (OCR 1회)
# ============================================================
OCR_CHUNK_SIZE = 10  # 한 번에 OCR 스캔할 페이지 수


def extract_templates_once(reader, doc, start_page: int, end_page: int, scale: float = SCALE, debug: bool = False) -> dict:
    """
    PDF에서 '질의'/'회시' 마커 템플릿 이미지 추출
    - 10페이지씩 청크로 나눠서 탐색
    - 두 마커 모두 찾으면 즉시 종료
    - OCR은 이 함수에서만 사용됨
    """
    templates = {}
    total_pages = min(end_page, len(doc))

    # 10페이지씩 청크로 나눠서 탐색
    chunk_start = start_page - 1
    while chunk_start < total_pages:
        chunk_end = min(chunk_start + OCR_CHUNK_SIZE, total_pages)
        print(f"    페이지 {chunk_start + 1}~{chunk_end} OCR 스캔 중...")

        for page_num in range(chunk_start, chunk_end):
            page = doc[page_num]
            img_array = page_to_image(page, scale)

            # OCR 실행
            results = reader.readtext(img_array, detail=1)

            # 디버깅: OCR이 읽은 텍스트 출력
            if debug:
                texts_found = [r[1].strip() for r in results[:20]]
                print(f"      페이지 {page_num + 1} OCR 결과: {texts_found}")

            for bbox, text, conf in results:
                text = text.strip()
                if text in ['질의', '회시'] and text not in templates:
                    # bbox 좌표로 이미지 크롭
                    x1 = max(0, int(bbox[0][0]) - TEMPLATE_PADDING)
                    y1 = max(0, int(bbox[0][1]) - TEMPLATE_PADDING)
                    x2 = int(bbox[2][0]) + TEMPLATE_PADDING
                    y2 = int(bbox[2][1]) + TEMPLATE_PADDING

                    template_img = img_array[y1:y2, x1:x2]
                    templates[text] = {
                        'image': template_img,
                        'gray': to_grayscale(template_img),
                        'height': y2 - y1,
                        'width': x2 - x1
                    }
                    print(f"    템플릿 추출: '{text}' (페이지 {page_num + 1}, 크기: {template_img.shape[:2]})")

            # 두 마커 모두 찾으면 종료
            if '질의' in templates and '회시' in templates:
                print(f"    페이지 {page_num + 1}에서 템플릿 확보 완료")
                return templates

        # 다음 청크로
        chunk_start = chunk_end
        if '질의' not in templates or '회시' not in templates:
            print(f"    아직 못 찾음. 다음 10페이지 탐색...")

    return templates


# ============================================================
# 템플릿 매칭 (OCR 없이 빠름)
# ============================================================
def find_markers_by_template(
    img_array: np.ndarray,
    templates: dict,
    page_num: int,
    scale: float = SCALE,
    threshold: float = MATCH_THRESHOLD
) -> list:
    """
    템플릿 매칭으로 마커 위치 찾기
    - OCR 대비 10배 이상 빠름
    - 중복 위치 자동 제거
    """
    markers = []
    img_gray = to_grayscale(img_array)

    for marker_type, template_data in templates.items():
        template_gray = template_data['gray']

        # 템플릿 매칭 실행
        result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        # 중복 제거 (가까운 위치는 하나로)
        found_ys = []
        for pt in zip(*locations[::-1]):
            y = pt[1] / scale

            # 이미 찾은 위치와 DUPLICATE_DISTANCE 이내면 스킵
            if any(abs(y - fy) < DUPLICATE_DISTANCE for fy in found_ys):
                continue

            found_ys.append(y)
            markers.append({
                'type': marker_type,
                'page': page_num,
                'y': y,
                'global_y': page_num * PAGE_OFFSET + y
            })

    return markers


# ============================================================
# 텍스트 추출 (pymupdf)
# ============================================================
def get_text_blocks(page, page_num: int) -> list:
    """pymupdf로 텍스트 블록 추출 (전역 좌표 포함)"""
    blocks = page.get_text("dict")["blocks"]

    text_items = []
    for block in blocks:
        if block["type"] == 0:  # 텍스트 블록
            for line in block["lines"]:
                y = line["bbox"][1]
                text = " ".join(span["text"] for span in line["spans"])
                if text.strip():
                    text_items.append({
                        'text': text,
                        'page': page_num,
                        'y': y,
                        'global_y': page_num * PAGE_OFFSET + y
                    })

    return text_items


# ============================================================
# 장/절 헤더 이미지 기반 탐지 (점 패턴 템플릿 매칭 + pymupdf 텍스트 추출)
# ============================================================
SECTION_DOT_THRESHOLD = 0.80  # 점 패턴 매칭 임계값
GRAY_BAR_MIN = 160  # 회색 바 밝기 최소값
GRAY_BAR_MAX = 210  # 회색 바 밝기 최대값


def extract_dot_pattern_template(doc, start_page: int, end_page: int, scale: float = SCALE) -> Optional[dict]:
    """
    PDF에서 장/절 헤더의 점 패턴(18개 점) 템플릿 이미지 추출
    - 회색 배경 바 탐지 후 오른쪽 끝에서 점 패턴 크롭
    - OCR 없이 이미지 처리만 사용

    Returns:
        {'image': np.ndarray, 'gray': np.ndarray, 'height': int, 'width': int, 'bar_width': int} 또는 None
    """
    for page_num in range(start_page - 1, min(start_page + 5, end_page)):
        if page_num >= len(doc):
            continue

        page = doc[page_num]
        img_array = page_to_image(page, scale)
        img_gray = to_grayscale(img_array)

        # 회색 영역 탐지 (장/절 헤더 배경)
        gray_mask = cv2.inRange(img_gray, GRAY_BAR_MIN, GRAY_BAR_MAX)

        # 연결된 영역 찾기
        contours, _ = cv2.findContours(gray_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # 헤더 바 특성: 가로로 긴 직사각형 (너비 > 높이 * 5)
            if w > h * 5 and w > 300 * scale and 20 * scale < h < 80 * scale:
                # 오른쪽 끝 영역에서 점 패턴 크롭
                dot_x1 = max(0, x + w - int(80 * scale))
                dot_y1 = max(0, y)
                dot_x2 = x + w
                dot_y2 = y + h

                dot_template = img_array[dot_y1:dot_y2, dot_x1:dot_x2]

                if dot_template.size > 0:
                    print(f"    점 패턴 템플릿 추출: 페이지 {page_num + 1}, 크기 {dot_template.shape[:2]}")
                    return {
                        'image': dot_template,
                        'gray': to_grayscale(dot_template),
                        'height': dot_y2 - dot_y1,
                        'width': dot_x2 - dot_x1,
                        'bar_width': w,
                        'bar_height': h
                    }

    return None


def find_headers_by_dot_template(
    img_array: np.ndarray,
    dot_template: dict,
    page_num: int,
    scale: float = SCALE,
    threshold: float = SECTION_DOT_THRESHOLD
) -> list:
    """
    템플릿 매칭으로 장/절 헤더 점 패턴 위치 찾기

    Returns:
        [{'page': int, 'y': float, 'global_y': float, 'text_bbox': (x1, y1, x2, y2)}]
        text_bbox는 원본 PDF 좌표 (scale 적용 전)
    """
    headers = []
    img_gray = to_grayscale(img_array)
    template_gray = dot_template['gray']

    # 템플릿 매칭 실행
    result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    # 중복 제거
    found_ys = []
    for pt in zip(*locations[::-1]):
        x, y = pt
        y_orig = y / scale

        # 이미 찾은 위치와 가까우면 스킵
        if any(abs(y_orig - fy) < DUPLICATE_DISTANCE * 2 for fy in found_ys):
            continue

        found_ys.append(y_orig)

        # 텍스트 영역 bbox 계산 (점 패턴 왼쪽, 원본 PDF 좌표로 변환)
        bar_width = dot_template['bar_width']
        bar_height = dot_template['bar_height']

        # scale로 나눠서 원본 PDF 좌표로 변환
        text_x1 = max(0, (x - bar_width + dot_template['width']) / scale)
        text_y1 = y / scale
        text_x2 = x / scale
        text_y2 = (y + bar_height) / scale

        headers.append({
            'page': page_num,
            'y': y_orig,
            'global_y': page_num * PAGE_OFFSET + y_orig,
            'text_bbox': (text_x1, text_y1, text_x2, text_y2)  # 원본 PDF 좌표
        })

    return headers


def extract_text_from_bbox(page, bbox: tuple) -> str:
    """
    pymupdf로 지정된 bbox 영역에서 텍스트 추출 (OCR 없음)

    Args:
        page: fitz.Page 객체
        bbox: (x1, y1, x2, y2) 원본 PDF 좌표

    Returns:
        추출된 텍스트
    """
    x1, y1, x2, y2 = bbox
    rect = fitz.Rect(x1, y1, x2, y2)

    # 해당 영역의 텍스트 추출
    text = page.get_text("text", clip=rect).strip()

    # 여러 줄이면 공백으로 합치기
    text = ' '.join(text.split())

    return text


# ============================================================
# 장/절 구조 추출 (텍스트 기반 - 폴백용)
# ============================================================
def extract_chapter_structure(doc, start_page: int, end_page: int) -> dict:
    """
    PDF에서 장/절 구조 추출 (텍스트 기반 - 폴백용)
    반환: {global_y: {'type': 'chapter'|'section', 'number': '1', 'title': '총칙'}}
    """
    structure = {}

    chapter_pattern = r'^제\s*(\d+)\s*장\s+(.+)$'
    section_pattern = r'^(\d+)\s+([가-힣][가-힣\s]*)$'

    for page_num in range(start_page - 1, end_page):
        if page_num >= len(doc):
            continue

        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block["type"] == 0:
                for line in block["lines"]:
                    y = line["bbox"][1]
                    global_y = page_num * PAGE_OFFSET + y
                    text = " ".join(span["text"] for span in line["spans"]).strip()

                    chapter_match = re.match(chapter_pattern, text)
                    if chapter_match:
                        structure[global_y] = {
                            'type': 'chapter',
                            'number': chapter_match.group(1),
                            'title': chapter_match.group(2).strip()
                        }
                        continue

                    section_match = re.match(section_pattern, text)
                    if section_match and len(text) <= 20:
                        structure[global_y] = {
                            'type': 'section',
                            'number': section_match.group(1),
                            'title': section_match.group(2).strip()
                        }

    return structure


def find_current_chapter_section(structure: dict, marker_global_y: float) -> dict:
    """
    마커 위치 기준으로 현재 장/절 정보 반환
    """
    result = {
        'chapter': '',
        'chapter_title': '',
        'section': '',
        'section_title': ''
    }

    # global_y 기준 정렬
    sorted_positions = sorted(structure.keys())

    current_chapter = None
    current_section = None

    for pos in sorted_positions:
        if pos > marker_global_y:
            break

        item = structure[pos]
        if item['type'] == 'chapter':
            current_chapter = item
            current_section = None  # 새 장이면 절 초기화
        elif item['type'] == 'section':
            current_section = item

    if current_chapter:
        result['chapter'] = current_chapter['number']
        result['chapter_title'] = current_chapter['title']

    if current_section:
        result['section'] = current_section['number']
        result['section_title'] = current_section['title']

    return result


# ============================================================
# 헤더/푸터 필터링
# ============================================================
def is_header_footer(text: str) -> bool:
    """헤더/푸터 패턴 확인"""
    stripped = text.strip()

    patterns = [
        r'^제\s\d\s장\s[가-힣\s]+/\s*\d+$',  # "제 1 장 총칙 / 3", "제 2 장 근로 계약 / 15",  # "제 1 장 총칙 / 3"
        r'^\d+\s*/\s*근로기준법\s*질의회시집$',  # "4 / 근로기준법 질의회시집"
        r'^근로기준법\s*질의회시집$',  # "근로기준법 질의회시집"
        r'^[가-힣]+\s*/\s*\d+$',  # "총칙 / 11" (페이지 하단 표시)
    ]

    for pattern in patterns:
        if re.match(pattern, stripped):
            return True

    # 페이지 번호만
    if stripped.isdigit():
        return True

    return False


def clean_title(text: str) -> str:
    """제목에서 불필요한 문자 제거"""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()


# ============================================================
# 제목 추출
# ============================================================
def find_title_before_marker(
    text_items: list,
    marker_global_y: float,
    prev_marker_global_y: float = 0
) -> tuple:
    """마커 바로 위에 있는 제목 찾기"""
    title_candidates = []

    for item in text_items:
        if prev_marker_global_y < item['global_y'] < marker_global_y:
            if not is_header_footer(item['text']):
                title_candidates.append(item)

    if not title_candidates:
        return None, []

    # 마커에 가장 가까운 텍스트가 제목
    title_candidates.sort(key=lambda x: x['global_y'], reverse=True)

    # 마커와 TITLE_DISTANCE 이내의 텍스트를 제목으로
    title_items = []
    for item in title_candidates:
        if marker_global_y - item['global_y'] < TITLE_DISTANCE:
            title_items.insert(0, item)
        else:
            break

    if title_items:
        title_text = ' '.join(item['text'].strip() for item in title_items)
        title_text = clean_title(title_text)
        return title_text, [item['global_y'] for item in title_items]

    return None, []


# ============================================================
# 메인 추출 함수
# ============================================================
def extract_qa_from_pdf(
    pdf_path: str,
    start_page: int,
    end_page: int,
    output_path: str,
    use_gpu: bool = False
) -> Optional[list]:
    """
    PDF에서 질의/회시 섹션 추출 (템플릿 매칭 최적화)

    Args:
        pdf_path: PDF 파일 경로
        start_page: 시작 페이지 (1-indexed), 0이면 전체
        end_page: 종료 페이지 (1-indexed), 0이면 전체
        output_path: 출력 JSON 파일 경로
        use_gpu: EasyOCR GPU 사용 여부

    Returns:
        추출된 QA 리스트 또는 None (실패 시)
    """
    print("=" * 60)
    print("PDF 질의/회시 추출기 (템플릿 매칭 최적화)")
    print("=" * 60)
    print(f"PDF: {pdf_path}")
    print(f"Pages: {start_page} ~ {end_page}")
    print()

    # PDF 파일명 추출
    pdf_filename = pathlib.Path(pdf_path).name
    chapter_from_filename = extract_chapter_from_filename(pdf_filename)
    print(f"파일명에서 추출한 장 번호: {chapter_from_filename or '(없음)'}")

    # PDF 열기
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"ERROR: PDF 파일을 열 수 없습니다 - {e}")
        return None

    # start_page, end_page 둘 다 0이면 전체 페이지
    if start_page == 0 and end_page == 0:
        start_page = 1
        end_page = len(doc)
        print(f"전체 페이지 처리: 1 ~ {end_page}")
        print()

    # ===== 0단계: 장/절 구조 초기화 =====
    print("[0단계] 장/절 구조 초기화")
    chapter_structure = {}
    print()

    # ===== 1단계: 템플릿 추출 (OCR 1회 + 점 패턴) =====
    print("[1단계] 템플릿 추출")
    print(f"  EasyOCR 초기화 중 (GPU: {use_gpu})...")
    reader = easyocr.Reader(['ko'], gpu=use_gpu, verbose=False)

    # 질의/회시 템플릿 추출 (OCR) - 최대 5페이지만 스캔
    # debug=True로 변경하면 OCR 결과 확인 가능
    templates = extract_templates_once(reader, doc, start_page, end_page, debug=False)

    # OCR reader 해제
    del reader

    # 절 헤더 점 패턴 템플릿 추출 (OCR 없음)
    print("  절 점 패턴 템플릿 탐색 중...")
    dot_template = extract_dot_pattern_template(doc, start_page, end_page, SCALE)

    if '질의' not in templates or '회시' not in templates:
        print("ERROR: 템플릿을 찾을 수 없습니다.")
        print(f"  찾은 템플릿: {list(templates.keys())}")
        doc.close()
        return None

    print()

    # ===== 2단계: 전체 페이지에서 마커 + 장/절 헤더 + 텍스트 수집 (한 번에) =====
    print("[2단계] 템플릿 매칭 (마커 + 장/절 헤더)")
    all_markers = []
    all_text_items = []
    chapter_pattern = re.compile(r'^제\s*(\d+)\s*장\s+(.+)$')

    for page_num in range(start_page - 1, end_page):
        if page_num >= len(doc):
            continue

        page = doc[page_num]
        img_array = page_to_image(page, SCALE)

        # 질의/회시 마커 템플릿 매칭
        markers = find_markers_by_template(img_array, templates, page_num)
        all_markers.extend(markers)

        # 절 헤더 템플릿 매칭 (dot_template이 있으면)
        if dot_template:
            section_headers = find_headers_by_dot_template(img_array, dot_template, page_num, SCALE)
            for header in section_headers:
                text = extract_text_from_bbox(page, header['text_bbox'])
                section_match = re.match(r'^(\d+)\s+(.+)$', text)
                if section_match:
                    chapter_structure[header['global_y']] = {
                        'type': 'section',
                        'number': section_match.group(1),
                        'title': section_match.group(2).strip()
                    }

        # 텍스트 추출 (pymupdf) + 장 헤더 탐색
        text_items = get_text_blocks(page, page_num)
        all_text_items.extend(text_items)

        # 장 헤더 탐색: "제N장" 패턴 찾고, 같은 y좌표 근처 텍스트를 title로
        chapter_number_pattern = re.compile(r'^제\s*(\d+)\s*장$')

        for item in text_items:
            text = item['text'].strip()

            # 헤더/푸터는 스킵
            if is_header_footer(text):
                continue

            # "제N장" 패턴 (title 없이 장 번호만)
            chapter_num_match = chapter_number_pattern.match(text)
            if chapter_num_match:
                chapter_num = chapter_num_match.group(1)
                chapter_y = item['global_y']

                # 같은 y좌표 근처(±50)에서 title 찾기
                title = ""
                for other_item in text_items:
                    if other_item['global_y'] == chapter_y:
                        continue
                    # y좌표 차이가 50 이내이고, 헤더/푸터 아니고, 한글로 시작
                    y_diff = abs(other_item['global_y'] - chapter_y)
                    other_text = other_item['text'].strip()
                    if y_diff < 50 and not is_header_footer(other_text):
                        if re.match(r'^[가-힣]', other_text) and '/' not in other_text:
                            # 띄어쓰기 정리 ("총 칙" -> "총칙")
                            title = other_text.replace(' ', '')
                            break

                if title:
                    chapter_structure[item['global_y']] = {
                        'type': 'chapter',
                        'number': chapter_num,
                        'title': title
                    }
                    print(f"  페이지 {page_num + 1}: 장 발견 - 제{chapter_num}장 {title}")

            # 기존 패턴도 유지 ("제1장 총칙" 한 줄로 된 경우)
            elif chapter_pattern.match(text):
                match = chapter_pattern.match(text)
                title = match.group(2).strip()
                if '/' not in title:
                    chapter_structure[item['global_y']] = {
                        'type': 'chapter',
                        'number': match.group(1),
                        'title': title.replace(' ', '')
                    }
                    print(f"  페이지 {page_num + 1}: 장 발견 - 제{match.group(1)}장 {title}")

        marker_info = [m['type'] for m in markers]
        print(f"  페이지 {page_num + 1}: {len(markers)}개 마커 {marker_info}")

    doc.close()
    chapter_count = len([v for v in chapter_structure.values() if v['type'] == 'chapter'])
    section_count = len([v for v in chapter_structure.values() if v['type'] == 'section'])
    print(f"  발견된 장: {chapter_count}개, 절: {section_count}개")

    # ===== 3단계: 전역 좌표로 정렬 =====
    all_markers.sort(key=lambda x: x['global_y'])
    all_text_items.sort(key=lambda x: x['global_y'])

    print()
    print(f"총 마커: {len(all_markers)}개")
    print(f"총 텍스트 블록: {len(all_text_items)}개")
    print()

    # ===== 3단계: 제목 위치 수집 =====
    print("[3단계] 제목 추출")
    marker_titles = {}
    marker_chapter_info = {}
    all_title_ys = set()

    for i, marker in enumerate(all_markers):
        if marker['type'] == '질의':
            prev_marker_y = all_markers[i - 1]['global_y'] if i > 0 else 0
            title, title_ys = find_title_before_marker(
                all_text_items, marker['global_y'], prev_marker_y
            )
            marker_titles[i] = title
            all_title_ys.update(title_ys)

            # 장/절 정보
            chapter_info = find_current_chapter_section(chapter_structure, marker['global_y'])
            # 파일명에서 추출한 장 번호로 오버라이드 (있으면)
            if chapter_from_filename:
                chapter_info['chapter'] = chapter_from_filename
            marker_chapter_info[i] = chapter_info

            if title:
                title_preview = title[:40] + '...' if len(title) > 40 else title
                print(f"  마커 {i + 1}: {title_preview}")

    print()

    # ===== 4단계: 엔드포인트(행정번호) 위치 수집 =====
    print("[4단계] 엔드포인트 수집")
    all_endpoints = []  # 행정번호 패턴이 있는 텍스트 위치
    
    # 회시 마커의 global_y 리스트 생성
    hoesi_marker_ys = [m['global_y'] for m in all_markers if m['type'] == '회시']
    jilui_marker_ys = [m['global_y'] for m in all_markers if m['type'] == '질의']
    
    for item in all_text_items:
        # 해당 줄에 행정번호만 있는지 확인
        if not is_endpoint_line(item['text']):
            continue
        
        item_y = item['global_y']
        
        # 이 행정번호가 회시 마커 이후에 있는지 확인
        # 가장 가까운 이전 회시 마커를 찾기
        closest_hoesi_y = None
        for hoesi_y in hoesi_marker_ys:
            if hoesi_y < item_y:
                if closest_hoesi_y is None or hoesi_y > closest_hoesi_y:
                    closest_hoesi_y = hoesi_y
        
        # 회시 마커 이후가 아니면 스킵
        if closest_hoesi_y is None:
            continue
        
        # 이 행정번호와 다음 질의 마커 사이에 회시 마커가 있는지 확인
        # (즉, 이 행정번호가 회시의 끝인지 확인)
        next_jilui_y = None
        for jilui_y in jilui_marker_ys:
            if jilui_y > item_y:
                next_jilui_y = jilui_y
                break
        
        # 이 행정번호와 다음 질의 사이에 또 다른 회시 마커가 있으면 스킵
        # (본문 중간에 인용된 행정번호)
        has_hoesi_between = False
        if next_jilui_y:
            for hoesi_y in hoesi_marker_ys:
                if item_y < hoesi_y < next_jilui_y:
                    has_hoesi_between = True
                    break
        
        if has_hoesi_between:
            continue
        
        # 조건을 모두 만족하면 endpoint로 추가
        all_endpoints.append({
            'global_y': item['global_y'],
            'text': item['text'],
            'page': item['page']
        })
    
    print(f"  발견된 엔드포인트: {len(all_endpoints)}개")

    # 마커 global_y 세트 (빠른 조회용)
    marker_global_ys = {m['global_y'] for m in all_markers}

    # ===== 5단계: 섹션 구성 (엔드포인트 기반) =====
    print("[5단계] 섹션 구성")
    sections = []

    # 이진 탐색용 global_y 리스트 추출
    text_global_ys = [item['global_y'] for item in all_text_items]

    for i, marker in enumerate(all_markers):
        start_global_y = marker['global_y']
        end_global_y = all_markers[i + 1]['global_y'] if i + 1 < len(all_markers) else float('inf')

        # 이진 탐색으로 범위 내 텍스트 인덱스 찾기
        start_idx = bisect.bisect_right(text_global_ys, start_global_y)
        end_idx = bisect.bisect_left(text_global_ys, end_global_y)

        # 해당 구간의 텍스트 수집 (제목 및 헤더/푸터 제외)
        content = []
        for idx in range(start_idx, end_idx):
            item = all_text_items[idx]
            if item['global_y'] not in all_title_ys:
                if not is_header_footer(item['text']):
                    content.append(item['text'])
                    # 회시 마커인 경우, 행정번호 패턴에서 종료
                    if marker['type'] == '회시' and find_admin_marker_in_text(item['text']):
                        break

        sections.append({
            'marker_index': i,
            'title': marker_titles.get(i),
            'chapter_info': marker_chapter_info.get(i, {}),
            'type': marker['type'],
            'content': content
        })
        
    # ===== 6단계: JSON 생성 =====
    print("[6단계] JSON 생성")
    qa_list = []
    current_item = None
    collected_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 질의/회시 항목 처리
    for section in sections:
        if section['type'] == '질의':
            # 이전 항목 저장
            if current_item and current_item.get('_question'):
                qa_list.append(build_qa_item(current_item, pdf_filename, collected_at))

            # 새 항목 시작
            current_item = {
                'title': section['title'] or '',
                'chapter_info': section['chapter_info'],
                '_question': '\n'.join(section['content']),
                '_answer': ''
            }
        elif section['type'] == '회시' and current_item:
            current_item['_answer'] = '\n'.join(section['content'])

    # 마지막 항목 저장
    if current_item and current_item.get('_question'):
        qa_list.append(build_qa_item(current_item, pdf_filename, collected_at))

    # 마커 없는 구간 (extra_sections) 처리
    for extra in extra_sections:
        extra_item = build_extra_item(extra, pdf_filename, collected_at)
        qa_list.append(extra_item)

    # 파일 저장
    output_file = pathlib.Path(output_path)
    output_file.write_text(
        json.dumps(qa_list, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print("=" * 60)
    print(f"완료! 총 {len(qa_list)}개 QA 항목 추출")
    print("=" * 60)

    for i, item in enumerate(qa_list):
        title_info = item['title'][:35] + '...' if len(item['title']) > 35 else item['title']
        print(f"  {i + 1}. [{item['id']}] {title_info}")

    print()
    print(f"출력 파일: {output_path}")
    print(f"파일 크기: {output_file.stat().st_size:,} bytes")

    return qa_list


def build_qa_item(raw_item: dict, pdf_filename: str, collected_at: str) -> dict:
    """
    질의/회시 내부 형식을 최종 JSON 형식으로 변환
    """
    question = raw_item['_question']
    answer = raw_item['_answer']
    chapter_info = raw_item.get('chapter_info', {})

    # 회시에서 행정번호/날짜 추출
    admin_no, admin_date_raw = parse_admin_info(answer)

    # content 조합 (질의/회시)
    content = f"질의 : {question}\n\n회시 : {answer}"

    # effective_date 변환
    effective_date = format_effective_date(admin_date_raw)

    # ID 생성
    doc_id = generate_id(admin_no, admin_date_raw)

    return {
        "id": doc_id,
        "type": DOC_TYPE,
        "domain": DOC_DOMAIN,
        "title": raw_item['title'],
        "content": content,
        "source": {
            "name": pdf_filename,
            "url": "",
            "collected_at": collected_at
        },
        "effective_date": effective_date,
        "metadata": {
            "category": DOC_CATEGORY,
            "chapter": chapter_info.get('chapter', ''),
            "chapter_title": chapter_info.get('chapter_title', ''),
            "section": chapter_info.get('section', ''),
            "section_title": chapter_info.get('section_title', ''),
            "admin_no": admin_no,
            "admin_date_raw": admin_date_raw
        }
    }


def build_extra_item(extra: dict, pdf_filename: str, collected_at: str) -> dict:
    """
    마커 없는 구간(엔드포인트 사이)을 최종 JSON 형식으로 변환
    """
    chapter_info = extra.get('chapter_info', {})
    admin_no = extra.get('admin_no', '')
    admin_date_raw = extra.get('admin_date_raw', '')

    # effective_date 변환
    effective_date = format_effective_date(admin_date_raw)

    # ID 생성
    doc_id = generate_id(admin_no, admin_date_raw)

    return {
        "id": doc_id,
        "type": DOC_TYPE,
        "domain": DOC_DOMAIN,
        "title": extra['title'],
        "content": f"내용 : {extra['content']}",
        "source": {
            "name": pdf_filename,
            "url": "",
            "collected_at": collected_at
        },
        "effective_date": effective_date,
        "metadata": {
            "category": DOC_CATEGORY,
            "chapter": chapter_info.get('chapter', ''),
            "chapter_title": chapter_info.get('chapter_title', ''),
            "section": chapter_info.get('section', ''),
            "section_title": chapter_info.get('section_title', ''),
            "admin_no": admin_no,
            "admin_date_raw": admin_date_raw
        }
    }


# ============================================================
# 결과 예시
# ============================================================
# 1. 기본 질의/회시 항목
# {
#     "id": "INTERP_근로기준정책과-5076_201881",
#     "type": "interpretation",
#     "domain": "labor",
#     "title": "실무수습 중인 공인노무사의 근로자성 여부",
#     "content": "질의 : ...\n\n회시 : ...(근로기준정책과-5076, 2018.8.1.)",
#     "source": {
#         "name": "근로기준법질의회시집(2018-2023)_1장.pdf",
#         "url": "",
#         "collected_at": "2026-01-27T21:56:55"
#     },
#     "effective_date": "2018-08-01",
#     "metadata": {
#         "category": "질의회시",
#         "chapter": "1",
#         "chapter_title": "총칙",
#         "section": "2",
#         "section_title": "근로자",
#         "admin_no": "근로기준정책과-5076",
#         "admin_date_raw": "2018.8.1"
#     }
# }
#
# 2. 추가 내용 항목 (회시 종료 후 ~ 다음 질의 사이 텍스트가 있는 경우)
# {
#     "id": "INTERP_근로기준정책과-5076_201881_extra",
#     "type": "interpretation",
#     "domain": "labor",
#     "title": "실무수습 중인 공인노무사의 근로자성 여부 (추가)",
#     "content": "내용 : 추가 설명 텍스트...",
#     "source": { ... },
#     "effective_date": "2018-08-01",
#     "metadata": {
#         "category": "질의회시",
#         ...
#     }
# }


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    # 설정
    PDF_FILE = "근로기준법 질의회시집(2018.4.~2023.6.).pdf"
    OUTPUT_FILE = "근로기준법_질의회시_추출_total.json"
    START_PAGE = 22  # 0, 0 이면 전체 페이지
    END_PAGE = 615

    # 실행
    result = extract_qa_from_pdf(
        pdf_path=PDF_FILE,
        start_page=START_PAGE,
        end_page=END_PAGE,
        output_path=OUTPUT_FILE,
        use_gpu=False
    )

    if result is None:
        print("\n추출 실패")
        exit(1)
