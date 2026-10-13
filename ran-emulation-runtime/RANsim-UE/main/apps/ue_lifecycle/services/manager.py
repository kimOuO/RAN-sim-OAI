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

    _SCENE_CLOCK_REFRESH_MS = 2000

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
        # 劇本在場時段 {ue: [[t0, t1], ...]}(秒)。空 = 沒有劇本(live 模式),
        # 完全不動可見性。
        self._active_windows: dict[str, list[list[float]]] = {}
        self._serving_hint: dict[str, str] = {}      # 回場時要 attach 回哪個 cell
        self._traffic_hint: dict[str, dict] = {}     # 回場時要還原的流量 profile
        # 劇本倍速。軌跡與在場時段的 t 都是「劇本秒」,而這裡的時鐘是牆鐘,
        # 兩者差一個 speed_x —— 不乘回去,2x 的場景位置就慢一半,30x 的人永遠進不了場。
        self._sim_speed_x: float = 1.0
        # 劇本時鐘快取:(DU 回報的 scene_sim_ms, 取得當下的牆鐘 ms)。
        # 每 _SCENE_CLOCK_REFRESH_MS 跟 DU 對一次,中間用倍速外推 —— 每個 tick 都打 DU 太吵,
        # 而 2 秒內的漂移遠小於在場時段的解析度。
        self._scene_clock: tuple[int, int] | None = None
        self._last_visible: dict[str, bool] = {}
        # 天線高度 {ue: 公尺}。waypoints 的 y 是腳底高度(視覺層要的),
        # 推給 RU/Sionna 時要加上這個值 —— 少了它等於把人埋在地板裡算通道。
        self._antenna_h: dict[str, float] = {}

    def set_session_uuid(self, session_uuid: str | None) -> None:
        self._session_uuid = session_uuid
        logger.info("UeLifecycleManager session_uuid=%s", session_uuid)

    def set_antenna_heights(self, heights: dict[str, float] | None) -> None:
        """設定每個 UE 的天線高度(相對腳底)。換 session 要重設。"""
        self._antenna_h = heights or {}
        logger.info("UeLifecycleManager antenna_heights=%d ues", len(self._antenna_h))

    def set_presence_hints(self, serving: dict[str, str] | None, traffic: dict[str, dict] | None) -> None:
        """UE 回場重新 attach 時要還原的 serving cell 與流量 profile。
        由 sim_orchestrator 在 start 時從劇本填入。"""
        self._serving_hint = dict(serving or {})
        # traffic=None 是「這次沒有要改流量提示」,不是「清空」—— sim_orchestrator 與
        # scenario_driver 都會呼叫,兩者順序不該讓後者的 profile 被前者洗掉。
        if traffic is not None:
            self._traffic_hint = dict(traffic)

    def set_sim_speed(self, speed_x: float) -> None:
        """劇本倍速,由 driver 在 start 時填入。軌跡/在場時段換算劇本時間要用。"""
        self._sim_speed_x = max(0.01, float(speed_x or 1.0))
        self._scene_clock = None
        logger.info("UeLifecycleManager sim_speed_x=%.3f", self._sim_speed_x)

    def _scenario_now_ms(self, now_ms: int) -> float:
        """目前的劇本時間(ms)。來源是 DU 的 scene clock —— cached 通道查表用的同一個。

        DU 沒跑滿設定倍速時,牆鐘×倍速會比真正的劇本時鐘跑得快;在場時段若用前者,
        進出場的時間點就會跟通道與 KPM 對不起來。
        """
        from main.apps.ue_lifecycle.services import du_client
        if (self._scene_clock is None
                or now_ms - self._scene_clock[1] >= self._SCENE_CLOCK_REFRESH_MS):
            v = du_client.get_scene_clock()
            if v is not None:
                # (劇本 ms, 讀到的牆鐘, 實際達成倍率)
                self._scene_clock = (v[0], now_ms, v[1])
        if self._scene_clock is None:
            return 0.0
        scene_ms, at_ms, ach = self._scene_clock
        # 2026-09-22:外推用 DU **實際達成**的倍率,不用設定值(見 du_client.get_scene_clock),
        # 並且**永不倒退**:校正時若 DU 的值比上次回的小,就停在原地等 DU 追上。
        # 時鐘倒退會讓在場時段邊界的 UE 反覆離場/回場,每次都是一整套 RRC 流程,
        # 過載時這股負載會把 DU 拖得更慢 —— 正回饋。
        est = scene_ms + (now_ms - at_ms) * min(ach, self._sim_speed_x)
        last = getattr(self, "_scene_now_last_ms", 0.0)
        if est < last:
            est = last
        self._scene_now_last_ms = est
        return est

    def _scenario_elapsed_ms(self, traj: dict, now_ms: int) -> float:
        """目前的劇本經過時間,並套用 loop/once 的收尾規則。"""
        elapsed_ms = self._scenario_now_ms(now_ms)
        wps = traj.get("waypoints") or []
        total_ms = wps[-1].get("t_ms", 0) if wps else 0
        if total_ms > 0 and traj.get("mode", "loop") == "loop":
            elapsed_ms %= total_ms
        return max(0.0, elapsed_ms)

    def _apply_presence(self, ue_id: str, present: bool) -> bool:
        """UE 進場 / 離場時同步 RAN 側狀態。**沒有開關** —— 人不在場景裡就不該算他的
        網路連線,這是語意而非選項(2026-09-21)。

        離場:CU 釋放 RRC + F1AP UE Context Release(DU 一併清排程與 RLC)。
        回場:重跑一次 attach(RRC → DU register → serving cell → 流量),
        與開場的 ue_attach 同一組步驟。
        失敗只記 log:在場狀態是模擬情境的一部分,不該讓它中斷整個 driver。
        """
        from main.apps.ue_lifecycle.services import cu_client
        try:
            if not present:
                cu_client.release_ue(ue_id)
                return True
            serving = self._serving_hint.get(ue_id) or ""
            from main.apps.ue_lifecycle.services import ran_endpoints
            topo = ran_endpoints.topology()
            if topo is not None and serving:
                # 多 gNB:在回場 cell 的 DU 接入(Initial UL RRC 帶 cell),不再事後強制換 cell。
                # 被拒(cell barred / 正在進入節能 = RRC Reject)時改選場上其他 cell,
                # 就像真實 UE 看到 SIB1 cellBarred 改駐別顆;之後 A3 會再把它帶到最好的 cell。
                candidates = [serving] + [c.cell_id for d in topo.dus() for c in d.cells if c.cell_id != serving]
                chosen = next((c for c in candidates if cu_client.rrc_attach(ue_id, c)), None)
                if chosen is None:
                    logger.warning("UE %s 回場:RRC attach 失敗(試過 %s)", ue_id, candidates)
                    return False
                if chosen != serving:
                    logger.info("UE %s 回場:%s 不收(barred / 節能),改接 %s", ue_id, serving, chosen)
            else:
                if not cu_client.rrc_attach(ue_id):
                    logger.warning("UE %s 回場:RRC attach 失敗", ue_id)
                    return False
                from main.apps.ue_lifecycle.services import du_client
                if serving:
                    du_client.register_ue_at(ue_id, serving_cell=serving)
                    cu_client.force_serving_cell(ue_id, serving)
            # 開場就不在場的人 CU 端從沒收過 profile(release_ue 只是沒清掉既有的),
            # 所以有提示就推一次;沒有提示才沿用 CU 既存值。
            prof = self._traffic_hint.get(ue_id)
            if prof:
                cu_client.update_traffic_profile(ue_id, prof)
            logger.info("UE %s 回場:已重新 attach(serving=%s)", ue_id, serving or "(由 CU 決定)")
            return True
        except Exception:  # noqa: BLE001
            logger.exception("UE %s 進出場同步失敗(present=%s)", ue_id, present)
            return False

    def set_active_windows(self, windows: dict[str, list[list[float]]] | None) -> None:
        """設定劇本在場時段。換 session 要重設,否則沿用上一齣戲的時間軸。"""
        self._active_windows = windows or {}
        self._last_visible = {}
        logger.info("UeLifecycleManager active_windows=%d ues", len(self._active_windows))

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
                elapsed = self._scenario_elapsed_ms(traj, now_ms)
                x, y, z = interp_position(
                    traj["waypoints"], elapsed, mode=traj.get("mode", "loop"),
                )
                ue.position = (x, y, z)
            else:
                # No trajectory — use current static position (default 0,0,0)
                x, y, z = ue.position if ue.position else (0.0, 0.0, 0.0)
            # 無線電要的是**天線位置**,不是腳底位置。waypoints 的 y 被歸零成
            # 腳底高度是為了視覺層(Kit 把 y 當腳底),直接拿去算通道等於把人
            # 埋進地板 —— 實測室內走廊 RSRP 掉到 -139 dBm,UE 一直掉話重駐留。
            positions_for_ru.append({
                "id": ue_id,
                "position": {"x": x, "y": y + self._antenna_h.get(ue_id, 0.0), "z": z},
            })
            positions_for_kit.append((ue_id, x, y, z))

            # ── (2) 掉話中:自己選網,訊號回來就重新發起連線(TS 38.304 + 38.331)
            if camping:
                # 選網也要用天線位置,跟推給 RU 的同一個座標
                self._try_recamp(
                    ue_id, (x, y + self._antenna_h.get(ue_id, 0.0), z), now_ms)
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
            for ue_id, x, _y, z in positions_for_kit:
                # 不傳 y：劇本的 y 是天線高度，Kit 的 move_ue 把 y 當腳底高度，
                # 直接推過去人會浮在半空。UE 走在地面上，高度由 build 時決定，
                # 每 tick 只需要更新平面位置。
                kit_client.move_ue(ue_id, x, z)

        # 在場判斷只看劇本時間與 trajectory,跟「現在有沒有人在場上」無關,
        # 所以不能掛在 positions_for_ru 底下 —— 2026-09-21:全員離場時這個 list 是空的,
        # 於是可見性永遠不再同步,誰都回不來(要在場上才進得來的死結)。
        self._sync_visibility(traj_store, now_ms)

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

    def _sync_visibility(self, traj_store, now_ms: int) -> None:
        """讓「離場」的人真的從畫面消失,而不是站在走廊盡頭被看見。

        時間軸取自 UE 自己的 trajectory(now_ms - start_at_ms),跟
        interp_position 用的是同一個 elapsed —— 位置與可見性因此不可能各走各的。

        判準不能改用位置:等候點就在走廊的兩個盡頭上,而人正常來回走也會走到
        盡頭,用距離判斷會把走到底的人誤判成離場。

        只在狀態「有變」時才推 Kit —— 每 tick 對 18 個人各打一發 HTTP 會把
        Kit 的命令佇列塞爆,而進出場一天也才數次。
        """
        if not self._active_windows:
            return
        for ue_id, windows in self._active_windows.items():
            traj = traj_store.get(ue_id)
            if not traj:
                continue
            t = self._scenario_elapsed_ms(traj, now_ms) / 1000.0
            visible = any(a <= t < b for a, b in windows)
            if self._last_visible.get(ue_id) == visible:
                continue
            # 2026-09-27:RAN 側(回場接入)失敗就不記成已同步,3 秒後重試 —— 以前失敗一次那個人就整段沒有服務
            _retry_at = getattr(self, "_presence_retry_at", {})
            if now_ms < _retry_at.get(ue_id, 0):
                continue
            self._last_visible[ue_id] = visible
            # 2026-09-20:active_windows 以前只管「看不看得到」—— 3D 不畫、Kit 藏起來,
            # 但 RRC 連線、DU 排程、流量注入全照舊,於是「人不見了卻還掛在 gNB 上傳資料」。
            # 這裡讓它真的離場 / 回場,沒有開關 —— 不在場景裡的人不該算網路連線。
            # 注意:Kit 不是我們的元件、也可能沒在跑,所以 RAN 側動作不能綁在它的成敗上。
            if not self._apply_presence(ue_id, visible):
                self._last_visible.pop(ue_id, None)
                self._presence_retry_at = {**_retry_at, ue_id: now_ms + 3000}
                continue
            if not kit_client.set_ue_visible(ue_id, visible):
                # 推失敗就把快取清掉,下一個 tick 會重試(不要記成已同步)
                self._last_visible.pop(ue_id, None)
                continue
            n_on = sum(1 for v in self._last_visible.values() if v)
            logger.info("visibility @ %02d:%02d — %s → %s (在場 %d/%d)",
                        int(t // 3600), int((t % 3600) // 60), ue_id,
                        "在場" if visible else "離場",
                        n_on, len(self._last_visible))

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
            from main.apps.ue_lifecycle.services import ran_endpoints
            if ran_endpoints.topology() is not None:
                cu_client.rrc_attach(ue_id, cell)       # 多 gNB:在選到的 cell 的 DU 接入
            elif cu_client.rrc_attach(ue_id):
                cu_client.force_serving_cell(ue_id, cell)
                # 不 pop —— attach 回 True 只代表訊息送出去了,是否真的回到
                # CONNECTED 由下一輪 _sync_from_cu 認定。這裡 pop 會讓節流失效,
                # 變成每個 tick 都重送(2026-08-20 實測 0.3 秒一次)。
        except Exception:  # noqa: BLE001
            logger.exception("re-camp attach failed ue=%s", ue_id)

    def _sync_from_cu(self) -> None:
        sessions = cu_client.list_sessions()
        if sessions is None:
            # CU 不可達(重啟/暫時斷線)→ 凍結本輪 diff,現有執行緒原樣保留。
            # 千萬不可把失敗當空表:那會殺光執行緒再重建,重建者間歇性斷量測鏈(坑7)。
            self._cu_down_streak = getattr(self, "_cu_down_streak", 0) + 1
            if self._cu_down_streak in (1, 10, 60):
                logger.warning("CU 不可達(連續 %d 次)— UE 執行緒凍結保留,等 CU 回來", self._cu_down_streak)
            return
        if getattr(self, "_cu_down_streak", 0):
            logger.info("CU 恢復(斷 %d 輪)— 續用原執行緒,快照照常更新", self._cu_down_streak)
            self._cu_down_streak = 0
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
            threads = [t.status() for t in self._threads.values()]
        # 前端 Scene Layout 讀這支拿即時位置,可見性也一起帶出去 ——
        # 否則 Omniverse 裡離場的人消失了,前端卻還把他畫在走廊盡頭。
        # 沒有劇本(live 模式)時 _last_visible 是空的,一律 True。
        for t in threads:
            t["visible"] = self._last_visible.get(t.get("ue_id"), True)
        return {
            "sim_running": self.sim_running,
            "thread_count": len(threads),
            "threads": threads,
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
