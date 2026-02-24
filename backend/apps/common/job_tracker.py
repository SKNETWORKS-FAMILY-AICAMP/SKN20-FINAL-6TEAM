"""스케줄러 작업 실행 상태 추적 유틸리티."""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def track_job(
    db: Session,
    job_name: str,
    **meta: Any,
) -> AsyncGenerator[Any, None]:
    """스케줄러 작업의 시작/성공/실패를 job_logs 테이블에 자동 기록합니다.

    Args:
        db: SQLAlchemy 세션
        job_name: 작업 이름 (예: "token_cleanup", "announce_crawler")
        **meta: JSON으로 저장할 추가 메타데이터

    Yields:
        JobLog 인스턴스 (record_count 등 직접 설정 가능)

    Example:
        async with track_job(db, "token_cleanup") as job:
            count = cleanup_expired(db)
            job.record_count = count
    """
    from apps.common.models import JobLog

    log = JobLog(
        job_name=job_name,
        status="started",
        started_at=datetime.utcnow(),
        meta=meta if meta else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    start = time.perf_counter()
    try:
        yield log
        log.status = "success"
        log.finished_at = datetime.utcnow()
        log.duration_ms = int((time.perf_counter() - start) * 1000)
        db.commit()
        logger.info(
            "작업 완료: job_name=%s duration_ms=%d record_count=%s",
            job_name,
            log.duration_ms,
            log.record_count,
        )
    except Exception as exc:
        log.status = "failed"
        log.finished_at = datetime.utcnow()
        log.duration_ms = int((time.perf_counter() - start) * 1000)
        log.error_msg = str(exc)[:2000]
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.error("작업 실패: job_name=%s error=%s", job_name, exc)
        raise
