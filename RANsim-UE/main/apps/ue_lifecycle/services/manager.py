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

from main.apps.ue_lifecycle.services import cu_client, du_client, kit_client, omniverse_client, ru_client
from main.apps.ue_lifecycle.services.interp import interp_position
from main.apps.ue_lifecycle.services import cell_selection
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
        # SimSession uuid — sim_orchestrator 在 start_sim 時 set,signal/position
        # history 寫入時帶這個 group key,Playback 才能依 session 撈回放。
        self._session_uuid: str | None = None
        # signal ingest 節流 — 每 N 個 trajectory tick 才打一次(避免每 100ms
        # 打 Omniverse 太頻繁)。N=5 → 500ms 一次,跟 sim_dt 對齊。
        self._camp_last_try_ms: dict[str, int] = {}   # 掉話 UE 上次選網時間(節流)
        self._tick_count_since_signal_ingest = 0

    def set_session_uuid(self, session_uuid: str | None) -> None:
        self._session_uuid = session_uuid
        logger.info("UeLifecycleManager session_uuid=%s", session_uuid)

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
            # RUNNING = 正常;STANDBY = 掉話中,位置照算(量測鏈才會恢復)但不灌流量。
            # 只有 STOPPED 才真的不動它。
            if ue.state not in (UeThreadState.RUNNING, UeThreadState.STANDBY):
                continue
            camping = ue.state is UeThreadState.STANDBY

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

            # ── (2) 掉話中:自己選網,訊號回來就重新發起連線(TS 38.304 + 38.331)
            if camping:
                self._try_recamp(ue_id, (x, y, z), now_ms)
                continue          # 掉話中沒有承載,不得灌流量
            try:
                injected_total += ue.traffic_gen.tick()
            except Exception:
                logger.exception("traffic_gen.tick failed for ue=%s", ue_id)

        # ── (3) Batch write RU + per-UE Kit ─
        # RU = RAN 模擬用(同步,影響 path loss/SINR 正確性)
        # Kit = 純視覺化,move_ue 已改為非阻塞發佈(latest-wins,背景 worker 推送),
        #       Kit 卡住時只會丟棄中間畫格,不會拖慢這個 trajectory loop。
        if positions_for_ru:
            ru_client.update_ues_batch(positions_for_ru)
            for ue_id, x, y, z in positions_for_kit:
                kit_client.move_ue(ue_id, x, y, z)

        # ── (4) Signal history ingest(每 N 個 tick 一次,寫 signal_history + UeState)
        # Playback / KpmSummaryLine / /scenarios chart 都依賴 signal_history。
        self._tick_count_since_signal_ingest += 1
        if positions_for_ru and self._tick_count_since_signal_ingest >= 5:
            self._tick_count_since_signal_ingest = 0
            try:
                self._ingest_signals(positions_for_kit)
            except Exception:
                logger.exception("signal ingest failed (non-fatal)")

        # 每 100 tick (~10s) log 一次 traffic 累計, 避免 spam
        if injected_total > 0 and (now_ms // 1000) % 10 == 0:
            logger.debug("traffic tick injected=%d sdu", injected_total)

    def _ingest_signals(self, positions_for_kit: list[tuple[str, float, float, float]]) -> None:
        """每隔 N tick 從 DU 拉最新 per-UE 訊號,bundle 位置一起 POST Omniverse
        SignalIngestor.create → 寫 signal_history 表(Playback 回放用)。
        positions_for_kit = [(ue_id, x, y, z), ...] 給訊號 attach 當前位置。
        """
        ue_signals = du_client.fetch_ue_signals()  # {ue_id: {rsrp_dbm, sinr_db, ...}}
        if not ue_signals:
            return
        pos_map = {ue_id: (x, y, z) for ue_id, x, y, z in positions_for_kit}
        signals_payload: list[dict] = []
        for ue_id, sig in ue_signals.items():
            if sig.get("rsrp_dbm") is None or sig.get("sinr_db") is None:
                continue
            entry: dict = {
                "ue_name": ue_id,
                "serving_cell": sig.get("serving_cell") or "unknown",
                # serving_cell_id 讓 Kit label 的「Cell X PCI Y」行有值(否則顯示 '-')。
                # DU dump_pm 目前只提供 cell_id(serving_cell),PCI 尚未提供 → 帶 cell_id,
                # PCI 由 label 端在缺值時省略(見 labels/extension.py)。
                "serving_cell_id": sig.get("serving_cell"),
                "rsrp_dbm": float(sig["rsrp_dbm"]),
                "sinr_db": float(sig["sinr_db"]),
            }
            # serving PCI(DU 由 cell_id→pci 對照提供)→ label 顯示 "Cell X PCI Y"
            if sig.get("serving_pci") is not None:
                entry["serving_pci"] = sig["serving_pci"]
            # 可選 KPM 欄
            for k in ("throughput_dl_mbps", "throughput_ul_mbps", "mcs_dl",
                      "prb_used_dl", "mimo_rank"):
                if sig.get(k) is not None:
                    entry[k] = sig[k]
            # rsrp_map(per-cell)
            rsrp_map = sig.get("rsrp_map") or {}
            if rsrp_map:
                entry["rsrp_map"] = rsrp_map
            # 帶當前位置
            if ue_id in pos_map:
                x, y, z = pos_map[ue_id]
                entry["position"] = [x, y, z]
            signals_payload.append(entry)
        if signals_payload:
            omniverse_client.ingest_signals(signals_payload, session_uuid=self._session_uuid)

    def _try_recamp(self, ue_id: str, pos: tuple[float, float, float], now_ms: int) -> None:
        """掉話 UE 的 IDLE 態選網。節流:每 CAMP_RETRY_SEC 才量一次。

        決策在 UE 端 —— IDLE 沒有 measConfig,網路端看不到它,只能自己量自己決定。
        量到合格 cell 就走 rrc_attach(RRCSetupRequest + RRCSetupComplete),
        跟開機初次入網同一條路;CU 收到就把它帶回 CONNECTED,
        下一輪 _sync_from_cu 自然把 thread 拉回 RUNNING。
        """
        last = self._camp_last_try_ms.get(ue_id, 0)
        if now_ms - last < settings.CAMP_RETRY_SEC * 1000:
            return
        self._camp_last_try_ms[ue_id] = now_ms
        cell, rsrp = cell_selection.select_cell(
            ue_id, pos, min_rsrp_dbm=settings.CAMP_MIN_RSRP_DBM,
        )
        if not cell:
            return
        logger.info("UE %s 選到 %s(rsrp=%.1f ≥ %.1f)→ 重新發起 RRC 連線",
                    ue_id, cell, rsrp, settings.CAMP_MIN_RSRP_DBM)
        try:
            if cu_client.rrc_attach(ue_id):
                cu_client.force_serving_cell(ue_id, cell)
                # 不 pop —— attach 回 True 只代表訊息送出去了,是否真的回到
                # CONNECTED 由下一輪 _sync_from_cu 認定。這裡 pop 會讓節流失效,
                # 變成每個 tick 都重送(2026-08-20 實測 0.3 秒一次)。
        except Exception:  # noqa: BLE001
            logger.exception("re-camp attach failed ue=%s", ue_id)

    def _sync_from_cu(self) -> None:
        sessions = cu_client.list_sessions()
        # CU 端「真實 active」: rrc_state == CONNECTED (含 traffic_profile)
        cu_set = {
            s["ue_id"]: s for s in sessions
            if s.get("rrc_state") == "CONNECTED"
        }
        # 掉話(IDLE)但 context 還在的 UE —— **不可以殺 thread**。
        # 殺掉就不再推位置 → RU 量不到 → DU 不產量測 → CU 永遠不知道它回到覆蓋內,
        # 於是走出死角也回不來(死結)。保留 thread 繼續走軌跡、但不灌流量,
        # 量測鏈就會自己恢復,CU 的 [RE-CAMP] 會把它收回 CONNECTED。
        idle_ids = {
            s["ue_id"] for s in sessions
            if s.get("rrc_state") == "IDLE" and s["ue_id"] not in cu_set
        }

        with self._lock:
            existing = set(self._threads.keys())
            cu_ids = set(cu_set.keys())

            new_ues = cu_ids - existing
            # 掉話中的不算「消失」—— 留著讓它繼續走(見上方說明)
            removed = existing - cu_ids - idle_ids
            camping = (existing & idle_ids)
            kept = cu_ids & existing

            # 新加: spawn thread
            for ue_id in new_ues:
                self._spawn_thread(ue_id, cu_set[ue_id])

            # 消失: stop thread
            for ue_id in removed:
                t = self._threads.pop(ue_id, None)
                if t:
                    t.stop()

            # 掉話中: 降到 STANDBY(位置照算、traffic 停),等 CU 收回
            for ue_id in camping:
                t = self._threads.get(ue_id)
                if t is not None and t.state == UeThreadState.RUNNING:
                    t.transition_to(UeThreadState.STANDBY)
                    logger.info("UE %s 掉話 → STANDBY(保留軌跡,等訊號回來重新駐留)", ue_id)

            # 沿用: 更新 snapshot
            for ue_id in kept:
                t = self._threads[ue_id]
                t.update_snapshot(self._build_snapshot(cu_set[ue_id]))
                # 掉話後重新駐留成功 → thread 拉回 RUNNING。少了這段,UE 會
                # 一直卡在 STANDBY:CU 已經是 CONNECTED、位置也在動,但不灌流量。
                if self.sim_running and t.state == UeThreadState.STANDBY:
                    t.transition_to(UeThreadState.RUNNING)
                    self._camp_last_try_ms.pop(ue_id, None)
                    logger.info("UE %s 重新駐留成功 → RUNNING(serving=%s)",
                                ue_id, cu_set[ue_id].get("serving_cell", ""))

        if new_ues or removed or camping:
            logger.info(
                "UE list diff: added=%s removed=%s camping=%s kept_count=%d",
                sorted(new_ues), sorted(removed), sorted(camping), len(kept),
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
