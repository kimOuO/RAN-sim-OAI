"""簡單 TTL cache — 同位置短時間內不重打 Physics。

key = (ue_id, position_quantized_cm, antenna_signature)。
TTL 由 RU_CHANNEL_CACHE_TTL_SEC 控制（env_loader 讀；預設 0.5s）。

★ 2026-09-16 VM 記憶體耗盡事故:舊版只在「同一個 key 再被 get」時刪過期項。
  移動中的 UE 每個 tick 都是新 key(位置量化到 50 cm),舊 key 永遠不會再被查 → 永遠不刪。
  實測寫 36,000 筆全部過期仍留 36,000 筆;corridor 兩個 run 合計約 0.3 GB/小時。
  2026-10-15:每次 set 清過期項，並以 RU_CHANNEL_CACHE_MAX_MB 限制總大小。
  原先每 256 次才清理，在 128 元件陣列的 JSON 矩陣下仍可能先耗盡 2 GiB。
"""
from __future__ import annotations

import time
import sys
from threading import Lock
from typing import Any

from main.utils.env_loader import get_float


_TTL_SEC = get_float("RU_CHANNEL_CACHE_TTL_SEC", default=0.5)
_MAX_ENTRIES = int(get_float("RU_CHANNEL_CACHE_MAX", default=5000))
_MAX_BYTES = int(get_float("RU_CHANNEL_CACHE_MAX_MB", default=128) * 1024 * 1024)


def _size(value: Any, seen: set[int] | None = None) -> int:
    seen = seen if seen is not None else set()
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = max(sys.getsizeof(value), int(getattr(value, "nbytes", 0)))
    if isinstance(value, dict):
        size += sum(_size(k, seen) + _size(v, seen) for k, v in value.items())
    elif isinstance(value, (list, tuple)):
        size += sum(_size(v, seen) for v in value)
    return size


class _Entry:
    __slots__ = ("value", "expires_at", "size")

    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at
        self.size = _size(value)


class ChannelCache:
    """thread-safe；非分散式（單 process worker）。"""

    def __init__(self, ttl_sec: float = _TTL_SEC, max_entries: int = _MAX_ENTRIES, max_bytes: int = _MAX_BYTES):
        self._ttl = max(0.0, ttl_sec)
        self._max = max(1, int(max_entries))
        self._store: dict[tuple, _Entry] = {}
        self._lock = Lock()
        self._max_bytes = max(0, int(max_bytes))
        self._bytes = 0

    def _remove(self, key: tuple) -> None:
        self._bytes -= self._store.pop(key).size

    def get(self, key: tuple) -> Any | None:
        if self._ttl <= 0:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                self._remove(key)
                return None
            return entry.value

    def set(self, key: tuple, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            now = time.monotonic()
            # Moving UEs seldom reuse a key. Sweep every batch insertion so expired
            # large matrices cannot accumulate until the former 256-set threshold.
            self._evict(now)
            if key in self._store:
                self._remove(key)
            entry = _Entry(value, now + self._ttl)
            if entry.size > self._max_bytes:
                return
            self._store[key] = entry
            self._bytes += entry.size
            while len(self._store) > self._max or self._bytes > self._max_bytes:
                self._remove(next(iter(self._store)))

    def _evict(self, now: float) -> None:
        """呼叫端需持有 lock。先清過期,仍超量就從最早到期的淘汰到上限的 90%。"""
        expired = [k for k, e in self._store.items() if e.expires_at < now]
        for k in expired:
            self._remove(k)
        if len(self._store) > self._max:
            keep = int(self._max * 0.9)
            for k, _ in sorted(self._store.items(), key=lambda kv: kv[1].expires_at)[: len(self._store) - keep]:
                self._remove(k)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._bytes = 0


# 單一全域 cache（worker 內共享）
default_cache = ChannelCache()


def quantize_position(position: list[float], grid_cm: int = 50) -> tuple[int, int, int]:
    """把座標量化成 grid_cm 公分網格 — 同網格才命中。"""
    return tuple(int(round(p * 100 / grid_cm)) for p in position)
