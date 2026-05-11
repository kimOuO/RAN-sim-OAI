"""Timestamp generation — Common Service per backend_rule.md."""
from __future__ import annotations

import time


class TimestampService:
    @staticmethod
    def now_ms() -> int:
        """Wall-clock milliseconds since epoch — for log/E2 PDU timestamps."""
        return int(time.time() * 1000)

    @staticmethod
    def now_sec() -> float:
        return time.time()
