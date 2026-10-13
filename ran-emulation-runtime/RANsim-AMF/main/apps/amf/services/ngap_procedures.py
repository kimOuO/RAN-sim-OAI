"""NGAP 程序(HTTP + JSON,與平台其他介面一致;訊息內容對照 TS 38.413)。

  NG Setup                 gNB(CU)→ AMF:登記 gNB ID、PLMN、TAC、端點、served cells
  Initial UE Message       CU → AMF:UE 第一次接入 → AMF 配 AMF UE NGAP ID,非同步回 Initial Context Setup
  Path Switch Request      目標 CU → AMF:Xn 換手完成後改 UE 的 NG 關聯到新 gNB(§8.4.4)
  Handover Required        來源 CU → AMF:沒有 Xn 時的 NG 換手(§8.4.1)
     → AMF 對目標 CU 送 Handover Request(§8.4.2),拿到 Ack 後回來源 Handover Command
  Handover Notify          目標 CU → AMF:UE 已到目標 gNB(§8.4.3),AMF 更新關聯
  UE Context Release       CU → AMF:UE 進 IDLE(只接受目前服務它的 gNB 送的)
"""
from __future__ import annotations

import threading
from typing import Any

import requests
from django.conf import settings

from main.apps.amf.services.registry import get_registry

import logging

logger = logging.getLogger(__name__)

_session = requests.Session()
_DEFAULT_PDU = [{
    "pdu_session_id": 1,
    "qos_flow_5qi": [9],   # default 5QI=9(best-effort),與改版前 CU 內建假 AMF 相同
    "ul_tunnel": {"teid": 1, "transport_layer_address": "127.0.0.1"},
    "dl_tunnel": {"teid": 2, "transport_layer_address": "127.0.0.1"},
}]


class NgapError(Exception):
    def __init__(self, cause: str, detail: str = "", status: int = 400):
        super().__init__(f"{cause}: {detail}")
        self.cause, self.detail, self.status = cause, detail, status


