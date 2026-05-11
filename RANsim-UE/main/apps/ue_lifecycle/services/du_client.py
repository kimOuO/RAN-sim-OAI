"""DU HTTP client — 對 DU 注 SDU。"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 2.0


def inject_sdu(ue_id: str, sdu_bytes: int, *, bearer_type: str = "DRB", bearer_id: int = 1) -> bool:
    """POST DU /RLC/RlcDataController/inject_sdu.

    模擬「UE 收 DL data」(雖然概念上 DL 是 server → DU → UE, 但 sim 抽象為直接注 RLC TX queue)。
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
        return r.ok
    except requests.RequestException as exc:
        logger.warning("inject_sdu HTTP failed: %s", exc)
        return False
