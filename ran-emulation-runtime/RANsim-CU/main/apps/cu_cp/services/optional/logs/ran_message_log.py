"""RAN message log — in-memory ring buffer for monitoring CU/DU/RU 互傳訊息。

由 LoggingMiddleware 寫入，由 /Logs/Ring/read endpoint 讀出，給 Dashboard 展示。

不寫 DB（避免高流量打 DB）；單 process 共用，最多保留 N 筆。
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Any


_MAX_ENTRIES = 1000


class _LogRing:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: deque = deque(maxlen=_MAX_ENTRIES)
        self._seq = 0

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            entry["seq"] = self._seq
            self._entries.append(entry)

    def read(self, since_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            out = [e for e in self._entries if e["seq"] > since_seq]
        return out[-limit:]


_ring = _LogRing()


def get_ring() -> _LogRing:
    return _ring


# ── Categorization helpers（依 path 分類 message type）──

_CATEGORIES: list[tuple[str, str]] = [
    # F1AP CU 側（DU → CU）
    ("/F1AP/F1ApRouter/du_setup",                  "F1Setup"),
    ("/F1AP/F1ApRouter/ul_rrc_message",            "F1AP_UL_RRC"),
    ("/F1AP/F1ApRouter/measurement_report",        "F1AP_MeasReport"),
    # F1AP DU 側（CU → DU）
    ("/F1AP/F1ApRouter/dl_rrc_message",            "F1AP_DL_RRC"),
    ("/F1AP/F1ApRouter/ue_context_setup",          "F1AP_UeCtxSetup"),
    ("/F1AP/F1ApRouter/ue_context_release",        "F1AP_UeCtxRelease"),
    ("/F1AP/F1ApRouter/f1_setup_response",         "F1Setup_Resp"),
    # FAPI DU 側（RU → DU）
    ("/FAPI/FapiRouter/cqi_indication",            "FAPI_CQI"),
    ("/FAPI/FapiRouter/crc_indication",            "FAPI_CRC"),
    # FAPI RU 側（DU → RU）
    ("/FAPI/FapiRouter/dl_tti_request",            "FAPI_DL_TTI"),
    ("/FAPI/FapiRouter/ul_tti_request",            "FAPI_UL_TTI"),
    # NGAP
    ("/NGAP/NgapRouter/initial_ue_message",        "NGAP_InitialUE"),
    ("/NGAP/NgapRouter/initial_context_setup",     "NGAP_InitCtxSetup"),
    ("/NGAP/NgapRouter/downlink_nas_transport",    "NGAP_DLNAS"),
    # E1AP
    ("/E1AP/E1ApRouter/bearer_context_setup",      "E1AP_BearerSetup"),
    # Session (Dashboard / xApp control)
    ("/Session/SessionController/handover",        "HandoverCmd"),
    # E2 (xApp)
    ("/E2/E2KpmReporter/read",                     "E2_KPM_Read"),
    ("/E2/Subscription/create",                    "E2_Sub_Create"),
    ("/E2/Subscription/delete",                    "E2_Sub_Delete"),
    ("/E2/Indication/poll",                        "E2_Ind_Poll"),
    ("/E2/Control/request",                        "E2_Control"),
]


def categorize(path: str) -> str:
    for suffix, cat in _CATEGORIES:
        if path.endswith(suffix):
            return cat
    return "OTHER"


def extract_ue_id(path: str, body_text: str) -> str | None:
    """Best-effort 從 JSON body 抓 ue_id（不要 parse 失敗就崩潰）。"""
    if not body_text:
        return None
    try:
        body = json.loads(body_text)
    except Exception:
        return None
    if isinstance(body, dict):
        # 直接欄位
        for k in ("ue_id", "ueId"):
            if isinstance(body.get(k), str):
                return body[k]
        # 巢狀欄位（control_header）
        ch = body.get("control_header") or {}
        if isinstance(ch.get("ue_id"), str):
            return ch["ue_id"]
    return None


def make_entry(
    *,
    service: str,
    path: str,
    method: str,
    status: int,
    duration_ms: int,
    body_text: str = "",
    response_text: str = "",
) -> dict[str, Any]:
    # 2026-05-16 P4.3: request_body + response_body 留進 entry,
    # 前端 RanLogTable 可展開看完整 PDU JSON(plmn_id / tac / s_nssai / nr_cellid 編出來什麼樣)。
    return {
        "ts_ms": int(time.time() * 1000),
        "service": service,           # "CU" / "DU" / "RU"
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": duration_ms,
        "category": categorize(path),
        "ue_id": extract_ue_id(path, body_text),
        "request_body": body_text[:4096] if body_text else "",
        "response_body": response_text[:4096] if response_text else "",
    }
