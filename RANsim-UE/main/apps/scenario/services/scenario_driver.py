"""Phase B B.4 — Scenario setup orchestrator(Stage 3B 之後不再 spin tick loop)。

職責簡化:
  • 載入劇本 raw_json 轉 ScenarioSpec
  • 同步 Omniverse DB(UE/gNB/Building)
  • 切 RU channel mode(cached / live)
  • SceneApplyService.apply / UeAttachService.attach_all
  • 把 UE 軌跡推進 trajectory_store(Stage 3A adapter)
  • 啟動 UeLifecycleManager + DU TickController

跑 sim 時的 per-tick 邏輯(位置內插推 RU + traffic 灌 SDU)走 UeLifecycleManager
._trajectory_loop,跟 /editor live_db 模式完全同一份 code path。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from main.apps.scenario.services.scenario_loader import (
    ScenarioSpec, fetch, interpolate_position, positions_to_waypoints,
)
from main.apps.scenario.services.scene_apply import SceneApplyService
from main.apps.scenario.services.ue_attach import UeAttachService
from main.apps.ue_lifecycle.services import cu_client, du_client, omniverse_client, physics_client, ru_client
from main.apps.ue_lifecycle.services.trajectory_store import get_store as get_traj_store


logger = logging.getLogger(__name__)


class ScenarioDriver:
    def __init__(
        self,
        scenario: ScenarioSpec,
        target_wall_tick_ms: int = 500,
        sim_speed_x: float | None = None,
    ):
        self.scenario = scenario
        # target_wall_tick_ms 留參數但已不直接控速 — DU 那邊 sim_speed_x knob 才是
        # 真正的時間軸倍率。這欄保留純粹當 informational state。
        self.target_wall_tick_ms = max(10, min(500, int(target_wall_tick_ms)))
        # P1.13 fix: sim_speed_x 由 SimController 直接傳 (= DU sim_dt_ms / wall_tick_ms)。
        # 舊算法 scenario.tick_ms / target_wall_tick_ms 在 sim_dt_ms != scenario.tick_ms
        # 時會錯 (例如 sim_dt=250 + scenario.tick=500 → 算 2x 真實值, traffic_gen 提前
        # 燒完 piecewise schedule, 之後 PRB 永遠 0)。
        if sim_speed_x is None:
            sim_speed_x = scenario.tick_ms / self.target_wall_tick_ms
        self.state: dict[str, Any] = {
            "running": False,
            "scenario_id": scenario.scenario_id,
            "source": "scenario",
            "started_at_ms": None,
            "ue_count": len(scenario.ues),
            "traffic_count": len(scenario.traffic),
            "sim_speed_x": float(sim_speed_x),
            "scene_apply_errors": [],
            "attach_failed": [],
        }

    def live_state(self) -> dict[str, Any]:
        """state + live 計算的進度欄位（前端 ScenarioController/status 用）。

        driver 已不自跑 tick loop，進度從 started_at_ms + sim_speed_x + scenario
        推算：elapsed_wall ×speed = elapsed_sim ÷tick_ms = sim_tick_idx。
        前端 ScenarioProvider / ActiveSessionLens 依賴 total_ticks / sim_tick_idx /
        elapsed_sim_sec / elapsed_wall_sec，缺了會一路 NaN。
        """
        st = dict(self.state)
        started = self.state.get("started_at_ms")
        speed = float(self.state.get("sim_speed_x") or 1.0)
        total = int(self.scenario.total_ticks)
        tick_ms = max(1, int(self.scenario.tick_ms))
        if self.state.get("running") and started:
            elapsed_wall_sec = max(0.0, (int(time.time() * 1000) - int(started)) / 1000.0)
        else:
            elapsed_wall_sec = 0.0
        elapsed_sim_sec = elapsed_wall_sec * speed
        sim_tick_idx = min(total, int(elapsed_sim_sec * 1000 / tick_ms)) if total else 0
        st.update({
            "total_ticks": total,
            "sim_tick_idx": sim_tick_idx,
            "elapsed_wall_sec": round(elapsed_wall_sec, 2),
            "elapsed_sim_sec": round(elapsed_sim_sec, 2),
            # driver 不再跑 tick loop；push/inject 計數已移至 UeLifecycleManager，暫以 0 佔位
            "position_push_count": 0,
            "inject_call_count": 0,
            # 劇本定義的 dashboard 觸發門檻(前端 evaluator 用,改劇本就生效)
            "trigger_config": self.scenario.trigger_config or {},
        })
        return st

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
                    # per-cell 頻率/頻寬覆寫,寫進 GnbConfig.cells JSON(無 schema migration)。
                    # None 就不放 → 下游 fallback 到 gNB 的 frequency_ghz。
                    "frequency_ghz": (c.frequency_ghz if c.frequency_ghz is not None else g.frequency_ghz),
                    "bandwidth_mhz": (c.bandwidth_mhz if c.bandwidth_mhz is not None else g.bandwidth_mhz),
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

        # Step 1ab — 同步建築(強制對齊,與下面 UE 的 scene sync 一致):
        # 劇本帶 buildings 就對齊到那組,沒帶(payload 空)就清空既有建築,
        # 讓「跑無建築劇本 → Omniverse 3D 也沒建築」。故永遠呼叫 sync,不再 guard。
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
        # 永遠呼叫:空 payload → 清空建築(強制對齊語意)。失敗只 log,不擋 RAN sim。
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
                # live mode:把劇本場景推給跑著的 Physics(否則 live 用靜態 scene_config,
                # 劇本 gnbs/buildings/antenna 進不去)。cached 不用(npz 已 scenario-driven)。
                self._push_scene_to_physics()
        except Exception as e:  # noqa: BLE001
            logger.warning("set_channel_mode failed (continuing with whatever RU is in): %s", e)

        # Step 1c — RAN backend scene-apply 清理鏈 mirror Dashboard handleStartSim C.1〜C.5。
        # 沒這段的話,上一場 sim 的 UE/cell 會殘留在 CU/DU(/logs 看到「鬼魂 UE」),
        # 而且 DU MAC cell 列表跟劇本對不上,本場 UE 排不進 scheduler →
        # KpmReporter 給空值(/logs 看到「沒有數值」)。endpoint 全用既有的,
        # 失敗只 warn 不擋,維持「Omniverse 沒開仍能跑 RAN sim」的容忍度。
        # Step 1b.5 — 起場前準備(2026-08-28 十二題收官後,round_reset 三機制搬進正式路徑):
        # 掃+等靜默驗證(xApp 60s 聚合窗排空,錨才穩在新場首快照)、pre 區結構與場同生
        # (CellConfig→關係→容量覆寫先於一切量測 —— 出生鏈公理)、barred 預埋。
        # 只對帶 anr_fixture 的劇本有意義;其他劇本 CU 端會快速通過(無 pre/enforce 即空操作,
        # 掃+等仍會把上一場殘留排空 —— 這對所有劇本都是好事)。
        # fail-loud:errors 全數落日誌(Q11 三層吞錯教訓),但不擋場景啟動。
        try:
            if getattr(self.scenario, "has_anr_fixture", False):
                rep = cu_client.prepare_anr_fixture(self.scenario.scenario_id)
                for err in (rep.get("errors") or []):
                    logger.warning("fixture prepare error: %s", err)
                logger.info("scenario %s 起場前準備:sweep=%s pre=%s barred=%s",
                            self.scenario.scenario_id, rep.get("sweep"),
                            rep.get("pre"), rep.get("barred"))
        except Exception as e:  # noqa: BLE001
            logger.warning("prepare_anr_fixture failed: %s", e)

        self._apply_scene_to_backend()

        # Step 2 — Setup: 確保 CU 有 traffic_profile 對應的 UE session,RLC entity 建好。
        # (Dashboard Start Sim 通常會做這事;driver 直接被叫時自己保險一次。)
        self._setup_rlc_entities()

        # Step 2a2 — per-scenario 物理參數(inter-freq / discard / tx_power)→ 啟動套用。
        # 一律套(用劇本值或預設)→ 上一場 CCO 設定不殘留,其他劇本自動回 co-channel/300/23。
        try:
            ok = du_client.set_runtime_phys(
                inter_freq=self.scenario.inter_freq,
                discard_timer_ms=self.scenario.discard_timer_ms,
                tx_power_dbm=self.scenario.tx_power_dbm,
                rlc_delay_model=self.scenario.rlc_delay_model,
            )
            logger.info("scenario %s set_runtime_phys inter_freq=%s discard=%s tx=%s rlc_delay=%s: ok=%s",
                        self.scenario.scenario_id, self.scenario.inter_freq,
                        self.scenario.discard_timer_ms, self.scenario.tx_power_dbm,
                        self.scenario.rlc_delay_model, ok)
            # inter_freq 也送 RU → live SINR 路徑也吃劇本 inter_freq(否則 live cell 邊界
            # co-channel 把 SINR 算崩,跟 cached 差 ~20dB)。cached 走 DU 那條已有。
            ru_ok = ru_client.set_inter_freq(self.scenario.inter_freq)
            logger.info("scenario %s RU set_inter_freq=%s: ok=%s",
                        self.scenario.scenario_id, self.scenario.inter_freq, ru_ok)
        except Exception as e:  # noqa: BLE001
            logger.warning("set_runtime_phys failed: %s", e)

        # Step 2b — 劇本自帶 cell_quotas → 啟動自動套用 PRB quota(= xApp E2 Control Style2/Action6)。
        # CCO 容量受限 demo:c0 設 20% → 流量拉高即觸發。cell 必須先存在(上面 attach 後)。
        for q in (self.scenario.cell_quotas or []):
            try:
                ok = du_client.set_prb_quota(q["cell_id"], q["max_prb"], min_prb=q.get("min_prb", 0))
                logger.info("scenario %s set PRB quota cell=%s max_prb=%s: ok=%s",
                            self.scenario.scenario_id, q["cell_id"], q["max_prb"], ok)
            except Exception as e:  # noqa: BLE001
                logger.warning("set_prb_quota failed for %s: %s", q.get("cell_id"), e)

        # Step 2c — A3 自動換手開關 → 啟動套用(always-send 防上一場殘留)。
        # 劇本 a3_enabled None = 用預設關(CCO 等 RC 手動換手不被 A3 彈回);劇本要自動 A3 設 true。
        a3_on = bool(self.scenario.a3_enabled) if self.scenario.a3_enabled is not None else False
        try:
            ok = cu_client.set_a3(
                a3_on,
                offset_db=self.scenario.a3_offset_db,
                hys_db=self.scenario.a3_hys_db,
                ttt_ms=self.scenario.a3_ttt_ms,
            )
            logger.info("scenario %s set A3 enabled=%s: ok=%s",
                        self.scenario.scenario_id, a3_on, ok)
        except Exception as e:  # noqa: BLE001
            logger.warning("set_a3 failed: %s", e)

        # Step 2d — 病徵時間軸(劇本的 anr_fixture 區塊)。放在 A3 之後、推軌跡之前:
        # 佈病要在 UE 開始移動前完成,否則第一段時間的觀測是健康場,
        # xApp 會先看到一個沒有病的場景再看到病 —— 那是兩個場景不是一個。
        try:
            started = cu_client.start_anr_fixture(self.scenario.scenario_id)
            if started:
                logger.info("scenario %s 病徵時間軸已由 CU 接手", self.scenario.scenario_id)
        except Exception as e:  # noqa: BLE001 — 佈病失敗不該擋場景啟動
            logger.warning("start_anr_fixture failed: %s", e)

        # Step 3 — 推軌跡 waypoints 到 trajectory_store(UeLifecycleManager 接管 tick)
        self._push_waypoints_to_store()

        # Step 4 — 啟動 UeLifecycleManager(idempotent — 已 running 不會二度起)
        # 內部 _trajectory_loop 會 per UE 跑 interp.interp_position + traffic_gen.tick
        # 必須再 push sim_start event 才會把 UE state 從 STANDBY → RUNNING,
        # _trajectory_tick 才會真的跑(否則一進 loop 就 continue)。
        try:
            from main.apps.ue_lifecycle.services import manager as ue_manager
            mgr = ue_manager.get_manager()
            mgr.start()
            mgr.push_sync(event="sim_start")
        except Exception as e:  # noqa: BLE001
            logger.warning("UeLifecycleManager.start failed: %s", e)

        # Step 5 — 啟動 DU TickController(KPM / RLC processing)
        if not du_client.tick_start():
            logger.warning("DU TickController.start returned non-ok (sim may run but DU tick idle)")

        self.state["running"] = True
        self.state["started_at_ms"] = int(time.time() * 1000)
        logger.info(
            "ScenarioDriver started: scenario=%s ues=%d traffic=%d duration=%.1fs",
            self.scenario.scenario_id, len(self.scenario.ues),
            len(self.scenario.traffic), self.scenario.duration_sec,
        )
        return True

    def _push_waypoints_to_store(self) -> None:
        """把劇本 ues[].positions 轉 waypoints 丟到 trajectory_store。

        mode="once" → 劇本跑完 UE 停在最後一個位置(不 loop)。
        """
        store = get_traj_store()
        start_at_ms = int(time.time() * 1000)
        for ue in self.scenario.ues:
            wps = positions_to_waypoints(ue.positions)
            if not wps:
                continue
            try:
                store.set(ue.name, waypoints=wps, start_at_ms=start_at_ms, mode="once")
            except ValueError as e:
                logger.warning("trajectory_store.set ue=%s failed: %s", ue.name, e)
        logger.info(
            "scenario %s: pushed waypoints for %d UEs to trajectory_store",
            self.scenario.scenario_id, len(self.scenario.ues),
        )

    def _push_scene_to_physics(self):
        """live mode 用:把劇本 gnbs/buildings/antenna 推給跑著的 Physics live 引擎。
        cached 不呼(npz 已由 run_precompute 的 apply_override 用劇本幾何建好)。"""
        try:
            gnb_dicts = [{
                "name": g.name,
                "position": list(g.position),
                "frequency_ghz": g.frequency_ghz,
                "power_dbm": g.power_dbm,
                "bandwidth_mhz": g.bandwidth_mhz,
                "cells": [{
                    "pci": c.pci, "cell_id": c.cell_id,
                    "position": list(c.position) if c.position else None,
                    "azimuth_deg": c.azimuth_deg,
                } for c in (g.cells or [])],
            } for g in (self.scenario.gnbs or [])]
            bld_dicts = [{
                "name": b.name, "position": list(b.position),
                "size": list(b.size) if b.size else [10, 10, 10],
            } for b in (self.scenario.buildings or [])]
            ok = physics_client.push_scene(
                scene_id=self.scenario.scene_id, gnbs=gnb_dicts,
                buildings=bld_dicts, antenna_pattern=self.scenario.antenna_pattern,
            )
            logger.info("scenario %s push_scene to Physics(live): ok=%s",
                        self.scenario.scenario_id, ok)
        except Exception as e:  # noqa: BLE001
            logger.warning("push_scene_to_physics failed (live 仍用靜態 scene_config): %s", e)

    def _apply_scene_to_backend(self):
        """把劇本拓樸推進 RU/DU/CU 並清掉上一場留下的 stale row。

        實際邏輯走共用的 SceneApplyService(對齊 /editor C.1〜C.5)。
        本函式只負責把劇本資料結構轉成 service 需要的 payload 格式。
        劇本沒帶 gnbs 時 C.1/C.3 skip(payload 空),沿用前端 /editor 拉出來的拓樸。
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
                # per-cell 頻率/頻寬覆寫(對齊 OAI 1-gNB-2-DU 異頻);None 就 fallback gNB 值
                cell_freq = c.frequency_ghz if c.frequency_ghz is not None else g.frequency_ghz
                cell_bw = c.bandwidth_mhz if c.bandwidth_mhz is not None else g.bandwidth_mhz
                ru_cells.append({
                    "name": cell_id,
                    "pci": c.pci,
                    "azimuth_deg": c.azimuth_deg,
                    "position": [cell_pos[0], cell_pos[1], cell_pos[2]],
                    "frequency_ghz": cell_freq,
                    "bandwidth_mhz": cell_bw,
                    "gnb_id": g.name,
                    "power_dbm": g.power_dbm,
                })
                du_cells.append({
                    "cell_id": cell_id,
                    "pci": c.pci,
                    "freq_ghz": cell_freq,
                    "bw_mhz": cell_bw,
                    "gnb_id": g.name,
                })

        # 劇本第一個 tick 的 UE 位置(餵 RU update_ues)
        ru_ue_payload = []
        for ue in self.scenario.ues:
            pos = interpolate_position(ue.positions, 0.0)
            ru_ue_payload.append({"id": ue.name, "position": {"x": pos[0], "y": pos[1], "z": pos[2]}})

        SceneApplyService.apply(
            ru_cells=ru_cells,
            du_cells=du_cells,
            ru_ue_payload=ru_ue_payload,
            ue_names=scenario_ue_names,
            clear_stale_ues=True,
            context=f"scenario {self.scenario.scenario_id}",
        )

    def _build_piecewise_profile(self, ue_name: str) -> dict[str, Any]:
        """劇本 traffic[].profile=[[t_sec, dl_kbps, ul_kbps]] → traffic_gen piecewise profile.

        sim_speed_x 從 driver.target_wall_tick_ms 推算(scenario.tick_ms / target_wall_tick_ms)。
        UE 在劇本中沒 traffic entry 就回 cbr-0(等同 idle)。
        """
        for tf in self.scenario.traffic:
            if tf.ue_name != ue_name:
                continue
            # 保留第 3 欄 ul_kbps(最小可用 UL 用);沒給就 0。格式 [t, dl_kbps, ul_kbps]。
            schedule = [
                [
                    float(p[0]),
                    float(p[1]) if len(p) > 1 else 0.0,
                    float(p[2]) if len(p) > 2 else 0.0,
                ]
                for p in tf.profile
            ]
            return {
                "pattern": "piecewise",
                "schedule": schedule,
                "sim_speed_x": float(self.state["sim_speed_x"]),
                "bearer_id": 1,
            }
        return {"pattern": "cbr", "rate_mbps": 0.0, "bearer_id": 1}

    def _setup_rlc_entities(self):
        """自動 attach 所有 scenario UE,委派給共用 UeAttachService。

        對齊 /editor handleStartSim § D–E 的 chain:
          RRC → DU register → force_serving_cell → update_traffic_profile

        每個 UE 帶 scenario 自己的 piecewise traffic profile(取代之前的 default CBR 1 Mbps)。
        """
        ues_payload = [
            {
                "name": ue.name,
                "traffic_profile": self._build_piecewise_profile(ue.name),
            }
            for ue in self.scenario.ues
        ]
        UeAttachService.attach_all(
            ues_payload,
            default_serving_cell=self.scenario.default_serving_cell,
            context=f"scenario {self.scenario.scenario_id}",
        )

    def stop(self) -> bool:
        if not self.state["running"]:
            return False
        # 停 UeLifecycleManager(trajectory + traffic_gen tick 一起停)
        # sim_stop event 把 UE state 從 RUNNING → STANDBY,traffic_gen 停發 SDU。
        try:
            from main.apps.ue_lifecycle.services import manager as ue_manager
            mgr = ue_manager.get_manager()
            mgr.push_sync(event="sim_stop")
            mgr.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning("UeLifecycleManager.stop failed: %s", e)
        # 停 DU tick
        du_client.tick_stop()
        # 清掉劇本 UE 的 trajectory(避免下次跑時殘留)
        store = get_traj_store()
        for ue in self.scenario.ues:
            store.clear(ue.name)
        self.state["running"] = False
        logger.info("ScenarioDriver stopped: scenario=%s", self.scenario.scenario_id)
        return True


