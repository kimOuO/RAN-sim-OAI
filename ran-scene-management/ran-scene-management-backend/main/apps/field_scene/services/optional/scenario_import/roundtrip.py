
"""往返比對用的正規化:把「原劇本」與「export 出來的劇本」都化成 loader 眼中的語意形狀再比。"""
from __future__ import annotations

from typing import Any

from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import A3_KEYS, KNOB_KEYS, normalize_positions


def canonical(raw: dict[str, Any]) -> dict[str, Any]:
    dur = float(raw.get("duration_sec") or 0.0)
    gnbs = []
    for g in raw.get("gnbs") or []:
        g_f = float(g.get("frequency_ghz") or 3.5); g_bw = float(g.get("bandwidth_mhz") or 40.0); g_p = float(g.get("power_dbm") or 23.0)
        cells_raw = g.get("cells")
        if cells_raw is None and g.get("cell_id"):
            cells_raw = [{"cell_id": g["cell_id"], "pci": g.get("pci", 0), "azimuth_deg": g.get("azimuth_deg", 0.0)}]
        cells = [{"cell_id": str(c["cell_id"]), "pci": int(c.get("pci") or 0), "azimuth_deg": float(c.get("azimuth_deg") or 0.0),
                  "position": (list(map(float, c["position"])) if c.get("position") else None),
                  "frequency_ghz": float(c["frequency_ghz"]) if c.get("frequency_ghz") is not None else g_f,
                  "bandwidth_mhz": float(c["bandwidth_mhz"]) if c.get("bandwidth_mhz") is not None else g_bw,
                  "barred": bool(c.get("barred", False))} for c in cells_raw or []]
        gnbs.append({"name": str(g["name"]), "position": list(map(float, g.get("position") or [0, 0, 0])), "power_dbm": g_p,
                     "active": bool(g.get("active", True)), "cells": cells})
    ues = [{"name": str(u["name"]), "positions": normalize_positions(list(u.get("positions") or []), dur),
            "active": [[float(a), float(b)] for a, b in (u.get("active") or [])],
            "target_height_m": float(u["target_height_m"]) if u.get("target_height_m") is not None else 1.5,
            "loop": bool(u.get("loop", False))} for u in raw.get("ues") or []]
    traffic = sorted(({"ue_name": str(t["ue_name"]), "profile": [list(map(float, p)) for p in (t.get("profile") or [])]}
                      for t in raw.get("traffic") or []), key=lambda t: t["ue_name"])
    knobs = {k: raw[k] for k in KNOB_KEYS if k in raw}
    a3 = {k: raw.get(k) for k in A3_KEYS if raw.get(k) is not None}
    return {"scenario_id": raw.get("scenario_id"), "scene_id": raw.get("scene_id") or "", "duration_sec": dur,
            "tick_ms": int(raw.get("tick_ms") or 500), "gnbs": gnbs, "ues": ues, "traffic": traffic, "knobs": knobs, "a3": a3,
            "buildings": len(raw.get("buildings") or [])}
