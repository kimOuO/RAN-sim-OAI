"""Fire-and-forget push 給 Omniverse playback ingestor。

CU 內部各 actor/service 落地事件後可選擇推一份到 Omniverse,
讓 playback 能把該事件切回對應 frame。失敗只 log,不影響 CU 主流程。
"""
from __future__ import annotations

import os
import threading
from typing import Any

import requests

from main.utils.logger import get_logger


_TIMEOUT_SEC = 1.5
log = get_logger(__name__)


def _base_url() -> str:
    return (os.getenv("OMNIVERSE_URL") or "").rstrip("/")


def _post_async(path: str, payload: dict[str, Any]) -> None:
    base = _base_url()
    if not base:
        return  # 沒設定 = 停推

    def _do():
        url = f"{base}{path}"
        try:
            resp = requests.post(url, json=payload, timeout=_TIMEOUT_SEC)
            if resp.status_code >= 400:
                log.debug("Omniverse push %s -> %s %s", path, resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            log.debug("Omniverse push %s failed: %s", path, exc)

    threading.Thread(target=_do, daemon=True).start()


def push_handover_event(*,
                        ho_uuid: str,
                        ue_id: str,
                        source_cell: str,
                        target_cell: str,
                        trigger: str,
                        status: str,
                        event_ts: str | None = None) -> None:
    """Push HO event to Omniverse `/api/v0.1/RAN/Playback/HandoverIngestor/create`."""
    payload = {
        "ho_uuid": ho_uuid,
        "ue_name": ue_id,
        "source_cell": source_cell,
        "target_cell": target_cell,
        "trigger": trigger,
        "status": status,
    }
    if event_ts:
        payload["event_ts"] = event_ts
    _post_async("/api/v0.1/RAN/Playback/HandoverIngestor/create", payload)


def push_control_action(*,
                        control_style: int,
                        control_action_id: int,
                        action_label: str,
                        ric_req_id: dict | None = None,
                        ue_name: str | None = None,
                        cell_id: str | None = None,
                        payload_json: dict | None = None,
                        outcome: str = "OK",
                        error: str | None = None,
                        action_ts: str | None = None) -> None:
    """Push E2 Control Request 給 Omniverse `/api/v0.1/RAN/Playback/ControlActionIngestor/create`。"""
    payload = {
        "control_style": int(control_style),
        "control_action_id": int(control_action_id),
        "action_label": action_label,
        "ric_req_id": ric_req_id or {},
        "ue_name": ue_name,
        "cell_id": cell_id,
        "payload_json": payload_json or {},
        "outcome": outcome,
    }
    if error:
        payload["error"] = error
    if action_ts:
        payload["action_ts"] = action_ts
    _post_async("/api/v0.1/RAN/Playback/ControlActionIngestor/create", payload)
