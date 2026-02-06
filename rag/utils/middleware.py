"""미들웨어 및 유틸리티 모듈.

Rate Limiting, 타임아웃, 메트릭 수집 등의 기능을 제공합니다.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Rate Limiting
# =============================================================================


@dataclass
class RateLimitState:
    """Rate Limit 상태."""

    tokens: float
    last_update: float = field(default_factory=time.time)


class RateLimiter:
    """Token Bucket 기반 Rate Limiter.

    Attributes:
        rate: 초당 토큰 충전 속도
        capacity: 최대 토큰 수

    Example:
        >>> limiter = RateLimiter(rate=10, capacity=100)
        >>> limiter.is_allowed("user_123")
        True
    """

    def __init__(
        self,
        rate: float = 10.0,
        capacity: float = 100.0,
        cleanup_interval: float = 3600.0,
    ):
        """RateLimiter를 초기화합니다.

        Args:
            rate: 초당 토큰 충전 속도
            capacity: 최대 토큰 수 (버스트 허용량)
            cleanup_interval: stale 상태 정리 주기 (초)
        """
        self.rate = rate
        self.capacity = capacity
        self._states: dict[str, RateLimitState] = {}
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def _cleanup_stale_states(self, now: float) -> None:
        """오래된 상태를 정리합니다."""
        stale_keys = [
            k for k, s in self._states.items()
            if now - s.last_update > self._cleanup_interval
        ]
        for k in stale_keys:
            del self._states[k]
        if stale_keys:
            logger.debug("Rate limiter cleanup: %d개 항목 제거", len(stale_keys))
        self._last_cleanup = now

    def is_allowed(self, key: str, tokens: float = 1.0) -> bool:
        """요청이 허용되는지 확인합니다.

        Args:
            key: 클라이언트 식별자 (IP, user_id 등)
            tokens: 소비할 토큰 수

        Returns:
            요청 허용 여부
        """
        now = time.time()

        # 주기적 stale 상태 정리
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_stale_states(now)

        if key not in self._states:
            self._states[key] = RateLimitState(tokens=self.capacity)

        state = self._states[key]

        # 토큰 충전
        elapsed = now - state.last_update
        state.tokens = min(self.capacity, state.tokens + elapsed * self.rate)
        state.last_update = now

        # 토큰 소비 가능 여부
        if state.tokens >= tokens:
            state.tokens -= tokens
            return True

        return False

    def get_retry_after(self, key: str, tokens: float = 1.0) -> float:
        """재시도까지 대기 시간을 반환합니다.

        Args:
            key: 클라이언트 식별자
            tokens: 필요한 토큰 수

        Returns:
            대기 시간 (초)
        """
        if key not in self._states:
            return 0.0

        state = self._states[key]
        needed = tokens - state.tokens

        if needed <= 0:
            return 0.0

        return needed / self.rate

    def reset(self, key: str) -> None:
        """특정 클라이언트의 상태를 리셋합니다."""
        if key in self._states:
            del self._states[key]

    def clear(self) -> None:
        """모든 상태를 리셋합니다."""
        self._states.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI Rate Limiting 미들웨어."""

    def __init__(
        self,
        app,
        rate: float = 10.0,
        capacity: float = 100.0,
        key_func: Callable[[Request], str] | None = None,
    ):
        """RateLimitMiddleware를 초기화합니다.

        Args:
            app: FastAPI 앱
            rate: 초당 토큰 충전 속도
            capacity: 최대 토큰 수
            key_func: 클라이언트 키 추출 함수
        """
        super().__init__(app)
        self.limiter = RateLimiter(rate=rate, capacity=capacity)
        self.key_func = key_func or self._default_key_func

    @staticmethod
    def _default_key_func(request: Request) -> str:
        """기본 키 함수: IP 주소."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청을 처리합니다."""
        # 특정 경로는 제외 (health check 등)
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        key = self.key_func(request)

        if not self.limiter.is_allowed(key):
            retry_after = self.limiter.get_retry_after(key)
            logger.warning(f"Rate limit exceeded: {key}")
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Retry after {retry_after:.1f} seconds.",
                headers={"Retry-After": str(int(retry_after))},
            )

        return await call_next(request)


# =============================================================================
# Metrics Collection
# =============================================================================


