"""RU HTTP client — 對 RU 寫 UE 位置。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 3.0


def update_ues_batch(ues: list[dict[str, Any]]) -> bool:
    """POST RU /api/v0.1/RU/Config/RuController/update_ues (batch).

    ues = [{id, position:{x,y,z}, velocity?}, ...]
    """
    if not ues:
        return True
    url = f"{settings.SIM_RU_URL.rstrip('/')}/api/v0.1/RU/Config/RuController/update_ues"
    try:
        r = requests.post(url, json={"ues": ues}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("update_ues_batch non-OK: %d %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("update_ues_batch HTTP failed: %s", exc)
        return False
