"""
PDF 전처리기 (통일 스키마 적용 + 법령 바인딩)

data_pipeline.md / happy-tinkering-toucan.md 기반
- 청킹 없음 (RAG 시스템에서 처리)
- 통일 스키마 출력 (id, type, domain, title, content, source, related_laws, metadata)
- JSONL 출력
- law_lookup.json 기반 현행법 바인딩

구조:
- 대단원 (장): "1장 세법 상 중소기업의 범위"
- 중단원 (로마자): "I. 창업단계 지원내용"
- 소단원 (번호): "01. 개요"
"""

import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime


# ============================================================================
# 통일 스키마 데이터 클래스
# ============================================================================

@dataclass
class Source:
    """데이터 출처"""
    name: str
    url: Optional[str] = None
    collected_at: Optional[str] = None


@dataclass
class RelatedLaw:
    """관련 법령 참조"""
    law_id: Optional[str] = None
    law_name: str = ""
    article_ref: Optional[str] = None


@dataclass
class PDFMetadata:
    """PDF 문서 메타데이터"""
    filename: str
    total_pages: int
    section_type: str  # "large", "medium", "small"
    section_num: str
    page_start: int
    page_end: int
    parent_section: Optional[str] = None
    law_ref_count: int = 0
    bound_law_count: int = 0


@dataclass
class BaseDocument:
    """통일 스키마 기본 문서"""
    id: str
    type: str  # "guide"
    domain: str  # "tax", "labor", "startup", etc.
    title: str
    content: str
    source: Source
    related_laws: List[RelatedLaw] = field(default_factory=list)
    effective_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 섹션 구조 클래스
# ============================================================================

@dataclass
class Section:
    """문서 섹션"""
    level: str  # "large", "medium", "small"
    num: str
    title: str
    start_page: int
    end_page: Optional[int] = None
    text: str = ""
    law_refs: List[Dict] = field(default_factory=list)
    parent_section: Optional[str] = None


# ============================================================================
# 정규표현식 패턴
# ============================================================================

PATTERNS = {
    # 대단원: "1장", "제1장"
    'large_section': re.compile(
        r'^(?:제\s*)?(\d+)\s*장[\.．\s]+([가-힣A-Za-z\s·\-]+)',
        re.MULTILINE
    ),

    # 중단원: "I.", "II.", "III."
    'medium_section': re.compile(
        r'([IⅠⅡⅢⅣⅤViv]{1,4})\s*[\.．]\s*([가-힣][가-힣\s·\-]+)',
        re.MULTILINE
    ),

    # 소단원: "01.", "02."
    'small_section': re.compile(
        r'^(0?\d{1,2})\s*[\.．]\s*([가-힣][가-힣\s·\-「」]+)',
        re.MULTILINE
    ),

    # 법령 약칭: 조특법§6
    'law_abbrev': re.compile(
        r'(조특법|조특령|조특칙|법인세법|법인령|법인칙|소득세법|소득령|소득칙|'
        r'부가법|부가령|상증법|상증령|중기법|중기령|벤처법|근로기준법|고용보험법|'
        r'통계법|상법|민법|지특법|농특세법|소법|소령|법법|법령|법칙)'
        r'[§](\d+(?:의\d+)?)'
        r'(?:([①②③④⑤⑥⑦⑧⑨⑩]))?'
        r'(?:(\d+)호)?'
    ),

    # 정식 법령명: 「조세특례제한법」 제6조
    'law_formal': re.compile(
        r'[「『]([^」』]+)[」』]\s*'
        r'제(\d+(?:의\d+)?)조'
        r'(?:제(\d+)항)?'
        r'(?:제(\d+)호)?'
    ),
}


