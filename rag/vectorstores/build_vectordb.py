#!/usr/bin/env python3
"""Bizi RAG 시스템의 VectorDB 빌드 스크립트.

이 스크립트는 전처리된 데이터를 ChromaDB에 임베딩하여 저장합니다.
모든 컬렉션은 하나의 ChromaDB 인스턴스에 저장됩니다.

사용법 (rag/ 디렉토리에서 .venv 활성화 후):
    # 가상환경 활성화
    source .venv/bin/activate  # macOS/Linux
    # 또는: .venv\\Scripts\\activate  # Windows

    # 전체 데이터베이스 빌드
    python -m vectorstores.build_vectordb --all

    # 특정 도메인만 빌드
    python -m vectorstores.build_vectordb --domain startup_funding

    # 강제 재빌드 (기존 데이터 삭제 후 재생성)
    python -m vectorstores.build_vectordb --all --force

    # 통계 확인
    python -m vectorstores.build_vectordb --stats
"""

import argparse
import sys
from pathlib import Path

# 상위 디렉토리를 path에 추가하여 import 가능하게 함
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from vectorstores.chroma import ChromaVectorStore
from vectorstores.config import COLLECTION_NAMES
from vectorstores.loader import DataLoader


def main():
    """메인 진입점."""
    # 환경변수 로드
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Bizi RAG 시스템의 VectorDB를 빌드합니다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
    # 전체 데이터베이스 빌드
    python -m vectorstores.build_vectordb --all

    # 특정 도메인만 빌드
    python -m vectorstores.build_vectordb --domain startup_funding

    # 강제 재빌드
    python -m vectorstores.build_vectordb --all --force

    # 통계 확인
    python -m vectorstores.build_vectordb --stats
        """,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 벡터 데이터베이스 빌드",
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=list(COLLECTION_NAMES.keys()),
        help="특정 도메인만 빌드 (startup_funding, finance_tax, hr_labor, law_common)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="강제 재빌드 (기존 데이터 삭제 후 재생성)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="모든 데이터베이스 통계 표시",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 임베딩/저장 없이 로드+청킹 통계만 출력",
    )

    args = parser.parse_args()

    # 인자 유효성 검사
    if not any([args.all, args.domain, args.stats, args.dry_run]):
        parser.print_help()
        sys.exit(1)

    # dry-run 모드
    if args.dry_run:
        _run_dry_run(args)
        return

    # 벡터 스토어 초기화
    store = ChromaVectorStore()

    # 통계 표시
    if args.stats:
        print("\n" + "=" * 60)
        print("VectorDB 통계")
        print("=" * 60)

        stats = store.get_all_stats()
        total_docs = 0
        for domain, domain_stats in stats.items():
            print(f"\n{domain}:")
            if "error" in domain_stats:
                print(f"  오류: {domain_stats['error']}")
            else:
                print(f"  컬렉션: {domain_stats['name']}")
                print(f"  문서 수: {domain_stats['count']}")
                total_docs += domain_stats['count']

        print(f"\n{'=' * 60}")
        print(f"총 문서 수: {total_docs}")
        return

    # 데이터베이스 빌드
    if args.all:
        print("\n" + "=" * 60)
        print("전체 VectorDB 빌드 시작")
        print("=" * 60)

        results = store.build_all_vectordbs(force_rebuild=args.force)

        print("\n" + "=" * 60)
        print("빌드 요약")
        print("=" * 60)
        for domain, count in results.items():
            print(f"  {domain}: {count}개 문서")

        total = sum(results.values())
        print(f"\n  총합: {total}개 문서")

    elif args.domain:
        print(f"\n{args.domain} 빌드 중...")
        count = store.build_vectordb(args.domain, force_rebuild=args.force)
        print(f"\n완료: {count}개 문서")


def _run_dry_run(args: argparse.Namespace) -> None:
    """실제 임베딩 없이 로드+청킹 통계만 출력합니다.

    Args:
        args: argparse 네임스페이스 (--all 또는 --domain 포함)
    """
    loader = DataLoader()

    domains: list[str] = []
    if args.all:
        domains = list(COLLECTION_NAMES.keys())
    elif args.domain:
        domains = [args.domain]
    else:
        domains = list(COLLECTION_NAMES.keys())

    print("\n" + "=" * 60)
    print("[DRY-RUN] 로드 + 청킹 통계 (임베딩 없음)")
    print("=" * 60)

    grand_total = 0
    for domain in domains:
        collection_name = COLLECTION_NAMES[domain]
        print(f"\n{domain} 빌드 시뮬레이션...")

        file_stats = loader.get_file_stats(domain)
        domain_total = 0
        for file_name, count in file_stats.items():
            print(f"  {file_name:<40} → {count:>6,}건")
            domain_total += count

        print(f"  {'합계':<40}   {domain_total:>6,}건 → {collection_name}")
        grand_total += domain_total

    print(f"\n{'=' * 60}")
    print(f"전체 합계: {grand_total:,}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
