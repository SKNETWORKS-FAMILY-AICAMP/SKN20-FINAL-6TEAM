"""채팅 상호작용 로깅 유틸리티.

채팅 로그와 RAGAS 메트릭 로그를 파일에 기록합니다.
"""

import json
import logging
import logging.handlers
import queue
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from utils.config import get_settings
from utils.logging_utils import mask_sensitive_data

_KST = timezone(timedelta(hours=9))

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOG_DIR / "chat.log"

# 채팅 로그용 QueueHandler/QueueListener (propagate=False로 루트 우회)
chat_logger = logging.getLogger("chat")
chat_logger.setLevel(logging.INFO)
chat_logger.propagate = False

_chat_handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
_chat_handler.setFormatter(logging.Formatter("%(message)s"))

_chat_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=-1)
chat_logger.addHandler(logging.handlers.QueueHandler(_chat_queue))
_chat_listener = logging.handlers.QueueListener(
    _chat_queue, _chat_handler, respect_handler_level=True
)
_chat_listener.start()


def log_chat_interaction(
    question: str,
    answer: str,
    sources: list,
    domains: list[str],
    response_time: float,
    evaluation: Any = None,
    token_usage: dict[str, Any] | None = None,
) -> None:
    """채팅 상호작용을 로그 파일에 기록합니다.

    Args:
        question: 사용자 질문
        answer: AI 응답
        sources: 참고 문서 리스트
        domains: 처리된 도메인 리스트
        response_time: 응답 시간 (초)
        evaluation: 평가 결과 (선택)
        token_usage: 토큰 사용량 (선택)
    """
    timestamp = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")

    # 민감 정보 마스킹 적용
    masked_question = mask_sensitive_data(question)
    masked_answer = mask_sensitive_data(answer)

    log_entry = f"""
{'='*80}
[{timestamp}] Response Time: {response_time:.2f}초
{'='*80}

[Q] {masked_question}

[A] {masked_answer}

[도메인] {', '.join(domains)}

[참고문서]
"""

    # 유효한 참고문서만 필터링 (content가 있는 것만)
    valid_sources = [s for s in sources if s.content and s.content.strip()]

    if valid_sources:
        for i, source in enumerate(valid_sources, 1):
            title = source.title
            src = source.source
            content = source.content

            if source.metadata:
                if not title:
                    title = source.metadata.get("title")
                if not src:
                    src = (
                        source.metadata.get("source_name")
                        or source.metadata.get("source_file")
                        or source.metadata.get("source")
                    )

            title = title or "제목 없음"
            src = src or "출처 없음"
            content_preview = content[:200] + "..." if len(content) > 200 else content
            log_entry += f"  [{i}] {title}\n      출처: {src}\n      내용: {content_preview}\n\n"
    else:
        log_entry += "  (참고문서 없음 - VectorDB 데이터 확인 필요)\n"

    if evaluation:
        log_entry += f"\n[평가] 점수: {evaluation.total_score}, 통과: {evaluation.passed}\n"

    if token_usage and token_usage.get("total_tokens", 0) > 0:
        log_entry += f"""
[토큰 사용량]
  입력 토큰: {token_usage['input_tokens']:,}
  출력 토큰: {token_usage['output_tokens']:,}
  합계: {token_usage['total_tokens']:,}
  비용: ${token_usage['cost']:.6f}
"""
        components = token_usage.get("components", {})
        if components:
            log_entry += "\n  [컴포넌트별 상세]\n"
            for name, comp in components.items():
                log_entry += (
                    f"    {name}: {comp['call_count']}회 호출, "
                    f"{comp['total_tokens']:,} 토큰, "
                    f"${comp['cost']:.6f}\n"
                )

    log_entry += "\n"
    chat_logger.info(log_entry)


_ragas_listener: logging.handlers.QueueListener | None = None


def _get_ragas_logger() -> logging.Logger:
    """RAGAS 메트릭 전용 로거를 반환합니다 (지연 초기화, QueueListener 사용)."""
    global _ragas_listener
    ragas_log = logging.getLogger("ragas_metrics")
    if not ragas_log.handlers:
        ragas_log.setLevel(logging.INFO)
        ragas_log.propagate = False

        ragas_handler = RotatingFileHandler(
            LOG_DIR / get_settings().ragas_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        ragas_handler.setFormatter(logging.Formatter("%(message)s"))

        ragas_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=-1)
        ragas_log.addHandler(logging.handlers.QueueHandler(ragas_queue))
        _ragas_listener = logging.handlers.QueueListener(
            ragas_queue, ragas_handler, respect_handler_level=True
        )
        _ragas_listener.start()
    return ragas_log


def stop_chat_loggers() -> None:
    """채팅/RAGAS 로거의 QueueListener를 정지합니다. lifespan shutdown에서 호출."""
    global _ragas_listener
    _chat_listener.stop()
    if _ragas_listener:
        _ragas_listener.stop()
        _ragas_listener = None


def log_ragas_metrics(
    question: str,
    answer: str,
    metrics_dict: dict[str, Any],
    domains: list[str],
    response_time: float,
) -> None:
    """RAGAS 메트릭을 로그 파일에 JSON 형식으로 기록합니다.

    Args:
        question: 사용자 질문
        answer: AI 응답
        metrics_dict: RAGAS 메트릭 딕셔너리
        domains: 처리된 도메인 리스트
        response_time: 응답 시간 (초)
    """
    timestamp = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
    log_data = {
        "timestamp": timestamp,
        "question": mask_sensitive_data(question)[:200],
        "answer_preview": mask_sensitive_data(answer)[:200],
        "domains": domains,
        "response_time": round(response_time, 2),
        "ragas_metrics": metrics_dict,
    }

    ragas_log = _get_ragas_logger()
    ragas_log.info(json.dumps(log_data, ensure_ascii=False))
