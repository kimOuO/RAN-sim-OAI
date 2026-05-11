"""Omniverse Kit HTTP client — 寫 UE 視覺化位置。

Kit endpoint: POST /ue/{name}/move {x, y, z}
最佳 effort, 失敗不影響 RAN 模擬
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 1.5


def move_ue(ue_id: str, x: float, y: float, z: float) -> bool:
    base = settings.OMNIVERSE_KIT_URL.rstrip('/')
    url = f"{base}/ue/{ue_id}/move"
    try:
        r = requests.post(url, json={"x": x, "y": y, "z": z}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException:
        # Kit 可能沒跑, 不算 error
        return False
