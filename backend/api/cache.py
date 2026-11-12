"""Small thread-safe in-memory LRU cache.

Uploads are keyed by a SHA-256 hash of their bytes, so uploading the same file again (or
asking for the same results twice) returns instantly instead of re-running the analysis.
In-memory is enough for one server process; with several servers you'd swap this for Redis.
"""
import hashlib
import threading
from collections import OrderedDict
from typing import Generic, TypeVar

V = TypeVar("V")


def content_hash(*parts: bytes | str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode() if isinstance(part, str) else part)
        digest.update(b"\x00")  # separator so ("ab", "c") and ("a", "bc") hash differently
    return digest.hexdigest()[:24]


class LRUCache(Generic[V]):
    def __init__(self, max_items: int) -> None:
        self._items: OrderedDict[str, V] = OrderedDict()
        self._max_items = max_items
        self._lock = threading.Lock()   # FastAPI runs sync routes in a thread pool

    def get(self, key: str) -> V | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: str, value: V) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)   # drop the least recently used
