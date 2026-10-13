"""CU → AMF(NGAP,HTTP + JSON)—— 多 gNB P5。env HTTP_AMF_HOST 沒設時一律不送(CU 用內建的假 AMF,與改版前相同)。

  NG Setup                開機(與 cell 有變時)登記本 gNB:gNB ID、PLMN、TAC、端點、served cells
  Initial UE Message      UE 完成 RRC 建立 → AMF 配 AMF UE NGAP ID,回 Initial Context Setup
  Path Switch Request     Xn 換手 / 跨 gNB 重建後,把 UE 的 NG 關聯改到本 gNB
  Handover Required       沒有 Xn 時的 NG 換手(AMF 轉目標 gNB)
  Handover Notify         NG 換手的 UE 已到本 gNB
  UE Context Release      UE 進 IDLE / 離開本 gNB
"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from main.utils.env_loader import get_float, get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)
_session = requests.Session()


def base_url() -> str:
    host = get_str("HTTP_AMF_HOST", "")
    return f"http://{host}:{get_str('HTTP_AMF_PORT', '8000')}" if host else ""


def enabled() -> bool:
    return bool(base_url())


def gnb_id() -> int:
    return int(get_str("GNB_ID_HEX", "0x000e00"), 16)


class AmfError(Exception):
    pass


def post(element: str, body: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    if not enabled():
        raise AmfError("AMF not configured")
    r = _session.post(f"{base_url()}/api/v0.1/AMF/Ngap/AmfRouter/{element}", json=body,
                      timeout=timeout or get_float("NGAP_TIMEOUT_SEC", 5.0))
    try:
        data = r.json()
    except ValueError:
        data = {"success": False, "message": r.text[:200]}
    if not r.ok:
        raise AmfError(f"{element}: {data.get('message')} {data.get('errors')}")
    return data.get("data") or {}


_ng_lock = threading.Lock()
_ng_thread: threading.Thread | None = None
_ng_done = threading.Event()


def ng_setup_done() -> bool:
    return _ng_done.is_set()


def ensure_ng_setup(retry_sec: float = 3.0, give_up_sec: float = 900.0) -> None:
    """背景做 NG Setup 直到成功(AMF 容器可能比 CU 晚起)。cell 有變時再呼叫一次(= RAN Configuration Update)。"""
    global _ng_thread
    if not enabled():
        return

    def _run() -> None:
        from django.db import close_old_connections
        from main.apps.cu_cp.services.business import xn
        t0 = time.time()
        while time.time() - t0 < give_up_sec:
            close_old_connections()
            me = xn.self_gnb()
            try:
                post("ng_setup", {"gnb_id": gnb_id(), "gnb_name": me.name if me else get_str("GNB_NAME", ""),
                                  "cu_url": get_str("CU_SELF_URL", "") or (me.cu_url if me else ""),
                                  "plmn": f"{get_str('PLMN_MCC', '208')}{get_str('PLMN_MNC', '95').zfill(2)}",
                                  "tac": get_int("SERVED_TAC", 0xA000), "served_cells": xn.local_served_cells()})
                _ng_done.set()
                logger.info("NG Setup with AMF %s done (gNB 0x%06x)", base_url(), gnb_id())
                break
            except Exception as exc:  # noqa: BLE001
                logger.info("NG Setup 尚未成功: %s", exc)
                time.sleep(retry_sec)
        close_old_connections()

    with _ng_lock:
        if _ng_thread is not None and _ng_thread.is_alive():
            return
        _ng_thread = threading.Thread(target=_run, name="ng-setup", daemon=True)
        _ng_thread.start()


def release_ue(amf_ue_ngap_id: int | None) -> None:
    """UE 在本 gNB 被釋放(IDLE / 掉話 / 換走)。fire-and-forget。"""
    if not enabled() or not amf_ue_ngap_id:
        return

    def _run() -> None:
        try:
            post("ue_context_release", {"amf_ue_ngap_id": int(amf_ue_ngap_id), "gnb_id": gnb_id()})
        except Exception as exc:  # noqa: BLE001
            logger.info("UE Context Release → AMF failed: %s", exc)
    threading.Thread(target=_run, name="ngap-release", daemon=True).start()
