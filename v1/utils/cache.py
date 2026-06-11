"""
Simple in-memory LRU cache for embeddings and retrieval results.
Reduces repeated embedding calls for identical queries.
"""
import hashlib
from functools import lru_cache
from typing import Any, Optional


class SimpleCache:
    """Thread-safe in-memory cache with max-size eviction."""

    def __init__(self, max_size: int = 256):
        self._cache: dict = {}
        self._order: list = []
        self.max_size = max_size

    def _key(self, value: str) -> str:
        return hashlib.md5(value.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        k = self._key(key)
        return self._cache.get(k)

    def set(self, key: str, value: Any) -> None:
        k = self._key(key)
        if k in self._cache:
            self._order.remove(k)
        elif len(self._cache) >= self.max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[k] = value
        self._order.append(k)

    def clear(self) -> None:
        self._cache.clear()
        self._order.clear()

    def __len__(self) -> int:
        return len(self._cache)


# Global embedding query cache
embedding_cache = SimpleCache(max_size=512)
retrieval_cache = SimpleCache(max_size=128)
