"""JSON 형식 파일 로깅 핸들러 추가 유틸리티 (RAG 서비스용).

backend/config/logging_config.py와 동일한 로직을 RAG 서비스에 독립적으로 제공합니다.
"""

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path


class _JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "rag"):
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


def setup_json_file_logging(
    service_name: str = "rag",
    log_dir: str = "/var/log/app",
    level: int = logging.INFO,
) -> None:
    """루트 로거에 JSON RotatingFileHandler를 추가합니다.

    Args:
        service_name: 로그 파일명 기반 서비스 이름
        log_dir: 로그 파일 저장 경로 (볼륨 마운트 위치)
        level: 파일 핸들러 로그 레벨
    """
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.getLogger(__name__).warning(
            "로그 디렉토리 생성 실패: %s — 파일 로깅 비활성화 (%s)", log_dir, e
        )
        return

    log_file = f"{log_dir}/{service_name}.log"
    root_logger = logging.getLogger()

    # 중복 핸들러 방지
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            if getattr(handler, "baseFilename", "").endswith(f"{service_name}.log"):
                return

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(_JSONFormatter(service_name=service_name))
    file_handler.setLevel(level)

    root_logger.addHandler(file_handler)
    logging.getLogger(__name__).info(
        "JSON 파일 로깅 활성화: %s (service=%s)", log_file, service_name
    )
