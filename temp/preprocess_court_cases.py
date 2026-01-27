"""
판례 JSON 전처리 스크립트
- 대상 파일: D:\p.pp\data\court_cases\prec_tax_accounting.json
- 출력 형식: JSONL (RAG용)
"""

import json
import re
from pathlib import Path
from typing import Optional


def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""

    # 1. HTML 태그 제거 (<br/> 등)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)

    # 2. 과도한 줄바꿈 제거 (3개 이상 -> 2개)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 3. 연속 공백 제거
    text = re.sub(r'[ \t]+', ' ', text)

    # 4. 줄 앞뒤 공백 제거
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # 5. 전각문자 정규화
    text = text.replace('\u3000', ' ')  # 전각 공백
    text = text.replace('ㆍ', '·')  # 가운데점
    text = text.replace('？', '?')  # 전각 물음표 -> 반각 물음표

    # 6. 앞뒤 공백 제거
    text = text.strip()

    return text


def handle_missing_value(value: str, default: str = "미상") -> str:
    """결측값 처리"""
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def format_date(date_str: str) -> str:
    """날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)"""
    if not date_str or len(date_str) != 8:
        return "미상"
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
        return "미상"


def create_embedding_text(item: dict) -> str:
    """임베딩용 텍스트 생성 (핵심 정보 위주)"""
    case_name = clean_text(item.get('case_name', ''))
    case_no = item.get('case_no', '')
    court_name = item.get('court_name', '')
    summary = clean_text(item.get('summary', ''))
    decision_summary = clean_text(item.get('decision_summary', ''))

    # 기본 형식: [사건명] + 사건번호 + 요약
    parts = []

    if case_name:
        parts.append(f"[{case_name}]")
    if case_no:
        parts.append(f"사건번호: {case_no}")
    if court_name:
        parts.append(f"법원: {court_name}")

    # 요약이 있으면 요약 사용, 없으면 판시사항 사용
    if summary:
        parts.append(f"\n판시사항:\n{summary}")
    if decision_summary:
        parts.append(f"\n판결요지:\n{decision_summary}")

    return '\n'.join(parts)


def create_full_text(item: dict) -> str:
    """전체 텍스트 생성 (full_text 포함)"""
    case_name = clean_text(item.get('case_name', ''))
    case_no = item.get('case_no', '')
    court_name = item.get('court_name', '')
    decision_date = format_date(item.get('decision_date', ''))
    decision_type = item.get('decision_type', '')
    decision = item.get('decision', '')
    summary = clean_text(item.get('summary', ''))
    decision_summary = clean_text(item.get('decision_summary', ''))
    reference = clean_text(item.get('reference', ''))
    reference_cases = clean_text(item.get('reference_cases', ''))
    full_text = clean_text(item.get('full_text', ''))

    parts = []

    # 헤더
    if case_name:
        parts.append(f"[{case_name}]")
    if case_no:
        parts.append(f"사건번호: {case_no}")

    meta_parts = []
    if court_name:
        meta_parts.append(court_name)
    if decision_date != "미상":
        meta_parts.append(decision_date)
    if decision_type:
        meta_parts.append(decision_type)
    if decision:
        meta_parts.append(decision)
    if meta_parts:
        parts.append(" | ".join(meta_parts))

    parts.append("")  # 빈 줄

    # 판시사항
    if summary:
        parts.append("【판시사항】")
        parts.append(summary)
        parts.append("")

    # 판결요지
    if decision_summary:
        parts.append("【판결요지】")
        parts.append(decision_summary)
        parts.append("")

    # 참조조문
    if reference:
        parts.append("【참조조문】")
        parts.append(reference)
        parts.append("")

    # 참조판례
    if reference_cases:
        parts.append("【참조판례】")
        parts.append(reference_cases)
        parts.append("")

    # 전문
    if full_text:
        parts.append("【전문】")
        parts.append(full_text)

    return '\n'.join(parts)


def extract_metadata(item: dict, category: str) -> dict:
    """메타데이터 추출"""
    return {
        "source": "판례",
        "doc_type": "판례",
        "category": category,
        "precedent_id": item.get('id', ''),
        "case_name": clean_text(item.get('case_name', '')),
        "case_no": item.get('case_no', ''),
        "decision_date": format_date(item.get('decision_date', '')),
        "court_name": handle_missing_value(item.get('court_name', '')),
        "court_type": handle_missing_value(item.get('court_type', '')),
        "decision_type": handle_missing_value(item.get('decision_type', '')),
    }