# 법령 약칭 매핑
LAW_MAPPINGS = {
    "조특법": {"full_name": "조세특례제한법", "law_id": "001584"},
    "조특령": {"full_name": "조세특례제한법 시행령", "law_id": "004920"},
    "조특칙": {"full_name": "조세특례제한법 시행규칙", "law_id": "008218"},
    "법인세법": {"full_name": "법인세법", "law_id": "001563"},
    "법인령": {"full_name": "법인세법 시행령", "law_id": "003608"},
    "법법": {"full_name": "법인세법", "law_id": "001563"},
    "법령": {"full_name": "법인세법 시행령", "law_id": "003608"},
    "소득세법": {"full_name": "소득세법", "law_id": "001565"},
    "소득령": {"full_name": "소득세법 시행령", "law_id": "003956"},
    "소법": {"full_name": "소득세법", "law_id": "001565"},
    "소령": {"full_name": "소득세법 시행령", "law_id": "003956"},
    "부가법": {"full_name": "부가가치세법", "law_id": "001571"},
    "부가령": {"full_name": "부가가치세법 시행령", "law_id": "003666"},
    "상증법": {"full_name": "상속세 및 증여세법", "law_id": "001561"},
    "상증령": {"full_name": "상속세 및 증여세법 시행령", "law_id": "003814"},
    "중기법": {"full_name": "중소기업기본법", "law_id": "001477"},
    "중기령": {"full_name": "중소기업기본법 시행령", "law_id": "004958"},
    "벤처법": {"full_name": "벤처기업육성에 관한 특별조치법", "law_id": "001491"},
    "근로기준법": {"full_name": "근로기준법", "law_id": "001264"},
    "고용보험법": {"full_name": "고용보험법", "law_id": "001364"},
}


# 도메인 분류 키워드
DOMAIN_KEYWORDS = {
    "tax": ["세법", "소득세", "법인세", "부가가치세", "국세청", "세금", "세무", "조특법", "세액"],
    "labor": ["근로", "노동", "고용", "임금", "퇴직", "해고", "휴가", "4대보험", "산재"],
    "startup": ["사업자", "창업", "법인설립", "업종", "인허가", "벤처"],
    "funding": ["지원사업", "보조금", "정책자금", "공고"],
    "legal": ["상법", "민법", "특허법", "상표법", "저작권법", "공정거래", "계약"],
}


# ============================================================================
# 법령 바인딩 (law_lookup.json 기반)
# ============================================================================

class LawLookup:
    """law_lookup.json 기반 법령 바인딩"""

    def __init__(self, lookup_path: Path = None):
        self.lookup_path = lookup_path
        self.lookup: Dict[str, str] = {}  # law_name -> law_id
        self.lookup_normalized: Dict[str, str] = {}  # normalized_name -> law_id
        self._loaded = False

    def load(self):
        """법령 룩업 테이블 로드"""
        if self._loaded:
            return

        if self.lookup_path and self.lookup_path.exists():
            print(f"[LawLookup] Loading: {self.lookup_path}")
            with open(self.lookup_path, 'r', encoding='utf-8') as f:
                self.lookup = json.load(f)

            # 정규화된 버전도 추가
            for law_name, law_id in self.lookup.items():
                normalized = self._normalize(law_name)
                self.lookup_normalized[normalized] = law_id

            print(f"[LawLookup] Loaded {len(self.lookup)} laws")

        self._loaded = True

    def _normalize(self, name: str) -> str:
        """법령명 정규화"""
        normalized = name.replace(' ', '')
        normalized = normalized.replace('·', 'ㆍ').replace('•', 'ㆍ').replace('‧', 'ㆍ')
        return normalized

    def find_law_id(self, law_name: str) -> Optional[str]:
        """법령명으로 law_id 찾기 (현행법만)"""
        self.load()

        # 직접 매칭
        if law_name in self.lookup:
            return self.lookup[law_name]

        # 정규화 매칭
        normalized = self._normalize(law_name)
        if normalized in self.lookup_normalized:
            return self.lookup_normalized[normalized]

        return None


# 전역 룩업
_law_lookup: Optional[LawLookup] = None

def get_law_lookup(lookup_path: Path = None) -> LawLookup:
    global _law_lookup
    if _law_lookup is None:
        _law_lookup = LawLookup(lookup_path)
    return _law_lookup


# ============================================================================
# 텍스트 처리 함수
# ============================================================================

