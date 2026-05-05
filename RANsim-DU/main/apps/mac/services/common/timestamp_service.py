"""時間戳 — 統一回傳 ms-since-epoch (UTC)。"""
from __future__ import annotations

import time


class TimestampService:
    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def now_s() -> float:
        return time.time()
