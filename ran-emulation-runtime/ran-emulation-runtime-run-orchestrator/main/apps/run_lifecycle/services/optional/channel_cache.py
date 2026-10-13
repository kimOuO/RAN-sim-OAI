"""場景有沒有預算好的通道快取(2026-09-28)。

「有沒有預算」是場景的屬性、不是場次狀態:快取檔 `<legacy_scenario_id 或 scene_uuid>.npz`
在共用的 channel_cache 目錄裡(DU / RU 以同一個 scenario id 載入)。以前前端只看 registry 的
cache_path,但從舊劇本匯入的場景有檔案、cache_path 卻是空的 —— 以檔案為準。
"""
from __future__ import annotations

import os

from django.conf import settings

CACHE_DIR = getattr(settings, "PRECOMPUTE_LOG_DIR", "/data/channel_cache")   # orchestrator 內的掛載點
CACHE_DIR_IN_RAN = "/app/data/channel_cache"                                  # registry cache_path 慣用的寫法


def scenario_id(scene: dict) -> str:
    return str((scene or {}).get("legacy_scenario_id") or (scene or {}).get("scene_uuid") or "")


def available(scene: dict) -> bool:
    sid = scenario_id(scene)
    return bool(sid) and os.path.isfile(os.path.join(CACHE_DIR, f"{sid}.npz"))


def cache_path_for(scene: dict) -> str:
    return f"{CACHE_DIR_IN_RAN}/{scenario_id(scene)}.npz"
