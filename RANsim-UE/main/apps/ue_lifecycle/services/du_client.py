"""DU HTTP client — 對 DU 注 SDU。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 2.0
# 連線復用:scenario_driver 在高倍率下每 tick 4 個 HTTP,session 池避免 TCP handshake
_session = requests.Session()


def inject_sdu(
    ue_id: str, sdu_bytes: int, *, bearer_type: str = "DRB", bearer_id: int = 1,
) -> str:
    """POST DU /RLC/RlcDataController/inject_sdu.

    模擬「UE 收 DL data」(雖然概念上 DL 是 server → DU → UE, 但 sim 抽象為直接注 RLC TX queue)。

    AL3 — 改回 tri-state 讓 caller (traffic_gen.tick) 區分 "RLC entity 不存在"
    跟 "其他錯誤", 前者觸發 CU update_traffic_profile 自我修復。

    Returns:
      - "ok"            inject 成功
      - "no_entity"     RLC entity 不存在 (DU restart 後常見) — caller 該觸發 re-sync
      - "fail"          其他失敗 (HTTP error, validation, etc)
    """
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/RLC/RlcDataController/inject_sdu"
    body = {
        "ue_id": ue_id,
        "bearer_type": bearer_type,
        "bearer_id": bearer_id,
        "sdu_bytes": sdu_bytes,
    }
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if r.ok:
            return "ok"
        # body 樣式: {"status": "error", "message": "RLC entity not found", ...}
        try:
            msg = (r.json().get("message") or "").lower()
        except (ValueError, AttributeError):
            msg = ""
        if "rlc entity not found" in msg or "no rlc" in msg:
            return "no_entity"
        return "fail"
    except requests.RequestException as exc:
        logger.warning("inject_sdu HTTP failed: %s", exc)
        return "fail"


def replace_cells(cells: list[dict[str, Any]]) -> bool:
    """POST DU /MAC/MacCellController/replace_cells — 全量替換 MAC 端 cell 列表。

    cells = [{cell_id, pci, freq_ghz, bw_mhz, gnb_id?}, ...]
    給 scenario_driver start() 用,跟 Dashboard handleStartSim C.3 對齊 — 把上一場 sim
    在 DU MAC 留下的 stale cell row 清掉,避免 scheduler 用過時 cell 列表排程,
    讓本場 scenario UE 進不了 PM aggregator(/logs 看到「沒有數值」)。
    """
    if not cells:
        return True
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/MAC/MacCellController/replace_cells"
    try:
        r = _session.post(url, json={"cells": cells}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("replace_cells non-OK %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("replace_cells HTTP failed: %s", exc)
        return False


def replace_ues(ue_ids: list[str]) -> bool:
    """POST DU /Tick/TickController/replace_ues — 用 list 取代 DU Tick 的 UE registry。

    給 scenario_driver start() 用,跟 Dashboard handleStartSim C.4 對齊 — unregister
    上一場留下的 stale UE,避免 DU tick loop 還在跑舊 UE 的 scheduling 動作。
    """
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/Tick/TickController/replace_ues"
    body = {"ues": [{"ue_id": uid} for uid in ue_ids]}
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("replace_ues non-OK %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("replace_ues HTTP failed: %s", exc)
        return False


def register_ue_at(ue_id: str, serving_cell: str = "") -> bool:
    """POST DU /Tick/TickController/register_ue (給 scenario_driver attach 用)。

    serving_cell 不空時直接帶上;空字串時 DU 會走 UeMacState fallback。
    """
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/Tick/TickController/register_ue"
    body: dict[str, Any] = {"ue_id": ue_id}
    if serving_cell:
        body["serving_cell"] = serving_cell
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning(
                "register_ue_at %s non-OK %s: %s", ue_id, r.status_code, r.text[:200],
            )
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("register_ue_at HTTP failed: %s: %s", ue_id, exc)
        return False


def inject_sdu_batch(
    ue_id: str,
    items: list[dict[str, Any]],
    *,
    window_ms: int = 100,
    bearer_type: str = "DRB",
    bearer_id: int = 1,
) -> str:
    """AL: POST DU /RLC/RlcDataController/inject_sdu_batch — 一次帶 N 個 sub-SDU.

    items 結構: [{"sdu_bytes": 1500, "ts_offset_us": 0}, ...]
    DU 還原成 per-packet enqueue_ts_ms 寫進 RLC entity, 解決三項 KPM 失真.

    Returns same tri-state semantics as inject_sdu: "ok" / "no_entity" / "fail".
    """
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/RLC/RlcDataController/inject_sdu_batch"
    body = {
        "ue_id": ue_id,
        "bearer_type": bearer_type,
        "bearer_id": bearer_id,
        "window_ms": window_ms,
        "items": items,
    }
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if r.ok:
            return "ok"
        try:
            msg = (r.json().get("message") or "").lower()
        except (ValueError, AttributeError):
            msg = ""
        if "rlc entity not found" in msg or "no rlc" in msg:
            return "no_entity"
        return "fail"
    except requests.RequestException as exc:
        logger.warning("inject_sdu_batch HTTP failed: %s", exc)
        return "fail"


def fetch_ue_signals() -> dict[str, dict[str, Any]]:
    """POST DU /Tick/TickController/dump_pm → 抽 per-UE 即時訊號(scenario_driver
    每隔幾百 ms 拉一次,跟著位置一起塞給 Omniverse 顯示)。

    回傳 {ue_name: {sinr_db, rsrp_dbm, serving_cell}} — 拉不到時回空 dict 不擋 driver。
    """
    url = f"{settings.SIM_DU_URL.rstrip('/')}/api/v0.1/DU/Tick/TickController/dump_pm"
    try:
        r = _session.post(url, json={}, timeout=1.0)
        if not r.ok:
            return {}
        data = r.json().get("data", {})
    except (requests.RequestException, ValueError) as exc:
        logger.warning("fetch_ue_signals HTTP failed: %s", exc)
        return {}
    out: dict[str, dict[str, Any]] = {}
    # 先用 last_ue_stats(per-tick 即時),fallback ue_latest
    src = data.get("last_ue_stats") or data.get("ue_latest") or {}
    for ue_name, s in src.items():
        out[ue_name] = {
            "sinr_db": s.get("sinr_db"),
            "rsrp_dbm": s.get("rsrp_dbm"),
            "serving_cell": s.get("serving_cell") or "",
        }
    return out
