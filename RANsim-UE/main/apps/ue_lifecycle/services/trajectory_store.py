"""Trajectory store — in-memory dict, 從 Dashboard 收 waypoints 後 store。

每個 UE 的 trajectory:
  {
    waypoints: [{x, y, z, t_ms}, ...],   # t_ms 相對 start
    start_at_ms: 1234567890000,           # set 時 wallclock
    mode: "loop" | "once" | "stay",       # 走完最後一點怎處理
  }
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class TrajectoryStore:
    """Singleton — thread-safe waypoint container。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, dict[str, Any]] = {}

    def set(
        self,
        ue_id: str,
        *,
        waypoints: list[dict[str, Any]],
        start_at_ms: int,
        mode: str = "loop",
    ) -> None:
        if not waypoints:
            self.clear(ue_id)
            return
        # validate waypoints have t_ms ascending
        prev_t = -1
        for wp in waypoints:
            if wp.get("t_ms", -1) < prev_t:
                raise ValueError("waypoints t_ms must be non-decreasing")
            prev_t = wp.get("t_ms", 0)
        with self._lock:
            self._store[ue_id] = {
                "waypoints": list(waypoints),
                "start_at_ms": start_at_ms,
                "mode": mode,
            }
        logger.info(
            "TrajectoryStore set ue=%s waypoints=%d duration=%dms mode=%s",
            ue_id, len(waypoints), waypoints[-1].get("t_ms", 0), mode,
        )

    def get(self, ue_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._store.get(ue_id)

    def clear(self, ue_id: str) -> None:
        with self._lock:
            self._store.pop(ue_id, None)

    def all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._store)


_singleton: TrajectoryStore | None = None
_lock = threading.Lock()


def get_store() -> TrajectoryStore:
    global _singleton
    if _singleton is None:
        with _lock:
            if _singleton is None:
                _singleton = TrajectoryStore()
    return _singleton
