"""QueueHandler/QueueListener 기반 비동기 로깅 유틸리티.

파일 I/O를 백그라운드 스레드로 분리하여
async FastAPI 핸들러에서 이벤트 루프 블로킹을 방지합니다.
"""

import atexit
import logging
import logging.handlers
import queue

_listener: logging.handlers.QueueListener | None = None


def setup_async_logging(
    handlers: list[logging.Handler],
    root_level: int = logging.INFO,
) -> logging.handlers.QueueListener:
    """루트 로거 핸들러를 QueueHandler로 교체하고 QueueListener를 시작합니다.

    Args:
        handlers: QueueListener가 백그라운드 스레드에서 처리할 핸들러 목록
        root_level: 루트 로거 레벨

    Returns:
        시작된 QueueListener 인스턴스
    """
    global _listener

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    root = logging.getLogger()
    root.setLevel(root_level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(queue_handler)

    _listener = logging.handlers.QueueListener(
        log_queue, *handlers, respect_handler_level=True
    )
    _listener.start()
    atexit.register(stop_async_logging)
    return _listener


def stop_async_logging() -> None:
    """QueueListener를 정지하고 남은 로그를 flush합니다."""
    global _listener
    if _listener:
        _listener.stop()
        _listener = None
