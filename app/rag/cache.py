"""Small TTL cache for query embeddings."""

from __future__ import annotations

import hashlib
from threading import RLock

from cachetools import TTLCache


class QueryEmbeddingCache:
    def __init__(self, maxsize: int, ttl_seconds: int):
        self._cache: TTLCache[str, list[float]] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = RLock()

    @staticmethod
    def key_for(query_text: str) -> str:
        return hashlib.sha256((query_text or "").encode("utf-8")).hexdigest()

    def get(self, query_text: str) -> list[float] | None:
        key = self.key_for(query_text)
        with self._lock:
            value = self._cache.get(key)
            return list(value) if value is not None else None

    def set(self, query_text: str, vector: list[float]) -> None:
        key = self.key_for(query_text)
        with self._lock:
            self._cache[key] = list(vector)

