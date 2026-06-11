import time
import threading
from typing import Any, Optional, Tuple


class TTLCache:
    def __init__(self, ttl: int = 3600, max_entries: int = 1000):
        self._cache: dict[Any, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl
        self._max_entries = max_entries

    def get(self, key) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() < entry[0]:
                return entry[1]
        return None

    def set(self, key, value) -> None:
        with self._lock:
            self._cache[key] = (time.time() + self._ttl, value)
            if len(self._cache) > self._max_entries:
                self._evict()

    def _evict(self) -> None:
        # Caller must hold self._lock. Drop expired entries first, then
        # oldest-expiry entries until back under the bound.
        now = time.time()
        for key in [k for k, (expiry, _) in self._cache.items() if expiry <= now]:
            del self._cache[key]
        while len(self._cache) > self._max_entries:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
