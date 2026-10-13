"""本 DU 的 F1 身分(多 gNB,2026-09-27)。orchestrator 以 env 注入;舊的共用 ransim-du 沒設就用預設。

SIM_GNB_DU_ID  gNB 內唯一的 gNB-DU ID(F1 Setup、Initial UL RRC 都帶)
DU_SELF_URL    CU 送 F1 訊息給本 DU 用的端點(例 http://du-ab12cd34-1:8000)
DU_NAME        拓樸內的 DU 名稱(<gNB>/<DU>,查 RUN_TOPOLOGY 用)
"""
from __future__ import annotations

from main.utils.env_loader import get_int, get_str


def gnb_du_id() -> int:
    return get_int("SIM_GNB_DU_ID", 1)


def self_url() -> str:
    return (get_str("DU_SELF_URL", "") or "").rstrip("/")


def name() -> str:
    return get_str("DU_NAME", "") or ""
