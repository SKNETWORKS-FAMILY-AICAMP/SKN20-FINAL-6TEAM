#!/usr/bin/env python3
"""로그 파일 S3 업로드 배치 스크립트.

로테이션된 로그 파일(.log.1, .log.2 등)을 S3에 업로드합니다.
현재 활성 로그(.log)는 대상에서 제외합니다.

S3 키 구조:
    logs/{service}/{YYYY}/{MM}/{DD}/{filename}

    예) logs/backend/2026/02/25/backend.log.1
        logs/nginx/2026/02/25/access.log.1
        logs/rag/2026/02/25/chat.log.1

로그 디렉토리 (환경변수로 재정의 가능):
    APP_LOG_DIR      : backend/rag 시스템 로그  (기본: /var/log/app)
    NGINX_LOG_DIR    : nginx access/error 로그  (기본: /var/log/nginx)
    RAG_CHAT_LOG_DIR : RAG 채팅/RAGAS 로그     (기본: {PROJECT_ROOT}/rag/logs)
    BATCH_LOG_DIR    : 배치 실행 로그           (기본: {PROJECT_ROOT}/logs)

Usage:
    python scripts/batch/upload_logs.py
    python scripts/batch/upload_logs.py --delete-after-upload
    python scripts/batch/upload_logs.py --dry-run
    python scripts/batch/upload_logs.py --service backend

종료 코드:
    0: 성공 (업로드 오류 0건)
    1: S3_BUCKET_NAME 미설정
    2: 업로드 중 일부 오류 발생
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# =============================================================================
# 로그 소스 정의
# =============================================================================

# (서비스명, 로그 디렉토리 환경변수, 기본 경로, glob 패턴) 목록
_LOG_SOURCE_SPECS: list[tuple[str, str, Path, str]] = [
    ("backend", "APP_LOG_DIR",      Path("/var/log/app"),          "backend.log.*"),
    ("rag",     "APP_LOG_DIR",      Path("/var/log/app"),          "rag.log.*"),
    ("nginx",   "NGINX_LOG_DIR",    Path("/var/log/nginx"),        "access.log.*"),
    ("nginx",   "NGINX_LOG_DIR",    Path("/var/log/nginx"),        "error.log.*"),
    ("rag",     "RAG_CHAT_LOG_DIR", PROJECT_ROOT / "rag" / "logs", "chat.log.*"),
    ("rag",     "RAG_CHAT_LOG_DIR", PROJECT_ROOT / "rag" / "logs", "ragas.log.*"),
    ("batch",   "BATCH_LOG_DIR",    PROJECT_ROOT / "logs",         "batch_announcements.log.*"),
]


def _resolve_log_sources() -> list[tuple[str, Path, str]]:
    """환경변수를 반영하여 (service, log_dir, pattern) 목록을 반환합니다."""
    resolved: list[tuple[str, Path, str]] = []
    seen: set[tuple[str, str]] = set()  # (dir, pattern) 중복 방지

    for service, env_key, default_path, pattern in _LOG_SOURCE_SPECS:
        log_dir = Path(os.getenv(env_key, str(default_path)))
        key = (str(log_dir), pattern)
        if key not in seen:
            resolved.append((service, log_dir, pattern))
            seen.add(key)

    return resolved


# =============================================================================
# 로깅 설정
# =============================================================================


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("batch.upload_logs")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


# =============================================================================
# 로그 파일 탐색
# =============================================================================


def _find_rotated_logs(log_dir: Path, pattern: str) -> list[Path]:
    """로테이션된 로그 파일(.log.N) 목록을 반환합니다.

    현재 활성 로그(.log)는 제외하고, 백업 번호가 있는 파일만 반환합니다.
    예) backend.log.1, backend.log.2 → 포함
        backend.log               → 제외 (활성 중)
    """
    if not log_dir.exists():
        return []
    return sorted(
        f for f in log_dir.glob(pattern) if f.suffix.lstrip(".").isdigit()
    )


# =============================================================================
# 배치 실행
# =============================================================================


class LogUploader:
    """로그 파일 S3 업로드 오케스트레이터."""

    def __init__(
        self,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        service_filter: str | None,
        delete_after: bool,
        dry_run: bool,
    ) -> None:
        self.bucket = bucket
        self.service_filter = service_filter
        self.delete_after = delete_after
        self.dry_run = dry_run
        self.logger = _setup_logger()

        from scripts.batch.s3_uploader import S3Uploader

        self.uploader = S3Uploader(bucket, region, endpoint_url)

    def run(self) -> int:
        """업로드 배치를 실행합니다.

        Returns:
            종료 코드 (0=성공, 2=부분 오류)
        """
        self.logger.info("=" * 55)
        self.logger.info("로그 S3 업로드 시작 (버킷: %s)", self.bucket)
        if self.dry_run:
            self.logger.info("  [DRY RUN] 실제 업로드 없이 시뮬레이션합니다.")
        if self.service_filter:
            self.logger.info("  서비스 필터: %s", self.service_filter)
        self.logger.info("=" * 55)

        uploaded = 0
        errors = 0

        for service, log_dir, pattern in _resolve_log_sources():
            if self.service_filter and service != self.service_filter:
                continue

            files = _find_rotated_logs(log_dir, pattern)
            if not files:
                continue

            self.logger.info("[%s] %s/%s — %d개 발견", service, log_dir, pattern, len(files))

            for file_path in files:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                s3_key = self.uploader.generate_log_key(service, file_path.name, mtime)

                if self.dry_run:
                    self.logger.info("  → s3://%s/%s", self.bucket, s3_key)
                    uploaded += 1
                    continue

                try:
                    self.uploader.upload_log_file(file_path, service, mtime)
                    self.logger.info("  ✓ %s → %s", file_path.name, s3_key)
                    uploaded += 1

                    if self.delete_after:
                        file_path.unlink()
                        self.logger.info("  ✗ 삭제: %s", file_path.name)

                except Exception as e:
                    self.logger.warning("  ✗ 업로드 실패 [%s]: %s", file_path.name, e)
                    errors += 1

        self.logger.info("=" * 55)
        self.logger.info(
            "완료: 업로드 %d건, 오류 %d건%s",
            uploaded,
            errors,
            " (DRY RUN)" if self.dry_run else "",
        )
        self.logger.info("=" * 55)

        return 0 if errors == 0 else 2


# =============================================================================
# CLI 진입점
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="로테이션된 로그 파일을 S3에 업로드합니다."
    )
    parser.add_argument(
        "--service",
        choices=["backend", "rag", "nginx", "batch"],
        help="특정 서비스 로그만 업로드 (미지정 시 전체)",
    )
    parser.add_argument(
        "--delete-after-upload",
        action="store_true",
        help="업로드 성공한 로컬 파일 삭제",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 업로드 없이 대상 파일 목록만 출력",
    )
    args = parser.parse_args()

    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        logging.error("S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")
        return 1

    region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    endpoint_url = os.getenv("S3_ENDPOINT_URL") or None

    uploader = LogUploader(
        bucket=bucket,
        region=region,
        endpoint_url=endpoint_url,
        service_filter=args.service,
        delete_after=args.delete_after_upload,
        dry_run=args.dry_run,
    )
    return uploader.run()


if __name__ == "__main__":
    sys.exit(main())
