"""
법률 JSON 전처리 스크립트
- 대상 파일: 01_laws_full.json
- 출력 형식: JSONL (RAG용)
- 청킹 전략: 하이브리드 (조문 단위 기본, 1500자 초과시 항 단위 분할)
- 삭제된 조항 제외
"""

import json
import re
from pathlib import Path
from typing import Generator, Tuple


# 청킹 설정
MAX_ARTICLE_LENGTH = 1500  # 조문 최대 길이 (초과시 항 단위 분할)

# 삭제된 조항 패턴 (예: "삭제 <2016.2.3>", "삭제<2020.1.1>")
DELETED_PATTERN = re.compile(r'^\s*삭제\s*<\d{4}\.\d{1,2}\.\d{1,2}>\s*$')


def is_deleted(content: str) -> bool:
    """삭제된 조항인지 확인"""
    if not content:
        return True

    content = content.strip()

    # 앞에 붙는 번호/조항 표시 제거
    # 예: "1.", "①", "제4조", "제6조의2" 등
    content_without_num = re.sub(
        r'^(?:[\d①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]+[\.\s]*|제\d+조(?:의\d+)?\s*)',
        '',
        content
    )

    return bool(DELETED_PATTERN.match(content_without_num))


def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""

    # 1. 연속된 줄바꿈 정리 (3개 이상 -> 2개)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 2. 연속 공백 제거 (탭 포함)
    text = re.sub(r'[ \t]+', ' ', text)

    # 3. 줄 앞뒤 공백 제거
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # 4. 특수문자 정규화
    text = text.replace('\u3000', ' ')  # 전각 공백
    text = text.replace('ㆍ', '·')  # 가운데점
    text = text.replace('･', '·')  # 반각 가운데점

    # 5. 앞뒤 공백 제거
    text = text.strip()

    return text


def format_date(date_str: str) -> str:
    """날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)"""
    if not date_str or len(date_str) != 8:
        return date_str or ""
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
        return date_str


def build_article_content(article: dict) -> Tuple[str, int]:
    """조문 전체 내용 구성 (항, 호 포함), 삭제된 항목 제외

    Returns:
        Tuple[str, int]: (구성된 텍스트, 삭제된 항목 수)
    """
    parts = []
    deleted_count = 0

    # 조문 본문
    content = article.get('content', '')
    if content and not is_deleted(content):
        parts.append(clean_text(content))
    elif is_deleted(content):
        deleted_count += 1

    # 항(clauses) 처리
    clauses = article.get('clauses', [])
    for clause in clauses:
        clause_content = clause.get('content', '')

        # 삭제된 항 제외
        if is_deleted(clause_content):
            deleted_count += 1
            continue

        clause_num = clause.get('number', '')
        if clause_content:
            parts.append(f"{clause_num} {clean_text(clause_content)}")

        # 호(items) 처리
        items = clause.get('items', [])
        for item in items:
            item_content = item.get('content', '')

            # 삭제된 호 제외
            if is_deleted(item_content):
                deleted_count += 1
                continue

            item_num = item.get('number', '')
            if item_content:
                parts.append(f"  {item_num} {clean_text(item_content)}")

    return '\n'.join(parts), deleted_count


def build_clause_content(clause: dict) -> Tuple[str, int]:
    """항 단위 내용 구성, 삭제된 항목 제외

    Returns:
        Tuple[str, int]: (구성된 텍스트, 삭제된 항목 수)
    """
    parts = []
    deleted_count = 0

    clause_num = clause.get('number', '')
    clause_content = clause.get('content', '')

    # 삭제된 항이면 빈 문자열 반환
    if is_deleted(clause_content):
        return '', 1

    if clause_content:
        parts.append(f"{clause_num} {clean_text(clause_content)}")

    # 호(items) 처리
    items = clause.get('items', [])
    for item in items:
        item_content = item.get('content', '')

        # 삭제된 호 제외
        if is_deleted(item_content):
            deleted_count += 1
            continue

        item_num = item.get('number', '')
        if item_content:
            parts.append(f"  {item_num} {clean_text(item_content)}")

    return '\n'.join(parts), deleted_count


def create_article_chunk(law: dict, article: dict, article_idx: int, full_content: str) -> dict:
    """조문 단위 청크 생성

    Args:
        law: 법률 정보
        article: 조문 정보
        article_idx: 조문 순차 인덱스 (고유성 보장용)
        full_content: 조문 전체 내용
    """
    law_name = law.get('name', '')
    article_num = article.get('number', '')
    article_title = article.get('title', '')

    # 임베딩용 텍스트
    if article_title:
        text = f"[{law_name}] 제{article_num}조({article_title})\n{full_content}"
    else:
        text = f"[{law_name}] 제{article_num}조\n{full_content}"

    # 청크 ID (article_idx로 고유성 보장)
    chunk_id = f"law_{law.get('law_id', '')}_{article_idx}_{article_num}"

    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "source": "law",
            "doc_type": "현행법령",
            "law_id": law.get('law_id', ''),
            "law_name": law_name,
            "ministry": law.get('ministry', ''),
            "enforcement_date": format_date(law.get('enforcement_date', '')),
            "article_num": article_num,
            "article_title": article_title,
            "chunk_type": "article"
        }
    }


