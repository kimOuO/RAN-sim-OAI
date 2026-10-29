
"""劇本 v1 JSON ↔ registry 樹 的雙向轉換(Optional Service,backend_rule §14-4)。

語意對齊 RANsim-UE `scenario_loader.fetch()` / `_normalize_positions()`:
  * positions 3 元素 [x,y,z] → 依 duration 平均補時間軸;4 元素 [t,x,y,z] 原樣
  * gnb 層級 frequency_ghz / bandwidth_mhz / power_dbm 為 cell 預設;cell 可覆寫
  * 倉庫版 flat gnb(gnbs[i] 直接帶 pci/cell_id,無 cells)→ 視為一個 cell
  * default_serving_cell / antenna_pattern / cell_quotas / inter_freq / discard_timer_ms /
    tx_power_dbm / rlc_delay_model / anr_fixture / _metadata.trigger_config → run_knob(掛在匯入時建立的 draft scene_run)
  * duration_sec / tick_ms → draft scene_run 的 duration_sec / sim_dt_ms
  * a3_* → gnb 欄位(劇本是全域,套到每個 gnb)

export 是 import 的反函數:對 loader 而言語意相同(見 tests 的 round-trip)。
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.field_scene.models.material import Material
from main.apps.equipment_ran.models.cell import Cell
from main.apps.equipment_ran.models.du import Du
from main.apps.equipment_ran.models.gnb import Gnb
from main.apps.equipment_ran.models.ru import Ru
from main.apps.field_scene.models.building import Building
from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.services.business.sqldb_operations import SqlDbBusinessService as DB
from main.apps.field_scene.services.common.timestamp_service import TimestampService
from main.apps.field_scene.services.common.uuid_service import UUIDService
from main.apps.simulation_run.models.run_knob import RunKnob
from main.apps.simulation_run.models.scene_run import SceneRun
from main.apps.equipment_ue.models.ue import Ue
from main.apps.equipment_ue.models.ue_active_window import UeActiveWindow
from main.apps.equipment_ue.models.ue_traffic import UeTraffic
from main.apps.equipment_ue.models.ue_waypoint import UeWaypoint

KNOB_KEYS = ("default_serving_cell", "antenna_pattern", "cell_quotas", "inter_freq",
             "discard_timer_ms", "tx_power_dbm", "rlc_delay_model", "anr_fixture")
A3_KEYS = ("a3_enabled", "a3_offset_db", "a3_hys_db", "a3_ttt_ms")


# ── 38.104 §5.4.2.1 NR-ARFCN ↔ 頻率 ──
def ghz_to_arfcn(f_ghz: float) -> int:
    mhz = f_ghz * 1000.0
    if mhz < 3000.0:
        return int(round(mhz / 0.005))
    if mhz < 24250.0:
        return int(round(600000 + (mhz - 3000.0) / 0.015))
    return int(round(2016667 + (mhz - 24250.08) / 0.06))


def arfcn_to_ghz(n: int) -> float:
    if n < 600000:
        return n * 0.005 / 1000.0
    if n < 2016667:
        return (3000.0 + (n - 600000) * 0.015) / 1000.0
    return (24250.08 + (n - 2016667) * 0.06) / 1000.0


def normalize_positions(positions: list[list[float]], duration_sec: float) -> list[list[float]]:
    """與 RANsim-UE scenario_loader._normalize_positions 完全相同。"""
    if not positions:
        return []
    if len(positions[0]) >= 4:
        return [[float(p[0]), float(p[1]), float(p[2]), float(p[3])] for p in positions]
    n = len(positions)
    if n == 1:
        return [[0.0, float(positions[0][0]), float(positions[0][1]), float(positions[0][2])]]
    dur = duration_sec if (duration_sec and duration_sec > 0) else float(n - 1)
    return [[round(dur * i / (n - 1), 3), float(p[0]), float(p[1]), float(p[2])] for i, p in enumerate(positions)]


def _stamp(prefix: str) -> dict[str, Any]:
    now = TimestampService.now()
    return {f"{prefix}_uuid": UUIDService.generate_uuid(prefix), f"{prefix}_created_at": now, f"{prefix}_updated_at": now}


def _antenna_preset_for(pattern: str | None) -> AntennaPreset | None:
    """劇本 antenna_pattern → 1×1 單極化 preset(不存在就建)。"""
    if not pattern:
        return None
    name = f"legacy-{pattern}-1x1-V"
    obj = DB.get_or_none(AntennaPreset, "name", name)
    if obj is None:
        obj = DB.create_entity(AntennaPreset, {**_stamp("antenna_preset"), "name": name, "source": "legacy",
                                               "pattern": pattern, "rows": 1, "cols": 1, "polarization": "V",
                                               "max_gain_dbi": {"tr38901": 8.0, "iso": 0.0}.get(pattern, 2.15),
                                               "notes": "auto-created by scenario_v1 importer"})
    return obj


@transaction.atomic
def import_scenario(raw: dict[str, Any], *, precompute_status: str = "pending", cache_path: str = "") -> dict[str, Any]:
    """劇本 raw_json → scene 樹 + draft scene_run。回傳各層 uuid 與計數。"""
    sid = str(raw.get("scenario_id") or "")
    duration = float(raw.get("duration_sec") or 0.0)
    tick_ms = int(raw.get("tick_ms") or 500)

    scene = DB.create_entity(Scene, {**_stamp("scene"), "name": sid or "imported", "description": str((raw.get("_metadata") or {}).get("intent") or ""),
                                     "legacy_scenario_id": sid, "geometry_scene_id": str(raw.get("scene_id") or ""),
                                     "geometry_source": raw.get("geometry_source")})
    # buildings
    n_b = 0
    for b in raw.get("buildings") or []:
        mat = DB.get_or_none(Material, "key", str(b.get("material") or "")) if b.get("material") else None
        DB.create_entity(Building, {**_stamp("building"), "scene": scene, "name": str(b.get("name") or f"b{n_b}"), "source": "manual_box",
                                    "position": list(b.get("position") or [0, 0, 0]), "size": list(b.get("size") or []),
                                    "rotation": list(b.get("rotation_xyz_deg") or []), "scale": [], "default_material": mat,
                                    "geometry_ref": ""})
        n_b += 1
    # gnbs → du → cells → ru
    a3 = {k: raw.get(k) for k in A3_KEYS}
    preset = _antenna_preset_for(raw.get("antenna_pattern"))
    cell_by_name: dict[str, Cell] = {}
    n_g = n_c = 0
    for g in raw.get("gnbs") or []:
        gnb = DB.create_entity(Gnb, {**_stamp("gnb"), "scene": scene, "name": str(g["name"]), "position": list(g.get("position") or [0, 0, 0]),
                                     "is_active": bool(g.get("active", True)), "color": g.get("color"),
                                     "a3_enabled": (None if a3["a3_enabled"] is None else bool(a3["a3_enabled"])),
                                     "a3_offset_db": (None if a3["a3_offset_db"] is None else float(a3["a3_offset_db"])),
                                     "a3_hys_db": (None if a3["a3_hys_db"] is None else float(a3["a3_hys_db"])),
                                     "a3_ttt_ms": (None if a3["a3_ttt_ms"] is None else int(a3["a3_ttt_ms"]))})
        du = DB.create_entity(Du, {**_stamp("du"), "gnb": gnb, "name": f"{g['name']}_du0", "gnb_du_id": 1})
        g_f = float(g.get("frequency_ghz") or 3.5); g_bw = float(g.get("bandwidth_mhz") or 40.0); g_p = float(g.get("power_dbm") or 23.0)
        cells_raw = g.get("cells")
        if cells_raw is None and g.get("cell_id"):           # 倉庫版 flat gnb
            cells_raw = [{"cell_id": g["cell_id"], "pci": g.get("pci", 0), "azimuth_deg": g.get("azimuth_deg", 0.0)}]
        for c in cells_raw or []:
            f = float(c["frequency_ghz"]) if c.get("frequency_ghz") is not None else g_f
            bw = float(c["bandwidth_mhz"]) if c.get("bandwidth_mhz") is not None else g_bw
            cell = DB.create_entity(Cell, {**_stamp("cell"), "du": du, "name": str(c["cell_id"]), "pci": int(c.get("pci") or 0),
                                           "arfcn": ghz_to_arfcn(f), "center_frequency_ghz": f, "bandwidth_mhz": bw,
                                           "position": (list(c["position"]) if c.get("position") else None),
                                           "azimuth_deg": float(c.get("azimuth_deg") or 0.0), "power_dbm": g_p,
                                           "is_active": bool(g.get("active", True)), "is_barred": bool(c.get("barred", False))})
            DB.create_entity(Ru, {**_stamp("ru"), "cell": cell, "name": f"{c['cell_id']}_ru", "antenna_preset": preset})
            cell_by_name[cell.name] = cell; n_c += 1
        n_g += 1
    # ues
    traffic_by_ue: dict[str, list] = {}
    for t in raw.get("traffic") or []:
        traffic_by_ue.setdefault(str(t["ue_name"]), []).append(t)
    n_u = 0
    for u in raw.get("ues") or []:
        ue = DB.create_entity(Ue, {**_stamp("ue"), "scene": scene, "name": str(u["name"]), "antenna_preset": None,
                                   "antenna_height_m": float(u["target_height_m"]) if u.get("target_height_m") is not None else 1.5,
                                   "presence_restricted": "active" in u and u["active"] is not None,
                                   "loop": bool(u.get("loop", False)), "speed_mps": (float(u["speed_mps"]) if u.get("speed_mps") is not None else None)})
        for i, p in enumerate(normalize_positions(list(u.get("positions") or []), duration)):
            DB.create_entity(UeWaypoint, {**_stamp("ue_waypoint"), "ue": ue, "ord": i, "t_sec": p[0], "x": p[1], "y": p[2], "z": p[3]})
        for w in u.get("active") or []:
            DB.create_entity(UeActiveWindow, {**_stamp("ue_active_window"), "ue": ue, "t0_sec": float(w[0]), "t1_sec": float(w[1])})
        for t in traffic_by_ue.get(ue.name, []):
            DB.create_entity(UeTraffic, {**_stamp("ue_traffic"), "ue": ue, "pattern": "piecewise", "rate_mbps": 0.0,
                                         "schedule": list(t.get("profile") or []), "bearer_id": int(t.get("bearer_id") or 1)})
        n_u += 1
    # draft run + knobs
    run = DB.create_entity(SceneRun, {**_stamp("scene_run"), "scene": scene, "mode": "cached" if precompute_status == "ready" else "live",
                                      "speed_x": 1.0, "sim_dt_ms": tick_ms, "duration_sec": int(duration), "status": "idle",
                                      "cache_path": cache_path or "", "notes": "draft created by scenario_v1 importer"})
    knobs = {k: raw[k] for k in KNOB_KEYS if k in raw}
    tc = (raw.get("_metadata") or {}).get("trigger_config")
    if tc:
        knobs["trigger_config"] = tc
    for k, v in knobs.items():
        DB.create_entity(RunKnob, {**_stamp("run_knob"), "scene_run": run, "key": k, "value": v})
    return {"scene_uuid": scene.scene_uuid, "scene_run_uuid": run.scene_run_uuid, "gnbs": n_g, "cells": n_c, "ues": n_u,
            "buildings": n_b, "knobs": sorted(knobs)}


def export_scenario(scene_uuid: str, scene_run_uuid: str | None = None) -> dict[str, Any]:
    """scene 樹(+ 一個 scene_run 的 knobs)→ 劇本 v1 raw_json。"""
    scene = DB.get_entity(Scene, "scene_uuid", scene_uuid)
    run = (DB.get_entity(SceneRun, "scene_run_uuid", scene_run_uuid) if scene_run_uuid
           else SceneRun.objects.filter(scene=scene).order_by("id").first())
    knobs = {k.key: k.value for k in RunKnob.objects.filter(scene_run=run)} if run else {}
    out: dict[str, Any] = {"scenario_id": scene.legacy_scenario_id or scene.name, "scene_id": scene.geometry_scene_id,
                           "duration_sec": float(run.duration_sec) if run else 0.0, "tick_ms": int(run.sim_dt_ms) if run else 500}
    if scene.geometry_source is not None:
        out["geometry_source"] = scene.geometry_source
    # 2026-09-17:場景層天線 preset 一起匯出(precompute 用;以前沒帶 → 預算一律 tr38901/dipole,與 live 不一致)
    def _arr(p):
        return None if p is None else {"pattern": p.pattern, "polarization": p.polarization, "rows": p.rows, "cols": p.cols,
                                       "vertical_spacing": p.v_spacing, "horizontal_spacing": p.h_spacing}
    for key, attr in (("tx_antenna", "gnb_antenna_preset"), ("ue_antenna", "ue_antenna_preset")):
        a = _arr(getattr(scene, attr, None))
        if a:
            out[key] = a
    for k in ("default_serving_cell", "antenna_pattern", "cell_quotas", "inter_freq", "discard_timer_ms", "tx_power_dbm", "rlc_delay_model", "anr_fixture"):
        if k in knobs:
            out[k] = knobs[k]
    gnbs = []
    first_gnb = None
    for g in Gnb.objects.filter(scene=scene).order_by("id"):
        first_gnb = first_gnb or g
        cells = list(Cell.objects.filter(du__gnb=g).order_by("id"))
        # gnb 層級預設 = 第一個 cell 的值;cell 與之不同才輸出覆寫
        f0 = cells[0].center_frequency_ghz if cells else 3.5
        bw0 = cells[0].bandwidth_mhz if cells else 40.0
        p0 = cells[0].power_dbm if cells else 23.0
        gd: dict[str, Any] = {"name": g.name, "position": g.position, "frequency_ghz": f0, "bandwidth_mhz": bw0, "power_dbm": p0,
                              "active": g.is_active, "cells": []}
        if g.color is not None:
            gd["color"] = g.color
        for c in cells:
            cd: dict[str, Any] = {"pci": c.pci, "cell_id": c.name, "azimuth_deg": c.azimuth_deg}
            if c.position:
                cd["position"] = c.position
            if c.center_frequency_ghz != f0:
                cd["frequency_ghz"] = c.center_frequency_ghz
            if c.bandwidth_mhz != bw0:
                cd["bandwidth_mhz"] = c.bandwidth_mhz
            if c.is_barred:
                cd["barred"] = True
            gd["cells"].append(cd)
        gnbs.append(gd)
    out["gnbs"] = gnbs
    if first_gnb is not None:   # None = 劇本未指定,不輸出(loader 會用 CU env)
        for k in A3_KEYS:
            v = getattr(first_gnb, k)
            if v is not None:
                out[k] = v
    out["buildings"] = [{"name": b.name, "position": b.position, **({"size": b.size} if b.size else {}),
                         **({"rotation_xyz_deg": b.rotation} if b.rotation else {}),
                         **({"material": b.default_material.key} if b.default_material_id else {})}
                        for b in Building.objects.filter(scene=scene).order_by("id")]
    ues, traffic = [], []
    for u in Ue.objects.filter(scene=scene).order_by("id"):
        ud: dict[str, Any] = {"name": u.name, "positions": [[w.t_sec, w.x, w.y, w.z] for w in UeWaypoint.objects.filter(ue=u).order_by("ord")]}
        wins = [[w.t0_sec, w.t1_sec] for w in UeActiveWindow.objects.filter(ue=u).order_by("id")]
        if wins or u.presence_restricted:
            ud["active"] = wins
        if u.loop:
            ud["loop"] = True
        if u.speed_mps is not None:
            ud["speed_mps"] = u.speed_mps
        if u.antenna_height_m != 1.5:
            ud["target_height_m"] = u.antenna_height_m
        ues.append(ud)
        for t in UeTraffic.objects.filter(ue=u).order_by("id"):
            traffic.append({"ue_name": u.name, "profile": t.schedule or []})
    out["ues"] = ues
    out["traffic"] = traffic
    return out
