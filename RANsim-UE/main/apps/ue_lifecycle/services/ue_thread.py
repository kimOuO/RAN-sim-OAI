"""Per-UE thread 主迴圈 — 三狀態機 (STANDBY / RUNNING / STOPPED)。

Phase A 第一版只做 lifecycle, 不做 traffic / measurement / trajectory。
之後 Phase B/C/D 在這個 thread 裡加 tick 邏輯。
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class UeThreadState(str, enum.Enum):
    STANDBY = "STANDBY"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


@dataclass
class UeContextSnapshot:
    """從 CU /Session/list 拉到的 UE 狀態快照, manager 會週期更新。"""
    ue_id: str
    serving_cell: str = ""
    rrc_state: str = ""
    traffic_profile: dict[str, Any] = field(default_factory=dict)
    last_synced_at_ms: int = 0


class UeThread:
    """每個 active UE 對應一個。內部跑 idle loop, 之後 phase 加 tick 邏輯。"""

    def __init__(self, ue_id: str) -> None:
        from main.apps.ue_lifecycle.services.traffic_gen import UeTrafficGen
        self.ue_id = ue_id
        self.state = UeThreadState.STANDBY
        self.snapshot = UeContextSnapshot(ue_id=ue_id)
        self.position: tuple[float, float, float] = (0.0, 0.0, 0.0)  # 由 trajectory_tick 寫
        self.traffic_gen = UeTrafficGen(ue_id)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name=f"ue-{self.ue_id}",
        )
        self._thread.start()
        logger.info("UeThread[%s] started in state=%s", self.ue_id, self.state.value)

    def stop(self) -> None:
        self._stop.set()
        self.state = UeThreadState.STOPPED
        logger.info("UeThread[%s] stop signaled", self.ue_id)

    def transition_to(self, new_state: UeThreadState) -> None:
        with self._lock:
            old = self.state
            self.state = new_state
        logger.info("UeThread[%s] %s → %s", self.ue_id, old.value, new_state.value)

    def update_snapshot(self, snap: UeContextSnapshot) -> None:
        with self._lock:
            self.snapshot = snap
            # 同步 traffic_profile 進 traffic_gen
            self.traffic_gen.update_profile(snap.traffic_profile or {})

    def _loop(self) -> None:
        """Idle loop — 之後 phase B 加 trajectory_tick, phase C 加 traffic_tick, phase D 加 measurement_tick."""
        log_period_sec = 30
        last_log = 0.0
        while not self._stop.is_set():
            now = time.time()
            if now - last_log >= log_period_sec:
                logger.info(
                    "UeThread[%s] alive state=%s serving=%s",
                    self.ue_id, self.state.value, self.snapshot.serving_cell,
                )
                last_log = now
            self._stop.wait(1.0)
        logger.info("UeThread[%s] exited", self.ue_id)

    def status(self) -> dict[str, Any]:
        return {
            "ue_id": self.ue_id,
            "state": self.state.value,
            "serving_cell": self.snapshot.serving_cell,
            "rrc_state": self.snapshot.rrc_state,
            "traffic_profile": self.snapshot.traffic_profile or {},
            "injected_sdu_count": self.traffic_gen.injected_sdu_count,
            "last_synced_at_ms": self.snapshot.last_synced_at_ms,
            "position": {"x": self.position[0], "y": self.position[1], "z": self.position[2]},
        }
