"""RU HTTP client — 對 RU 寫 UE 位置。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 3.0
# 連線復用:避免高倍率(30x wall_tick=17ms)下每 tick 都重做 TCP handshake
_session = requests.Session()


def set_channel_mode(mode: str, scenario_id: str = "") -> bool:
    """POST RU /Config/RuController/set_channel_mode — 切 live ⇄ cached。

    給 scenario_driver.start() 用,根據劇本 precompute_status 自動切:
      ready → cached + scenario_id 載對應 cache(npz)
      其他   → live(每 dl_tti 即時呼 Sionna)

    沒這步的話 RU 會卡在上一場跑過的 cached/scenario_id 上,下一場劇本來 lookup
    會 miss → SINR/MCS/thp 全 0,/logs CellStatusGrid / UeSignalLab 看起來
    都不變(其實是 lookup 沒值,不是 polling 出問題)。
    """
    url = f"{settings.SIM_RU_URL.rstrip('/')}/api/v0.1/RU/Config/RuController/set_channel_mode"
    body: dict[str, Any] = {"mode": mode}
    if mode == "cached":
        body["scenario_id"] = scenario_id
    try:
        r = _session.post(url, json=body, timeout=10.0)  # cached load 可能要讀大 npz,timeout 拉寬
        if not r.ok:
            logger.warning("set_channel_mode non-OK %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("set_channel_mode HTTP failed: %s", exc)
        return False


def update_cells(cells: list[dict[str, Any]]) -> bool:
    """POST RU /Config/RuController/update_cells — 全量替換 RU cell 拓樸(exclude-delete)。

    cells = [{name, pci, azimuth_deg, position:[x,y,z], frequency_ghz, bandwidth_mhz,
              gnb_id, power_dbm}, ...]
    給 scenario_driver start() 用,劇本有 gnbs 區塊時跟 Dashboard handleStartSim C.1
    對齊 — 把不在劇本列表裡的舊 cell 刪掉,避免 SINR/path-loss 還在算上一場留下
    的 stray cell。
    """
    if not cells:
        return True
    url = f"{settings.SIM_RU_URL.rstrip('/')}/api/v0.1/RU/Config/RuController/update_cells"
    try:
        r = _session.post(url, json={"cells": cells}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("update_cells non-OK %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("update_cells HTTP failed: %s", exc)
        return False


def update_ues_batch(ues: list[dict[str, Any]], clear_stale: bool = False) -> bool:
    """POST RU /api/v0.1/RU/Config/RuController/update_ues (batch).

    ues = [{id, position:{x,y,z}, velocity?}, ...]
    clear_stale: True 觸發 RU 端 stale UE DELETE(scenario start 那次傳 True 清乾淨,
                 per-tick 之後傳 False 跳過 DELETE 省 ~15ms,給高倍率用)
    """
    if not ues:
        return True
    url = f"{settings.SIM_RU_URL.rstrip('/')}/api/v0.1/RU/Config/RuController/update_ues"
    body = {"ues": ues}
    if clear_stale:
        body["clear_stale"] = True
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("update_ues_batch non-OK: %d %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("update_ues_batch HTTP failed: %s", exc)
        return False
