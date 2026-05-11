"""DU HTTP client — 對 DU 注 SDU。"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 2.0


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
        r = requests.post(url, json=body, timeout=_TIMEOUT_SEC)
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
