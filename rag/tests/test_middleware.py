"""미들웨어 모듈 테스트."""

import asyncio
import time

import pytest

from utils.middleware import (
    RateLimiter,
    MetricsCollector,
    with_timeout,
    TimeoutError,
)


class TestRateLimiter:
    """RateLimiter 테스트."""

    def test_basic_allow(self):
        """기본 허용 테스트."""
        limiter = RateLimiter(rate=10.0, capacity=10.0)
        assert limiter.is_allowed("user1") is True

    def test_rate_limiting(self):
        """Rate limiting 동작 테스트."""
        limiter = RateLimiter(rate=1.0, capacity=2.0)

        # 초기 토큰 2개
        assert limiter.is_allowed("user1") is True  # 남은 토큰: 1
        assert limiter.is_allowed("user1") is True  # 남은 토큰: 0
        assert limiter.is_allowed("user1") is False  # 토큰 부족

    def test_token_refill(self):
        """토큰 충전 테스트."""
        limiter = RateLimiter(rate=10.0, capacity=10.0)

        # 토큰 모두 소진
        for _ in range(10):
            limiter.is_allowed("user1")

        assert limiter.is_allowed("user1") is False

        # 0.1초 대기 (1개 토큰 충전)
        time.sleep(0.15)
        assert limiter.is_allowed("user1") is True

    def test_separate_users(self):
        """사용자별 분리 테스트."""
        limiter = RateLimiter(rate=1.0, capacity=1.0)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False
        assert limiter.is_allowed("user2") is True  # 다른 사용자는 별도 한도

    def test_retry_after(self):
        """재시도 시간 계산 테스트."""
        limiter = RateLimiter(rate=1.0, capacity=1.0)

        limiter.is_allowed("user1")  # 토큰 소진
        retry_after = limiter.get_retry_after("user1")

        assert retry_after > 0
        assert retry_after <= 1.0  # 최대 1초 대기

    def test_reset(self):
        """리셋 테스트."""
        limiter = RateLimiter(rate=1.0, capacity=1.0)

        limiter.is_allowed("user1")
        assert limiter.is_allowed("user1") is False

        limiter.reset("user1")
        assert limiter.is_allowed("user1") is True


class TestMetricsCollector:
    """MetricsCollector 테스트."""

    def test_record_request(self):
        """요청 기록 테스트."""
        collector = MetricsCollector()

        collector.record_request("/api/chat", "POST", 200, 0.5)
        collector.record_request("/api/chat", "POST", 200, 0.3)
        collector.record_request("/api/chat", "POST", 500, 1.0)

        stats = collector.get_stats()
        assert stats["request_count"] == 3

    def test_error_rate(self):
        """에러율 계산 테스트."""
        collector = MetricsCollector()

        collector.record_request("/api/chat", "POST", 200, 0.5)
        collector.record_request("/api/chat", "POST", 200, 0.3)
        collector.record_request("/api/chat", "POST", 500, 1.0)
        collector.record_request("/api/chat", "POST", 503, 0.1)

        stats = collector.get_stats()
        assert stats["error_rate"] == pytest.approx(0.5, rel=0.01)

    def test_percentiles(self):
        """백분위수 계산 테스트."""
        collector = MetricsCollector()

        durations = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for d in durations:
            collector.record_request("/api/chat", "POST", 200, d)

        stats = collector.get_stats()
        assert stats["p50_duration"] > 0
        assert stats["p95_duration"] > stats["p50_duration"]

    def test_endpoint_stats(self):
        """엔드포인트별 통계 테스트."""
        collector = MetricsCollector()

        collector.record_request("/api/chat", "POST", 200, 0.5)
        collector.record_request("/api/chat", "POST", 200, 0.3)
        collector.record_request("/health", "GET", 200, 0.01)

        endpoint_stats = collector.get_endpoint_stats()
        assert "POST:/api/chat" in endpoint_stats
        assert "GET:/health" in endpoint_stats
        assert endpoint_stats["POST:/api/chat"]["count"] == 2

    def test_counters_and_gauges(self):
        """카운터와 게이지 테스트."""
        collector = MetricsCollector()

        collector.increment_counter("custom_counter", 5)
        collector.set_gauge("active_connections", 10)

        stats = collector.get_stats()
        assert stats["counters"]["custom_counter"] == 5
        assert stats["gauges"]["active_connections"] == 10


class TestTimeout:
    """타임아웃 유틸리티 테스트."""

    @pytest.mark.asyncio
    async def test_within_timeout(self):
        """타임아웃 내 완료."""
        async def fast_operation():
            await asyncio.sleep(0.01)
            return "success"

        result = await with_timeout(fast_operation(), timeout=1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_with_fallback(self):
        """타임아웃 시 fallback 반환."""
        async def slow_operation():
            await asyncio.sleep(10)
            return "never reached"

        result = await with_timeout(
            slow_operation(),
            timeout=0.1,
            fallback="fallback_value",
        )
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self):
        """타임아웃 시 에러 발생."""
        async def slow_operation():
            await asyncio.sleep(10)
            return "never reached"

        with pytest.raises(TimeoutError):
            await with_timeout(slow_operation(), timeout=0.1)
