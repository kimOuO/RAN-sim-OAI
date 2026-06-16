"""SimOrchestrator — Stage 2 統一 sim start 流程。

兩個 source:
  - "live_db":  Dashboard /editor 拉拖的場景(直接讀 Omniverse 三表)
  - "scenario": 上傳的劇本(走 ScenarioLoader.fetch + 反向 sync DB)

兩條共用後段:
  SceneApplyService.apply → UeAttachService.attach_all
  → DU TickController.start → UE Lifecycle.start
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests
from django.conf import settings

from main.apps.scenario.services.scene_apply import SceneApplyService
from main.apps.scenario.services.ue_attach import UeAttachService
from main.apps.scenario.services.scenario_loader import waypoints_with_speed_to_trajectory
from main.apps.scenario.services import scenario_driver
from main.apps.ue_lifecycle.services import (
    cu_client, du_client, omniverse_client, ru_client,
)
from main.apps.ue_lifecycle.services.trajectory_store import get_store as get_traj_store


logger = logging.getLogger(__name__)

OMNIVERSE_URL = os.environ.get("OMNIVERSE_URL", "http://omniver_backend:8000")
DU_URL = getattr(settings, "SIM_DU_URL", "http://ransim-du:8000")
# e2adapter 跑 network_mode=host → 從 container 內走 host.docker.internal 連 8201。
# 用途:跨 sim cleanup 時呼叫 KpmSnapshot/SnapshotReader/reset 清 ring buffer。
E2_ADAPTER_URL = os.environ.get("E2_ADAPTER_URL", "http://host.docker.internal:8201")


def _post(url: str, body: dict | None = None, timeout: float = 5.0) -> dict:
    r = requests.post(url, json=body or {}, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {}


# ---------------------------------------------------------------------------
# Source loaders — 兩種來源轉成 SceneApplyService / UeAttachService 用的 payload
# ---------------------------------------------------------------------------


def _load_live_db() -> dict[str, Any]:
    """從 Omniverse 三表讀:UeConfig / GnbConfig / BuildingObject。

    產出:
      cells_payload: SceneApplyService 用(每 cell 一筆,DAS 展開)
      ues_payload:   SceneApplyService + UeAttachService 用
    """
    # 讀 gNBs(GNBReader 已經回完整 cells[])
    gnbs_resp = _post(f"{OMNIVERSE_URL}/api/v0.1/RAN/GNB/GNBReader/read")
    gnbs = gnbs_resp.get("data") or []
    # 讀 UEs
    ues_resp = _post(f"{OMNIVERSE_URL}/api/v0.1/RAN/UE/UEReader/read")
    ues = ues_resp.get("data") or []

    ru_cells: list[dict[str, Any]] = []
    du_cells: list[dict[str, Any]] = []
    for g in gnbs:
        gnb_pos = g.get("position") or [0, 0, 0]
        gnb_name = g["name"]
        freq = float(g.get("frequency_ghz", 3.5))
        bw = float(g.get("bandwidth_mhz", 40.0))
        power = float(g.get("power_dbm", 23.0))
        cells = g.get("cells") or [{"pci": 0, "cell_id": f"{gnb_name}_c0"}]
        for i, c in enumerate(cells):
            cell_id = str(c.get("cell_id") or f"{gnb_name}_c{i}")
            cpos = c.get("position") or gnb_pos
            # per-cell 頻率/頻寬覆寫(對齊 OAI 1-gNB-2-DU 異頻);沒給就 fallback gNB 值。
            cell_freq = float(c.get("frequency_ghz") or freq)
            cell_bw = float(c.get("bandwidth_mhz") or bw)
            ru_cells.append({
                "name": cell_id,
                "pci": int(c.get("pci") or 0),
                "azimuth_deg": float(c.get("azimuth_deg") or 0.0),
                "position": [float(cpos[0]), float(cpos[1]), float(cpos[2])],
                "frequency_ghz": cell_freq,
                "bandwidth_mhz": cell_bw,
                "gnb_id": gnb_name,
                "power_dbm": power,
            })
            du_cells.append({
                "cell_id": cell_id,
                "pci": int(c.get("pci") or 0),
                "freq_ghz": cell_freq,
                "bw_mhz": cell_bw,
                "gnb_id": gnb_name,
            })

    ru_ue_payload = []
    ue_names: list[str] = []
    ue_waypoint_specs: list[dict] = []   # for trajectory_store push
    for u in ues:
        name = u.get("name")
        if not name:
            continue
        pos = u.get("position") or [0, 0, 0]
        if isinstance(pos, dict):
            pos = [pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)]
        ru_ue_payload.append({
            "id": name,
            "position": {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
        })
        ue_names.append(name)
        # /editor 拉軌跡:waypoints = [[x,y,z], ...] + speed_mps + loop
        wps = u.get("waypoints") or []
        if wps and len(wps) >= 2:
            ue_waypoint_specs.append({
                "name": name,
                "waypoints": wps,
                "speed_mps": float(u.get("speed_mps") or 1.0),
                "loop": bool(u.get("loop", True)),
            })

    return {
        "source": "live_db",
        "ru_cells": ru_cells,
        "du_cells": du_cells,
        "ru_ue_payload": ru_ue_payload,
        "ue_names": ue_names,
        "ues_with_profile": [{"name": n} for n in ue_names],  # default profile in UeAttachService
        "ue_waypoint_specs": ue_waypoint_specs,
        "default_serving_cell": (du_cells[0]["cell_id"] if du_cells else "gnb1_cell0"),
    }


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    """劇本來源 — 走既有 scenario_driver.start_scenario(spinning tick loop 仍會起來)。

    Stage 2 暫時委派 scenario_driver,讓行為跟之前一致。
    Stage 3 會把 tick loop 砍掉,改由 UeLifecycleManager._trajectory_loop 接管。
    """
    # 劇本載入後 driver 內部會做完整 setup(sync DB / scene-apply / RLC entity / loop),
    # SimOrchestrator 在這層不另外重做 — 否則 double-apply 會出現重複 RRC 等噪音。
    return {"source": "scenario", "scenario_id": scenario_id}


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def _broadcast_speed(speed_x: float, sim_dt_ms: int = 500) -> dict[str, Any]:
    """把 sim_speed_x 廣播到 DU / CU。

    DU set_speed 改 sim_tick_ms;CU KpmSpeed/set 改 KPM indication 速率。
    e2adapter 會 background pull DU sim_speed_x 自動跟上 (~4s wall 收斂)。
    """
    # wall_tick = sim_dt_ms / speed_x — 例: sim_dt=100ms, 5x → wall=20ms
    target_tick_ms = max(10, min(500, int(round(sim_dt_ms / max(speed_x, 0.01)))))
    out: dict[str, Any] = {"target_tick_ms": target_tick_ms, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms}
    try:
        _post(f"{DU_URL}/api/v0.1/DU/Tick/TickController/set_speed",
              {"tick_ms": target_tick_ms, "sim_dt_ms": sim_dt_ms})
    except Exception as e:  # noqa: BLE001
        out["du_set_speed_error"] = str(e)
        logger.warning("DU set_speed failed: %s", e)
    try:
        from django.conf import settings as dj_settings
        cu_url = getattr(dj_settings, "SIM_CU_URL", "http://ransim-cu:8000")
        _post(f"{cu_url}/api/v0.1/CU/E2/KpmSpeed/set", {"sim_speed_x": speed_x})
    except Exception as e:  # noqa: BLE001
        out["cu_kpm_speed_error"] = str(e)
        logger.warning("CU KpmSpeed/set failed: %s", e)
    return out


_ACTIVE_SESSION_UUID: str | None = None


def _create_sim_session(source: str, scenario_id: str, speed_x: float) -> str | None:
    """為這次 sim 建一筆 SimulationSession,Playback 需要這個 uuid 才能 group 之後的
    SignalHistory / PositionHistory / HandoverHistory / ControlAction。失敗回 None 不擋。
    """
    global _ACTIVE_SESSION_UUID
    import uuid as _uuid
    session_uuid = f"sim_{_now_ms()}_{_uuid.uuid4().hex[:8]}"
    try:
        _post(
            f"{OMNIVERSE_URL}/api/v0.1/RAN/SimSession/SimSessionController/create",
            {
                "session_uuid": session_uuid,
                "scene_id": scenario_id or "live_editor",
                "mode": "fast_cached" if source == "scenario" else "live",
                "scenario_id": scenario_id,
                "time_compression_ratio": speed_x,
            },
        )
        logger.info("SimSession created uuid=%s source=%s speed_x=%.1f",
                    session_uuid, source, speed_x)
        _ACTIVE_SESSION_UUID = session_uuid
        return session_uuid
    except Exception as e:  # noqa: BLE001
        logger.warning("SimSession.create failed (Playback group key 不會有): %s", e)
        return None


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def start_sim(
    source: str,
    *,
    scenario_id: str = "",
    speed_x: float = 1.0,
    sim_dt_ms: int = 500,
) -> dict[str, Any]:
    """Unified sim start entry.

    Returns:
        {source, applied_steps, attach_summary, errors?, scenario_state?}
    """
    # AUTO-STOP — 啟動新劇本一律先把上一個收乾淨。避免:
    #   1. scenario_driver singleton 409 conflict (見 scenario_driver.py:353)
    #   2. CU UeContext 殘留 CONNECTED 導致 indication_producer 持續往 RIC 噴 stale KPM
    #   3. DU Tick / UeLifecycle leak 過去 session 狀態
    # stop_sim() 是 idempotent — 沒東西在跑就 no-op,不擋第一次的 cold start。
    cleanup_summary = stop_sim()
    logger.info("start_sim auto-stop preceding cleanup: %s", cleanup_summary)

    # 先廣播速度到 DU/CU,後面 attach + tick 啟動才會在正確速度開始跑
    speed_broadcast = _broadcast_speed(speed_x, sim_dt_ms=sim_dt_ms)
    # 建 SimSession(Playback group key)。失敗不擋 sim。
    session_uuid = _create_sim_session(source, scenario_id, speed_x)
    # 把 session_uuid 傳給 UeLifecycleManager(signal ingest 帶這個 group key)
    try:
        from main.apps.ue_lifecycle.services import manager as ue_manager
        ue_manager.get_manager().set_session_uuid(session_uuid)
    except Exception as e:  # noqa: BLE001
        logger.warning("set_session_uuid failed: %s", e)

    if source == "scenario":
        if not scenario_id:
            raise ValueError("source=scenario requires scenario_id")
        _ = _load_scenario(scenario_id)
        target_wall_tick_ms = max(10, min(500, int(round(sim_dt_ms / max(speed_x, 0.01)))))
        drv = scenario_driver.start_scenario(
            scenario_id, target_wall_tick_ms=target_wall_tick_ms,
            sim_speed_x=float(speed_x),
        )
        return {
            "source": "scenario",
            "scenario_id": scenario_id,
            "speed_x": speed_x,
            "speed_broadcast": speed_broadcast,
            "session_uuid": session_uuid,
            "scenario_state": drv.state,
        }

    if source == "live_db":
        bundle = _load_live_db()
        apply_result = SceneApplyService.apply(
            ru_cells=bundle["ru_cells"],
            du_cells=bundle["du_cells"],
            ru_ue_payload=bundle["ru_ue_payload"],
            ue_names=bundle["ue_names"],
            clear_stale_ues=True,
            context="editor",
        )
        attach_result = UeAttachService.attach_all(
            bundle["ues_with_profile"],
            default_serving_cell=bundle["default_serving_cell"],
            context="editor",
        )

        # 把 /editor UE 軌跡推進 trajectory_store(讓 UeLifecycleManager 接管位置內插)
        # /editor 用 [[x,y,z], ...] + speed_mps + loop;轉成 [{x,y,z,t_ms}] + mode。
        import time as _time
        store = get_traj_store()
        start_at_ms = int(_time.time() * 1000)
        traj_pushed = 0
        for spec in bundle["ue_waypoint_specs"]:
            wps = waypoints_with_speed_to_trajectory(spec["waypoints"], spec["speed_mps"])
            if not wps:
                continue
            mode = "loop" if spec["loop"] else "once"
            try:
                store.set(spec["name"], waypoints=wps, start_at_ms=start_at_ms, mode=mode)
                traj_pushed += 1
            except ValueError as e:
                logger.warning("trajectory_store.set ue=%s failed: %s", spec["name"], e)

        # DU Tick 啟動
        tick_start_err: str | None = None
        try:
            du_client.tick_start()
        except Exception as e:  # noqa: BLE001
            tick_start_err = str(e)
            logger.warning("DU TickController.start failed: %s", e)

        # UE Lifecycle 啟動(in-process,讓 UeLifecycleManager 接管 trajectory + traffic_gen tick)
        # 注意:start() 只起 thread,真正 STANDBY→RUNNING 需 push_sync(event="sim_start")。
        # 沒這步 _trajectory_tick 看到 ue.state != RUNNING 就 skip,traffic_gen 永遠不發 SDU。
        lifecycle_err: str | None = None
        try:
            from main.apps.ue_lifecycle.services import manager as ue_manager
            mgr = ue_manager.get_manager()
            mgr.start()
            mgr.push_sync(event="sim_start")
        except Exception as e:  # noqa: BLE001
            lifecycle_err = str(e)
            logger.warning("UE Lifecycle start failed: %s", e)

        return {
            "source": "live_db",
            "speed_x": speed_x,
            "speed_broadcast": speed_broadcast,
            "session_uuid": session_uuid,
            "apply": apply_result,
            "attach": attach_result,
            "trajectories_pushed": traj_pushed,
            "tick_start_error": tick_start_err,
            "lifecycle_error": lifecycle_err,
            "cells": len(bundle["du_cells"]),
            "ues": len(bundle["ue_names"]),
        }

    raise ValueError(f"unknown source: {source!r}")


def _end_sim_session() -> None:
    """收尾 active SimulationSession(set ended_at + status=ended)。失敗不擋。"""
    global _ACTIVE_SESSION_UUID
    if not _ACTIVE_SESSION_UUID:
        return
    try:
        _post(
            f"{OMNIVERSE_URL}/api/v0.1/RAN/SimSession/SimSessionController/end",
            {"session_uuid": _ACTIVE_SESSION_UUID},
        )
        logger.info("SimSession ended uuid=%s", _ACTIVE_SESSION_UUID)
    except Exception as e:  # noqa: BLE001
        logger.warning("SimSession.end failed: %s", e)
    finally:
        _ACTIVE_SESSION_UUID = None


def stop_sim() -> dict[str, Any]:
    """Stop both scenario driver thread (if any) and UE lifecycle manager."""
    out: dict[str, Any] = {}
    out["scenario_stopped"] = scenario_driver.stop_scenario()
    _end_sim_session()
    try:
        from main.apps.ue_lifecycle.services import manager as ue_manager
        mgr = ue_manager.get_manager()
        mgr.push_sync(event="sim_stop")  # RUNNING→STANDBY,traffic_gen 停發 SDU
        mgr.stop()
        out["lifecycle_stopped"] = True
    except Exception as e:  # noqa: BLE001
        out["lifecycle_error"] = str(e)
    try:
        _post(f"{DU_URL}/api/v0.1/DU/Tick/TickController/stop")
        out["du_tick_stopped"] = True
    except Exception as e:  # noqa: BLE001
        out["du_tick_error"] = str(e)
    # 通知 CU 把所有 UE 降回 IDLE — CU indication_producer 看到沒 CONNECTED 就停 emit,
    # 解決「stop sim 後 Influx 還持續收 stale KPM」的問題。
    try:
        cu_url = getattr(settings, "SIM_CU_URL", "http://ransim-cu:8000")
        resp = _post(f"{cu_url}/api/v0.1/CU/Session/SessionController/release_all", {})
        out["cu_release_all"] = resp.get("data", {}) if isinstance(resp, dict) else resp
    except Exception as e:  # noqa: BLE001
        out["cu_release_all_error"] = str(e)
    # 跨 sim 隔離 cleanup — 清 DU PM window + e2adapter KPM ring buffer。
    # 沒這兩步:下次 sim 起來時 dump_pm / KPM RecentReader 還會回上輪殘留,
    # KPM window mean 也帶舊累積值,讓 xApp 在 sim 初期看到「上次的數字」誤判。
    try:
        _post(f"{DU_URL}/api/v0.1/DU/Tick/TickController/reset_pm")
        out["du_pm_reset"] = True
    except Exception as e:  # noqa: BLE001
        out["du_pm_reset_error"] = str(e)
    try:
        _post(f"{E2_ADAPTER_URL}/api/v0.1/E2Adapter/KpmSnapshot/SnapshotReader/reset")
        out["e2adapter_kpm_reset"] = True
    except Exception as e:  # noqa: BLE001
        out["e2adapter_kpm_reset_error"] = str(e)
    # 清掉上輪 xApp 下的 PRB Quota(RC Control Style 2 / Action 6)。
    # _PrbQuotaStore 是 DU in-memory dict,DU 沒重啟就會跨 sim 殘留,
    # 讓下一輪 sim 起來時 scheduler 還被舊 cap 卡住。
    # 取所有 active quota 的 cell_id,逐 cell call clear_prb_quota。
    try:
        list_resp = _post(f"{DU_URL}/api/v0.1/DU/MAC/MacScheduler/list_prb_quota")
        quotas = list_resp.get("data", {}).get("quotas", []) if isinstance(list_resp, dict) else []
        cleared = []
        for q in quotas:
            cid = q.get("cell_id")
            if not cid:
                continue
            try:
                _post(f"{DU_URL}/api/v0.1/DU/MAC/MacScheduler/clear_prb_quota", {"cell_id": cid})
                cleared.append(cid)
            except Exception as e:  # noqa: BLE001
                logger.warning("clear_prb_quota %s failed: %s", cid, e)
        out["du_prb_quota_cleared"] = cleared
    except Exception as e:  # noqa: BLE001
        out["du_prb_quota_cleared_error"] = str(e)
    return out
