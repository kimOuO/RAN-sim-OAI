"""CU HTTP client — 拉 UE list / Cell list / scene state。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 5.0


def list_sessions() -> list[dict[str, Any]]:
    """Fetch CU /Session/SessionController/list — 回傳 active UE sessions.

    每筆 dict 至少含: ue_id, serving_cell, rrc_state, traffic_profile (新欄位, 可能不存在)
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/list"
    try:
        r = requests.post(url, json={}, timeout=_TIMEOUT_SEC)
    except requests.RequestException as exc:
        logger.warning("list_sessions HTTP failed: %s", exc)
        return []
    if not r.ok:
        logger.warning("list_sessions non-OK status %s", r.status_code)
        return []
    try:
        body = r.json()
    except ValueError:
        logger.warning("list_sessions returned non-JSON")
        return []
    # CU schema: {"data": [{ue_id, rrc_state, serving_cell, ...}, ...]}
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "sessions" in data:
        return data["sessions"]
    return []
