"""
PDF 키워드 기반 섹션 추출 스크립트
- 대상: kstartup-pdf 폴더의 PDF 파일들
- 추출: 지원대상/제외대상 관련 키워드 섹션
- 출력: JSON 파일
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF가 필요합니다: pip install pymupdf")
    exit(1)


# ============================================================
# 설정
# ============================================================

# 지원 대상 관련 키워드 (우선순위순)
# 공백 없이 정의 - 비교 시 텍스트의 공백도 제거하여 매칭
POSITIVE_KEYWORDS = [
    '지원대상', '신청자격', '모집대상', '참여자격', '자격요건',
    '신청대상', '입주자격', '참가자격', '응모자격', '지원요건',
    '신청요건', '입주대상', '선정대상', '수혜대상', '적용대상',
    '참여가능대상', '대상기관', '대상업체', '신청범위', '지원범위',
    '대상및자격', '선발대상'
]

# 제외/제한 대상 관련 키워드 (우선순위순)
# 공백 없이 정의 - 비교 시 텍스트의 공백도 제거하여 매칭
NEGATIVE_KEYWORDS = [
    '참여제한', '제외대상', '지원제외', '신청제한', '결격사유',
    '신청제외', '제한사항', '지원제외대상', '신청불가대상',
    '제외요건', '부적격자', '제외기업', '제한기업',
    '배제대상', '불참대상', '제재대상', '부정당업자',
    '중복지원제한', '미달요건', '배제요건', '지원불가', '자격미달', '사업대상제외자'
]

# 섹션 구분 패턴
SECTION_PATTERNS = [
    r'^□\s*',                          # □ 로 시작
    r'^\d+\s+[가-힣]',                  # 숫자 + 한글 (예: "3 신청자격")
    r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*',          # 원문자로 시작
    r'^<[^>]+>',                        # <참고: ...> 형태
    r'^\[\s*[가-힣]+\s*\]',             # [참고] 형태
    r'^[가-힣]+\s*:\s*$',               # "지원대상:" 형태
]


# ============================================================
# 데이터 클래스
# ============================================================

@dataclass
class ExtractedSection:
    """추출된 섹션 정보"""
    keyword: str
    keyword_type: str  # 'positive' or 'negative'
    content: str
    page_start: int
    page_end: int


@dataclass
class PDFResult:
    """PDF 처리 결과"""
    filename: str
    filepath: str
    total_pages: int
    total_chars: int
    sections: List[Dict]
    keywords_found: List[str]
    has_positive: bool
    has_negative: bool


# ============================================================
# 텍스트 추출
# ============================================================

def extract_text_from_pdf(pdf_path: Path) -> Tuple[str, List[Tuple[int, str]]]:
    """
    PDF에서 텍스트 추출

    Returns:
        Tuple[str, List[Tuple[int, str]]]: (전체 텍스트, [(페이지번호, 페이지텍스트), ...])
    """
    pages_text = []
    full_text = ""

    try:
        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, 1):
                text = page.get_text("text")
                pages_text.append((page_num, text))
                full_text += f"\n\n--- PAGE {page_num} ---\n\n{text}"
    except Exception as e:
        print(f"  [오류] PDF 읽기 실패: {e}")
        return "", []

    return full_text, pages_text


def clean_extracted_text(text: str) -> str:
    """추출된 텍스트 정제"""
    # 연속 공백 제거
    text = re.sub(r'[ \t]+', ' ', text)
    # 연속 줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 줄 앞뒤 공백 제거
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


# ============================================================
# 섹션 추출
# ============================================================

def make_space_flexible_pattern(keyword: str) -> str:
    """
    키워드를 공백 유연 패턴으로 변환
    예: "지원대상" -> "지\\s*원\\s*대\\s*상"
    """
    chars = list(keyword)
    return r'\s*'.join(re.escape(c) for c in chars)


def find_keyword_positions(text: str, keywords: List[str]) -> List[Tuple[str, int, int]]:
    """
    텍스트에서 키워드 위치 찾기 (공백 유연 매칭)

    Returns:
        List[Tuple[str, int, int]]: [(키워드, 시작위치, 끝위치), ...]
    """
    positions = []

    for keyword in keywords:
        # 키워드를 공백 유연 패턴으로 변환
        kw_pattern = make_space_flexible_pattern(keyword)

        # 다양한 패턴으로 검색
        patterns = [
            rf'□\s*{kw_pattern}',           # □ 지원대상
            rf'[◦◯•]\s*{kw_pattern}',       # ◦ 지원대상
            rf'\d+\.\s*{kw_pattern}',        # 1. 지원대상
            rf'<[^>]*{kw_pattern}[^>]*>',    # <참고: 지원 제외 대상>
            rf'\[\s*{kw_pattern}\s*\]',      # [지원대상]
            rf'\(\s*{kw_pattern}\s*\)',      # (지원대상)
            rf'{kw_pattern}\s*[:：]',        # 지원대상:
            rf'{kw_pattern}\s*\n',           # 지원대상 (줄 끝)
            rf'(?<=[□◦◯•\s]){kw_pattern}',  # 앞에 기호가 있는 경우
            rf'(?<=[\(]){kw_pattern}',       # 괄호 안의 키워드
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                positions.append((keyword, match.start(), match.end()))

    # 위치순 정렬, 중복 제거
    positions = list(set(positions))
    positions.sort(key=lambda x: x[1])

    return positions


def find_section_end(text: str, start_pos: int, max_length: int = 5000) -> int:
    """
    섹션 끝 위치 찾기
    - 다음 주요 섹션 시작점까지
    - 또는 최대 길이까지
    """
    search_text = text[start_pos:start_pos + max_length]

    # 다음 섹션 시작 패턴
    end_patterns = [
        r'\n□\s*[가-힣]',                # 다음 □ 섹션
        r'\n\d+\s+[가-힣]{2,}',           # 다음 숫자 섹션 (예: "4 접수방법")
        r'\n<[가-힣]+\s*[:：]',           # <참고: 형태
        r'\n---\s*PAGE\s*\d+',            # 페이지 구분
    ]

    min_end = len(search_text)

    for pattern in end_patterns:
        match = re.search(pattern, search_text[100:])  # 최소 100자 이후부터 검색
        if match:
            end_pos = match.start() + 100
            if end_pos < min_end:
                min_end = end_pos

    return start_pos + min_end


def get_page_number(pages_text: List[Tuple[int, str]], char_position: int, full_text: str) -> int:
    """문자 위치로 페이지 번호 찾기"""
    current_pos = 0
    for page_num, page_text in pages_text:
        page_marker = f"\n\n--- PAGE {page_num} ---\n\n"
        marker_pos = full_text.find(page_marker)
        if marker_pos != -1 and marker_pos <= char_position:
            current_pos = marker_pos
        else:
            break

    for page_num, _ in pages_text:
        page_marker = f"--- PAGE {page_num} ---"
        if page_marker in full_text[:char_position + 500]:
            return page_num

    return 1


def remove_duplicate_sections(sections: List[ExtractedSection]) -> List[ExtractedSection]:
    """중복 섹션 제거 (내용 + 키워드 타입 기준)"""
    seen_contents = set()
    unique_sections = []

    for section in sections:
        # 내용의 앞 200자 + 키워드 타입을 기준으로 중복 판단
        content_key = (section.keyword_type, section.content[:200].strip())

        if content_key not in seen_contents:
            seen_contents.add(content_key)
            unique_sections.append(section)

    return unique_sections


def extract_sections(
    text: str,
    pages_text: List[Tuple[int, str]],
    vrf_str : str = 'k'
) -> List[ExtractedSection]:
    """키워드 기반 섹션 추출"""
    sections = []
    positive_found_positions = set()  # 긍정 키워드 위치
    negative_found_positions = set()  # 부정 키워드 위치 (별도 관리)

    # 긍정 키워드 검색
    if vrf_str == 'b' :
        positive_positions = find_keyword_positions(text, POSITIVE_KEYWORDS)
        for keyword, start, _ in positive_positions:
            # 근접 위치 중복 방지 (±50자 이내) - 긍정 키워드 내에서만
            if any(abs(start - pos) < 50 for pos in positive_found_positions):
                continue
            positive_found_positions.add(start)

            # 섹션 시작점 (키워드 포함 줄의 시작)
            line_start = text.rfind('\n', 0, start) + 1
            section_end = find_section_end(text, line_start)

            content = text[line_start:section_end]
            content = clean_extracted_text(content)

            if len(content) > 50:  # 최소 50자 이상만
                page_start = get_page_number(pages_text, line_start, text)
                page_end = get_page_number(pages_text, section_end, text)

                sections.append(ExtractedSection(
                    keyword=keyword,
                    keyword_type='positive',
                    content=content,
                    page_start=page_start,
                    page_end=page_end
                ))

    # 부정 키워드 검색

    negative_positions = find_keyword_positions(text, NEGATIVE_KEYWORDS)
    for keyword, start, _ in negative_positions:
        # 근접 위치 중복 방지 (±50자 이내) - 부정 키워드 내에서만
        if any(abs(start - pos) < 50 for pos in negative_found_positions):
            continue
        negative_found_positions.add(start)

        line_start = text.rfind('\n', 0, start) + 1
        section_end = find_section_end(text, line_start)

        content = text[line_start:section_end]
        content = clean_extracted_text(content)

        if len(content) > 50:
            page_start = get_page_number(pages_text, line_start, text)
            page_end = get_page_number(pages_text, section_end, text)

            sections.append(ExtractedSection(
                keyword=keyword,
                keyword_type='negative',
                content=content,
                page_start=page_start,
                page_end=page_end
            ))

    # 위치순 정렬 (positive를 먼저 처리하도록 역순 정렬)
    sections.sort(key=lambda x: (x.page_start, x.keyword_type), reverse=False)
    # keyword_type: 'negative' < 'positive' 이므로 positive가 뒤에 옴
    # 따라서 positive를 먼저 처리하려면 별도 정렬 필요
    sections.sort(key=lambda x: (x.page_start, 0 if x.keyword_type == 'positive' else 1))

    # 내용 기준 중복 제거
    sections = remove_duplicate_sections(sections)

    return sections


# ============================================================
# 메인 처리
# ============================================================

def process_pdf(pdf_path: Path) -> Optional[PDFResult]:
    """단일 PDF 처리"""
    full_text, pages_text = extract_text_from_pdf(pdf_path)

    if not full_text:
        return None

    # 섹션 추출
    sections = extract_sections(full_text, pages_text, vrf_str='b')

    # 결과 생성
    keywords_found = list(set(s.keyword for s in sections))
    has_positive = any(s.keyword_type == 'positive' for s in sections)
    has_negative = any(s.keyword_type == 'negative' for s in sections)

    return PDFResult(
        filename=pdf_path.name,
        filepath=str(pdf_path),
        total_pages=len(pages_text),
        total_chars=len(full_text),
        sections=[asdict(s) for s in sections],
        keywords_found=keywords_found,
        has_positive=has_positive,
        has_negative=has_negative
    )


def process_directory(
    input_dir: Path,
    output_path: Path,
    skip_no_keywords: bool = True
) -> Dict:
    """디렉토리 내 모든 PDF 처리"""

    pdf_files = list(input_dir.glob('*.pdf'))

    print("=" * 60)
    print("PDF 키워드 섹션 추출")
    print("=" * 60)
    print(f"입력 폴더: {input_dir}")
    print(f"PDF 파일 수: {len(pdf_files)}개")
    print(f"출력 파일: {output_path}")
    print("=" * 60)

    results = []
    stats = {
        'total': len(pdf_files),
        'processed': 0,
        'with_keywords': 0,
        'with_positive': 0,
        'with_negative': 0,
        'skipped': 0,
        'failed': 0
    }

    for i, pdf_path in enumerate(pdf_files, 1):
        safe_name = pdf_path.name[:50].encode('cp949', errors='replace').decode('cp949')
        print(f"\n[{i}/{len(pdf_files)}] {safe_name}...")

        try:
            result = process_pdf(pdf_path)

            if result is None:
                stats['failed'] += 1
                print("  [실패] 텍스트 추출 불가")
                continue

            stats['processed'] += 1

            if result.sections:
                stats['with_keywords'] += 1
                if result.has_positive:
                    stats['with_positive'] += 1
                if result.has_negative:
                    stats['with_negative'] += 1

                results.append(asdict(result))
                print(f"  [성공] 섹션 {len(result.sections)}개 추출")
                print(f"         키워드: {', '.join(result.keywords_found)}")
            else:
                if skip_no_keywords:
                    stats['skipped'] += 1
                    print("  [스킵] 키워드 없음")
                else:
                    results.append(asdict(result))
                    print("  [완료] 키워드 없음")

        except Exception as e:
            stats['failed'] += 1
            print(f"  [오류] {e}")

    # JSON 저장
    output_data = {
        'metadata': {
            'input_directory': str(input_dir),
            'total_files': stats['total'],
            'processed_files': stats['processed'],
            'files_with_keywords': stats['with_keywords'],
            'positive_keywords': POSITIVE_KEYWORDS,
            'negative_keywords': NEGATIVE_KEYWORDS
        },
        'statistics': stats,
        'results': results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 결과 출력
    print("\n" + "=" * 60)
    print("처리 완료")
    print("=" * 60)
    print(f"총 파일: {stats['total']}개")
    print(f"처리 성공: {stats['processed']}개")
    print(f"키워드 발견: {stats['with_keywords']}개")
    print(f"  - 지원대상 키워드: {stats['with_positive']}개")
    print(f"  - 제외대상 키워드: {stats['with_negative']}개")
    print(f"스킵 (키워드 없음): {stats['skipped']}개")
    print(f"실패: {stats['failed']}개")
    print(f"\n출력 파일: {output_path}")
    print(f"파일 크기: {output_path.stat().st_size / 1024:.1f} KB")

    return stats


def main():
    """메인 실행 함수"""
    input_dir = Path("D:/f.pp/bizinfo-pdf")
    output_path = Path("D:/f.pp/bizinfo-pdf/extracted_sections.json")

    if not input_dir.exists():
        print(f"[오류] 폴더 없음: {input_dir}")
        return

    process_directory(input_dir, output_path, skip_no_keywords=True)


if __name__ == "__main__":
    main()