def _cu_post(cu_url: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    r = _session.post(f"{cu_url}/api/v0.1/CU/NGAP/NgapRouter/{path}", json=body, timeout=settings.NGAP_TIMEOUT_SEC)
    try:
        data = r.json()
    except ValueError:
        data = {"success": False, "message": r.text[:200]}
    if not r.ok:
        raise NgapError("CuRejected", f"{path} HTTP {r.status_code}: {str(data)[:200]}", 502)
    return data


def ng_setup(body: dict[str, Any]) -> dict[str, Any]:
    for k in ("gnb_id", "cu_url"):
        if body.get(k) in (None, ""):
            raise NgapError("MissingIE", k)
    g = get_registry().ng_setup(int(body["gnb_id"]), str(body.get("gnb_name") or ""), str(body["cu_url"]),
                                str(body.get("plmn") or f"{settings.PLMN_MCC}{settings.PLMN_MNC}"),
                                int(body.get("tac") or 0), body.get("served_cells") or [])
    logger.info("NG Setup: gNB 0x%06x (%s) at %s, %d cell(s)", g.gnb_id, g.gnb_name, g.cu_url, len(g.served_cells))
    return {"amf_name": settings.AMF_NAME, "plmn": f"{settings.PLMN_MCC}{settings.PLMN_MNC}",
            "guami": {"region": settings.AMF_REGION_ID, "set": settings.AMF_SET_ID, "pointer": settings.AMF_POINTER},
            "relative_capacity": 255}


def _send_initial_context_setup(gnb_cu_url: str, ran_ue_ngap_id: int, amf_ue_ngap_id: int, sessions: list[dict]) -> None:
    """非同步:CU 送 Initial UE Message 的那個請求還沒結束,同步回呼可能卡住 CU 的工作執行緒。"""
    try:
        _cu_post(gnb_cu_url, "initial_context_setup",
                 {"ran_ue_ngap_id": ran_ue_ngap_id, "amf_ue_ngap_id": amf_ue_ngap_id, "pdu_session_resources": sessions})
        get_registry().bump("initial_context_setup")
    except Exception as exc:  # noqa: BLE001
        get_registry().bump("initial_context_setup_failed")
        logger.warning("Initial Context Setup → %s failed (ran_ue_ngap_id=%s): %s", gnb_cu_url, ran_ue_ngap_id, exc)


def initial_ue_message(body: dict[str, Any]) -> dict[str, Any]:
    for k in ("gnb_id", "ran_ue_ngap_id", "ue_id"):
        if body.get(k) in (None, ""):
            raise NgapError("MissingIE", k)
    reg = get_registry()
    g = reg.gnb(int(body["gnb_id"]))
    if g is None:
        raise NgapError("UnknownGnb", f"gNB 0x{int(body['gnb_id']):06x} has not done NG Setup", 409)
    ue = reg.attach(str(body["ue_id"]), g.gnb_id, int(body["ran_ue_ngap_id"]), str(body.get("cell_id") or ""))
    if not ue.pdu_sessions:
        ue.pdu_sessions = [dict(s) for s in _DEFAULT_PDU]
    threading.Thread(target=_send_initial_context_setup, name=f"ics-{ue.ue_id}",
                     args=(g.cu_url, ue.ran_ue_ngap_id, ue.amf_ue_ngap_id, ue.pdu_sessions), daemon=True).start()
    logger.info("Initial UE Message: %s via gNB 0x%06x ran=%s → amf_ue_ngap_id=%s",
                ue.ue_id, g.gnb_id, ue.ran_ue_ngap_id, ue.amf_ue_ngap_id)
    return {"amf_ue_ngap_id": ue.amf_ue_ngap_id}


def path_switch_request(body: dict[str, Any]) -> dict[str, Any]:
    """目標 gNB 在 Xn 換手完成後送;AMF 把 UE 的 NG 關聯改到目標 gNB,回 Ack(帶 PDU session)。"""
    for k in ("gnb_id", "ran_ue_ngap_id", "amf_ue_ngap_id"):
        if body.get(k) in (None, ""):
            raise NgapError("MissingIE", k)
    reg = get_registry()
    if reg.gnb(int(body["gnb_id"])) is None:
        raise NgapError("UnknownGnb", f"gNB 0x{int(body['gnb_id']):06x}", 409)
    ue = reg.move(int(body["amf_ue_ngap_id"]), int(body["gnb_id"]), int(body["ran_ue_ngap_id"]),
                  str(body.get("cell_id") or ""), "path_switch")
    if ue is None:
        reg.bump("path_switch_failed")
        raise NgapError("UnknownLocalUE-NGAP-ID", str(body["amf_ue_ngap_id"]), 404)
    reg.bump("path_switch")
    logger.info("Path Switch: %s amf=%s → gNB 0x%06x ran=%s cell=%s", ue.ue_id, ue.amf_ue_ngap_id,
                ue.gnb_id, ue.ran_ue_ngap_id, ue.cell_id)
    return {"amf_ue_ngap_id": ue.amf_ue_ngap_id, "ran_ue_ngap_id": ue.ran_ue_ngap_id,
            "pdu_session_resources": ue.pdu_sessions}


def handover_required(body: dict[str, Any]) -> dict[str, Any]:
    """NG 換手(沒有 Xn 時的退路):來源 CU → AMF → 目標 CU 的 Handover Request → 回來源 Handover Command。

    body: {gnb_id(來源), ran_ue_ngap_id, amf_ue_ngap_id, target_gnb_id, target_cell_id, target_nci?, cause?, ue_state?}
    """
    for k in ("gnb_id", "amf_ue_ngap_id", "target_gnb_id", "target_cell_id"):
        if body.get(k) in (None, ""):
            raise NgapError("MissingIE", k)
    reg = get_registry()
    ue = reg.ue(int(body["amf_ue_ngap_id"]))
    if ue is None or ue.gnb_id != int(body["gnb_id"]):
        reg.bump("handover_prep_failed")
        raise NgapError("UnknownLocalUE-NGAP-ID", f"UE amf={body['amf_ue_ngap_id']} not served by gNB 0x{int(body['gnb_id']):06x}", 404)
    tgt = reg.gnb(int(body["target_gnb_id"]))
    if tgt is None:
        reg.bump("handover_prep_failed")
        raise NgapError("UnknownTargetID", f"gNB 0x{int(body['target_gnb_id']):06x}", 409)
    req = {"amf_ue_ngap_id": ue.amf_ue_ngap_id, "ue_id": ue.ue_id, "target_cell_id": body["target_cell_id"],
           "source_gnb_id": ue.gnb_id, "source_cell_id": ue.cell_id, "cause": body.get("cause") or "handover-desirable-for-radio-reasons",
           "pdu_session_resources": ue.pdu_sessions, "ue_state": body.get("ue_state") or {}}
    try:
        ack = (_cu_post(tgt.cu_url, "handover_request", req).get("data") or {})
    except NgapError as exc:
        reg.bump("handover_prep_failed")
        raise NgapError("HandoverResourceAllocationFailure", exc.detail, 409) from exc
    if not ack.get("ran_ue_ngap_id"):
        reg.bump("handover_prep_failed")
        raise NgapError("HandoverResourceAllocationFailure", str(ack)[:200], 409)
    reg.bump("handover_command")
    logger.info("NG Handover prepared: %s amf=%s gNB 0x%06x → 0x%06x (%s)", ue.ue_id, ue.amf_ue_ngap_id,
                ue.gnb_id, tgt.gnb_id, body["target_cell_id"])
    # Handover Command:目標已配好資源(新的 RAN UE NGAP ID);UE 由目標 CU 的 Handover Notify 完成搬移
    return {"amf_ue_ngap_id": ue.amf_ue_ngap_id, "target_gnb_id": tgt.gnb_id,
            "target_ran_ue_ngap_id": int(ack["ran_ue_ngap_id"]), "target_cell_id": body["target_cell_id"]}


def handover_notify(body: dict[str, Any]) -> dict[str, Any]:
    for k in ("gnb_id", "ran_ue_ngap_id", "amf_ue_ngap_id"):
        if body.get(k) in (None, ""):
            raise NgapError("MissingIE", k)
    ue = get_registry().move(int(body["amf_ue_ngap_id"]), int(body["gnb_id"]), int(body["ran_ue_ngap_id"]),
                             str(body.get("cell_id") or ""), "ng_handover")
    if ue is None:
        raise NgapError("UnknownLocalUE-NGAP-ID", str(body["amf_ue_ngap_id"]), 404)
    get_registry().bump("handover_notify")
    return {"amf_ue_ngap_id": ue.amf_ue_ngap_id}


def ue_context_release(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("amf_ue_ngap_id") in (None, ""):
        raise NgapError("MissingIE", "amf_ue_ngap_id")
    ue = get_registry().release(int(body["amf_ue_ngap_id"]), body.get("gnb_id"))
    return {"amf_ue_ngap_id": int(body["amf_ue_ngap_id"]), "cm_state": ue.cm_state if ue else "UNKNOWN"}
