"""RAN message log — in-memory ring buffer (per-service)."""
from __future__ import annotations
import json, threading, time
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


_CATEGORIES: list[tuple[str, str]] = [
    ("/F1AP/F1ApRouter/du_setup",                  "F1Setup"),
    ("/F1AP/F1ApRouter/ul_rrc_message",            "F1AP_UL_RRC"),
    ("/F1AP/F1ApRouter/measurement_report",        "F1AP_MeasReport"),
    ("/F1AP/F1ApRouter/dl_rrc_message",            "F1AP_DL_RRC"),
    ("/F1AP/F1ApRouter/ue_context_setup",          "F1AP_UeCtxSetup"),
    ("/F1AP/F1ApRouter/ue_context_release",        "F1AP_UeCtxRelease"),
    ("/F1AP/F1ApRouter/f1_setup_response",         "F1Setup_Resp"),
    ("/FAPI/FapiRouter/cqi_indication",            "FAPI_CQI"),
    ("/FAPI/FapiRouter/crc_indication",            "FAPI_CRC"),
    ("/FAPI/FapiRouter/dl_tti_request",            "FAPI_DL_TTI"),
    ("/FAPI/FapiRouter/ul_tti_request",            "FAPI_UL_TTI"),
    ("/Tick/TickController/run_once",              "Tick_RunOnce"),
    ("/Tick/TickController/start",                 "Tick_Start"),
    ("/Tick/TickController/stop",                  "Tick_Stop"),
    ("/RLC/RlcDataController/inject_sdu",          "RLC_SDU"),
    ("/Config/RuController/update_ues",            "RU_UpdateUEs"),
    ("/Config/RuController/update_cells",          "RU_UpdateCells"),
    ("/Config/RuController/update_antenna",        "RU_UpdateAnt"),
    ("/PathSolver/compute",                        "Physics_PathSolver"),
]


def categorize(path: str) -> str:
    for suffix, cat in _CATEGORIES:
        if path.endswith(suffix):
            return cat
    return "OTHER"


def extract_ue_id(path: str, body_text: str) -> str | None:
    if not body_text:
        return None
    try:
        body = json.loads(body_text)
    except Exception:
        return None
    if isinstance(body, dict):
        for k in ("ue_id", "ueId"):
            if isinstance(body.get(k), str):
                return body[k]
    return None


def make_entry(*, service: str, path: str, method: str, status: int, duration_ms: int, body_text: str = "") -> dict[str, Any]:
    return {
        "ts_ms": int(time.time() * 1000),
        "service": service,
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": duration_ms,
        "category": categorize(path),
        "ue_id": extract_ue_id(path, body_text),
    }
