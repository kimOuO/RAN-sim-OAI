"""簡單 TTL cache — 同位置短時間內不重打 Physics。

key = (ue_id, position_quantized_cm, antenna_signature)。
TTL 由 RU_CHANNEL_CACHE_TTL_SEC 控制（env_loader 讀；預設 0.5s）。
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

from main.utils.env_loader import get_float


_TTL_SEC = get_float("RU_CHANNEL_CACHE_TTL_SEC", default=0.5)


class _Entry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at


class ChannelCache:
    """thread-safe；非分散式（單 process worker）。"""

    def __init__(self, ttl_sec: float = _TTL_SEC):
        self._ttl = max(0.0, ttl_sec)
        self._store: dict[tuple, _Entry] = {}
        self._lock = Lock()

    def get(self, key: tuple) -> Any | None:
        if self._ttl <= 0:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                del self._store[key]
                return None
            return entry.value

    def set(self, key: tuple, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            self._store[key] = _Entry(value, time.monotonic() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# 單一全域 cache（worker 內共享）
default_cache = ChannelCache()


def quantize_position(position: list[float], grid_cm: int = 50) -> tuple[int, int, int]:
    """把座標量化成 grid_cm 公分網格 — 同網格才命中。"""
    return tuple(int(round(p * 100 / grid_cm)) for p in position)
