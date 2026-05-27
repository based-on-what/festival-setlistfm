import time
import threading
from typing import Any, Optional, Tuple


class TTLCache:
    def __init__(self, ttl: int = 3600):
        self._cache: dict[Any, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def get(self, key) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() < entry[0]:
                return entry[1]
        return None

    def set(self, key, value) -> None:
        with self._lock:
            self._cache[key] = (time.time() + self._ttl, value)
