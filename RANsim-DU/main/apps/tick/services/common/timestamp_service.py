from __future__ import annotations

import time


class TimestampService:
    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