@dataclass
class RequestMetrics:
    """요청 메트릭."""

    endpoint: str
    method: str
    status_code: int
    duration: float
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """메트릭 수집기.

    요청/응답 메트릭을 수집하고 통계를 제공합니다.
    """

    def __init__(self, max_history: int = 10000):
        """MetricsCollector를 초기화합니다.

        Args:
            max_history: 최대 저장할 메트릭 수
        """
        self.max_history = max_history
        self._metrics: deque[RequestMetrics] = deque(maxlen=max_history)
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
    ) -> None:
        """요청 메트릭을 기록합니다.

        Args:
            endpoint: 엔드포인트 경로
            method: HTTP 메서드
            status_code: 응답 상태 코드
            duration: 처리 시간 (초)
        """
        metric = RequestMetrics(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration,
        )
        self._metrics.append(metric)

        # 카운터 업데이트
        self._counters[f"{method}:{endpoint}:count"] += 1
        self._counters[f"status:{status_code}"] += 1

    def increment_counter(self, name: str, value: int = 1) -> None:
        """카운터를 증가시킵니다."""
        self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """게이지 값을 설정합니다."""
        self._gauges[name] = value

    def get_stats(self, window_seconds: float = 3600) -> dict[str, Any]:
        """통계를 반환합니다.

        Args:
            window_seconds: 통계 계산 윈도우 (초)

        Returns:
            통계 딕셔너리
        """
        now = time.time()
        cutoff = now - window_seconds

        # 윈도우 내 메트릭 필터
        recent = [m for m in self._metrics if m.timestamp >= cutoff]

        if not recent:
            return {
                "request_count": 0,
                "avg_duration": 0,
                "p50_duration": 0,
                "p95_duration": 0,
                "p99_duration": 0,
                "error_rate": 0,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

        durations = sorted([m.duration for m in recent])
        errors = sum(1 for m in recent if m.status_code >= 400)

        def percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            p = max(0.0, min(100.0, p))
            idx = int(len(data) * p / 100)
            return data[max(0, min(idx, len(data) - 1))]

        return {
            "request_count": len(recent),
            "avg_duration": sum(durations) / len(durations),
            "p50_duration": percentile(durations, 50),
            "p95_duration": percentile(durations, 95),
            "p99_duration": percentile(durations, 99),
            "error_rate": errors / len(recent) if recent else 0,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def get_endpoint_stats(self) -> dict[str, dict[str, Any]]:
        """엔드포인트별 통계를 반환합니다."""
        endpoint_metrics: dict[str, list[RequestMetrics]] = defaultdict(list)

        for metric in self._metrics:
            key = f"{metric.method}:{metric.endpoint}"
            endpoint_metrics[key].append(metric)

        stats = {}
        for key, metrics in endpoint_metrics.items():
            durations = [m.duration for m in metrics]
            errors = sum(1 for m in metrics if m.status_code >= 400)

            stats[key] = {
                "count": len(metrics),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "error_count": errors,
            }

        return stats


class MetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI 메트릭 수집 미들웨어."""

    def __init__(self, app, collector: MetricsCollector | None = None):
        """MetricsMiddleware를 초기화합니다.

        Args:
            app: FastAPI 앱
            collector: MetricsCollector 인스턴스
        """
        super().__init__(app)
        self.collector = collector or MetricsCollector()

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청을 처리하고 메트릭을 수집합니다."""
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            self.collector.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                duration=duration,
            )

        return response


# =============================================================================
# Timeout Utilities
# =============================================================================


class TimeoutError(Exception):
    """타임아웃 예외."""

    pass


async def with_timeout(
    coro,
    timeout: float,
    fallback: T | None = None,
    error_message: str = "Operation timed out",
) -> T:
    """코루틴에 타임아웃을 적용합니다.

    Args:
        coro: 실행할 코루틴
        timeout: 타임아웃 (초)
        fallback: 타임아웃 시 반환할 기본값
        error_message: 에러 메시지

    Returns:
        코루틴 결과 또는 fallback

    Raises:
        TimeoutError: fallback이 None이고 타임아웃 발생 시
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"{error_message} (timeout={timeout}s)")
        if fallback is not None:
            return fallback
        raise TimeoutError(error_message)


def timeout_decorator(
    timeout: float,
    fallback: Any = None,
):
    """타임아웃 데코레이터.

    Args:
        timeout: 타임아웃 (초)
        fallback: 타임아웃 시 반환할 기본값

    Example:
        >>> @timeout_decorator(5.0)
        ... async def slow_function():
        ...     await asyncio.sleep(10)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                fallback=fallback,
            )
        return wrapper
    return decorator


# =============================================================================
# Singleton Instances
# =============================================================================


_rate_limiter: RateLimiter | None = None
_metrics_collector: MetricsCollector | None = None


def get_rate_limiter() -> RateLimiter:
    """RateLimiter 싱글톤 인스턴스를 반환합니다."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_metrics_collector() -> MetricsCollector:
    """MetricsCollector 싱글톤 인스턴스를 반환합니다."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
