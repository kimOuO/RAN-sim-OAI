"""F1AP CU-side router. Mirrors OAI's F1AP_CU_task switch dispatch.

OAI ref: openair2/F1AP/f1ap_cu_task.c (F1AP_CU_task at L110-239).
"""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.du_registry import DuRegistry
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.f1ap_serializers import (
    F1SetupWriteSerializer,
    MeasurementReportWriteSerializer,
    UlRrcMessageWriteSerializer,
)
from main.apps.cu_cp.services.business.cuup_client_operations import CuupClientBusinessService
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.apps.cu_cp.services.optional.mobility.a3_handover_calculation import (
    A3HandoverCalculation, get_ue_state,
)
from main.apps.cu_cp.services.optional.ngap.ngap_handler import NgapHandler
from main.utils.env_loader import default_served_plmn
from main.apps.cu_cp.services.optional.rrc.message_handler import (
    RrcMessageHandler, RrcMessageType,
)
from main.apps.cu_cp.services.optional.rrc.state_machine import RrcStateMachine
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class F1ApRouterActor:
    """All F1-C messages from DU come through this Actor."""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def du_setup(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = F1SetupWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        data = serializer.validated_data
        gnb_du_id = data["gnb_du_id"]
        cells = data["served_cells"]

        now = TimestampService.now()
        du_uuid = UUIDService.generate_uuid("du", gnb_du_id)

        SqlDbBusinessService.upsert_entity(
            DuRegistry,
            "gnb_du_id",
            gnb_du_id,
            defaults={
                "du_uuid": du_uuid,
                "name": f"DU#{gnb_du_id}",
                "served_cells_json": cells,
                "registered_at": now,
                "last_seen_at": now,
            },
        )

        incoming_cell_ids = [c["cell_id"] for c in cells]
        for cell in cells:
            cell_uuid = UUIDService.generate_uuid("cell", cell["cell_id"])
            SqlDbBusinessService.upsert_entity(
                CellConfig,
                "cell_id",
                cell["cell_id"],
                defaults={
                    "cell_uuid": cell_uuid,
                    "pci": cell["pci"],
                    "frequency_ghz": cell["frequency_ghz"],
                    "bandwidth_mhz": cell["bandwidth_mhz"],
                    "served_plmn": cell.get("served_plmn") or default_served_plmn(),
                    "gnb_id": cell.get("gnb_id", ""),
                    "served_by_du_id": gnb_du_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        # 把屬於這個 DU 但不在這次 F1Setup 的 cell 刪掉（DU 重啟 → 重發 F1Setup 表示
        # 「我現在 serve 的就是這些」，不在的就應該移除）。只限 same gnb_du_id，避免動到其他 DU 的 cells。
        stale = CellConfig.objects.filter(served_by_du_id=gnb_du_id).exclude(cell_id__in=incoming_cell_ids)
        deleted = stale.count()
        if deleted > 0:
            stale.delete()
            logger.info("F1 Setup cleared %d stale cells from DU#%s", deleted, gnb_du_id)

        logger.info("F1 Setup accepted: DU#%s with %d cell(s)", gnb_du_id, len(cells))
        resp = F1apHandler.build_f1_setup_response(transaction_id=gnb_du_id, accepted=True)
        return success_response(resp, "F1 Setup accepted", status=200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def du_configuration_update(request: HttpRequest):
        """處理 gNB-DU Configuration Update（3GPP TS 38.473 §8.2.4）。

        DU 在 F1 ACTIVE 後新增 / 修改 / 刪除 cell 會送這個訊息。
        body: {gnb_du_id, transaction_id, served_cells_to_add[], served_cells_to_modify[], served_cells_to_delete[]}
        每個 cell 帶完整 CellConfig 欄位（含 gnb_id、is_active）。
        """
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        gnb_du_id = body.get("gnb_du_id")
        if gnb_du_id is None:
            return error_response("gnb_du_id required", status=400)

        to_add = body.get("served_cells_to_add") or []
        to_modify = body.get("served_cells_to_modify") or []
        to_delete = body.get("served_cells_to_delete") or []

        now = TimestampService.now()

        for cell in list(to_add) + list(to_modify):
            if not isinstance(cell, dict):
                continue
            cell_uuid = UUIDService.generate_uuid("cell", cell["cell_id"])
            SqlDbBusinessService.upsert_entity(
                CellConfig,
                "cell_id",
                cell["cell_id"],
                defaults={
                    "cell_uuid": cell_uuid,
                    "pci": cell["pci"],
                    "frequency_ghz": cell["frequency_ghz"],
                    "bandwidth_mhz": cell["bandwidth_mhz"],
                    "served_plmn": cell.get("served_plmn") or default_served_plmn(),
                    "gnb_id": cell.get("gnb_id", ""),
                    "is_active": cell.get("is_active", True),
                    "served_by_du_id": gnb_du_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        deleted = 0
        if to_delete:
            ids = [c["cell_id"] if isinstance(c, dict) else str(c) for c in to_delete]
            deleted, _ = CellConfig.objects.filter(
                served_by_du_id=gnb_du_id, cell_id__in=ids,
            ).delete()

        logger.info(
            "DU Config Update DU#%s: add=%d modify=%d delete=%d",
            gnb_du_id, len(to_add), len(to_modify), deleted,
        )
        return success_response(
            {"accepted": True, "transaction_id": body.get("transaction_id", 0)},
            "config update accepted",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ul_rrc_message(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = UlRrcMessageWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        ue_id = serializer.validated_data["ue_id"]
        rrc_msg_b64 = serializer.validated_data["rrc_msg_b64"]

        try:
            decoded = RrcMessageHandler.decode(rrc_msg_b64)
        except ValueError as exc:
            return error_response("corrupt RRC message", str(exc), status=400)

        msg_type = decoded.get("type", "")
        now = TimestampService.now()
        ue_uuid = UUIDService.generate_uuid("ue", ue_id)

        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            # 沒真 AMF — 但 xApp / E2 介面要求 amf_ue_ngap_id 唯一可識別。
            # 用 hash(ue_id) 衍生三個 ID（rrc / ran / amf）— deterministic，相同 UE ID
            # 重 attach 也拿到同一組 ID。
            base = abs(hash(ue_id)) % (2 ** 31)
            ue = SqlDbBusinessService.create_entity(UeContext, {
                "ue_uuid": ue_uuid,
                "ue_id": ue_id,
                "rrc_state": "IDLE",
                "rrc_ue_id": base,
                "ran_ue_ngap_id": base,
                "amf_ue_ngap_id": base + 1,    # 跟 ran_ue_ngap_id 差 1 避免混淆
                "created_at": now,
                "updated_at": now,
            })

        next_state = ue.rrc_state
        downstream = {}

        if msg_type == RrcMessageType.SETUP_REQUEST:
            next_state = RrcStateMachine.transition(ue.rrc_state, "SETUP")
            setup_b64 = RrcMessageHandler.encode_rrc_setup(transaction_id=1)
            downstream = DuClientBusinessService.post_dl_rrc_message(
                F1apHandler.build_dl_rrc_message_transfer(ue_id, setup_b64),
            )
            logger.info("RRC Setup → DU for UE %s", ue_id)
        elif msg_type == RrcMessageType.SETUP_COMPLETE:
            next_state = RrcStateMachine.transition(ue.rrc_state, "CONNECTED")
            ngap_payload = {
                "ran_ue_ngap_id": ue.ran_ue_ngap_id,
                "nas_pdu_b64": decoded.get("payload", {}).get("nas_pdu_b64", ""),
                "selected_plmn": "00101",
            }
            NgapHandler.push_initial_ue_message(ngap_payload)
            logger.info("UE %s reached CONNECTED; InitialUEMessage queued", ue_id)
        elif msg_type == RrcMessageType.RECONFIGURATION_COMPLETE:
            logger.info("UE %s confirmed RRCReconfigurationComplete", ue_id)
        elif msg_type == RrcMessageType.MEASUREMENT_REPORT:
            logger.debug("UE %s sent MeasurementReport via UL RRC (handled in /measurement_report)", ue_id)
        else:
            logger.warning("Unhandled UL RRC message type %s for UE %s", msg_type, ue_id)

        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"rrc_state": next_state, "updated_at": now},
        )

        return success_response({
            "ue_id": ue_id,
            "next_state": next_state,
            "rrc_msg_type": msg_type,
            "downstream": downstream,
        }, "UL RRC processed")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def measurement_report(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = MeasurementReportWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        d = serializer.validated_data
        ue_id = d["ue_id"]
        now = TimestampService.now()

        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)

        SqlDbBusinessService.create_entity(MeasurementLog, {
            "meas_uuid": UUIDService.random_uuid(),
            "ue_id": ue_id,
            "rsrp_dbm": d["rsrp_dbm"],
            "sinr_db": d["sinr_db"],
            "throughput_dl_mbps": d["throughput_dl_mbps"],
            "throughput_ul_mbps": d["throughput_ul_mbps"],
            "mcs_dl": d["mcs_dl"],
            "rb_width_dl": d["rb_width_dl"],
            "mimo_rank": d["mimo_rank"],
            "pdcp_sdu_volume_dl": d.get("pdcp_sdu_volume_dl", 0),
            "pdcp_sdu_volume_ul": d.get("pdcp_sdu_volume_ul", 0),
            "rlc_sdu_delay_dl_ms": d.get("rlc_sdu_delay_dl_ms", 0.0),
            "neighbor_cells_json": d["neighbor_cells"],
            "recorded_at": now,
        })

        # ── A3 自動觸發 handover 評估（對齊 OAI rrc_gNB_mobility::trigger_HO） ──
        # 公式：RSRP(neighbor) - hys > RSRP(serving) + offset 持續 TTT_MS
        neighbors = [(n.get("cell_id"), n.get("rsrp_dbm")) for n in (d.get("neighbor_cells") or [])
                     if n.get("cell_id") and n.get("rsrp_dbm") is not None]
        if neighbors and ue.serving_cell:
            verdict = A3HandoverCalculation().evaluate(
                ue_state=get_ue_state(ue_id),
                serving_cell=ue.serving_cell,
                serving_rsrp=d["rsrp_dbm"],
                neighbors=neighbors,
            )
            if verdict.triggered and verdict.target_cell:
                from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
                ho = execute_f1_handover(
                    ue_id=ue_id, target_cell=verdict.target_cell, trigger="A3_TTT",
                )
                if ho:
                    logger.info(
                        "A3 auto-trigger handover: ue=%s elapsed_TTT=%dms %s → %s",
                        ue_id, verdict.elapsed_ms, ho["source_cell"], ho["target_cell"],
                    )

        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"last_measurement_at": now, "updated_at": now},
        )

        if not RrcStateMachine.can_handover(ue.rrc_state):
            return success_response({"ue_id": ue_id, "ho_triggered": False, "reason": "not_connected"})

        # A3 evaluation
        calc = A3HandoverCalculation()
        ue_state = get_ue_state(ue_id)
        neighbors = [(nb["cell_id"], nb["rsrp_dbm"]) for nb in d["neighbor_cells"]]
        verdict = calc.evaluate(ue_state, ue.serving_cell or "", d["rsrp_dbm"], neighbors)

        ho_payload = {"ho_triggered": False}
        if verdict.triggered:
            target_cell = verdict.target_cell
            source_cell = ue.serving_cell or ""
            ho_uuid = UUIDService.random_uuid()
            SqlDbBusinessService.create_entity(HandoverEvent, {
                "ho_uuid": ho_uuid,
                "ue_id": ue_id,
                "source_cell": source_cell,
                "target_cell": target_cell,
                "trigger": "A3_TTT",
                "status": "PREP",
                "started_at": now,
            })
            mod = F1apHandler.build_ue_context_modification(ue_id, target_cell)
            DuClientBusinessService.post_ue_context_modification(mod)
            SqlDbBusinessService.update_entity(
                UeContext, "ue_id", ue_id,
                {"serving_cell": target_cell, "updated_at": now},
            )
            ho_payload = {
                "ho_triggered": True,
                "ho_uuid": ho_uuid,
                "source_cell": source_cell,
                "target_cell": target_cell,
                "elapsed_ms": verdict.elapsed_ms,
            }
            logger.info("A3 HO fired: UE %s %s → %s", ue_id, source_cell, target_cell)

        return success_response(ho_payload, "measurement processed")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def cell_measurement_report(request: HttpRequest):
        """AL2 — cell-level KPI from DU (3GPP TS 28.552 RRU.PrbTotDl).

        Body: GnbDuCellMeasurementReport dict.
        """
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        cell_id = (body.get("cell_id") or "").strip()
        if not cell_id:
            return error_response("cell_id required", status=400)
        try:
            prb_pct_dl = float(body.get("prb_pct_dl", 0.0))
            prb_pct_ul = float(body.get("prb_pct_ul", 0.0))
            tick_count = int(body.get("tick_count", 0))
            window_seconds = float(body.get("window_seconds", 0.0))
        except (TypeError, ValueError) as exc:
            return error_response("invalid numeric field", str(exc), status=400)

        SqlDbBusinessService.create_entity(CellMeasurementLog, {
            "cell_id": cell_id,
            "prb_pct_dl": max(0.0, min(100.0, prb_pct_dl)),
            "prb_pct_ul": max(0.0, min(100.0, prb_pct_ul)),
            "tick_count": tick_count,
            "window_seconds": window_seconds,
            "recorded_at": TimestampService.now(),
        })
        return success_response({"cell_id": cell_id}, "cell measurement stored")
