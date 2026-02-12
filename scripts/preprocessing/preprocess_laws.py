"""
법령 데이터 전처리기 (도메인 필터링 포함)

data_pipeline.md / happy-tinkering-toucan.md 기반
- 법령 (01_laws_full.json) → law/laws_full.jsonl (RAG 관련) + law/laws_etc.jsonl (기타)
- 법령해석례 (expc_전체.json) → law/interpretations.jsonl (RAG 관련) + law/interpretations_etc.jsonl (기타)
- 판례 (prec_*.json) → law/court_cases_*.jsonl

3단계 도메인 분류로 RAG 관련 법령만 VectorDB에 투입:
  1단계: 소관부처 매핑 (ORG_DOMAIN_MAP)
  2단계: 키워드 매칭 (DOMAIN_KEYWORDS + KEYWORD_OVERRIDES)
  3단계: 매칭 없으면 'etc'로 분류 (VectorDB 제외)
"""

import json
import re
from io import TextIOWrapper
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict


# ============================================================================
# 경로 설정
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "law-raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "preprocessed"


# ============================================================================
# 스키마 정의
# ============================================================================

@dataclass
class Source:
    name: str
    url: Optional[str] = None
    collected_at: Optional[str] = None


@dataclass
class RelatedLaw:
    law_id: Optional[str] = None
    law_name: str = ""
    article_ref: Optional[str] = None


@dataclass
class Document:
    id: str
    type: str
    domain: str
    title: str
    content: str
    source: Source
    related_laws: List[RelatedLaw] = field(default_factory=list)
    effective_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 도메인 분류 (3단계 필터링)
# ============================================================================

DOMAIN_KEYWORDS = {
    "finance_tax": [
        "세법", "소득세", "법인세", "부가가치세", "국세", "세금", "세무",
        "조특법", "세액", "과세", "납세", "상속세", "증여세", "관세",
        "지방세", "종합부동산세", "인지세", "조세", "증권거래세",
    ],
    "hr_labor": [
        "근로", "노동", "고용", "임금", "퇴직", "해고", "휴가",
        "4대보험", "산재", "근로기준", "최저임금", "산업재해",
        "국민연금", "건강보험", "고용보험", "직업안정", "직업능력",
        "산업안전", "남녀고용평등",
    ],
    "startup_funding": [
        "창업", "벤처", "중소기업", "소상공인", "사업자", "법인설립",
        "업종", "인허가", "지원사업", "보조금", "정책자금", "공고", "융자",
        "특허", "상표", "저작권", "지식재산", "발명", "실용신안",
        "공정거래", "하도급",
    ],
    "general": [
        "민법", "상법", "행정절차", "행정심판", "전자상거래", "소비자",
        "개인정보", "정보통신", "전자서명",
    ],
}

ORG_DOMAIN_MAP = {
    "고용노동부": "hr_labor",
    "기획재정부": "finance_tax",
    "국세청": "finance_tax",
    "중소벤처기업부": "startup_funding",
    "공정거래위원회": "startup_funding",
    "지식재산처": "startup_funding",
}

KEYWORD_OVERRIDES = {
    "법인세": "finance_tax",
    "법인세법": "finance_tax",
}


def classify_domain(text: str, org: str = None) -> str:
    """3단계 도메인 분류.

    Stage 1: 소관부처 매핑 (최고 신뢰도)
    Stage 2: 키워드 매칭 (KEYWORD_OVERRIDES 포함)
    Stage 3: 매칭 없으면 'etc' 반환
    """
    # Stage 1: 소관부처 매핑
    if org:
        for org_name, domain in ORG_DOMAIN_MAP.items():
            if org_name in org:
                return domain

    # Stage 2: 키워드 매칭
    combined = text.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                scores[domain] += 1

    # 오버라이드 적용 (충돌 방지)
    for override_kw, override_domain in KEYWORD_OVERRIDES.items():
        if override_kw in combined:
            scores[override_domain] += 5

    max_domain = max(scores, key=scores.get)
    if scores[max_domain] > 0:
        return max_domain

    # Stage 3: 매칭 없음
    return "etc"


