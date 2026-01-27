#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
법령 데이터 전처리기

data_pipeline.md / happy-tinkering-toucan.md 기반
- 법령 (01_laws_full.json) → laws/laws_full.jsonl + law_lookup.json
- 법령해석례 (expc_전체.json) → interpretations/interpretations.jsonl
- 판례 (prec_*.json) → court_cases/*.jsonl

통일 스키마:
{
  "id": "LAW_xxx | INTERP_xxx | CASE_xxx",
  "type": "law | interpretation | court_case",
  "domain": "legal | tax | labor | startup | funding",
  "title": "string",
  "content": "string",
  "source": {"name": "string", "url": "string?", "collected_at": "string?"},
  "related_laws": [{"law_id": "string?", "law_name": "string", "article_ref": "string?"}],
  "effective_date": "YYYY-MM-DD?",
  "metadata": {}
}
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict


# ============================================================================
# 경로 설정
# ============================================================================

INPUT_DIR = Path("D:/f.pp/law-raw")
OUTPUT_DIR = Path("D:/f.pp/final_files/data/processed")


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
# 도메인 분류
# ============================================================================

DOMAIN_KEYWORDS = {
    "tax": ["세법", "소득세", "법인세", "부가가치세", "국세", "세금", "세무", "조특법", "세액", "과세", "납세", "상속세", "증여세"],
    "labor": ["근로", "노동", "고용", "임금", "퇴직", "해고", "휴가", "4대보험", "산재", "근로기준", "최저임금"],
    "startup": ["사업자", "창업", "법인설립", "업종", "인허가", "벤처", "중소기업", "소상공인"],
    "funding": ["지원사업", "보조금", "정책자금", "공고", "융자"],
}

ORG_DOMAIN_MAP = {
    "국세청": "tax",
    "기획재정부": "tax",
    "고용노동부": "labor",
    "중소벤처기업부": "startup",
    "공정거래위원회": "legal",
    "법제처": "legal",
}


def classify_domain(text: str, org: str = None) -> str:
    """도메인 자동 분류"""
    if org:
        for org_name, domain in ORG_DOMAIN_MAP.items():
            if org_name in org:
                return domain

    combined = text.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                scores[domain] += 1

    max_domain = max(scores, key=scores.get)
    return max_domain if scores[max_domain] > 0 else "legal"


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
    """YYYYMMDD → YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
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
                law_id=None,  # 바인딩 단계에서 채움
                law_name=law_name,
                article_ref=article_ref
            ))

    return references


# ============================================================================
# 법령 처리
# ============================================================================

def process_laws(input_path: Path, output_dir: Path) -> Dict[str, str]:
    """법령 전처리 → laws_full.jsonl + law_lookup.json"""
    print(f"\n{'='*60}")
    print(f"[법령 처리] {input_path.name}")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    laws = data.get('laws', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 법령 수: {len(laws):,}개")

    # 출력 디렉토리 생성
    laws_dir = output_dir / "laws"
    laws_dir.mkdir(parents=True, exist_ok=True)

    law_lookup = {}  # 법령명 → law_id
    processed = 0

    with open(laws_dir / "laws_full.jsonl", 'w', encoding='utf-8') as f:
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
            domain = classify_domain(content, law.get('ministry', ''))

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
                    'ministry': law.get('ministry', ''),
                    'enforcement_date': law.get('enforcement_date', ''),
                    'article_count': len(articles)
                }
            }

            f.write(json.dumps(doc, ensure_ascii=False) + '\n')
            law_lookup[name] = law_id
            processed += 1

            if processed % 1000 == 0:
                print(f"    처리 중: {processed:,}개")

    # law_lookup.json 저장
    with open(laws_dir / "law_lookup.json", 'w', encoding='utf-8') as f:
        json.dump(law_lookup, f, ensure_ascii=False, indent=2)

    print(f"\n  [완료] 법령: {processed:,}개")
    print(f"  [저장] {laws_dir / 'laws_full.jsonl'}")
    print(f"  [저장] {laws_dir / 'law_lookup.json'} ({len(law_lookup):,}개)")

    return law_lookup


# ============================================================================
# 법령해석례 처리
# ============================================================================

def process_interpretations(input_path: Path, output_dir: Path) -> int:
    """법령해석례 전처리"""
    print(f"\n{'='*60}")
    print(f"[법령해석례 처리] {input_path.name}")
    print(f"{'='*60}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    collected_at = data.get('collected_at', '')
    print(f"  총 해석례 수: {len(items):,}개")

    interp_dir = output_dir / "interpretations"
    interp_dir.mkdir(parents=True, exist_ok=True)

    processed = 0

    with open(interp_dir / "interpretations.jsonl", 'w', encoding='utf-8') as f:
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
                    'question_org': item.get('question_org', '')
                }
            }

            f.write(json.dumps(doc, ensure_ascii=False) + '\n')
            processed += 1

            if processed % 2000 == 0:
                print(f"    처리 중: {processed:,}개")

    print(f"\n  [완료] 해석례: {processed:,}개")
    print(f"  [저장] {interp_dir / 'interpretations.jsonl'}")

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

    cases_dir = output_dir / "court_cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    output_file = f"court_cases_{category}.jsonl"
    processed = 0

    with open(cases_dir / output_file, 'w', encoding='utf-8') as f:
        for item in items:
            item_id = item.get('id', '')
            case_name = item.get('case_name', '')

            if not item_id:
                continue

            case_no = item.get('case_no', '')
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

            domain = "tax" if category == "tax" else "labor"

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
    print(f"  [저장] {cases_dir / output_file}")

    return processed


# ============================================================================
# 메인
# ============================================================================

def main():
    print("=" * 70)
    print("법령 데이터 전처리 파이프라인")
    print("=" * 70)
    print(f"입력: {INPUT_DIR}")
    print(f"출력: {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. 법령 처리
    laws_input = INPUT_DIR / "01_laws_full.json"
    if laws_input.exists():
        law_lookup = process_laws(laws_input, OUTPUT_DIR)
        results['laws'] = len(law_lookup)

    # 2. 법령해석례 처리
    interp_input = INPUT_DIR / "expc_전체.json"
    if interp_input.exists():
        results['interpretations'] = process_interpretations(interp_input, OUTPUT_DIR)

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
