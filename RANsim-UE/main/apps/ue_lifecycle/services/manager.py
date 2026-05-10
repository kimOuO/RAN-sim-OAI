"""UeLifecycleManager — 從 CU 拉 UE list, diff 啟停 per-UE thread。

雙保險同步:
1. Polling: 每 N 秒從 CU /Session/list 拉, diff active set
2. Push:    其他 service (CU NGAP, Dashboard) 透過 /UE/Lifecycle/sync 通知
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from django.conf import settings

from main.apps.ue_lifecycle.services import cu_client, kit_client, ru_client
from main.apps.ue_lifecycle.services.interp import interp_position
from main.apps.ue_lifecycle.services.trajectory_store import get_store as get_traj_store
from main.apps.ue_lifecycle.services.ue_thread import (
    UeContextSnapshot,
    UeThread,
    UeThreadState,
)

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


class UeLifecycleManager:
    """Singleton — 管所有 per-UE thread。Thread-safe via lock。"""

    def __init__(self) -> None:
        self._threads: dict[str, UeThread] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._trajectory_thread: threading.Thread | None = None
        # sim_running 由 Dashboard 透過 /Lifecycle/start 跟 /stop 控制
        self.sim_running = False

    def start(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="ue-lifecycle-mgr",
        )
        self._poll_thread.start()
        self._trajectory_thread = threading.Thread(
            target=self._trajectory_loop, daemon=True, name="ue-trajectory-tick",
        )
        self._trajectory_thread.start()
        logger.info("UeLifecycleManager started (poll + trajectory ticks)")

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for ue in list(self._threads.values()):
                ue.stop()
            self._threads.clear()
        logger.info("UeLifecycleManager stopped")

    def _poll_loop(self) -> None:
        period = settings.UE_LIST_POLL_PERIOD_SEC
        logger.info("UE list poll loop started, period=%ds", period)
        while not self._stop.is_set():
            try:
                self._sync_from_cu()
            except Exception:
                logger.exception("UE list poll iteration failed")
            self._stop.wait(period)
        logger.info("UE list poll loop stopped")

    def _trajectory_loop(self) -> None:
        """每 UE_TRAJECTORY_PERIOD_MS 算所有 RUNNING UE 的位置, batch 寫 RU + per-UE 寫 Kit."""
        period_sec = settings.UE_TRAJECTORY_PERIOD_MS / 1000.0
        traj_store = get_traj_store()
        logger.info("Trajectory tick loop started, period=%dms", settings.UE_TRAJECTORY_PERIOD_MS)
        while not self._stop.is_set():
            try:
                self._trajectory_tick(traj_store)
            except Exception:
                logger.exception("trajectory tick failed")
            self._stop.wait(period_sec)
        logger.info("Trajectory tick loop stopped")

    def _trajectory_tick(self, traj_store) -> None:
        """1 個 tick: 對所有 RUNNING UE 算位置, 收集後 batch 寫 RU + 平行寫 Kit + traffic tick."""
        if not self.sim_running:
            return  # sim 沒跑就不打位置/traffic
        now_ms = _now_ms()
        positions_for_ru: list[dict] = []
        positions_for_kit: list[tuple[str, float, float, float]] = []

        with self._lock:
            ue_list = list(self._threads.items())

        injected_total = 0
        for ue_id, ue in ue_list:
            if ue.state != UeThreadState.RUNNING:
                continue

            # ── (1) Trajectory: 算位置 ──────
            # AG3 fix: 即使 UE 沒設 trajectory, 也要 sync 一次 ue.position 給 RU.
            # Sionna ray-tracing 要 ue_positions 才能算 path_gain, 沒 sync UE
            # 位置就永遠是空 list → physics 走 graceful empty channel → RU 退
            # noise-only fall-back. 改成: 有 trajectory 就用 interp 算的點,
            # 沒有就用 ue.position (預設 0,0,0; 之後 setup_multi_ue.py / Dashboard
            # 會 set initial position). 至少 sionna 能跑.
            traj = traj_store.get(ue_id)
            if traj:
                elapsed = now_ms - traj["start_at_ms"]
                x, y, z = interp_position(
                    traj["waypoints"], elapsed, mode=traj.get("mode", "loop"),
                )
                ue.position = (x, y, z)
            else:
                # No trajectory — use current static position (default 0,0,0)
                x, y, z = ue.position if ue.position else (0.0, 0.0, 0.0)
            positions_for_ru.append({
                "id": ue_id, "position": {"x": x, "y": y, "z": z},
            })
            positions_for_kit.append((ue_id, x, y, z))

            # ── (2) Traffic gen tick ────────
            try:
                injected_total += ue.traffic_gen.tick()
            except Exception:
                logger.exception("traffic_gen.tick failed for ue=%s", ue_id)

        # ── (3) Batch write RU + per-UE Kit ─
        if positions_for_ru:
            ru_client.update_ues_batch(positions_for_ru)
            for ue_id, x, y, z in positions_for_kit:
                kit_client.move_ue(ue_id, x, y, z)

        # 每 100 tick (~10s) log 一次 traffic 累計, 避免 spam
        if injected_total > 0 and (now_ms // 1000) % 10 == 0:
            logger.debug("traffic tick injected=%d sdu", injected_total)

    def _sync_from_cu(self) -> None:
        sessions = cu_client.list_sessions()
        # CU 端「真實 active」: rrc_state == CONNECTED (含 traffic_profile)
        cu_set = {
            s["ue_id"]: s for s in sessions
            if s.get("rrc_state") == "CONNECTED"
        }

        with self._lock:
            existing = set(self._threads.keys())
            cu_ids = set(cu_set.keys())

            new_ues = cu_ids - existing
            removed = existing - cu_ids
            kept = cu_ids & existing

            # 新加: spawn thread
            for ue_id in new_ues:
                self._spawn_thread(ue_id, cu_set[ue_id])

            # 消失: stop thread
            for ue_id in removed:
                t = self._threads.pop(ue_id, None)
                if t:
                    t.stop()

            # 沿用: 更新 snapshot
            for ue_id in kept:
                t = self._threads[ue_id]
                t.update_snapshot(self._build_snapshot(cu_set[ue_id]))

        if new_ues or removed:
            logger.info(
                "UE list diff: added=%s removed=%s kept_count=%d",
                sorted(new_ues), sorted(removed), len(kept),
            )

    def _build_snapshot(self, cu_data: dict[str, Any]) -> UeContextSnapshot:
        # CU 回的 session schema: ue_id, serving_cell, rrc_state, ...
        # traffic_profile 是新欄位, 可能還沒上 (Phase C 才加)
        return UeContextSnapshot(
            ue_id=cu_data["ue_id"],
            serving_cell=cu_data.get("serving_cell", ""),
            rrc_state=cu_data.get("rrc_state", ""),
            traffic_profile=cu_data.get("traffic_profile_json") or {},
            last_synced_at_ms=_now_ms(),
        )

    def _spawn_thread(self, ue_id: str, cu_data: dict[str, Any]) -> None:
        snap = self._build_snapshot(cu_data)
        t = UeThread(ue_id)
        t.update_snapshot(snap)
        # sim_running 決定起始狀態
        if self.sim_running:
            t.transition_to(UeThreadState.RUNNING)
        else:
            t.transition_to(UeThreadState.STANDBY)
        t.start()
        self._threads[ue_id] = t

    def kill_ue(self, ue_id: str) -> bool:
        with self._lock:
            t = self._threads.pop(ue_id, None)
        if t:
            t.stop()
            return True
        return False

    def push_sync(self, event: str, ue_id: str | None = None) -> dict[str, Any]:
        """即時 push 同步入口 (CU/Dashboard 通知)。
        event: "attach" | "detach" | "profile_changed" | "sim_start" | "sim_stop"
        """
        if event in ("sim_start", "sim_stop"):
            return self._handle_sim_lifecycle(event)
        if not ue_id:
            return {"ok": False, "error": "ue_id required for per-UE event"}
        if event == "attach":
            # 立即去 CU 拉一次, diff 會 spawn 新 thread
            self._sync_from_cu()
            return {"ok": True, "event": event, "ue_id": ue_id}
        if event == "detach":
            killed = self.kill_ue(ue_id)
            return {"ok": True, "event": event, "ue_id": ue_id, "killed": killed}
        if event == "profile_changed":
            self._sync_from_cu()
            return {"ok": True, "event": event, "ue_id": ue_id}
        return {"ok": False, "error": f"unknown event {event!r}"}

    def _handle_sim_lifecycle(self, event: str) -> dict[str, Any]:
        with self._lock:
            if event == "sim_start":
                self.sim_running = True
                target = UeThreadState.RUNNING
            else:
                self.sim_running = False
                target = UeThreadState.STANDBY
            for t in self._threads.values():
                t.transition_to(target)
        logger.info("Sim lifecycle: %s → all threads %s", event, target.value)
        return {"ok": True, "event": event, "thread_count": len(self._threads)}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "sim_running": self.sim_running,
                "thread_count": len(self._threads),
                "threads": [t.status() for t in self._threads.values()],
            }


_singleton: UeLifecycleManager | None = None
_singleton_lock = threading.Lock()


def get_manager() -> UeLifecycleManager:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = UeLifecycleManager()
    return _singleton
