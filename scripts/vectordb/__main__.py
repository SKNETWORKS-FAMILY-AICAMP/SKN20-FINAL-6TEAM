#!/usr/bin/env python3
"""VectorDB 빌드 CLI.

이 스크립트는 전처리된 데이터를 ChromaDB에 임베딩하여 저장합니다.
모든 컬렉션은 하나의 ChromaDB 인스턴스에 저장됩니다.

사용법:
    # 프로젝트 루트에서 실행
    python -m scripts.vectordb --all
    python -m scripts.vectordb --domain startup_funding
    python -m scripts.vectordb --all --force
    python -m scripts.vectordb --all --resume
    python -m scripts.vectordb --stats
    python -m scripts.vectordb --dry-run

    # Docker
    docker compose --profile build up vectordb-builder
"""

import argparse
import sys
from pathlib import Path

# rag/ 모듈 참조를 위한 경로 설정
_rag_dir = Path(__file__).resolve().parent.parent.parent / "rag"
if _rag_dir.exists():
    sys.path.insert(0, str(_rag_dir))
else:
    sys.path.insert(0, "/app")  # Docker 환경

from dotenv import load_dotenv

load_dotenv()

from vectorstores.config import COLLECTION_NAMES
from .builder import VectorDBBuilder
from .loader import DataLoader


def main():
    """메인 진입점."""
    parser = argparse.ArgumentParser(
        description="Bizi RAG 시스템의 VectorDB를 빌드합니다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
    # 전체 데이터베이스 빌드
    python -m scripts.vectordb --all

    # 특정 도메인만 빌드
    python -m scripts.vectordb --domain startup_funding

    # 강제 재빌드
    python -m scripts.vectordb --all --force

    # 중단된 빌드 이어서 진행
    python -m scripts.vectordb --all --resume

    # 통계 확인
    python -m scripts.vectordb --stats
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
        "--resume",
        action="store_true",
        help="중단된 빌드를 이어서 진행 (기존 문서는 건너뛰고 누락분만 추가)",
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

    # 빌더 초기화
    builder = VectorDBBuilder()

    # 통계 표시
    if args.stats:
        print("\n" + "=" * 60)
        print("VectorDB 통계")
        print("=" * 60)

        stats = builder.get_all_stats()
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
        mode = "Resume" if args.resume else ("재빌드" if args.force else "빌드")
        print(f"전체 VectorDB {mode} 시작")
        print("=" * 60)

        results = builder.build_all_vectordbs(
            force_rebuild=args.force, resume=args.resume,
        )

        print("\n" + "=" * 60)
        print("빌드 요약")
        print("=" * 60)
        for domain, count in results.items():
            print(f"  {domain}: {count}개 문서")

        total = sum(results.values())
        print(f"\n  총합: {total}개 문서")

    elif args.domain:
        mode = "Resume" if args.resume else ("재빌드" if args.force else "빌드")
        print(f"\n{args.domain} {mode} 중...")
        count = builder.build_vectordb(
            args.domain, force_rebuild=args.force, resume=args.resume,
        )
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
