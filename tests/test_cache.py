import threading
import time

from infrastructure.cache import TTLCache


def test_set_get_roundtrip():
    cache = TTLCache(ttl=60)
    cache.set("k", [1, 2])
    assert cache.get("k") == [1, 2]


def test_missing_key_returns_none():
    assert TTLCache(ttl=60).get("nope") is None


def test_expired_entry_returns_none():
    cache = TTLCache(ttl=0)
    cache.set("k", "v")
    time.sleep(0.01)
    assert cache.get("k") is None


def test_tuple_keys():
    cache = TTLCache(ttl=60)
    cache.set(("mbid", True), ["song"])
    assert cache.get(("mbid", True)) == ["song"]
    assert cache.get(("mbid", False)) is None


def test_eviction_drops_expired_first():
    cache = TTLCache(ttl=60, max_entries=2)
    cache._cache["old"] = (time.time() - 1, "expired")  # simulate expired entry
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("old") is None
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert len(cache._cache) == 2


def test_eviction_drops_oldest_expiry_when_none_expired():
    cache = TTLCache(ttl=60, max_entries=2)
    cache.set("a", 1)
    time.sleep(0.01)
    cache.set("b", 2)
    time.sleep(0.01)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_thread_safety_smoke():
    cache = TTLCache(ttl=60)
    errors = []

    def worker(n):
        try:
            for i in range(200):
                cache.set((n, i % 10), i)
                cache.get((n, i % 10))
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
