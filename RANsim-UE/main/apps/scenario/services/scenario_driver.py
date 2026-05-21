"""Phase B B.4 — 跑在 RANsim-UE 內的 scenario driver thread。

每 wall_tick_ms 醒一次:
  1. 算當前 sim_tick_idx,內插所有 UE 位置 → batch POST RU update_ues
  2. 內插所有 UE traffic → 逐個 inject_sdu_batch 到 DU
  3. 進到下一 tick

不動原本 ue_lifecycle 邏輯;呼叫的是既有 du_client / ru_client。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from main.apps.scenario.services.scenario_loader import (
    ScenarioSpec, fetch, interpolate_position, interpolate_traffic,
)
from main.apps.ue_lifecycle.services import cu_client, du_client, omniverse_client, ru_client


logger = logging.getLogger(__name__)


class ScenarioDriver:
    def __init__(
        self,
        scenario: ScenarioSpec,
        target_wall_tick_ms: int = 500,
    ):
        self.scenario = scenario
        # wall_tick_ms 跟 DU 的 _wall_tick_ms 要保持一致才能讓 sfn/slot 對齊 cache
        self.target_wall_tick_ms = max(10, min(500, int(target_wall_tick_ms)))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = {
            "running": False,
            "scenario_id": scenario.scenario_id,
            "sim_tick_idx": 0,
            "total_ticks": scenario.total_ticks,
            "elapsed_wall_sec": 0.0,
            "elapsed_sim_sec": 0.0,
            "sim_speed_x": scenario.tick_ms / self.target_wall_tick_ms,
            "inject_call_count": 0,
            "position_push_count": 0,
            "last_error": "",
        }
        self._t_start: float = 0.0

    def start(self) -> bool:
        if self.state["running"]:
            return False
        # Step 1a — 同步 gNB 拓樸(如果劇本有指定 gnbs 欄位):
        # 把劇本的 gnbs/cells 推到 Omniverse DB + Kit,scene Layout 就會反映新拓樸。
        # 沒帶 gnbs 的劇本不會動到既有 gNB。
        # cell.position(optional)— DAS / multi-TRP 場景一個 gNB 多 cell 物理分離。
        # 沒指定就 fallback 到 gnb.position(傳統 co-sited sector)。
        gnb_payload = []
        for g in self.scenario.gnbs:
            cells_payload = []
            for c in g.cells:
                cell_entry: dict[str, Any] = {
                    "cell_id": c.cell_id,
                    "pci": c.pci,
                    "azimuth_deg": c.azimuth_deg,
                }
                if c.position is not None:
                    cell_entry["position"] = [c.position[0], c.position[1], c.position[2]]
                cells_payload.append(cell_entry)
            gnb_payload.append({
                "name": g.name,
                "position": [g.position[0], g.position[1], g.position[2]],
                "frequency_ghz": g.frequency_ghz,
                "bandwidth_mhz": g.bandwidth_mhz,
                "power_dbm": g.power_dbm,
                "active": g.active,
                "color": list(g.color),
                "target_height_m": g.target_height_m,
                "cells": cells_payload,
            })
        if gnb_payload:
            try:
                gstats = omniverse_client.sync_gnbs_to_scenario(gnb_payload)
                logger.info("scenario %s gnb sync: %s", self.scenario.scenario_id, gstats)
            except Exception as e:  # noqa: BLE001
                logger.warning("gnb sync failed (Omniverse offline?): %s", e)

        # Step 1ab — 同步建築(劇本可帶 buildings 區塊)
        # 只把劇本顯式給的欄位放進 payload,沒給的(size/color/rotation/target_height)
        # 留給 backend BuildingWriteSerializer 從 preset_id="brownstone01" 取
        # default_size / default_color / default_rotation,跟前端 /editor Build 一致。
        building_payload = []
        for b in self.scenario.buildings:
            entry: dict[str, Any] = {
                "name": b.name,
                "position": [b.position[0], b.position[1], b.position[2]],
            }
            if b.size is not None:
                entry["size"] = [b.size[0], b.size[1], b.size[2]]
            if b.color is not None:
                entry["color"] = [b.color[0], b.color[1], b.color[2]]
            if b.rotation_xyz_deg is not None:
                entry["rotation_xyz_deg"] = [
                    b.rotation_xyz_deg[0], b.rotation_xyz_deg[1], b.rotation_xyz_deg[2],
                ]
            if b.material:
                entry["material"] = b.material
            if b.target_height_m is not None:
                entry["target_height_m"] = b.target_height_m
            building_payload.append(entry)
        if building_payload:
            try:
                bstats = omniverse_client.sync_buildings_to_scenario(building_payload)
                logger.info("scenario %s building sync: %s", self.scenario.scenario_id, bstats)
            except Exception as e:  # noqa: BLE001
                logger.warning("building sync failed (Omniverse offline?): %s", e)

        # Step 1b — 把 Omniverse 場景同步成「只有 scenario 的 UE」:
        # 刪掉上次劇本留下的 + 前端手動建的 stray UE,建上 scenario 缺的,
        # 再 Scene/build 讓 Kit prim list 對齊。確保 Scene Layout 顯示乾淨。
        # 失敗(Omniverse 沒開)只 log,不擋 RAN sim。
        scenario_ue_names = [ue.name for ue in self.scenario.ues]
        try:
            stats = omniverse_client.sync_scene_to_scenario(scenario_ue_names)
            logger.info(
                "scenario %s scene sync: %s",
                self.scenario.scenario_id, stats,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("scene sync failed (Omniverse offline?): %s", e)

        # Step 1bc — 根據劇本 precompute 狀態自動切 RU channel mode。
        # precompute_status == "ready" → cached + 這個 scenario_id(載對應 npz)
        # 其他狀態 / 沒做過 precompute  → live(每 dl_tti 即時 Sionna)
        # 沒這步上一場留下的 cached/scenario_id 會把本場 lookup 全打到 miss,SINR/MCS/thp
        # 全 0,/logs Cell Grid / UE Lab 看起來都不動。
        try:
            if (self.scenario.precompute_status or "").lower() == "ready":
                ok = ru_client.set_channel_mode("cached", self.scenario.scenario_id)
                logger.info("scenario %s RU set_channel_mode=cached: ok=%s", self.scenario.scenario_id, ok)
            else:
                ok = ru_client.set_channel_mode("live")
                logger.info(
                    "scenario %s RU set_channel_mode=live (precompute_status=%s)",
                    self.scenario.scenario_id, self.scenario.precompute_status,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("set_channel_mode failed (continuing with whatever RU is in): %s", e)

        # Step 1c — RAN backend scene-apply 清理鏈 mirror Dashboard handleStartSim C.1〜C.5。
        # 沒這段的話,上一場 sim 的 UE/cell 會殘留在 CU/DU(/logs 看到「鬼魂 UE」),
        # 而且 DU MAC cell 列表跟劇本對不上,本場 UE 排不進 scheduler →
        # KpmReporter 給空值(/logs 看到「沒有數值」)。endpoint 全用既有的,
        # 失敗只 warn 不擋,維持「Omniverse 沒開仍能跑 RAN sim」的容忍度。
        self._apply_scene_to_backend()

        # Step 2 — Setup: 確保 CU 有 traffic_profile 對應的 UE session,RLC entity 建好。
        # (Dashboard Start Sim 通常會做這事;driver 直接被叫時自己保險一次。)
        self._setup_rlc_entities()
        self._stop.clear()
        self._t_start = time.perf_counter()
        self.state["running"] = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="scenario-driver",
        )
        self._thread.start()
        logger.info(
            "ScenarioDriver started: scenario=%s wall_tick=%dms sim_dt=%dms speed=%.2fx total_ticks=%d",
            self.scenario.scenario_id, self.target_wall_tick_ms,
            self.scenario.tick_ms, self.state["sim_speed_x"],
            self.scenario.total_ticks,
        )
        return True

    def _apply_scene_to_backend(self):
        """把劇本拓樸推進 RU/DU/CU 並清掉上一場留下的 stale row。

        對齊 Dashboard handleStartSim C.1〜C.5 的 best-effort scene-apply chain:
          C.1 RU update_cells       — 劇本有 gnbs.cells 才推,exclude-delete RU cell DB
          C.2 RU update_ues         — 用第一個 tick 的 UE 位置推,clear_stale=True
          C.3 DU MAC replace_cells  — 劇本有 cells 才推,清掉舊 cell
          C.4 DU Tick replace_ues   — 用劇本 UE 名單 unregister 舊 UE
          C.5 CU release_stale      — keep=劇本 UE 名單,其餘標 IDLE / DU fan-out

        劇本沒帶 gnbs 時 C.1/C.3 skip,沿用前端 /editor 拉出來的 cell 拓樸,只清 UE。
        任何一步失敗只 warn 不擋,跟 Dashboard 一樣維持 best-effort。
        """
        scenario_ue_names = [ue.name for ue in self.scenario.ues]

        # 構 RU/DU cell payload(僅當劇本帶 gnbs 時)
        # cell.position(optional)如有就用 → DAS / multi-TRP 場景一個 gNB 多 cell 物理分離,
        # 沒給就 fallback gnb.position(傳統 co-sited sector)
        ru_cells: list[dict[str, Any]] = []
        du_cells: list[dict[str, Any]] = []
        for g in self.scenario.gnbs:
            for i, c in enumerate(g.cells):
                cell_id = c.cell_id or f"{g.name}_c{i}"
                cell_pos = c.position if c.position else g.position
                ru_cells.append({
                    "name": cell_id,
                    "pci": c.pci,
                    "azimuth_deg": c.azimuth_deg,
                    "position": [cell_pos[0], cell_pos[1], cell_pos[2]],
                    "frequency_ghz": g.frequency_ghz,
                    "bandwidth_mhz": g.bandwidth_mhz,
                    "gnb_id": g.name,
                    "power_dbm": g.power_dbm,
                })
                du_cells.append({
                    "cell_id": cell_id,
                    "pci": c.pci,
                    "freq_ghz": g.frequency_ghz,
                    "bw_mhz": g.bandwidth_mhz,
                    "gnb_id": g.name,
                })

        # C.1 RU update_cells
        if ru_cells:
            try:
                ru_client.update_cells(ru_cells)
                logger.info("scenario %s RU update_cells: %d cells", self.scenario.scenario_id, len(ru_cells))
            except Exception as e:  # noqa: BLE001
                logger.warning("RU update_cells failed: %s", e)

        # C.2 RU update_ues — 用劇本第一個 tick 的位置推,clear_stale=True 觸發 RU 端 DELETE
        ru_ue_payload = []
        for ue in self.scenario.ues:
            pos = interpolate_position(ue.positions, 0.0)
            ru_ue_payload.append({"id": ue.name, "position": {"x": pos[0], "y": pos[1], "z": pos[2]}})
        if ru_ue_payload:
            try:
                ru_client.update_ues_batch(ru_ue_payload, clear_stale=True)
                logger.info("scenario %s RU update_ues(clear_stale): %d UEs", self.scenario.scenario_id, len(ru_ue_payload))
            except Exception as e:  # noqa: BLE001
                logger.warning("RU update_ues failed: %s", e)

        # C.3 DU MAC replace_cells
        if du_cells:
            try:
                du_client.replace_cells(du_cells)
                logger.info("scenario %s DU MAC replace_cells: %d cells", self.scenario.scenario_id, len(du_cells))
            except Exception as e:  # noqa: BLE001
                logger.warning("DU MAC replace_cells failed: %s", e)

        # C.4 DU Tick replace_ues — 即使劇本沒 UE 也 OK,replace_ues([]) 會清空
        try:
            du_client.replace_ues(scenario_ue_names)
            logger.info("scenario %s DU Tick replace_ues: keep=%s", self.scenario.scenario_id, scenario_ue_names)
        except Exception as e:  # noqa: BLE001
            logger.warning("DU Tick replace_ues failed: %s", e)

        # C.5 CU release_stale — 把不在劇本名單的 CONNECTED UE 標 IDLE,fan-out 通知 DU
        try:
            cu_client.release_stale(scenario_ue_names, force=False)
            logger.info("scenario %s CU release_stale: keep=%s", self.scenario.scenario_id, scenario_ue_names)
        except Exception as e:  # noqa: BLE001
            logger.warning("CU release_stale failed: %s", e)

    def _setup_rlc_entities(self):
        """自動 attach 所有 scenario UE,讓 traffic inject 找得到 RLC entity。

        Chain(對齊 Dashboard handleStartSim § D–E):
          1. CU RRC SetupRequest + SetupComplete  → UeContext, rrc_state=CONNECTED
          2. DU register_ue                        → _ue_registry
          3. CU force_serving_cell (manual HO)     → UeContext.serving_cell 填好
          4. CU update_traffic_profile             → F1AP UeCtxSetup → DU 建 RLC entity

        4 步任一失敗只 log 不擋 start;但後續 inject_sdu_batch 會收到 no_entity 警告。
        """
        target_cell = self.scenario.default_serving_cell
        n_attached = 0
        for ue in self.scenario.ues:
            steps_ok = True
            if not cu_client.rrc_attach(ue.name):
                logger.warning("attach UE %s: RRC failed", ue.name); steps_ok = False
            if steps_ok and not du_client.register_ue_at(ue.name, serving_cell=target_cell):
                logger.warning("attach UE %s: DU register_ue failed", ue.name); steps_ok = False
            if steps_ok and not cu_client.force_serving_cell(ue.name, target_cell):
                logger.warning("attach UE %s: handover failed", ue.name); steps_ok = False
            if steps_ok and not cu_client.update_traffic_profile(
                ue.name, {"pattern": "cbr", "rate_mbps": 1.0, "bearer_id": 1},
            ):
                logger.warning("attach UE %s: update_traffic_profile failed", ue.name)
                steps_ok = False
            if steps_ok:
                n_attached += 1
                logger.info("UE %s attached → serving=%s, RLC entity ready", ue.name, target_cell)
        logger.info(
            "scenario_driver attached %d/%d UEs (default_serving_cell=%s)",
            n_attached, len(self.scenario.ues), target_cell,
        )

    def stop(self) -> bool:
        if not self.state["running"]:
            return False
        self._stop.set()
        self.state["running"] = False
        logger.info(
            "ScenarioDriver stopped at tick %d/%d",
            self.state["sim_tick_idx"], self.scenario.total_ticks,
        )
        return True

    def _loop(self):
        next_t = time.perf_counter()
        while not self._stop.is_set():
            tick_idx = self.state["sim_tick_idx"]
            if tick_idx >= self.scenario.total_ticks:
                logger.info("Scenario %s finished all ticks", self.scenario.scenario_id)
                self.state["running"] = False
                break

            try:
                self._push_one_tick(tick_idx)
            except Exception as e:
                self.state["last_error"] = str(e)
                logger.exception("ScenarioDriver tick body error: %s", e)

            self.state["sim_tick_idx"] = tick_idx + 1
            self.state["elapsed_wall_sec"] = time.perf_counter() - self._t_start
            self.state["elapsed_sim_sec"] = (tick_idx + 1) * self.scenario.tick_ms / 1000.0

            # wall-clock pacing
            period = self.target_wall_tick_ms / 1000.0
            next_t += period
            sleep_for = next_t - time.perf_counter()
            if sleep_for > 0:
                self._stop.wait(sleep_for)
            else:
                # 跟不上節奏(Sionna ceiling 或網路堵塞)— 重設 next_t 防止累積飄移
                next_t = time.perf_counter()

    def _push_one_tick(self, tick_idx: int):
        # 在 scenario 的 sim-time 軸上,當前 tick 對應的 sim-second
        t_sec = tick_idx * self.scenario.tick_ms / 1000.0

        # 1. 收所有 UE 位置 batch 推 RU
        positions: list[dict[str, Any]] = []
        for ue in self.scenario.ues:
            pos = interpolate_position(ue.positions, t_sec)
            positions.append({
                "id": ue.name,
                "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
            })
        if positions:
            # 第一個 tick 清 stale,之後跳過 RU 端 DELETE 節省 ~15ms 給高倍率
            first_tick = (tick_idx == 0)
            ok = ru_client.update_ues_batch(positions, clear_stale=first_tick)
            if ok:
                self.state["position_push_count"] += 1
            # Omniverse 寫回 — 拆兩種節奏:
            # (1) 位置:每個 wall_tick 都推,3D 跟著 sim_tick 動,任何 speed 都不會脫節。
            # (2) 訊號 label(rsrp/sinr/cell):wall-clock 500ms 拉一次 DU dump_pm,
            #     並只在「剛 refresh 的那一 tick」把 signals 帶進 batch_move payload。
            #     中間 tick 只推位置,Kit 不會重複觸發 push_signal,省下 USD attribute write。
            # 失敗不擋 driver。
            now_ms = time.perf_counter() * 1000.0
            last_sig_fetch = getattr(self, "_last_signal_fetch_ms", 0.0)
            on_slow_tick = (now_ms - last_sig_fetch) >= 500.0
            if on_slow_tick:
                self._last_signal_fetch_ms = now_ms
                signals_for_this_tick = du_client.fetch_ue_signals()
            else:
                signals_for_this_tick = None  # 中間 tick 不帶 signal,只推位置
            # 慢節奏(2Hz wall)那一 tick 也同步 DB,讓 /draw SceneLayoutReader polling
            # 看到 UE 即時位置;中間 tick 只動 Kit USD 不寫 DB(Postgres 不會吃力)。
            omniverse_client.batch_move_ues(
                positions,
                signals=signals_for_this_tick,
                update_db=on_slow_tick,
            )

        # 2. 逐個 UE 內插 traffic → 注 SDU 給 DU
        # 注入量 = dl_kbps × tick_ms / 1000 / 8 bytes (CBR over this tick window)
        sim_dt_ms = self.scenario.tick_ms
        for tf in self.scenario.traffic:
            dl_kbps, _ul_kbps = interpolate_traffic(tf.profile, t_sec)
            if dl_kbps <= 0:
                continue
            bytes_to_inject = int(dl_kbps * 1000 * sim_dt_ms / 1000 / 8)
            if bytes_to_inject <= 0:
                continue
            # 拆 packet (1500B/SDU),per-packet 在這 wall-tick 平均分布
            sdu_size = 1500
            n_full = bytes_to_inject // sdu_size
            remainder = bytes_to_inject % sdu_size
            total_pkts = n_full + (1 if remainder > 0 else 0)
            if total_pkts == 0:
                continue
            window_us = self.target_wall_tick_ms * 1000  # 真實時間維度
            items: list[dict[str, Any]] = []
            for i in range(n_full):
                items.append({
                    "sdu_bytes": sdu_size,
                    "ts_offset_us": int(window_us * i / total_pkts),
                })
            if remainder > 0:
                items.append({
                    "sdu_bytes": remainder,
                    "ts_offset_us": int(window_us * (total_pkts - 1) / total_pkts),
                })
            result = du_client.inject_sdu_batch(
                tf.ue_name, items, window_ms=self.target_wall_tick_ms, bearer_id=1,
            )
            if result == "ok":
                self.state["inject_call_count"] += 1


# 全域單例 (一次只能跑一個 scenario)
_singleton: ScenarioDriver | None = None
_lock = threading.Lock()


def get_driver() -> ScenarioDriver | None:
    return _singleton


def start_scenario(scenario_id: str, target_wall_tick_ms: int = 500) -> ScenarioDriver:
    global _singleton
    with _lock:
        if _singleton is not None and _singleton.state["running"]:
            raise RuntimeError(
                f"Scenario driver already running: {_singleton.scenario.scenario_id}"
            )
        spec = fetch(scenario_id)
        if spec.total_ticks == 0:
            raise ValueError(f"Scenario {scenario_id} has zero ticks")
        _singleton = ScenarioDriver(spec, target_wall_tick_ms=target_wall_tick_ms)
        _singleton.start()
    return _singleton


def stop_scenario() -> bool:
    global _singleton
    if _singleton is None:
        return False
    return _singleton.stop()
