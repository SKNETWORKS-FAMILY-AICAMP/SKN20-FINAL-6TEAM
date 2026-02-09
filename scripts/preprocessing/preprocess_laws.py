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

def process_laws(input_path: Path, output_dir: Path) -> Dict[str, str]:
    """법령 전처리 -> laws_full.jsonl (RAG) + laws_etc.jsonl (기타) + law_lookup.json"""
    print(f"\n{'='*60}")
    print(f"[법령 처리] {input_path.name}")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    laws = data.get('laws', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 법령 수: {len(laws):,}개")

    # 출력 디렉토리 생성
    law_dir = output_dir / "law"
    law_dir.mkdir(parents=True, exist_ok=True)

    law_lookup = {}
    domain_counts: Dict[str, int] = {}
    processed = 0

    f_rag = open(law_dir / "laws_full.jsonl", 'w', encoding='utf-8')
    f_etc = open(law_dir / "laws_etc.jsonl", 'w', encoding='utf-8')

    try:
        for law in laws:
            law_id = law.get('law_id', '')
            name = law.get('name', '')

            if not law_id or not name:
                continue

            # 조문 통합하여 content 생성
            content_parts = [f"[{name}]"]
            content_parts.append(f"소관부처: {law.get('ministry', '')}")
            content_parts.append(f"시행일: {format_date(law.get('enforcement_date', '')) or '미상'}")
            content_parts.append("")

            articles = law.get('articles', [])
            for article in articles:
                article_num = article.get('number', '')
                article_title = article.get('title', '')
                article_content = article.get('content', '')

                if '삭제' in article_content and len(article_content) < 30:
                    continue

                if article_title:
                    content_parts.append(f"제{article_num}조 ({article_title})")
                content_parts.append(clean_text(article_content))

                for clause in article.get('clauses', []):
                    clause_content = clause.get('content', '')
                    if clause_content:
                        content_parts.append(clean_text(clause_content))
                    for item in clause.get('items', []):
                        item_content = item.get('content', '')
                        if item_content:
                            content_parts.append(f"  {clean_text(item_content)}")

                content_parts.append("")

            content = '\n'.join(content_parts)
            ministry = law.get('ministry', '')
            domain = classify_domain(content, ministry)

            # 필터 메서드 기록
            if ministry:
                for org_name in ORG_DOMAIN_MAP:
                    if org_name in ministry:
                        filter_method = "org_mapping"
                        filter_reason = f"소관부처: {ministry}"
                        break
                else:
                    filter_method = "keyword" if domain != "etc" else "none"
                    filter_reason = f"키워드 매칭" if domain != "etc" else "매칭 없음"
            else:
                filter_method = "keyword" if domain != "etc" else "none"
                filter_reason = f"키워드 매칭" if domain != "etc" else "매칭 없음"

            doc = {
                'id': f"LAW_{law_id}",
                'type': 'law',
                'domain': domain,
                'title': name,
                'content': content,
                'source': {
                    'name': '국가법령정보센터',
                    'url': f"https://law.go.kr/법령/{name}",
                    'collected_at': collected_at
                },
                'related_laws': [],
                'effective_date': format_date(law.get('enforcement_date', '')),
                'metadata': {
                    'law_id': law_id,
                    'ministry': ministry,
                    'enforcement_date': law.get('enforcement_date', ''),
                    'article_count': len(articles),
                    'filter_method': filter_method,
                    'filter_reason': filter_reason,
                }
            }

            line = json.dumps(doc, ensure_ascii=False) + '\n'
            if domain != "etc":
                f_rag.write(line)
            else:
                f_etc.write(line)

            law_lookup[name] = law_id
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            processed += 1

            if processed % 1000 == 0:
                print(f"    처리 중: {processed:,}개")
    finally:
        f_rag.close()
        f_etc.close()

    # law_lookup.json 저장 (전체 법령)
    with open(law_dir / "law_lookup.json", 'w', encoding='utf-8') as f:
        json.dump(law_lookup, f, ensure_ascii=False, indent=2)

    rag_count = sum(v for k, v in domain_counts.items() if k != "etc")
    etc_count = domain_counts.get("etc", 0)

    print(f"\n  [완료] 법령: {processed:,}개")
    print(f"  [저장] {law_dir / 'laws_full.jsonl'} ({rag_count:,}개, RAG 관련)")
    print(f"  [저장] {law_dir / 'laws_etc.jsonl'} ({etc_count:,}개, 기타)")
    print(f"  [저장] {law_dir / 'law_lookup.json'} ({len(law_lookup):,}개)")

    print_filtering_stats(processed, domain_counts, "법령")

    return law_lookup


# ============================================================================
# 법령해석례 처리 (필터링 적용)
# ============================================================================

def process_interpretations(input_path: Path, output_dir: Path) -> int:
    """법령해석례 전처리 -> interpretations.jsonl (RAG) + interpretations_etc.jsonl (기타)"""
    print(f"\n{'='*60}")
    print(f"[법령해석례 처리] {input_path.name}")
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

            content = f"[{title}]\n\n"
            content += f"질의요지:\n{question}\n\n"
            content += f"회답:\n{answer}"
            if reason:
                content += f"\n\n이유:\n{reason}"

            related_laws = extract_law_references(content)
            answer_org = item.get('answer_org', '')
            domain = classify_domain(content, answer_org)

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

            doc = {
                'id': f"INTERP_{item_id}",
                'type': 'interpretation',
                'domain': domain,
                'title': title,
                'content': content,
                'source': {
                    'name': '국가법령정보센터',
                    'url': None,
                    'collected_at': collected_at
                },
                'related_laws': [asdict(r) for r in related_laws],
                'effective_date': format_date(item.get('answer_date', '')),
                'metadata': {
                    'case_no': item.get('case_no', ''),
                    'answer_date': item.get('answer_date', ''),
                    'answer_org': answer_org,
                    'question_org': item.get('question_org', ''),
                    'filter_method': filter_method,
                    'filter_reason': filter_reason,
                }
            }

            line = json.dumps(doc, ensure_ascii=False) + '\n'
            if domain != "etc":
                f_rag.write(line)
            else:
                f_etc.write(line)

            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            processed += 1

            if processed % 2000 == 0:
                print(f"    처리 중: {processed:,}개")
    finally:
        f_rag.close()
        f_etc.close()

    rag_count = sum(v for k, v in domain_counts.items() if k != "etc")
    etc_count = domain_counts.get("etc", 0)

    print(f"\n  [완료] 해석례: {processed:,}개")
    print(f"  [저장] {law_dir / 'interpretations.jsonl'} ({rag_count:,}개, RAG 관련)")
    print(f"  [저장] {law_dir / 'interpretations_etc.jsonl'} ({etc_count:,}개, 기타)")

    print_filtering_stats(processed, domain_counts, "법령해석례")

    return processed


# ============================================================================
# 판례 처리
# ============================================================================

def process_court_cases(input_path: Path, output_dir: Path, category: str) -> int:
    """판례 전처리"""
    print(f"\n{'='*60}")
    print(f"[판례 처리] {input_path.name} ({category})")
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

            content = f"[{case_name}]\n"
            content += f"사건번호: {case_no}\n"
            content += f"법원: {court_name}\n"
            content += f"선고일: {format_date(decision_date) or decision_date}\n\n"

            if summary:
                content += f"판시사항:\n{summary}\n\n"
            if decision_summary:
                content += f"판결요지:\n{decision_summary}\n\n"
            if full_text:
                if len(full_text) > 5000:
                    content += f"판례내용 (일부):\n{full_text[:5000]}..."
                else:
                    content += f"판례내용:\n{full_text}"

            ref_text = item.get('reference', '')
            related_laws = extract_law_references(ref_text + ' ' + content[:2000])

            domain = "finance_tax" if category == "tax" else "hr_labor"

            doc = {
                'id': f"CASE_{item_id}",
                'type': 'court_case',
                'domain': domain,
                'title': case_name,
                'content': content,
                'source': {
                    'name': '국가법령정보센터',
                    'url': None,
                    'collected_at': collected_at
                },
                'related_laws': [asdict(r) for r in related_laws],
                'effective_date': format_date(decision_date),
                'metadata': {
                    'case_no': case_no,
                    'court_name': court_name,
                    'court_type': item.get('court_type', ''),
                    'decision_type': item.get('decision_type', ''),
                    'decision': item.get('decision', ''),
                    'category': category,
                    'reference': item.get('reference', '')
                }
            }

            f.write(json.dumps(doc, ensure_ascii=False) + '\n')
            processed += 1

            if processed % 1000 == 0:
                print(f"    처리 중: {processed:,}개")

    print(f"\n  [완료] 판례: {processed:,}개")
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