# 全域單例 (一次只能跑一個 scenario)
_singleton: ScenarioDriver | None = None
_lock = threading.Lock()


def get_driver() -> ScenarioDriver | None:
    return _singleton


def start_scenario(
    scenario_id: str,
    target_wall_tick_ms: int = 500,
    sim_speed_x: float | None = None,
) -> ScenarioDriver:
    global _singleton
    with _lock:
        if _singleton is not None and (
                _singleton.state["running"]
                or _singleton.state.get("phase") == "preparing"):
            raise RuntimeError(
                f"Scenario driver already running: {_singleton.scenario.scenario_id}"
            )
        spec = fetch(scenario_id)
        if spec.total_ticks == 0:
            raise ValueError(f"Scenario {scenario_id} has zero ticks")
        _singleton = ScenarioDriver(
            spec, target_wall_tick_ms=target_wall_tick_ms, sim_speed_x=sim_speed_x,
        )
        # 非同步啟動(2026-08-29):帶 anr_fixture 的劇本起場前準備(掃+等靜默
        # 驗證)要 90 秒以上,同步跑會讓前端 Start Sim 的 HTTP 請求 client-timeout
        # (伺服器照跑但按鈕看起來像壞了)。改背景執行,立即回應;前端本來就
        # 輪詢 ScenarioController/status,state.phase 讓它分得出 preparing/running。
        drv = _singleton
        drv.state["phase"] = "preparing"

        def _run():
            try:
                drv.start()
                drv.state["phase"] = "running" if drv.state.get("running") else "failed"
            except Exception:  # noqa: BLE001 — fail-loud 進日誌,phase 標 failed
                logger.exception("scenario start failed in background")
                drv.state["phase"] = "failed"

        threading.Thread(target=_run, name="scenario-start", daemon=True).start()
    return _singleton


def stop_scenario() -> bool:
    global _singleton
    if _singleton is None:
        return False
    return _singleton.stop()
