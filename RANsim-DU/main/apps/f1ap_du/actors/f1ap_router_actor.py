"""F1ApRouter — DU 收 CU 訊息的入口。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ran_sim_protocol.f1ap import UeContextSetupResponse

from main.apps.f1ap_du.serializers.f1ap_message_serializers import (
    DlRrcMessageTransferSerializer,
    F1SetupResponseSerializer,
    UeContextModificationSerializer,
    UeContextReleaseSerializer,
    UeContextSetupSerializer,
    UlRrcInjectSerializer,
)
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    encode_ue_context_setup_response,
)
from main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher import UlRrcDispatcher
from main.apps.mac.models.ue_mac_state import UeMacState
from main.apps.mac.services.business.relational_db_operations import (
    RelationalDbBusinessService as MacRelDb,
)
from main.apps.mac.services.common.timestamp_service import TimestampService as MacTs
from main.apps.mac.services.common.uuid_service import UUIDService as MacUuid
from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import get_pm_aggregator
from main.apps.mac.services.optional.random_access.ra_manager import get_ra_manager
from main.apps.rlc.models.rlc_entity import RlcEntity
from main.apps.rlc.services.business.relational_db_operations import (
    RelationalDbBusinessService as RlcRelDb,
)
from main.apps.rlc.services.common.timestamp_service import TimestampService as RlcTs
from main.apps.rlc.services.common.uuid_service import UUIDService as RlcUuid
from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class F1ApRouterController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ue_context_setup(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = UeContextSetupSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        ue_id = v["ue_id"]

        # MAC: create or update UE state
        ue_mac_uuid = MacUuid.generate_uuid("ue_mac", ue_id)
        ts_mac = MacTs.now_ms()
        serving_cell_id = v.get("serving_cell_id", "") or payload.get("serving_cell_id", "")
        MacRelDb.upsert_entity(
            UeMacState, "ue_mac_uuid", ue_mac_uuid,
            {
                "ue_mac_uuid": ue_mac_uuid,
                "ue_id": ue_id,
                "serving_cell_id": serving_cell_id,
                "ue_mac_created_at": ts_mac,
                "ue_mac_updated_at": ts_mac,
            },
        )

        # 同步進 TickRunner._ue_registry — F1AP 是 serving_cell 的 source of truth,
        # 不能等 Dashboard 的 register_ue 來補（會 fallback 成 magic "default-cell-0"）。
        if serving_cell_id:
            from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
            get_tick_runner().update_ue_serving_cell(ue_id, serving_cell_id)

        # RA + HARQ in-memory hooks
        get_ra_manager().msg1_detected(ue_id, ts_mac)
        get_harq_manager().add_ue(ue_id)

        # P0-6:DRB 5QI → tick registry(PF 排程器 GBR-first 讀這個)
        _drbs = v.get("drbs", [])
        if _drbs:
            from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
            get_tick_runner().update_ue_qos(ue_id, int(_drbs[0].get("qos_5qi", 9) or 9))

        # RLC: 為每個 DRB 建 entity
        ts_rlc = RlcTs.now_ms()
        drbs_setup: list[int] = []
        for drb in v.get("drbs", []):
            drb_id = drb["drb_id"]
            mode = drb.get("rlc_mode", "AM")
            key = f"{ue_id}:DRB:{drb_id}"
            rlc_uuid = RlcUuid.generate_uuid("rlc", key)
            RlcRelDb.upsert_entity(
                RlcEntity, "rlc_uuid", rlc_uuid,
                {
                    "rlc_uuid": rlc_uuid,
                    "ue_id": ue_id,
                    "bearer_type": "DRB",
                    "bearer_id": drb_id,
                    "mode": mode,
                    "sn_field_length": 12,
                    "rlc_created_at": ts_rlc,
                    "rlc_updated_at": ts_rlc,
                },
            )
            ent = rlc_factory.make_entity(mode)
            rlc_factory.register(ue_id, "DRB", drb_id, ent)
            drbs_setup.append(drb_id)

        # SRB1 預設配 AM
        srb_key = f"{ue_id}:SRB:1"
        srb_uuid = RlcUuid.generate_uuid("rlc", srb_key)
        RlcRelDb.upsert_entity(
            RlcEntity, "rlc_uuid", srb_uuid,
            {
                "rlc_uuid": srb_uuid,
                "ue_id": ue_id,
                "bearer_type": "SRB",
                "bearer_id": 1,
                "mode": "AM",
                "sn_field_length": 12,
                "rlc_created_at": ts_rlc,
                "rlc_updated_at": ts_rlc,
            },
        )
        rlc_factory.register(ue_id, "SRB", 1, rlc_factory.make_entity("AM"))

        get_ra_manager().finalize(ue_id)
        logger.info("UE context setup ok ue=%s drbs=%s", ue_id, drbs_setup)

        resp = UeContextSetupResponse(ue_id=ue_id, success=True, drb_setup_list=drbs_setup)
        return success_response(encode_ue_context_setup_response(resp), "OK", http_status=201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ue_context_modification(request):
        """F1AP UE Context Modification — CU-CP 通知 DU 換 serving cell（HO 用）。

        對齊 OAI: openair2/F1AP/f1ap_du_ue_context_management.c::DU_handle_UE_CONTEXT_MODIFICATION_REQUEST。
        CU 在 RIC HO / A3 自動 HO / 手動 HO 後 push 到這裡，DU 把 serving_cell 換掉:
          1. UeMacState.serving_cell_id 更新（DB）
          2. TickRunner._ue_registry[ue]['serving_cell'] 更新（in-memory，影響下個 tick 的 PDU.cell_id）
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = UeContextModificationSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        ue_id = v["ue_id"]
        target_cell = v["target_cell"]

        # 1) 更新 UeMacState.serving_cell_id (DB)
        ts_mac = MacTs.now_ms()
        UeMacState.objects.filter(ue_id=ue_id).update(
            serving_cell_id=target_cell, ue_mac_updated_at=ts_mac,
        )

        # 2) 同步 TickRunner._ue_registry (in-memory) — 下個 tick 的 dl_tti PDU.cell_id 會生效
        from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
        get_tick_runner().update_ue_serving_cell(ue_id, target_cell)

        logger.info("UE Context Modification: ue=%s → serving_cell=%s", ue_id, target_cell)
        return success_response({"ue_id": ue_id, "serving_cell_id": target_cell}, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ue_context_release(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = UeContextReleaseSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        ue_id = ser.validated_data["ue_id"]

        UeMacState.objects.filter(ue_id=ue_id).delete()
        RlcEntity.objects.filter(ue_id=ue_id).delete()
        rlc_factory.unregister_ue(ue_id)
        get_harq_manager().remove_ue(ue_id)
        get_pm_aggregator().remove_ue(ue_id)
        # AG10: 同步清 tick_runner in-memory _ue_registry, 跟其他層對稱
        from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
        get_tick_runner().unregister_ue(ue_id)
        logger.info("UE context release ue=%s", ue_id)
        return success_response({"ue_id": ue_id}, "Released")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def dl_rrc_message(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = DlRrcMessageTransferSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data

        # 把 RRC PDU 推到對應 SRB1 的 RLC TX queue (假 size = b64 length)
        ue_id = v["ue_id"]
        ent = rlc_factory.lookup(ue_id, "SRB", 1)
        if ent is None:
            logger.warning("DL RRC for ue=%s but no SRB1 entity", ue_id)
            return error_response("UE SRB1 not found", http_status=404)
        msg_size = max(1, len(v["rrc_msg_b64"]) * 3 // 4)  # b64 → 原 bytes 估算
        ent.recv_sdu(msg_size)
        logger.info("DL RRC injected to SRB1 ue=%s size=%dB", ue_id, msg_size)
        return success_response({"ue_id": ue_id, "queued_bytes": msg_size}, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def ul_rrc_message(request):
        """UE simulator → DU 注入 UL RRC PDU,DU 編碼後轉送 CU。

        URL: /api/v0.1/DU/F1AP/F1ApRouter/ul_rrc_message

        Body: {ue_id, rrc_msg_b64, is_initial?}
          - is_initial=True 表示這是 RA Msg3 的 CCCH SRB0 PDU,會把該 UE 的 RA state
            從 WAIT_MSG3 推進到 MSG4_SENT(等 CU 回 DL RRC 才完成 finalize)
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = UlRrcInjectSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        ue_id = v["ue_id"]
        rrc_b64 = v["rrc_msg_b64"]
        is_initial = bool(v.get("is_initial", False))

        # RA hook:initial PDU 把 RA state 推進到 MSG4_SENT
        ra_state_after = None
        if is_initial:
            advanced = get_ra_manager().advance(ue_id, "MSG4_SENT")
            ra_state_after = advanced.state if advanced else None

        try:
            forwarded = UlRrcDispatcher.dispatch(ue_id, rrc_b64)
        except (ValueError, TypeError) as e:
            return error_response(f"Bad rrc_msg_b64: {e}", http_status=400)

        return success_response(
            {
                "ue_id": ue_id,
                "forwarded_to_cu": forwarded,
                "is_initial": is_initial,
                "ra_state": ra_state_after,
            },
            "Forwarded",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def f1_setup_response_callback(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = F1SetupResponseSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        # 簡化:只記 log
        logger.info(
            "F1Setup response from CU tid=%s accepted=%s",
            ser.validated_data.get("transaction_id"),
            ser.validated_data.get("accepted"),
        )
        return success_response(None, "OK")
