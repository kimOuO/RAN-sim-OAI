"""場景覆蓋圖(2026-09-17):registry 場景 → physics push_scene 形狀 → CoverageRunner/compute_scene。

網格未指定時取場景外框(gNB / cell / UE 路徑 / 建築)外擴 5 m,格距自動調到 ≤ 40000 格。
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from typing import Any

from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import export_scenario

PHYSICS_URL = os.environ.get("PHYSICS_URL", "http://ransim-physics:8000")
MAX_CELLS = 40_000


def _payload(raw: dict[str, Any]) -> dict[str, Any]:
    tx, ue = raw.get("tx_antenna"), raw.get("ue_antenna")
    ant: dict[str, Any] = {}
    if tx:
        ant.update({"gnb_antenna_pattern": tx["pattern"], "gnb_polarization": tx["polarization"],
                    "gnb_array_rows": tx["rows"], "gnb_array_cols": tx["cols"],
                    "gnb_v_spacing": tx["vertical_spacing"], "gnb_h_spacing": tx["horizontal_spacing"]})
    elif raw.get("antenna_pattern"):
        ant["gnb_antenna_pattern"] = raw["antenna_pattern"]
    if ue:
        ant.update({"ue_antenna_pattern": ue["pattern"], "ue_polarization": ue["polarization"]})
    return {"geometry_source": raw.get("geometry_source") or {"type": "buildings_json", "buildings": raw.get("buildings") or []},
            "gnbs": raw.get("gnbs") or [], "scene_antenna_config": ant}


def auto_grid(raw: dict[str, Any], height: float, step: float | None) -> dict[str, Any]:
    xs, zs = [], []
    for g in raw.get("gnbs") or []:
        for p in [g.get("position")] + [c.get("position") for c in g.get("cells") or []]:
            if p:
                xs.append(p[0]); zs.append(p[2])
    for u in raw.get("ues") or []:
        for w in u.get("positions") or []:
            xs.append(w[1]); zs.append(w[3] if len(w) > 3 else w[2])
    for b in raw.get("buildings") or []:
        p, s = b.get("position") or [0, 0, 0], b.get("size") or [0, 0, 0]
        xs += [p[0] - s[0] / 2, p[0] + s[0] / 2]; zs += [p[2] - s[2] / 2, p[2] + s[2] / 2]
    if not xs:
        xs, zs = [-50, 50], [-50, 50]
    x0, x1, z0, z1 = min(xs) - 5, max(xs) + 5, min(zs) - 5, max(zs) + 5
    area = (x1 - x0) * (z1 - z0)
    st = step or max(0.25, round(math.sqrt(area / MAX_CELLS) * 4) / 4)
    x1 = x0 + math.ceil((x1 - x0) / st) * st; z1 = z0 + math.ceil((z1 - z0) / st) * st
    return {"x_range": [round(x0, 3), round(x1, 3)], "z_range": [round(z0, 3), round(z1, 3)], "x_step": st, "z_step": st, "sample_height_m": height}


def compute(scene_uuid: str, *, grid: dict[str, Any] | None, height: float, step: float | None, max_depth: int) -> dict[str, Any]:
    raw = export_scenario(scene_uuid)
    body = {**_payload(raw), "grid": grid or auto_grid(raw, height, step), "include_sinr": True, "max_depth": max_depth, "diffraction": True}
    if not body["gnbs"]:
        raise ValueError("場景沒有 gNB")
    req = urllib.request.Request(f"{PHYSICS_URL}/api/v0.1/Physics/RanSignal/CoverageRunner/compute_scene",
                                 data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)["data"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read() or b"{}").get("message") or f"physics HTTP {e.code}") from e
    # cell tx 名稱(gnb#pci)→ registry cell 名稱
    names = {f"{g['name']}#{c['pci']}": c.get("cell_id") or f"{g['name']}#{c['pci']}" for g in raw.get("gnbs") or [] for c in g.get("cells") or []}
    data["summary"]["cell_names"] = [names.get(c, c) for c in data["summary"]["cells"]]
    return data
