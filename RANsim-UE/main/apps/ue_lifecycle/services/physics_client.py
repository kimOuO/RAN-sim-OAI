"""physics_client — 把劇本場景推給跑著的 Physics server(讓 live mode 也吃劇本幾何)。

問題:precompute(cached)走 run_precompute 的 apply_override → 寫 npz;但跑著的 Physics
server 的 live 引擎只有啟動時的靜態 scene_config。scenario_driver 切 live 時呼這個 client,
把劇本 gnbs/buildings/antenna 經 HTTP push_scene → apply_override 推進 live 引擎 → live 也
scenario-driven。

注意:Physics 的 GnbWriteSerializer 是「扁平」(每 gnb 一個 pci/cell_id/position),劇本是
巢狀 cells → 這裡攤平成多個 gnb entry,name 設 f"{gnb}#{pci}"(= cached npz 的 tx 命名,
靠 pci map 回 DU cell)。
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 30  # apply_override 會重建 Sionna engine(~4s)+ warmup


def _flatten_gnbs(scenario_gnbs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """劇本巢狀 gnbs(含 cells)→ Physics 扁平 gnbs(每 cell 一個 entry)。"""
    flat: list[dict[str, Any]] = []
    for g in scenario_gnbs or []:
        cells = g.get("cells") or []
        if not cells:
            cells = [{"pci": g.get("pci", 0), "cell_id": g.get("cell_id", f"{g['name']}_c0")}]
        for c in cells:
            flat.append({
                "name": f"{g['name']}#{c.get('pci', 0)}",  # 對齊 cached npz tx 命名(pci map 回 DU cell)
                "pci": int(c.get("pci", 0)),
                "cell_id": str(c.get("cell_id", f"{g['name']}_c{c.get('pci', 0)}")),
                "position": list(c.get("position") or g.get("position") or [0, 30, 0]),
                "frequency_ghz": float(g.get("frequency_ghz", 3.5)),
                "power_dbm": float(g.get("power_dbm", 23.0)),
                "bandwidth_mhz": float(g.get("bandwidth_mhz", 40.0)),
            })
    return flat


def push_scene(*, scene_id: str, gnbs: list[dict[str, Any]],
               buildings: list[dict[str, Any]] | None = None,
               antenna_pattern: str | None = None) -> bool:
    """把劇本場景推給 Physics live 引擎(apply_override full:換 geometry + gnbs + 天線)。

    buildings 空 = 平地(自由空間);antenna_pattern None = Physics 預設 tr38901。
    """
    flat = _flatten_gnbs(gnbs)
    if not flat:
        logger.warning("push_scene skip: no gnbs in scenario")
        return False
    payload: dict[str, Any] = {
        "scene_id": scene_id,
        "override_mode": "full",
        "geometry_source": {
            "type": "buildings_json",
            "buildings": buildings or [],   # 空 = 平地 = 自由空間
        },
        "gnbs": flat,
    }
    if antenna_pattern:
        payload["scene_antenna_config"] = {"gnb_antenna_pattern": antenna_pattern}
    url = f"{settings.SIM_PHYSICS_URL.rstrip('/')}/api/v0.1/Physics/RanSignal/ConfigManager/push_scene"
    try:
        r = requests.post(url, json=payload, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("push_scene non-OK %s: %s", r.status_code, r.text[:300])
            return False
        logger.info("push_scene ok: scene=%s gnbs=%d buildings=%d antenna=%s",
                    scene_id, len(flat), len(buildings or []), antenna_pattern or "(default)")
        return True
    except requests.RequestException as exc:
        logger.warning("push_scene HTTP failed: %s", exc)
        return False