def is_valid_item(item: dict) -> bool:
    """유효한 판례 항목인지 확인"""
    # 최소한 case_no나 summary, full_text 중 하나는 있어야 함
    case_no = item.get('case_no', '').strip()
    summary = item.get('summary', '').strip()
    full_text = item.get('full_text', '').strip()

    return bool(case_no or summary or full_text)


def process_court_cases_file(input_path: Path, output_path: Path) -> dict:
    """판례 파일 전처리"""
    print(f"\n처리 중: {input_path.name}")
    print(f"파일 크기: {input_path.stat().st_size / (1024*1024):.1f} MB")

    # JSON 로드
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_type = data.get('type', '판례')
    category = data.get('category', '세무/회계')
    items = data.get('items', [])

    print(f"  - 문서유형: {doc_type}")
    print(f"  - 카테고리: {category}")
    print(f"  - 총 항목 수: {len(items)}")

    # 통계
    stats = {
        "total": len(items),
        "processed": 0,
        "empty_case_no": 0,
        "empty_summary": 0,
        "empty_full_text": 0,
        "long_full_text": 0,  # 5000자 초과
        "skipped": 0,
    }

    chunks = []

    for item in items:
        # 유효하지 않은 항목 스킵
        if not is_valid_item(item):
            stats["skipped"] += 1
            continue

        # 결측값 통계
        if not item.get('case_no', '').strip():
            stats["empty_case_no"] += 1
        if not item.get('summary', '').strip():
            stats["empty_summary"] += 1
        if not item.get('full_text', '').strip():
            stats["empty_full_text"] += 1

        full_text = item.get('full_text', '')
        if len(full_text) > 5000:
            stats["long_full_text"] += 1

        # 청크 생성
        chunk_id = f"prec_{item.get('id', '')}"

        chunk = {
            "id": chunk_id,
            "text": create_embedding_text(item),
            "full_text": create_full_text(item),
            "metadata": extract_metadata(item, category)
        }

        chunks.append(chunk)
        stats["processed"] += 1

    # JSONL 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

    print(f"  - 처리 완료: {stats['processed']}개")
    print(f"  - 스킵됨 (필수필드 없음): {stats['skipped']}개")
    print(f"  - 결측값 - case_no: {stats['empty_case_no']}개, summary: {stats['empty_summary']}개, full_text: {stats['empty_full_text']}개")
    print(f"  - 긴 full_text(5000자+): {stats['long_full_text']}개")
    print(f"  - 저장: {output_path.name}")

    return stats


def analyze_chunk_distribution(output_path: Path):
    """청크 크기 분포 분석"""
    print("\n청크 크기 분포 분석 중...")

    sizes = []
    with open(output_path, 'r', encoding='utf-8') as f:
        for line in f:
            chunk = json.loads(line)
            sizes.append(len(chunk['text']))

    if not sizes:
        print("청크 없음")
        return

    sizes.sort()
    total = len(sizes)

    print(f"  - 총 청크 수: {total}")
    print(f"  - 최소: {sizes[0]}자")
    print(f"  - 최대: {sizes[-1]}자")
    print(f"  - 평균: {sum(sizes) / total:.0f}자")
    print(f"  - 중앙값: {sizes[total // 2]}자")

    # 구간별 분포
    ranges = [(0, 500), (500, 1000), (1000, 2000), (2000, 3000), (3000, 5000), (5000, float('inf'))]
    print("\n  청크 크기 분포:")
    for low, high in ranges:
        count = sum(1 for s in sizes if low <= s < high)
        pct = count / total * 100
        high_str = f"{high}" if high != float('inf') else "+"
        print(f"    {low:>5} - {high_str:<5}: {count:>6}개 ({pct:>5.1f}%)")


def main():
    """메인 실행 함수"""
    # 입력/출력 경로 설정
    input_path = Path("D:/p.pp/data/court_cases/prec_tax_accounting.json")
    output_path = Path("D:/p.pp/data/court_cases/prec_chunks.jsonl")

    print("=" * 60)
    print("판례 전처리 시작")
    print(f"입력: {input_path}")
    print(f"출력: {output_path}")
    print("=" * 60)

    if not input_path.exists():
        print(f"[오류] 파일 없음: {input_path}")
        return

    # 전처리 실행
    stats = process_court_cases_file(input_path, output_path)

    # 청크 분포 분석
    analyze_chunk_distribution(output_path)

    # 출력 파일 정보
    print("\n" + "=" * 60)
    print("전처리 완료")
    print("=" * 60)
    output_size = output_path.stat().st_size / (1024 * 1024)
    print(f"출력 파일: {output_path.name} ({output_size:.1f} MB)")
    print(f"총 청크: {stats['processed']}개")


if __name__ == "__main__":
    main()
