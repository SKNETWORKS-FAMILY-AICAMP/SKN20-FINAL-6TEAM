"""캐싱 유틸리티 모듈.

응답 캐싱, TTL 관리 등의 기능을 제공합니다.
"""

import asyncio
import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """캐시 엔트리."""

    value: T
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    ttl: float | None = None

    def is_expired(self) -> bool:
        """TTL 만료 여부를 확인합니다."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class LRUCache(Generic[T]):
    """TTL을 지원하는 LRU 캐시.

    스레드 안전한 LRU 캐시 구현입니다.

    Attributes:
        max_size: 최대 캐시 크기
        default_ttl: 기본 TTL (초)

    Example:
        >>> cache = LRUCache[str](max_size=100, default_ttl=3600)
        >>> cache.set("key1", "value1")
        >>> cache.get("key1")
        'value1'
    """

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: float | None = 3600,
    ):
        """LRUCache를 초기화합니다.

        Args:
            max_size: 최대 캐시 크기
            default_ttl: 기본 TTL (초), None이면 만료 없음
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def get(self, key: str) -> T | None:
        """캐시에서 값을 가져옵니다.

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 또는 None
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            entry = self._cache[key]

            # TTL 만료 확인
            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            # LRU: 맨 뒤로 이동
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats["hits"] += 1

            return entry.value

    def set(
        self,
        key: str,
        value: T,
        ttl: float | None = None,
    ) -> None:
        """캐시에 값을 저장합니다.

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초), None이면 기본값 사용
        """
        with self._lock:
            # 이미 존재하면 업데이트
            if key in self._cache:
                self._cache[key].value = value
                self._cache[key].created_at = time.time()
                self._cache[key].ttl = ttl or self.default_ttl
                self._cache.move_to_end(key)
                return

            # 캐시 크기 초과 시 가장 오래된 항목 제거
            while len(self._cache) >= self.max_size:
                removed_key, _ = self._cache.popitem(last=False)
                self._stats["evictions"] += 1
                logger.debug(f"캐시 eviction: {removed_key}")

            # 새 항목 추가
            self._cache[key] = CacheEntry(
                value=value,
                ttl=ttl or self.default_ttl,
            )

    def delete(self, key: str) -> bool:
        """캐시에서 항목을 삭제합니다.

        Args:
            key: 캐시 키

        Returns:
            삭제 성공 여부
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """캐시를 모두 비웁니다.

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def cleanup_expired(self) -> int:
        """만료된 항목을 정리합니다.

        Returns:
            정리된 항목 수
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """캐시 통계를 반환합니다.

        Returns:
            캐시 통계 딕셔너리
        """
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate, 4),
                "evictions": self._stats["evictions"],
            }

    def __contains__(self, key: str) -> bool:
        """캐시에 키가 존재하는지 확인합니다."""
        with self._lock:
            if key not in self._cache:
                return False
            return not self._cache[key].is_expired()

    def __len__(self) -> int:
        """캐시 크기를 반환합니다."""
        with self._lock:
            return len(self._cache)


class ResponseCache:
    """RAG 응답 전용 캐시.

    쿼리-응답 쌍을 캐싱하여 동일 질문에 빠르게 응답합니다.
    """

    def __init__(
        self,
        max_size: int = 500,
        ttl: float = 3600,  # 1시간
    ):
        """ResponseCache를 초기화합니다.

        Args:
            max_size: 최대 캐시 크기
            ttl: TTL (초)
        """
        self._cache: LRUCache[dict[str, Any]] = LRUCache(
            max_size=max_size,
            default_ttl=ttl,
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        """쿼리를 정규화합니다."""
        # 소문자 변환, 공백 정리
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    @staticmethod
    def _generate_key(query: str, domain: str | None = None) -> str:
        """캐시 키를 생성합니다."""
        normalized = ResponseCache._normalize_query(query)
        if domain:
            normalized = f"{domain}:{normalized}"
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(
        self,
        query: str,
        domain: str | None = None,
    ) -> dict[str, Any] | None:
        """캐시된 응답을 가져옵니다.

        Args:
            query: 사용자 쿼리
            domain: 도메인 (선택)

        Returns:
            캐시된 응답 또는 None
        """
        key = self._generate_key(query, domain)
        result = self._cache.get(key)

        if result:
            logger.debug(f"캐시 히트: {query[:50]}...")
        else:
            logger.debug(f"캐시 미스: {query[:50]}...")

        return result

    def set(
        self,
        query: str,
        response: dict[str, Any],
        domain: str | None = None,
        ttl: float | None = None,
    ) -> None:
        """응답을 캐시에 저장합니다.

        Args:
            query: 사용자 쿼리
            response: 응답 딕셔너리
            domain: 도메인 (선택)
            ttl: TTL (초)
        """
        key = self._generate_key(query, domain)
        self._cache.set(key, response, ttl)
        logger.debug(f"캐시 저장: {query[:50]}...")

    def invalidate(
        self,
        query: str,
        domain: str | None = None,
    ) -> bool:
        """캐시를 무효화합니다.

        Args:
            query: 사용자 쿼리
            domain: 도메인 (선택)

        Returns:
            삭제 성공 여부
        """
        key = self._generate_key(query, domain)
        return self._cache.delete(key)

    def clear(self) -> int:
        """모든 캐시를 비웁니다.

        Returns:
            삭제된 항목 수
        """
        return self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """캐시 통계를 반환합니다."""
        return self._cache.get_stats()


# 싱글톤 인스턴스
_response_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    """ResponseCache 싱글톤 인스턴스를 반환합니다.

    Returns:
        ResponseCache 인스턴스
    """
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache
