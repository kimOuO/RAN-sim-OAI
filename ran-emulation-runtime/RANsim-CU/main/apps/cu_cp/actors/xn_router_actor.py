"""XnRouter — 鄰居 gNB(別的 CU)→ 本 CU 的 Xn 訊息入口(多 gNB P6,TS 38.423)。

  POST /api/v0.1/CU/Xn/XnRouter/xn_setup              Xn Setup Request → Response(交換 served cells)
  POST /api/v0.1/CU/Xn/XnRouter/handover_request      Handover Request → Acknowledge / Preparation Failure
  POST /api/v0.1/CU/Xn/XnRouter/sn_status_transfer    UE 正在接入本 gNB → Path Switch、改 UE driver 路由、回送 UE Context Release
  POST /api/v0.1/CU/Xn/XnRouter/ue_context_release    對端已收下 UE → 刪掉本地 context
  POST /api/v0.1/CU/Xn/XnRouter/rrc_reestablishment   UE 在本 gNB 的 cell 重建(Retrieve UE Context 成功與否由來源判定)
  POST /api/v0.1/CU/Xn/XnRouter/handover_report       MRO:對端回報本 gNB 送出去的某次換手太早
  POST /api/v0.1/CU/Xn/XnRouter/anr_reverse           對端新增了指向本 gNB cell 的關係 → 本端建反向關係(ANR 經 Xn)
"""
from __future__ import annotations

import json
import threading

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.business import xn
from main.apps.cu_cp.services.business.ue_admission import AdmissionRejected, admit_incoming_ue, complete_arrival
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


def _bg(fn, *args) -> None:
    """Xn 回應要馬上回(對端在等);後續動作丟背景,並用新的 DB 連線。"""
    def _run():
        from django.db import close_old_connections
        close_old_connections()
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            logger.exception("Xn background step failed: %s", getattr(fn, "__name__", fn))
        finally:
            close_old_connections()
    threading.Thread(target=_run, daemon=True, name="xn-bg").start()


class XnRouterActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def xn_setup(request):
        try:
            b = _body(request)
            n = xn.store_peer(int(b["gnb_id"]), str(b.get("gnb_name") or ""), str(b.get("cu_url") or ""),
                              b.get("served_cells") or [])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return error_response("Xn Setup Failure", str(exc), status=400)
        me = xn.self_gnb()
        logger.info("Xn Setup from %s (0x%06x): %d served cell(s)", b.get("gnb_name"), int(b["gnb_id"]), n)
        return success_response({"gnb_id": me.gnb_id if me else 0, "gnb_name": me.name if me else "",
                                 "served_cells": xn.local_served_cells()}, "Xn Setup Response")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def handover_request(request):
        try:
            b = _body(request)
            ctx = b.get("ue_context") or {}
            out = admit_incoming_ue(ue_id=str(b["ue_id"]), target_cell=str(b["target_cell"]),
                                    amf_ue_ngap_id=b.get("amf_ue_ngap_id"), traffic_profile=ctx.get("traffic_profile"),
                                    source_gnb_id=b.get("source_gnb_id"), source_cell=str(b.get("source_cell") or ""),
                                    ho_uuid=str(b.get("ho_uuid") or ""), via="Xn")
        except AdmissionRejected as exc:
            logger.info("Xn Handover Preparation Failure: %s → %s cause=%s %s",
                        b.get("ue_id"), b.get("target_cell"), exc.cause, exc.detail)
            return error_response(exc.cause, exc.detail, status=409)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return error_response("Handover Preparation Failure", str(exc), status=400)
        return success_response(out, "Handover Request Acknowledge")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def sn_status_transfer(request):
        """來源已把 UE 放走:UE 正在本 gNB 接入 → Path Switch(AMF)、UE driver 改路由,再請來源釋放 context。"""
        try:
            b = _body(request)
            ue_id = str(b["ue_id"])
        except (json.JSONDecodeError, KeyError) as exc:
            return error_response("invalid SN Status Transfer", str(exc), status=400)

        def _arrive():
            complete_arrival(ue_id, "Xn")
            src = b.get("source_gnb_id")
            if src:
                try:
                    xn._post(xn.peer_url_for_gnb(int(src)), "ue_context_release", {"ue_id": ue_id, "ho_uuid": b.get("ho_uuid")})
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Xn UE Context Release → gNB 0x%06x failed for %s: %s", int(src), ue_id, exc)
        _bg(_arrive)
        return success_response({"ue_id": ue_id}, "SN Status Transfer received")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def ue_context_release(request):
        """UE 已在對端落地:本地 context 刪掉(只刪「服務 cell 已不是本 gNB 的 cell」的,避免誤刪回來的 UE)。"""
        try:
            b = _body(request)
            ue_id = str(b["ue_id"])
        except (json.JSONDecodeError, KeyError) as exc:
            return error_response("invalid UE Context Release", str(exc), status=400)
        from main.apps.cu_cp.models.cell_config import CellConfig
        ue = UeContext.objects.filter(ue_id=ue_id).first()
        deleted = 0
        if ue is not None and not CellConfig.objects.filter(cell_id=ue.serving_cell).exists():
            deleted, _ = UeContext.objects.filter(ue_id=ue_id).delete()
        return success_response({"ue_id": ue_id, "deleted": bool(deleted)}, "UE Context Release")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def rrc_reestablishment(request):
        """UE 在本 gNB 的 cell 做 RRC 重建。with_ctx = 來源判定 Retrieve UE Context 可成功(有 Xn 與鄰區關係)。"""
        try:
            b = _body(request)
            ctx = b.get("ue_context") or {}
            with_ctx = bool(b.get("with_ctx"))
            out = admit_incoming_ue(ue_id=str(b["ue_id"]), target_cell=str(b["target_cell"]),
                                    amf_ue_ngap_id=ctx.get("amf_ue_ngap_id") if with_ctx else None,
                                    traffic_profile=ctx.get("traffic_profile"),
                                    source_gnb_id=b.get("source_gnb_id"), source_cell=str(b.get("source_cell") or ""),
                                    ho_uuid="", via="Xn-reestablishment" if with_ctx else "reestablishment")
        except AdmissionRejected as exc:
            return error_response(exc.cause, exc.detail, status=409)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return error_response("invalid RRC Reestablishment", str(exc), status=400)
        ue_id = str(b["ue_id"])
        if with_ctx:
            _bg(complete_arrival, ue_id, "Xn")              # 取回 context:Path Switch 接續原 NG 關聯
        else:
            _bg(_fresh_registration, ue_id)                  # 取不回:完整重新接入(新的 Initial UE Message)
        return success_response({**out, "with_ctx": with_ctx}, "RRC Reestablishment accepted")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def handover_report(request):
        try:
            b = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("invalid Handover Report", str(exc), status=400)
        from main.apps.cu_cp.models.handover_event import HandoverEvent
        n = HandoverEvent.objects.filter(ho_uuid=str(b.get("ho_uuid") or "")).update(mro_class=str(b.get("type") or "")[:16])
        logger.info("Xn Handover Report: ho=%s ue=%s type=%s (updated %d)", str(b.get("ho_uuid"))[:8], b.get("ue_id"), b.get("type"), n)
        return success_response({"updated": n}, "Handover Report received")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def anr_reverse(request):
        try:
            b = _body(request)
            local_cell, peer_cell = str(b["target_cell"]), str(b["source_cell"])
        except (json.JSONDecodeError, KeyError) as exc:
            return error_response("invalid", str(exc), status=400)
        from main.apps.cu_cp.actors.anr_control_actor import establish_reverse_local
        created = establish_reverse_local(local_cell, peer_cell)
        return success_response({"created": created}, "reverse relation handled")


def _fresh_registration(ue_id: str) -> None:
    """重建取不回 context:UE 走完整接入 → 新的 Initial UE Message(真 AMF);UE driver 改路由。"""
    from main.apps.cu_cp.services.business import amf_client, ue_notify
    ue = UeContext.objects.filter(ue_id=ue_id).first()
    if ue is None:
        return
    ue_notify.path_update(ue_id, ue.serving_cell)
    if amf_client.enabled():
        try:
            amf_client.post("initial_ue_message", {"gnb_id": amf_client.gnb_id(), "ran_ue_ngap_id": int(ue.ran_ue_ngap_id),
                                                   "ue_id": ue_id, "cell_id": ue.serving_cell, "nas_pdu_b64": ""})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Initial UE Message after re-establishment failed for %s: %s", ue_id, exc)