def print_filtering_stats(
    total: int,
    domain_counts: Dict[str, int],
    data_type: str,
) -> None:
    """필터링 통계 출력."""
    rag_relevant = sum(v for k, v in domain_counts.items() if k != "etc")
    etc_count = domain_counts.get("etc", 0)
    pct_rag = (rag_relevant / total * 100) if total > 0 else 0
    pct_etc = (etc_count / total * 100) if total > 0 else 0
    print(f"\n  [필터링 결과] {data_type}")
    print(f"    전체: {total:,}건")
    print(f"    RAG 관련: {rag_relevant:,}건 ({pct_rag:.1f}%)")
    print(f"    기타: {etc_count:,}건 ({pct_etc:.1f}%)")
    for domain, count in sorted(domain_counts.items()):
        if domain != "etc":
            print(f"      {domain}: {count:,}건")


# ============================================================================
# 텍스트 처리
# ============================================================================

def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""

    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    text = text.replace('\u3000', ' ')

    return text.strip()


def format_date(date_str: str) -> Optional[str]:
    """YYYYMMDD -> YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return None


# ============================================================================
# 법령 참조 추출
# ============================================================================

LAW_PATTERN = re.compile(r'[「『]([^」』]+)[」』]')
ARTICLE_PATTERN = re.compile(r'제(\d+(?:의\d+)?)조')


def extract_law_references(text: str) -> List[RelatedLaw]:
    """텍스트에서 「법령명」 패턴 추출"""
    references = []
    seen = set()

    for match in LAW_PATTERN.finditer(text):
        law_name = match.group(1).strip()

        # 주변에서 조문 찾기
        start = match.end()
        end = min(start + 50, len(text))
        context = text[start:end]

        article_match = ARTICLE_PATTERN.search(context)
        article_ref = f"제{article_match.group(1)}조" if article_match else None

        key = f"{law_name}_{article_ref}"
        if key not in seen:
            seen.add(key)
            references.append(RelatedLaw(
                law_id=None,
                law_name=law_name,
                article_ref=article_ref
            ))

    return references


# ============================================================================
# 법령 처리 (필터링 적용)
# ============================================================================

# ============================================================================
# 법령 조문 단위 분할 상수
# ============================================================================

MIN_ARTICLE_CHUNK = 200   # 이 미만이면 다음 조문과 병합
MAX_ARTICLE_CHUNK = 3000  # 이 초과면 항(clause) 단위로 분할


def _format_article_text(article: Dict[str, Any]) -> str:
    """조문 1개를 포맷팅된 텍스트로 변환합니다.

    Args:
        article: 조문 데이터 (number, title, content, clauses)

    Returns:
        포맷팅된 조문 텍스트
    """
    parts: List[str] = []
    article_num = article.get('number', '')
    article_title = article.get('title', '')
    article_content = article.get('content', '')

    if article_title:
        parts.append(f"제{article_num}조({article_title})")
    elif article_num:
        parts.append(f"제{article_num}조")

    if article_content:
        parts.append(clean_text(article_content))

    for clause in article.get('clauses', []):
        clause_content = clause.get('content', '')
        if clause_content:
            parts.append(clean_text(clause_content))
        for item in clause.get('items', []):
            item_content = item.get('content', '')
            if item_content:
                parts.append(f"  {clean_text(item_content)}")

    return '\n'.join(parts)


def _split_large_article_by_clauses(
    law_header: str,
    article: Dict[str, Any],
    law_id: str,
    name: str,
    domain: str,
    collected_at: str,
    filter_method: str,
    filter_reason: str,
    effective_date: Optional[str],
    ministry: str,
    f_out: TextIOWrapper,
) -> int:
    """대형 조문을 항(clause) 단위로 분할하여 기록합니다.

    Args:
        law_header: 법령 헤더 텍스트
        article: 조문 데이터
        law_id: 법령 ID
        name: 법령명
        domain: 도메인
        collected_at: 수집일
        filter_method: 필터링 방법
        filter_reason: 필터링 사유
        effective_date: 시행일
        ministry: 소관부처
        f_out: 출력 파일 핸들

    Returns:
        기록된 레코드 수
    """
    article_num = article.get('number', '')
    article_title = article.get('title', '')
    clauses = article.get('clauses', [])
    article_content = article.get('content', '')

    # 항이 없으면 content 자체를 하나의 청크로
    if not clauses:
        article_text = _format_article_text(article)
        content = f"{law_header}\n{article_text}"
        doc = _build_article_doc(
            law_id=law_id, article_num=article_num, article_range=str(article_num),
            name=name, article_title=article_title, domain=domain,
            content=content, collected_at=collected_at,
            filter_method=filter_method, filter_reason=filter_reason,
            effective_date=effective_date, ministry=ministry,
        )
        f_out.write(json.dumps(doc, ensure_ascii=False) + '\n')
        return 1

    # 항 헤더 (조문 번호 + 제목 + 본문)
    article_prefix_parts: List[str] = []
    if article_title:
        article_prefix_parts.append(f"제{article_num}조({article_title})")
    elif article_num:
        article_prefix_parts.append(f"제{article_num}조")
    if article_content:
        article_prefix_parts.append(clean_text(article_content))
    article_prefix = '\n'.join(article_prefix_parts)

    count = 0
    clause_buffer: List[str] = []
    buffer_chars = 0

    for i, clause in enumerate(clauses):
        clause_parts: List[str] = []
        clause_content = clause.get('content', '')
        if clause_content:
            clause_parts.append(clean_text(clause_content))
        for item in clause.get('items', []):
            item_content = item.get('content', '')
            if item_content:
                clause_parts.append(f"  {clean_text(item_content)}")
        clause_text = '\n'.join(clause_parts)

        if buffer_chars + len(clause_text) > MAX_ARTICLE_CHUNK and clause_buffer:
            # 버퍼 출력
            chunk_content = f"{law_header}\n{article_prefix}\n" + '\n'.join(clause_buffer)
            clause_idx = i  # 현재 항 이전까지
            doc = _build_article_doc(
                law_id=law_id, article_num=f"{article_num}-{count+1}",
                article_range=f"{article_num}-part{count+1}",
                name=name, article_title=article_title, domain=domain,
                content=chunk_content, collected_at=collected_at,
                filter_method=filter_method, filter_reason=filter_reason,
                effective_date=effective_date, ministry=ministry,
            )
            f_out.write(json.dumps(doc, ensure_ascii=False) + '\n')
            count += 1
            clause_buffer = []
            buffer_chars = 0

        clause_buffer.append(clause_text)
        buffer_chars += len(clause_text)

    # 남은 버퍼 출력
    if clause_buffer:
        chunk_content = f"{law_header}\n{article_prefix}\n" + '\n'.join(clause_buffer)
        doc = _build_article_doc(
            law_id=law_id, article_num=f"{article_num}-{count+1}" if count > 0 else str(article_num),
            article_range=f"{article_num}-part{count+1}" if count > 0 else str(article_num),
            name=name, article_title=article_title, domain=domain,
            content=chunk_content, collected_at=collected_at,
            filter_method=filter_method, filter_reason=filter_reason,
            effective_date=effective_date, ministry=ministry,
        )
        f_out.write(json.dumps(doc, ensure_ascii=False) + '\n')
        count += 1

    return count


def _build_article_doc(
    law_id: str,
    article_num: str,
    article_range: str,
    name: str,
    article_title: str,
    domain: str,
    content: str,
    collected_at: str,
    filter_method: str,
    filter_reason: str,
    effective_date: Optional[str],
    ministry: str,
) -> Dict[str, Any]:
    """조문 단위 JSONL 레코드를 생성합니다."""
    title_suffix = f" 제{article_num}조"
    if article_title:
        title_suffix = f" 제{article_num}조 ({article_title})"

    return {
        'id': f"LAW_{law_id}_A{article_range}",
        'type': 'law_article',
        'domain': domain,
        'title': f"{name}{title_suffix}",
        'content': content,
        'source': {
            'name': '국가법령정보센터',
            'url': f"https://law.go.kr/법령/{name}",
            'collected_at': collected_at,
        },
        'related_laws': [],
        'effective_date': effective_date,
        'metadata': {
            'law_id': law_id,
            'law_name': name,
            'ministry': ministry,
            'article_number': str(article_num),
            'article_title': article_title or '',
            'article_range': article_range,
            'parent_id': f"LAW_{law_id}",
            'filter_method': filter_method,
            'filter_reason': filter_reason,
        },
    }


def _determine_filter_info(ministry: str, domain: str) -> tuple[str, str]:
    """필터 메서드와 이유를 결정합니다."""
    if ministry:
        for org_name in ORG_DOMAIN_MAP:
            if org_name in ministry:
                return "org_mapping", f"소관부처: {ministry}"
    if domain != "etc":
        return "keyword", "키워드 매칭"
    return "none", "매칭 없음"


def process_laws(input_path: Path, output_dir: Path) -> Dict[str, str]:
    """법령 전처리 -> laws_full.jsonl (RAG) + laws_etc.jsonl (기타) + law_lookup.json

    조문 단위로 분할하여 각 조문을 독립적인 JSONL 레코드로 저장합니다.
    - 작은 조문(< MIN_ARTICLE_CHUNK): 인접 조문과 병합
    - 일반 조문: 독립 레코드
    - 대형 조문(> MAX_ARTICLE_CHUNK): 항(clause) 단위로 분할
    """
    print(f"\n{'='*60}")
    print(f"[법령 처리] {input_path.name} (조문 단위 분할)")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    laws = data.get('laws', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 법령 수: {len(laws):,}개")

    law_dir = output_dir / "law"
    law_dir.mkdir(parents=True, exist_ok=True)

    law_lookup: Dict[str, str] = {}
    domain_counts: Dict[str, int] = {}
    processed_laws = 0
    total_records = 0

    f_rag = open(law_dir / "laws_full.jsonl", 'w', encoding='utf-8')
    f_etc = open(law_dir / "laws_etc.jsonl", 'w', encoding='utf-8')

    try:
        for law in laws:
            law_id = law.get('law_id', '')
            name = law.get('name', '')

            if not law_id or not name:
                continue

            ministry = law.get('ministry', '')
            effective_date = format_date(law.get('enforcement_date', ''))

            # 법령 헤더 (각 조문 청크에 반복 삽입)
            law_header = (
                f"[{name}]\n"
                f"소관부처: {ministry}\n"
                f"시행일: {effective_date or '미상'}"
            )

            # 도메인 분류 (법령 전체 텍스트 기반)
            all_article_texts: List[str] = []
            articles = law.get('articles', [])
            for article in articles:
                all_article_texts.append(_format_article_text(article))
            full_text = f"{name} {ministry} " + ' '.join(all_article_texts)
            domain = classify_domain(full_text, ministry)
            filter_method, filter_reason = _determine_filter_info(ministry, domain)

            f_out = f_rag if domain != "etc" else f_etc

            # 조문이 없는 법령 → 전체를 하나의 레코드로
            if not articles:
                doc = _build_article_doc(
                    law_id=law_id, article_num="0", article_range="0",
                    name=name, article_title="", domain=domain,
                    content=law_header, collected_at=collected_at,
                    filter_method=filter_method, filter_reason=filter_reason,
                    effective_date=effective_date, ministry=ministry,
                )
                f_out.write(json.dumps(doc, ensure_ascii=False) + '\n')
                total_records += 1
            else:
                # 조문 단위 분할
                article_buffer: List[Dict[str, Any]] = []  # (article, text) 쌍
                buffer_texts: List[str] = []
                buffer_chars = 0
                buffer_start_num = ''

                def flush_buffer() -> int:
                    """버퍼에 쌓인 조문들을 하나의 레코드로 출력합니다."""
                    nonlocal article_buffer, buffer_texts, buffer_chars, buffer_start_num
                    if not article_buffer:
                        return 0

                    combined_text = '\n\n'.join(buffer_texts)
                    content = f"{law_header}\n\n{combined_text}"

                    if len(article_buffer) == 1:
                        art = article_buffer[0]
                        art_num = art.get('number', '')
                        art_title = art.get('title', '')
                        art_range = str(art_num)
                    else:
                        art_num = buffer_start_num
                        last_num = article_buffer[-1].get('number', '')
                        art_title = ''
                        art_range = f"{buffer_start_num}-{last_num}"

                    doc = _build_article_doc(
                        law_id=law_id, article_num=art_num,
                        article_range=art_range,
                        name=name, article_title=art_title, domain=domain,
                        content=content, collected_at=collected_at,
                        filter_method=filter_method, filter_reason=filter_reason,
                        effective_date=effective_date, ministry=ministry,
                    )
                    f_out.write(json.dumps(doc, ensure_ascii=False) + '\n')

                    article_buffer = []
                    buffer_texts = []
                    buffer_chars = 0
                    buffer_start_num = ''
                    return 1

                records_for_law = 0

                for article in articles:
                    article_content = article.get('content', '')

                    # '삭제' 조문 스킵
                    if '삭제' in article_content and len(article_content) < 30:
                        continue

                    article_text = _format_article_text(article)
                    article_len = len(article_text)

                    if article_len > MAX_ARTICLE_CHUNK:
                        # 대형 조문: 버퍼 먼저 출력 후 항 단위로 분할
                        records_for_law += flush_buffer()
                        records_for_law += _split_large_article_by_clauses(
                            law_header=law_header,
                            article=article,
                            law_id=law_id,
                            name=name,
                            domain=domain,
                            collected_at=collected_at,
                            filter_method=filter_method,
                            filter_reason=filter_reason,
                            effective_date=effective_date,
                            ministry=ministry,
                            f_out=f_out,
                        )
                    elif buffer_chars + article_len > MAX_ARTICLE_CHUNK and article_buffer:
                        # 버퍼가 꽉 참: 출력 후 새 버퍼
                        records_for_law += flush_buffer()
                        article_buffer = [article]
                        buffer_texts = [article_text]
                        buffer_chars = article_len
                        buffer_start_num = article.get('number', '')
                    elif article_len < MIN_ARTICLE_CHUNK:
                        # 작은 조문: 병합
                        if not article_buffer:
                            buffer_start_num = article.get('number', '')
                        article_buffer.append(article)
                        buffer_texts.append(article_text)
                        buffer_chars += article_len
                    else:
                        # 일반 조문: 버퍼 출력 후 독립 레코드
                        records_for_law += flush_buffer()
                        article_buffer = [article]
                        buffer_texts = [article_text]
                        buffer_chars = article_len
                        buffer_start_num = article.get('number', '')
                        records_for_law += flush_buffer()

                # 남은 버퍼 출력
                records_for_law += flush_buffer()
                total_records += records_for_law

            law_lookup[name] = law_id
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            processed_laws += 1

            if processed_laws % 1000 == 0:
                print(f"    처리 중: {processed_laws:,}개 법령, {total_records:,}개 레코드")
    finally:
        f_rag.close()
        f_etc.close()

    # law_lookup.json 저장
    with open(law_dir / "law_lookup.json", 'w', encoding='utf-8') as f:
        json.dump(law_lookup, f, ensure_ascii=False, indent=2)

    rag_count = sum(v for k, v in domain_counts.items() if k != "etc")
    etc_count = domain_counts.get("etc", 0)

    print(f"\n  [완료] 법령: {processed_laws:,}개 → 레코드: {total_records:,}개")
    print(f"  [저장] {law_dir / 'laws_full.jsonl'} ({rag_count:,}개 법령, RAG 관련)")
    print(f"  [저장] {law_dir / 'laws_etc.jsonl'} ({etc_count:,}개 법령, 기타)")
    print(f"  [저장] {law_dir / 'law_lookup.json'} ({len(law_lookup):,}개)")

    print_filtering_stats(processed_laws, domain_counts, "법령")

    return law_lookup


# ============================================================================
# 법령해석례 처리 (필터링 적용)
# ============================================================================

def process_interpretations(input_path: Path, output_dir: Path) -> int:
    """법령해석례 전처리 -> interpretations.jsonl (RAG) + interpretations_etc.jsonl (기타)

    질의-회답은 core 청크로 보존 (절대 분리 금지).
    이유(reason)는 300자 이상일 때 별도 reason 청크로 분리.
    """
    print(f"\n{'='*60}")
    print(f"[법령해석례 처리] {input_path.name} (Q&A 보존)")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 해석례 수: {len(items):,}개")

    law_dir = output_dir / "law"
    law_dir.mkdir(parents=True, exist_ok=True)

    domain_counts: Dict[str, int] = {}
    processed = 0
    reason_chunks = 0

    f_rag = open(law_dir / "interpretations.jsonl", 'w', encoding='utf-8')
    f_etc = open(law_dir / "interpretations_etc.jsonl", 'w', encoding='utf-8')

    try:
        for item in items:
            item_id = item.get('id', '')
            title = item.get('title', '')

            if not item_id:
                continue

            question = clean_text(item.get('question_summary', ''))
            answer = clean_text(item.get('answer', ''))
            reason = clean_text(item.get('reason', ''))

            # Core 청크: 질의 + 회답 (절대 분리 금지)
            core_content = f"[{title}]\n\n질의요지:\n{question}\n\n회답:\n{answer}"

            related_laws = extract_law_references(core_content)
            answer_org = item.get('answer_org', '')

            # 도메인 분류는 전체 텍스트 기반
            full_text = core_content
            if reason:
                full_text += f"\n\n이유:\n{reason}"
            domain = classify_domain(full_text, answer_org)

            # 필터 메서드 기록
            if answer_org:
                for org_name in ORG_DOMAIN_MAP:
                    if org_name in answer_org:
                        filter_method = "org_mapping"
                        filter_reason = f"회답기관: {answer_org}"
                        break
                else:
                    filter_method = "keyword" if domain != "etc" else "none"
                    filter_reason = "키워드 매칭" if domain != "etc" else "매칭 없음"
            else:
                filter_method = "keyword" if domain != "etc" else "none"
                filter_reason = "키워드 매칭" if domain != "etc" else "매칭 없음"

            effective_date = format_date(item.get('answer_date', ''))
            base_metadata = {
                'case_no': item.get('case_no', ''),
                'answer_date': item.get('answer_date', ''),
                'answer_org': answer_org,
                'question_org': item.get('question_org', ''),
                'filter_method': filter_method,
                'filter_reason': filter_reason,
            }

            f_out = f_rag if domain != "etc" else f_etc

            # Core 레코드 출력
            core_doc = {
                'id': f"INTERP_{item_id}",
                'type': 'interpretation',
                'domain': domain,
                'title': title,
                'content': core_content,
                'source': {
                    'name': '국가법령정보센터',
                    'url': None,
                    'collected_at': collected_at,
                },
                'related_laws': [asdict(r) for r in related_laws],
                'effective_date': effective_date,
                'metadata': {
                    **base_metadata,
                    'chunk_type': 'core',
                },
            }
            f_out.write(json.dumps(core_doc, ensure_ascii=False) + '\n')

            # Reason 청크: 이유가 300자 이상일 때만 별도 분리
            if reason and len(reason) > 300:
                question_preview = question[:150] + '...' if len(question) > 150 else question
                reason_content = (
                    f"[{title}]\n"
                    f"질의: {question_preview}\n\n"
                    f"이유:\n{reason}"
                )
                reason_doc = {
                    'id': f"INTERP_{item_id}_reason",
                    'type': 'interpretation',
                    'domain': domain,
                    'title': f"{title} (이유)",
                    'content': reason_content,
                    'source': {
                        'name': '국가법령정보센터',
                        'url': None,
                        'collected_at': collected_at,
                    },
                    'related_laws': [asdict(r) for r in related_laws],
                    'effective_date': effective_date,
                    'metadata': {
                        **base_metadata,
                        'chunk_type': 'reason',
                        'parent_id': f"INTERP_{item_id}",
                    },
                }
                f_out.write(json.dumps(reason_doc, ensure_ascii=False) + '\n')
                reason_chunks += 1

            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            processed += 1

            if processed % 2000 == 0:
                print(f"    처리 중: {processed:,}개")
    finally:
        f_rag.close()
        f_etc.close()

    rag_count = sum(v for k, v in domain_counts.items() if k != "etc")
    etc_count = domain_counts.get("etc", 0)

    print(f"\n  [완료] 해석례: {processed:,}개 (reason 청크: {reason_chunks:,}개)")
    print(f"  [저장] {law_dir / 'interpretations.jsonl'} ({rag_count:,}개, RAG 관련)")
    print(f"  [저장] {law_dir / 'interpretations_etc.jsonl'} ({etc_count:,}개, 기타)")

    print_filtering_stats(processed, domain_counts, "법령해석례")

    return processed


# ============================================================================
# 판례 처리
# ============================================================================

def process_court_cases(input_path: Path, output_dir: Path, category: str) -> int:
    """판례 전처리 (summary/detail 분리)

    판례 1건을 2개 JSONL 레코드로 분리:
    - CASE_{id}_summary: 사건명 + 판시사항 + 판결요지
    - CASE_{id}_detail: 사건명 + 판례내용 전문 (하드커트 없음, full_text가 있을 때만)
    """
    print(f"\n{'='*60}")
    print(f"[판례 처리] {input_path.name} ({category}, summary/detail 분리)")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 판례 수: {len(items):,}개")

    law_dir = output_dir / "law"
    law_dir.mkdir(parents=True, exist_ok=True)

    output_file = f"court_cases_{category}.jsonl"
    processed = 0
    detail_chunks = 0
    skipped = 0

    with open(law_dir / output_file, 'w', encoding='utf-8') as f:
        for item in items:
            item_id = item.get('id', '')
            case_name = item.get('case_name', '')
            case_no = item.get('case_no', '')

            if not item_id:
                continue

            if not case_name and not case_no:
                skipped += 1
                continue

            court_name = item.get('court_name', '')
            decision_date = item.get('decision_date', '')

            summary = clean_text(item.get('summary', ''))
            decision_summary = clean_text(item.get('decision_summary', ''))
            full_text = clean_text(item.get('full_text', ''))

            # 공통 헤더
            case_header = (
                f"[{case_name}]\n"
                f"사건번호: {case_no}\n"
                f"법원: {court_name}\n"
                f"선고일: {format_date(decision_date) or decision_date}"
            )

            ref_text = item.get('reference', '')
            domain = "finance_tax" if category == "tax" else "hr_labor"
            effective_date = format_date(decision_date)

            base_metadata = {
                'case_no': case_no,
                'court_name': court_name,
                'court_type': item.get('court_type', ''),
                'decision_type': item.get('decision_type', ''),
                'decision': item.get('decision', ''),
                'category': category,
                'reference': item.get('reference', ''),
            }

            # Summary 청크: 판시사항 + 판결요지 (항상 생성)
            summary_parts = [case_header, ""]
            if summary:
                summary_parts.append(f"판시사항:\n{summary}")
                summary_parts.append("")
            if decision_summary:
                summary_parts.append(f"판결요지:\n{decision_summary}")

            summary_content = '\n'.join(summary_parts)
            related_laws = extract_law_references(
                ref_text + ' ' + summary_content[:2000]
            )

            summary_doc = {
                'id': f"CASE_{item_id}_summary",
                'type': 'court_case',
                'domain': domain,
                'title': case_name,
                'content': summary_content,
                'source': {
                    'name': '국가법령정보센터',
                    'url': None,
                    'collected_at': collected_at,
                },
                'related_laws': [asdict(r) for r in related_laws],
                'effective_date': effective_date,
                'metadata': {
                    **base_metadata,
                    'chunk_type': 'summary',
                    'parent_id': f"CASE_{item_id}",
                },
            }
            f.write(json.dumps(summary_doc, ensure_ascii=False) + '\n')

            # Detail 청크: 판례내용 전문 (있을 때만, 하드커트 없음)
            if full_text:
                detail_content = f"{case_header}\n\n판례내용:\n{full_text}"

                detail_doc = {
                    'id': f"CASE_{item_id}_detail",
                    'type': 'court_case',
                    'domain': domain,
                    'title': f"{case_name} (판례내용)",
                    'content': detail_content,
                    'source': {
                        'name': '국가법령정보센터',
                        'url': None,
                        'collected_at': collected_at,
                    },
                    'related_laws': [asdict(r) for r in related_laws],
                    'effective_date': effective_date,
                    'metadata': {
                        **base_metadata,
                        'chunk_type': 'detail',
                        'parent_id': f"CASE_{item_id}",
                    },
                }
                f.write(json.dumps(detail_doc, ensure_ascii=False) + '\n')
                detail_chunks += 1

            processed += 1

            if processed % 1000 == 0:
                print(f"    처리 중: {processed:,}개")

    print(f"\n  [완료] 판례: {processed:,}개 (detail 청크: {detail_chunks:,}개)")
    if skipped > 0:
        print(f"  [스킵] 빈 데이터 (case_name, case_no 모두 없음): {skipped:,}개")
    print(f"  [저장] {law_dir / output_file}")

    return processed


# ============================================================================
# 메인
# ============================================================================

def main():
    print("=" * 70)
    print("법령 데이터 전처리 파이프라인 (도메인 필터링)")
    print("=" * 70)
    print(f"입력: {INPUT_DIR}")
    print(f"출력: {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. 법령 처리 (필터링 적용)
    laws_input = INPUT_DIR / "01_laws_full.json"
    if laws_input.exists():
        law_lookup = process_laws(laws_input, OUTPUT_DIR)
        results['laws'] = len(law_lookup)
    else:
        print(f"\n  [경고] 법령 파일 없음: {laws_input}")

    # 2. 법령해석례 처리 (필터링 적용)
    interp_input = INPUT_DIR / "expc_전체.json"
    if interp_input.exists():
        results['interpretations'] = process_interpretations(interp_input, OUTPUT_DIR)
    else:
        print(f"\n  [경고] 해석례 파일 없음: {interp_input}")

    # 3. 판례 처리 - 세무/회계
    tax_case_input = INPUT_DIR / "prec_tax_accounting.json"
    if tax_case_input.exists():
        results['court_cases_tax'] = process_court_cases(tax_case_input, OUTPUT_DIR, "tax")

    # 4. 판례 처리 - 노무/근로
    labor_case_input = INPUT_DIR / "prec_labor.json"
    if labor_case_input.exists():
        results['court_cases_labor'] = process_court_cases(labor_case_input, OUTPUT_DIR, "labor")

    # 결과 요약
    print("\n" + "=" * 70)
    print("전처리 완료")
    print("=" * 70)

    total = 0
    for name, count in results.items():
        print(f"  - {name}: {count:,}개")
        total += count

    print(f"\n  총 문서 수: {total:,}개")
    print(f"  출력 폴더: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
