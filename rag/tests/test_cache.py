"""캐시 모듈 테스트."""

import time

import pytest

from utils.cache import LRUCache, ResponseCache


class TestLRUCache:
    """LRUCache 테스트."""

    def test_basic_set_get(self):
        """기본 set/get 동작."""
        cache = LRUCache[str](max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self):
        """캐시 미스 시 None 반환."""
        cache = LRUCache[str](max_size=10)
        assert cache.get("nonexistent") is None

    def test_max_size_eviction(self):
        """최대 크기 초과 시 eviction."""
        cache = LRUCache[int](max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 'a'가 evict되어야 함

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_lru_ordering(self):
        """LRU 순서 유지."""
        cache = LRUCache[int](max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # 'a'를 접근하면 가장 최근 사용으로 이동
        cache.get("a")

        # 'd'를 추가하면 'b'가 evict되어야 함
        cache.set("d", 4)

        assert cache.get("a") == 1  # 최근 접근했으므로 유지
        assert cache.get("b") is None  # evicted
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_ttl_expiration(self):
        """TTL 만료 테스트."""
        cache = LRUCache[str](max_size=10, default_ttl=0.1)  # 0.1초 TTL
        cache.set("key", "value")

        assert cache.get("key") == "value"
        time.sleep(0.15)  # TTL 초과 대기
        assert cache.get("key") is None

    def test_custom_ttl(self):
        """개별 TTL 설정."""
        cache = LRUCache[str](max_size=10, default_ttl=10)
        cache.set("short", "value", ttl=0.1)
        cache.set("long", "value", ttl=10)

        time.sleep(0.15)
        assert cache.get("short") is None
        assert cache.get("long") == "value"

    def test_delete(self):
        """삭제 테스트."""
        cache = LRUCache[str](max_size=10)
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        """전체 삭제 테스트."""
        cache = LRUCache[str](max_size=10)
        cache.set("a", "1")
        cache.set("b", "2")
        count = cache.clear()
        assert count == 2
        assert len(cache) == 0

    def test_stats(self):
        """통계 테스트."""
        cache = LRUCache[str](max_size=10)
        cache.set("key", "value")

        cache.get("key")  # hit
        cache.get("key")  # hit
        cache.get("miss")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3, rel=0.01)

    def test_contains(self):
        """in 연산자 테스트."""
        cache = LRUCache[str](max_size=10)
        cache.set("key", "value")
        assert "key" in cache
        assert "nonexistent" not in cache


class TestResponseCache:
    """ResponseCache 테스트."""

    def test_query_normalization(self):
        """쿼리 정규화 테스트."""
        cache = ResponseCache(max_size=10, ttl=3600)

        response = {"content": "답변", "sources": []}
        cache.set("창업 절차  알려주세요", response)

        # 공백/대소문자 다른 쿼리로도 조회 가능
        assert cache.get("창업 절차 알려주세요") is not None

    def test_domain_separation(self):
        """도메인별 캐시 분리."""
        cache = ResponseCache(max_size=10, ttl=3600)

        response1 = {"content": "창업 답변"}
        response2 = {"content": "세무 답변"}

        cache.set("질문", response1, domain="startup_funding")
        cache.set("질문", response2, domain="finance_tax")

        assert cache.get("질문", domain="startup_funding")["content"] == "창업 답변"
        assert cache.get("질문", domain="finance_tax")["content"] == "세무 답변"

    def test_invalidate(self):
        """캐시 무효화 테스트."""
        cache = ResponseCache(max_size=10, ttl=3600)

        response = {"content": "답변"}
        cache.set("질문", response)

        assert cache.invalidate("질문") is True
        assert cache.get("질문") is None
