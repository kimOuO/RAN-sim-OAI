"""NGAP router — handles 5GC → CU messages.

OAI ref: openair3/NGAP/ngap_gNB_handlers.c.
"""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.ngap_serializers import (
    DownlinkNasTransportWriteSerializer,
    InitialContextSetupWriteSerializer,
    InitialUeMessageWriteSerializer,
)
from main.apps.cu_cp.services.business.cuup_client_operations import CuupClientBusinessService
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.apps.cu_cp.services.optional.rrc.message_handler import RrcMessageHandler
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _parse_or_400(request: HttpRequest, serializer_cls):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        return None, error_response("invalid JSON", str(exc), status=400)
    serializer = serializer_cls(data=body)
    if not serializer.is_valid():
        return None, error_response("validation failed", serializer.errors, status=400)
    return serializer.validated_data, None


class NgapRouterActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def initial_ue_message(request: HttpRequest):
        """5GC -> CU echo path for testing; normally CU originates this."""
        data, err = _parse_or_400(request, InitialUeMessageWriteSerializer)
        if err is not None:
            return err
        logger.info("InitialUEMessage echoed: ran_ue_ngap_id=%s", data["ran_ue_ngap_id"])
        return success_response(data, "received")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def initial_context_setup(request: HttpRequest):
        """5GC → CU. Triggers E1 Bearer Setup + F1 UE Context Setup."""
        data, err = _parse_or_400(request, InitialContextSetupWriteSerializer)
        if err is not None:
            return err

        ran_ue_ngap_id = data["ran_ue_ngap_id"]
        amf_ue_ngap_id = data["amf_ue_ngap_id"]
        sessions = data["pdu_session_resources"]

        ue = SqlDbBusinessService.get_or_none(UeContext, "ran_ue_ngap_id", ran_ue_ngap_id)
        if ue is None:
            return error_response(f"unknown RAN-UE-NGAP-ID {ran_ue_ngap_id}", status=404)

        # 對齊真實 RAN: UE 透過 cell search + RA 選 serving cell；CU 從 RACH 訊息
        # 學到 SpCell。Sim 沒模擬 cell search/RA, 改用 fallback: 第一個 active cell。
        # 之後 A3 / xApp HO 會把它 reroute 到正確 cell。
        # 注意：不 overwrite — 若 UE.serving_cell 已有值（HO 後 attach），尊重。
        initial_cell = ue.serving_cell or ""
        if not initial_cell:
            # TS 38.304:出生安置 fallback 也不得選 barred cell(DB 旗標 OR fixture 檔)。
            from main.apps.cu_cp.services.common.fixture_state import admission_blocked
            for cell in CellConfig.objects.filter(is_active=True).order_by("cell_id"):
                if not admission_blocked(cell.cell_id, bool(cell.is_barred)):
                    initial_cell = cell.cell_id
                    break

        now = TimestampService.now()
        UeContext.objects.filter(ue_id=ue.ue_id).update(amf_ue_ngap_id=amf_ue_ngap_id, updated_at=now)
        # 2026-09-27:服務 cell 只在「還沒有」時才補(條件式更新)。AMF 的回應是非同步的,
        # 期間 UE 可能已經由 Initial UL RRC 或換手設好 cell;以前無條件寫回自己一開始讀到的值,
        # 把 UE 搬回「第一個 active cell」,CU 與 DU 從此認知不同。
        if initial_cell:
            UeContext.objects.filter(ue_id=ue.ue_id, serving_cell="").update(serving_cell=initial_cell, updated_at=now)
        initial_cell = UeContext.objects.filter(ue_id=ue.ue_id).values_list("serving_cell", flat=True).first() or initial_cell

        # Build DRB list (one DRB per PDU session, mirroring OAI restriction).
        drbs = []
        for idx, sess in enumerate(sessions):
            drbs.append({
                "drb_id": idx + 1,
                "qos_5qi": (sess.get("qos_flow_5qi") or [9])[0],
                "rlc_mode": "AM",
            })

        # E1 Bearer Setup → CU-UP
        bearer_resp = CuupClientBusinessService.bearer_context_setup({
            "ue_id": ue.ue_id,
            "drbs": drbs,
        })

        # F1 UE Context Setup → DU (carrying the RRCReconfiguration)
        rrc_b64 = RrcMessageHandler.encode_rrc_reconfiguration(transaction_id=1, drbs=drbs)
        DuClientBusinessService.post_ue_context_setup(
            F1apHandler.build_ue_context_setup(
                ue.ue_id, drbs, rrc_b64, serving_cell_id=initial_cell,
            ),
        )

        logger.info(
            "InitialContextSetup processed for %s (%d DRBs, serving_cell=%s)",
            ue.ue_id, len(drbs), initial_cell or "<none>",
        )
        # 2026-08-12:RRC 建立真累計 —— 這裡 serving cell 已知(RRC Setup 階段還沒有)。
        # 平台 attach 無失敗模型 → Att=Succ(真實語意:每次嘗試都成功,誠實反映)。
        if initial_cell:
            from main.apps.cu_cp.actors.f1ap_router_actor import _bump_estab_counter
            _bump_estab_counter(initial_cell, att=1, succ=1)
        return success_response({
            "ue_id": ue.ue_id,
            "drbs": drbs,
            "cu_up_bearer_setup": bearer_resp,
        }, "context setup")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def downlink_nas_transport(request: HttpRequest):
        """5GC → CU → UE. Wraps NAS PDU in DL RRC and forwards to DU."""
        data, err = _parse_or_400(request, DownlinkNasTransportWriteSerializer)
        if err is not None:
            return err

        ran_ue_ngap_id = data["ran_ue_ngap_id"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ran_ue_ngap_id", ran_ue_ngap_id)
        if ue is None:
            return error_response(f"unknown RAN-UE-NGAP-ID {ran_ue_ngap_id}", status=404)

        rrc_b64 = RrcMessageHandler.encode("DLInformationTransfer", {
            "nas_pdu_b64": data["nas_pdu_b64"],
        })
        downstream = DuClientBusinessService.post_dl_rrc_message(
            F1apHandler.build_dl_rrc_message_transfer(ue.ue_id, rrc_b64),
        )
        return success_response({"ue_id": ue.ue_id, "downstream": downstream}, "NAS forwarded")


class NgapHandoverActor:
    """NG 換手的目標側(多 gNB P6;TS 38.413 §8.4.2 Handover Resource Allocation)。

    AMF 收到來源 gNB 的 Handover Required 後送這裡。目標允入、配 RAN UE NGAP ID、目標 DU 建 context,
    回 Handover Request Acknowledge;UE 到達後由本 gNB 送 Handover Notify(背景)。
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def handover_request(request: HttpRequest):
        import threading
        from main.apps.cu_cp.services.business.ue_admission import AdmissionRejected, admit_incoming_ue, complete_arrival
        try:
            b = json.loads(request.body or b"{}")
            out = admit_incoming_ue(ue_id=str(b["ue_id"]), target_cell=str(b["target_cell_id"]),
                                    amf_ue_ngap_id=b.get("amf_ue_ngap_id"),
                                    traffic_profile=(b.get("ue_state") or {}).get("traffic_profile"),
                                    source_gnb_id=b.get("source_gnb_id"), source_cell=str(b.get("source_cell_id") or ""),
                                    ho_uuid="", via="NG")
        except AdmissionRejected as exc:
            return error_response(exc.cause, exc.detail, status=409)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return error_response("invalid Handover Request", str(exc), status=400)

        def _notify(ue_id: str) -> None:
            # 不等:以前等 0.2 s 牆鐘讓 Command 先回來源,但 10× 下那是 2 秒劇本時間 ——
            # UE 在目標的下一次 A3 會比 Notify 先到 AMF,被判「UE 不在本 gNB」(實測 3 次準備失敗)。
            from django.db import close_old_connections
            close_old_connections()
            try:
                complete_arrival(ue_id, "NG")
            finally:
                close_old_connections()
        threading.Thread(target=_notify, args=(str(b["ue_id"]),), daemon=True, name="ng-ho-notify").start()
        return success_response(out, "Handover Request Acknowledge")
