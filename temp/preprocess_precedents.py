"""
법령해석례 JSON 전처리 스크립트
- 대상 파일: D:\p.pp\data\law\expc_전체.json
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

    # 1. 과도한 줄바꿈 제거 (3개 이상 -> 2개)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 2. 연속 공백 제거
    text = re.sub(r'[ \t]+', ' ', text)

    # 3. 줄 앞뒤 공백 제거
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # 4. 전각문자 정규화
    text = text.replace('\u3000', ' ')  # 전각 공백
    text = text.replace('ㆍ', '·')  # 가운데점
    text = text.replace('？', '?')  # 전각 물음표 -> 반각 물음표

    # 5. 앞뒤 공백 제거
    text = text.strip()

    return text


def clean_reason(reason: str) -> str:
    """이유(reason) 필드 정제 - ○ 기호 처리"""
    if not reason:
        return ""

    # 기본 텍스트 정제 적용
    reason = clean_text(reason)

    # ○ 기호를 문단 구분자로 정리 (줄바꿈 + ○ -> 새 문단)
    reason = re.sub(r'\n\s*○\s*', '\n\n• ', reason)

    # 문서 시작의 ○ 처리
    if reason.startswith('○'):
        reason = '• ' + reason[1:].strip()

    return reason


def handle_missing_value(value: str, default: str = "미상") -> str:
    """결측값 처리"""
    if value is None or value.strip() == "":
        return default
    return value.strip()


def format_date(date_str: str) -> str:
    """날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)"""
    if not date_str or len(date_str) != 8:
        return "미상"
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
        return "미상"


def create_embedding_text(item: dict) -> str:
    """임베딩용 텍스트 생성"""
    title = clean_text(item.get('title', ''))
    question = clean_text(item.get('question_summary', ''))
    answer = clean_text(item.get('answer', ''))

    # 기본 형식: [제목] + 질의 + 회답
    text = f"[{title}]\n질의: {question}\n회답: {answer}"

    return text


def create_full_text(item: dict) -> str:
    """전체 텍스트 생성 (reason 포함)"""
    title = clean_text(item.get('title', ''))
    question = clean_text(item.get('question_summary', ''))
    answer = clean_text(item.get('answer', ''))
    reason = clean_reason(item.get('reason', ''))

    text = f"[{title}]\n\n질의요지:\n{question}\n\n회답:\n{answer}"

    if reason:
        text += f"\n\n이유:\n{reason}"

    return text


def extract_metadata(item: dict) -> dict:
    """메타데이터 추출"""
    return {
        "source": "법령해석례",
        "doc_type": "법령해석례",
        "precedent_id": item.get('id', ''),
        "case_no": item.get('case_no', ''),
        "title": clean_text(item.get('title', '')),
        "answer_date": format_date(item.get('answer_date', '')),
        "answer_org": handle_missing_value(item.get('answer_org', '')),
        "question_org": handle_missing_value(item.get('question_org', '')),
    }


def process_precedent_file(input_path: Path, output_path: Path) -> dict:
    """법령해석례 파일 전처리"""
    print(f"\n처리 중: {input_path.name}")
    print(f"파일 크기: {input_path.stat().st_size / (1024*1024):.1f} MB")

    # JSON 로드
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_type = data.get('type', '법령해석례')
    org = data.get('org', '전체')
    items = data.get('items', [])

    print(f"  - 문서유형: {doc_type}")
    print(f"  - 기관: {org}")
    print(f"  - 총 항목 수: {len(items)}")

    # 통계
    stats = {
        "total": len(items),
        "processed": 0,
        "empty_answer_date": 0,
        "empty_question_org": 0,
        "long_reason": 0,  # 3000자 초과
        "skipped": 0,
    }

    chunks = []

    for item in items:
        # 필수 필드 확인
        if not item.get('question_summary') and not item.get('answer'):
            stats["skipped"] += 1
            continue

        # 결측값 통계
        if not item.get('answer_date', '').strip():
            stats["empty_answer_date"] += 1
        if not item.get('question_org', '').strip():
            stats["empty_question_org"] += 1

        reason = item.get('reason', '')
        if len(reason) > 3000:
            stats["long_reason"] += 1

        # 청크 생성
        chunk_id = f"expc_{item.get('id', '')}"

        chunk = {
            "id": chunk_id,
            "text": create_embedding_text(item),
            "full_text": create_full_text(item),
            "metadata": extract_metadata(item)
        }

        chunks.append(chunk)
        stats["processed"] += 1

    # JSONL 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

    print(f"  - 처리 완료: {stats['processed']}개")
    print(f"  - 스킵됨 (필수필드 없음): {stats['skipped']}개")
    print(f"  - 결측값 - answer_date: {stats['empty_answer_date']}개, question_org: {stats['empty_question_org']}개")
    print(f"  - 긴 reason(3000자+): {stats['long_reason']}개")
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
    ranges = [(0, 500), (500, 1000), (1000, 1500), (1500, 2000), (2000, 3000), (3000, float('inf'))]
    print("\n  청크 크기 분포:")
    for low, high in ranges:
        count = sum(1 for s in sizes if low <= s < high)
        pct = count / total * 100
        high_str = f"{high}" if high != float('inf') else "+"
        print(f"    {low:>5} - {high_str:<5}: {count:>6}개 ({pct:>5.1f}%)")


def main():
    """메인 실행 함수"""
    # 입력/출력 경로 설정
    input_path = Path("D:/p.pp/data/law/expc_전체.json")
    output_path = Path("D:/p.pp/data/law/expc_chunks.jsonl")

    print("=" * 60)
    print("법령해석례 전처리 시작")
    print(f"입력: {input_path}")
    print(f"출력: {output_path}")
    print("=" * 60)

    if not input_path.exists():
        print(f"[오류] 파일 없음: {input_path}")
        return

    # 전처리 실행
    stats = process_precedent_file(input_path, output_path)

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