def create_clause_chunk(law: dict, article: dict, article_idx: int, clause: dict, clause_idx: int, clause_content: str) -> dict:
    """항 단위 청크 생성

    Args:
        law: 법률 정보
        article: 조문 정보
        article_idx: 조문 순차 인덱스 (고유성 보장용)
        clause: 항 정보
        clause_idx: 항 순차 인덱스
        clause_content: 항 내용
    """
    law_name = law.get('name', '')
    article_num = article.get('number', '')
    article_title = article.get('title', '')
    clause_num = clause.get('number', '')

    # 임베딩용 텍스트 (상위 조문 정보 포함)
    if article_title:
        text = f"[{law_name}] 제{article_num}조({article_title}) {clause_num}\n{clause_content}"
    else:
        text = f"[{law_name}] 제{article_num}조 {clause_num}\n{clause_content}"

    # 청크 ID (article_idx로 고유성 보장)
    chunk_id = f"law_{law.get('law_id', '')}_{article_idx}_{article_num}_c{clause_idx}"

    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "source": "law",
            "doc_type": "현행법령",
            "law_id": law.get('law_id', ''),
            "law_name": law_name,
            "ministry": law.get('ministry', ''),
            "enforcement_date": format_date(law.get('enforcement_date', '')),
            "article_num": article_num,
            "article_title": article_title,
            "clause_num": clause_num,
            "chunk_type": "clause"
        }
    }


def process_law(law: dict) -> Generator[Tuple[dict, int], None, None]:
    """단일 법률 처리 - 하이브리드 청킹

    Yields:
        Tuple[dict, int]: (청크, 삭제된 항목 수)
    """
    articles = law.get('articles', [])

    for article_idx, article in enumerate(articles, start=1):
        # 조문 전체 내용 구성 (삭제된 항목 제외)
        full_content, deleted_count = build_article_content(article)

        # 조문 전체가 삭제된 경우 스킵
        if not full_content.strip():
            yield None, deleted_count
            continue

        # 길이 체크 - 하이브리드 청킹
        if len(full_content) <= MAX_ARTICLE_LENGTH:
            # 조문 단위 청킹
            yield create_article_chunk(law, article, article_idx, full_content), deleted_count
        else:
            # 항 단위 분할
            clauses = article.get('clauses', [])

            if not clauses:
                # 항이 없으면 조문 전체로 청킹 (긴 경우에도)
                yield create_article_chunk(law, article, article_idx, full_content), deleted_count
            else:
                # 각 항을 개별 청크로
                first_yield = True
                for idx, clause in enumerate(clauses, start=1):
                    clause_content, clause_deleted = build_clause_content(clause)
                    if clause_content:
                        if first_yield:
                            yield create_clause_chunk(law, article, article_idx, clause, idx, clause_content), deleted_count + clause_deleted
                            first_yield = False
                        else:
                            yield create_clause_chunk(law, article, article_idx, clause, idx, clause_content), clause_deleted
                    else:
                        # 삭제된 항만 있는 경우 삭제 카운트 전달
                        if first_yield:
                            yield None, deleted_count + clause_deleted
                            first_yield = False
                        else:
                            yield None, clause_deleted


def process_laws_file(input_path: Path, output_path: Path) -> dict:
    """법률 파일 전처리 (스트리밍 방식)"""
    print(f"\n처리 중: {input_path.name}")
    print(f"파일 크기: {input_path.stat().st_size / (1024*1024):.1f} MB")

    # 통계
    stats = {
        "total_laws": 0,
        "total_articles": 0,
        "article_chunks": 0,
        "clause_chunks": 0,
        "total_chunks": 0,
        "deleted_items": 0,  # 삭제된 항목 수
        "skipped_articles": 0,  # 전체가 삭제된 조문 수
    }

    # JSON 로드 (대용량 파일)
    print("JSON 로드 중...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    laws = data.get('laws', [])
    stats["total_laws"] = len(laws)
    print(f"총 법률 수: {stats['total_laws']}개")

    # JSONL 저장
    print("청킹 및 저장 중...")
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, law in enumerate(laws):
            # 진행률 표시
            if (i + 1) % 500 == 0:
                print(f"  진행: {i + 1}/{stats['total_laws']} ({(i + 1) / stats['total_laws'] * 100:.1f}%)")

            articles = law.get('articles', [])
            stats["total_articles"] += len(articles)

            for chunk, deleted_count in process_law(law):
                stats["deleted_items"] += deleted_count

                if chunk is None:
                    stats["skipped_articles"] += 1
                    continue

                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
                stats["total_chunks"] += 1

                if chunk["metadata"]["chunk_type"] == "article":
                    stats["article_chunks"] += 1
                else:
                    stats["clause_chunks"] += 1

    print(f"\n처리 완료:")
    print(f"  - 총 법률: {stats['total_laws']}개")
    print(f"  - 총 조문: {stats['total_articles']}개")
    print(f"  - 삭제된 항목 제외: {stats['deleted_items']}개")
    print(f"  - 스킵된 조문 (전체 삭제): {stats['skipped_articles']}개")
    print(f"  - 생성된 청크: {stats['total_chunks']}개")
    print(f"    · 조문 단위: {stats['article_chunks']}개")
    print(f"    · 항 단위: {stats['clause_chunks']}개")
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
    law_dir = Path("D:/f.pp/law")
    input_path = law_dir / "01_laws_full.json"
    output_path = law_dir / "01_laws_chunks.jsonl"

    print("=" * 60)
    print("법률 데이터 전처리 시작")
    print(f"청킹 전략: 하이브리드 (조문 기본, {MAX_ARTICLE_LENGTH}자 초과시 항 분할)")
    print("=" * 60)

    if not input_path.exists():
        print(f"[오류] 파일 없음: {input_path}")
        return

    # 전처리 실행
    stats = process_laws_file(input_path, output_path)

    # 청크 분포 분석
    analyze_chunk_distribution(output_path)

    # 출력 파일 정보
    print("\n" + "=" * 60)
    print("전처리 완료")
    print("=" * 60)
    output_size = output_path.stat().st_size / (1024 * 1024)
    print(f"출력 파일: {output_path.name} ({output_size:.1f} MB)")


if __name__ == "__main__":
    main()