def clean_text(text: str) -> str:
    """PDF 아티팩트 제거"""
    if not text:
        return text

    # 페이지 마커 제거
    text = re.sub(r'---\s*PAGE\s*\d+\s*---\n?', '', text)

    # 세로 사이드바 텍스트 제거
    text = re.sub(r'제\n\d+\n장\n(?:[가-힣]\n)+', '', text)

    # 페이지 번호만 있는 줄 제거
    text = re.sub(r'^\d{1,3}\n', '', text, flags=re.MULTILINE)

    # 연속 줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def normalize_title(title: str) -> str:
    """섹션 제목 정규화"""
    if not title:
        return title
    title = re.sub(r'\n\s*', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def classify_domain(text: str, title: str = "") -> str:
    """도메인 자동 분류"""
    combined = f"{title} {text}".lower()

    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                scores[domain] += 1

    max_domain = max(scores, key=scores.get)
    return max_domain if scores[max_domain] > 0 else "legal"


# ============================================================================
# PDF 텍스트 추출
# ============================================================================

def extract_text_from_pdf(pdf_path: Path, start_page: int = 0, end_page: int = None) -> str:
    """PDF에서 텍스트 추출"""
    doc = fitz.open(str(pdf_path))
    if end_page is None:
        end_page = len(doc)

    text_parts = []
    for page_num in range(start_page, min(end_page, len(doc))):
        page = doc[page_num]
        text = page.get_text("text")
        text_parts.append(text)

    doc.close()
    return "\n\n".join(text_parts)


def detect_toc_pages(doc) -> List[int]:
    """목차 페이지 감지"""
    toc_pages = []
    toc_keywords = ['목 차', '목차', 'contents', 'table of contents']

    for page_num in range(min(15, len(doc))):
        text = doc[page_num].get_text("text").lower()
        for keyword in toc_keywords:
            if keyword.lower() in text:
                toc_pages.append(page_num)
                break

    if toc_pages:
        max_toc = max(toc_pages)
        return list(range(0, min(max_toc + 8, 15)))

    return toc_pages


# ============================================================================
# 법령 참조 추출
# ============================================================================

def extract_law_references(text: str, law_lookup: LawLookup = None) -> List[RelatedLaw]:
    """텍스트에서 법령 참조 추출 및 바인딩"""
    references = []
    seen = set()

    # 약칭 형식 추출
    for match in PATTERNS['law_abbrev'].finditer(text):
        abbrev = match.group(1)
        article = match.group(2)

        law_info = LAW_MAPPINGS.get(abbrev, {})
        law_name = law_info.get('full_name', abbrev)
        article_ref = f"제{article}조"

        # law_lookup.json 기반 바인딩 (현행법만)
        law_id = None
        if law_lookup:
            law_id = law_lookup.find_law_id(law_name)
        # fallback: LAW_MAPPINGS의 law_id 사용
        if not law_id:
            law_id = law_info.get('law_id')

        key = f"{law_name}_{article_ref}"
        if key not in seen:
            seen.add(key)
            references.append(RelatedLaw(
                law_id=law_id,
                law_name=law_name,
                article_ref=article_ref
            ))

    # 정식 형식 추출
    for match in PATTERNS['law_formal'].finditer(text):
        law_name = match.group(1)
        article = match.group(2)
        article_ref = f"제{article}조"

        # law_lookup.json 기반 바인딩 (현행법만)
        law_id = None
        if law_lookup:
            law_id = law_lookup.find_law_id(law_name)

        # fallback: LAW_MAPPINGS에서 찾기
        if not law_id:
            for abbrev, info in LAW_MAPPINGS.items():
                if info.get('full_name') == law_name or law_name in info.get('full_name', ''):
                    law_id = info.get('law_id')
                    break

        key = f"{law_name}_{article_ref}"
        if key not in seen:
            seen.add(key)
            references.append(RelatedLaw(
                law_id=law_id,
                law_name=law_name,
                article_ref=article_ref
            ))

    return references


# ============================================================================
# 문서 구조 분석
# ============================================================================

def detect_document_structure(pdf_path: Path) -> List[Section]:
    """PDF 문서의 계층 구조 분석"""
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    # TOC 페이지 감지
    toc_pages = detect_toc_pages(doc)
    content_start = max(toc_pages) + 1 if toc_pages else 0

    print(f"  [INFO] Content starts from page: {content_start + 1}")

    all_sections = []

    for page_num in range(content_start, total_pages):
        page = doc[page_num]
        text = page.get_text("text")

        # 대단원 감지
        for match in PATTERNS['large_section'].finditer(text):
            title = normalize_title(match.group(2))
            if len(title) >= 3:
                all_sections.append({
                    'level': 'large',
                    'num': str(match.group(1)),
                    'title': title[:50],
                    'page': page_num + 1
                })

        # 중단원 감지
        for match in PATTERNS['medium_section'].finditer(text):
            roman_raw = match.group(1)
            roman = roman_raw.replace('Ⅰ', 'I').replace('Ⅱ', 'II').replace('Ⅲ', 'III').replace('Ⅳ', 'IV').replace('Ⅴ', 'V').upper()
            title = normalize_title(match.group(2))
            if len(title) >= 3 and roman in ['I', 'II', 'III', 'IV', 'V', 'VI']:
                all_sections.append({
                    'level': 'medium',
                    'num': roman,
                    'title': title[:50],
                    'page': page_num + 1
                })

        # 소단원 감지
        for match in PATTERNS['small_section'].finditer(text):
            title = normalize_title(match.group(2))
            if 2 <= len(title) <= 50 and not title.isdigit():
                all_sections.append({
                    'level': 'small',
                    'num': match.group(1).lstrip('0') or '0',
                    'title': title,
                    'page': page_num + 1
                })

    doc.close()

    # 중복 제거
    seen = set()
    unique_sections = []
    for sec in all_sections:
        key = (sec['level'], sec['num'], sec['title'][:10])
        if key not in seen:
            seen.add(key)
            unique_sections.append(sec)

    # 정렬 및 Section 객체 생성
    unique_sections.sort(key=lambda x: (x['page'],
                                        0 if x['level'] == 'large' else
                                        1 if x['level'] == 'medium' else 2))

    sections = []
    current_large = None
    current_medium = None

    for i, sec in enumerate(unique_sections):
        # 다음 섹션 페이지로 종료 페이지 계산
        next_page = unique_sections[i + 1]['page'] if i + 1 < len(unique_sections) else total_pages + 1

        parent = None
        if sec['level'] == 'large':
            current_large = f"{sec['num']}장"
            current_medium = None
        elif sec['level'] == 'medium':
            current_medium = sec['num']
            parent = current_large
        elif sec['level'] == 'small':
            parent = f"{current_large} {current_medium}" if current_medium else current_large

        sections.append(Section(
            level=sec['level'],
            num=sec['num'],
            title=sec['title'],
            start_page=sec['page'],
            end_page=next_page - 1,
            parent_section=parent
        ))

    return sections


# ============================================================================
# 메인 전처리 클래스
# ============================================================================

class PDFPreprocessor:
    """PDF 전처리기 (통일 스키마 + 법령 바인딩)"""

    def __init__(self, law_lookup_path: Path = None):
        self.law_lookup = get_law_lookup(law_lookup_path) if law_lookup_path else None
        if self.law_lookup:
            self.law_lookup.load()

    def process_pdf(
        self,
        pdf_path: Path,
        output_path: Path,
        domain: str = None,
        source_name: str = "PDF 문서"
    ) -> Dict[str, Any]:
        """
        PDF 전처리 실행

        Args:
            pdf_path: 입력 PDF 파일 경로
            output_path: 출력 JSONL 파일 경로
            domain: 도메인 (None이면 자동 분류)
            source_name: 출처명

        Returns:
            처리 결과 통계
        """
        print("=" * 70)
        print(f"[PDF Preprocessor] Processing: {pdf_path.name}")
        print("=" * 70)

        # 구조 분석
        print("\n[STEP 1] Structure Analysis")
        print("-" * 50)
        sections = detect_document_structure(pdf_path)
        print(f"  Found {len(sections)} sections")

        # 섹션별 처리
        print("\n[STEP 2] Section Processing")
        print("-" * 50)

        documents = []
        stats = {
            'total_sections': len(sections),
            'processed': 0,
            'total_law_refs': 0,
            'bound_law_refs': 0,
            'by_level': {'large': 0, 'medium': 0, 'small': 0, 'full': 0}
        }

        # 섹션이 없으면 전체 문서를 하나로 처리
        if not sections:
            print("  [INFO] No sections detected, processing as single document")
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            doc.close()

            sections = [Section(
                level='full',
                num='1',
                title=pdf_path.stem,
                start_page=1,
                end_page=total_pages
            )]
            stats['total_sections'] = 1

        for section in sections:
            # 텍스트 추출
            raw_text = extract_text_from_pdf(pdf_path, section.start_page - 1, section.end_page)
            text = clean_text(raw_text)

            if not text.strip():
                continue

            # 법령 참조 추출 및 바인딩
            law_refs = extract_law_references(text, self.law_lookup)

            # 도메인 결정
            doc_domain = domain or classify_domain(text, section.title)

            # ID 생성
            doc_id = f"GUIDE_PDF_{pdf_path.stem}_{section.level[0].upper()}{section.num}"

            # 문서 생성
            doc = BaseDocument(
                id=doc_id,
                type="guide",
                domain=doc_domain,
                title=f"{section.num}. {section.title}" if section.level == 'small' else
                      f"{section.num} {section.title}",
                content=text,
                source=Source(
                    name=source_name,
                    url=None,
                    collected_at=datetime.now().isoformat()
                ),
                related_laws=law_refs,
                effective_date=None,
                metadata={
                    'filename': pdf_path.name,
                    'section_type': section.level,
                    'section_num': section.num,
                    'page_start': section.start_page,
                    'page_end': section.end_page,
                    'parent_section': section.parent_section,
                    'law_ref_count': len(law_refs),
                    'char_count': len(text)
                }
            )

            documents.append(doc)

            # 바인딩 통계
            bound_count = sum(1 for r in law_refs if r.law_id)

            stats['processed'] += 1
            stats['total_law_refs'] += len(law_refs)
            stats['bound_law_refs'] += bound_count
            if section.level in stats['by_level']:
                stats['by_level'][section.level] += 1

            print(f"  [OK] {section.level[0].upper()}{section.num}: {section.title[:30]}... "
                  f"({len(text):,} chars, {len(law_refs)} refs, {bound_count} bound)")

        # JSONL 출력
        print("\n[STEP 3] Saving Results")
        print("-" * 50)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in documents:
                # dataclass to dict 변환
                doc_dict = {
                    'id': doc.id,
                    'type': doc.type,
                    'domain': doc.domain,
                    'title': doc.title,
                    'content': doc.content,
                    'source': asdict(doc.source),
                    'related_laws': [asdict(r) for r in doc.related_laws],
                    'effective_date': doc.effective_date,
                    'metadata': doc.metadata
                }
                f.write(json.dumps(doc_dict, ensure_ascii=False) + '\n')

        print(f"  [OK] Saved: {output_path}")
        print(f"       {len(documents)} documents")

        # 구조 정보 저장 (별도 JSON)
        structure_path = output_path.with_suffix('.structure.json')
        structure_data = {
            'filename': pdf_path.name,
            'processed_at': datetime.now().isoformat(),
            'stats': stats,
            'sections': [
                {
                    'level': s.level,
                    'num': s.num,
                    'title': s.title,
                    'page_start': s.start_page,
                    'page_end': s.end_page,
                    'parent': s.parent_section
                }
                for s in sections
            ]
        }

        with open(structure_path, 'w', encoding='utf-8') as f:
            json.dump(structure_data, f, ensure_ascii=False, indent=2)

        print(f"  [OK] Structure: {structure_path}")

        # 완료
        print("\n" + "=" * 70)
        print("[DONE] PDF Preprocessing Complete!")
        print("=" * 70)
        print(f"\n[SUMMARY]")
        print(f"  - Total sections: {stats['total_sections']}")
        print(f"  - Processed: {stats['processed']}")
        if stats['by_level'].get('full', 0) > 0:
            print(f"  - Full document: {stats['by_level']['full']}")
        else:
            print(f"  - Large sections: {stats['by_level']['large']}")
            print(f"  - Medium sections: {stats['by_level']['medium']}")
            print(f"  - Small sections: {stats['by_level']['small']}")
        print(f"  - Law references: {stats['total_law_refs']}")
        print(f"  - Bound (current laws): {stats['bound_law_refs']}")
        bind_rate = (stats['bound_law_refs'] / stats['total_law_refs'] * 100) if stats['total_law_refs'] > 0 else 0
        print(f"  - Binding rate: {bind_rate:.1f}%")

        return stats


# ============================================================================
# 경로 설정
# ============================================================================

# 기본 경로
DATA_DIR = Path("D:/f.pp/final_files/data")
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "guides"

# PDF 파일 목록
PDF_FILES = [
    DATA_DIR / "2025 중소기업세제·세정지원 제도_part1_1-50p.pdf",
    DATA_DIR / "2025 중소기업세제·세정지원 제도_part2_51-100p.pdf",
    DATA_DIR / "2025 중소기업세제·세정지원 제도_part3_101-150p.pdf",
    DATA_DIR / "2025 중소기업세제·세정지원 제도_part4_151-152p.pdf",
]

# law_lookup.json 경로
LAW_LOOKUP_PATH = PROCESSED_DIR / "laws" / "law_lookup.json"


# ============================================================================
# CLI
# ============================================================================

def process_all_pdfs():
    """4개 PDF 파일 일괄 처리 및 통합 출력"""
    print("=" * 70)
    print("PDF 전처리 + 법령 바인딩 (4개 파일)")
    print("=" * 70)

    # law_lookup 로드
    print(f"\n[INIT] Law lookup: {LAW_LOOKUP_PATH}")
    preprocessor = PDFPreprocessor(LAW_LOOKUP_PATH)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "pdf_guides.jsonl"

    # 전체 통계
    total_stats = {
        'files': 0,
        'sections': 0,
        'law_refs': 0,
        'bound_refs': 0
    }

    all_documents = []

    # 각 PDF 처리
    for pdf_path in PDF_FILES:
        if not pdf_path.exists():
            print(f"\n[WARN] File not found: {pdf_path}")
            continue

        print(f"\n{'=' * 70}")
        print(f"Processing: {pdf_path.name}")
        print("=" * 70)

        # 구조 분석
        sections = detect_document_structure(pdf_path)
        print(f"  Found {len(sections)} sections")

        # 섹션이 없으면 전체 문서를 하나로
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        doc.close()

        if not sections:
            sections = [Section(
                level='full',
                num='1',
                title=pdf_path.stem,
                start_page=1,
                end_page=total_pages
            )]

        # 파트 번호 추출
        part_match = re.search(r'part(\d+)', pdf_path.name, re.IGNORECASE)
        part_num = part_match.group(1) if part_match else "1"

        # 각 섹션 처리
        for section in sections:
            raw_text = extract_text_from_pdf(pdf_path, section.start_page - 1, section.end_page)
            text = clean_text(raw_text)

            if not text.strip():
                continue

            # 법령 참조 추출 및 바인딩
            law_refs = extract_law_references(text, preprocessor.law_lookup)
            bound_count = sum(1 for r in law_refs if r.law_id)

            # ID 생성
            doc_id = f"GUIDE_PDF_TAXSUPPORT_P{part_num}_{section.level[0].upper()}{section.num}"

            # 문서 생성
            doc_obj = BaseDocument(
                id=doc_id,
                type="guide",
                domain="tax",
                title=f"{section.num}. {section.title}" if section.level == 'small' else
                      f"{section.num} {section.title}",
                content=text,
                source=Source(
                    name="2025 중소기업세제·세정지원 제도",
                    url=None,
                    collected_at=datetime.now().isoformat()
                ),
                related_laws=law_refs,
                effective_date="2025-01-01",
                metadata={
                    'filename': pdf_path.name,
                    'part': int(part_num),
                    'section_type': section.level,
                    'section_num': section.num,
                    'page_start': section.start_page,
                    'page_end': section.end_page,
                    'parent_section': section.parent_section,
                    'law_ref_count': len(law_refs),
                    'bound_law_count': bound_count,
                    'char_count': len(text)
                }
            )

            all_documents.append(doc_obj)
            total_stats['sections'] += 1
            total_stats['law_refs'] += len(law_refs)
            total_stats['bound_refs'] += bound_count

            print(f"  [OK] {section.level[0].upper()}{section.num}: {section.title[:30]}... "
                  f"({len(law_refs)} refs, {bound_count} bound)")

        total_stats['files'] += 1

    # JSONL 출력 (통합)
    print(f"\n{'=' * 70}")
    print("[OUTPUT] Writing merged JSONL")
    print("=" * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        for doc in all_documents:
            doc_dict = {
                'id': doc.id,
                'type': doc.type,
                'domain': doc.domain,
                'title': doc.title,
                'content': doc.content,
                'source': asdict(doc.source),
                'related_laws': [asdict(r) for r in doc.related_laws],
                'effective_date': doc.effective_date,
                'metadata': doc.metadata
            }
            f.write(json.dumps(doc_dict, ensure_ascii=False) + '\n')

    print(f"  [OK] Saved: {output_path}")
    print(f"       {len(all_documents)} documents")

    # 최종 결과
    print(f"\n{'=' * 70}")
    print("[COMPLETE] PDF Preprocessing + Law Binding")
    print("=" * 70)
    print(f"\n[FINAL SUMMARY]")
    print(f"  - PDF files: {total_stats['files']}")
    print(f"  - Total sections: {total_stats['sections']}")
    print(f"  - Law references: {total_stats['law_refs']}")
    print(f"  - Bound (current laws): {total_stats['bound_refs']}")
    bind_rate = (total_stats['bound_refs'] / total_stats['law_refs'] * 100) if total_stats['law_refs'] > 0 else 0
    print(f"  - Binding rate: {bind_rate:.1f}%")
    print(f"\n  Output: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="PDF 전처리기 (통일 스키마 + 법령 바인딩)"
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='4개 PDF 파일 일괄 처리 (기본)'
    )
    parser.add_argument(
        'pdf_file',
        type=str,
        nargs='?',
        help='입력 PDF 파일 (단일 파일 처리시)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='출력 JSONL 파일 (기본: 입력파일명.jsonl)'
    )
    parser.add_argument(
        '--domain',
        type=str,
        choices=['tax', 'labor', 'startup', 'funding', 'legal', 'marketing'],
        default=None,
        help='도메인 지정 (기본: 자동 분류)'
    )
    parser.add_argument(
        '--source',
        type=str,
        default="PDF 문서",
        help='출처명'
    )
    parser.add_argument(
        '--law-lookup',
        type=str,
        default=None,
        help='법령 룩업 파일 경로 (law_lookup.json)'
    )

    args = parser.parse_args()

    # --all 또는 인자 없이 실행시 일괄 처리
    if args.all or not args.pdf_file:
        process_all_pdfs()
    else:
        # 단일 파일 처리
        pdf_path = Path(args.pdf_file)
        output_path = Path(args.output) if args.output else pdf_path.with_suffix('.jsonl')
        law_lookup_path = Path(args.law_lookup) if args.law_lookup else LAW_LOOKUP_PATH

        preprocessor = PDFPreprocessor(law_lookup_path)
        preprocessor.process_pdf(
            pdf_path=pdf_path,
            output_path=output_path,
            domain=args.domain,
            source_name=args.source
        )


if __name__ == "__main__":
    main()
