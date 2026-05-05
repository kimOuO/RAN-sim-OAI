"""TimestampService — 鐵則 14-3 common 必備。"""
import time
from datetime import datetime, timezone


class TimestampService:
    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def now_s() -> int:
        return int(time.time())

    @staticmethod
    def format_iso8601(timestamp_ms: int) -> str:
        """Convert milliseconds timestamp to ISO 8601 string."""
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return dt.isoformat()
