"""Time helpers — uniform UTC timestamps."""
from __future__ import annotations

import time
from datetime import datetime, timezone


class TimestampService:
    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def now_iso() -> str:
        return TimestampService.now().isoformat()

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
