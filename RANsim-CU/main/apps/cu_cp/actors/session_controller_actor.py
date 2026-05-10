"""Dashboard-facing controller — list sessions, query state, force handover."""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.session_serializers import (
    GetStateWriteSerializer,
    HandoverWriteSerializer,
    SessionListReadSerializer,
    UeStateReadSerializer,
)
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class SessionControllerActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request: HttpRequest):
        ues = UeContext.objects.all()
        # 直接組 dict 不走 serializer, 因為 traffic_profile_json 是新欄位
        out = [
            {
                "ue_id": ue.ue_id,
                "rrc_state": ue.rrc_state,
                "serving_cell": ue.serving_cell,
                "last_measurement_at": ue.last_measurement_at.isoformat() if ue.last_measurement_at else None,
                "traffic_profile_json": ue.traffic_profile_json or {},
            } for ue in ues
        ]
        return success_response(out, f"{len(out)} session(s)")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_traffic_profile(request: HttpRequest):
        """body = {ue_id, traffic_profile: {pattern, rate_mbps, sdu_size?, bearer_id?}}"""
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        ue_id = body.get("ue_id")
        profile = body.get("traffic_profile") or {}
        if not ue_id:
            return error_response("ue_id required", status=400)
        # validate pattern
        pattern = profile.get("pattern", "idle")
        if pattern not in ("cbr", "idle", "bursty"):
            return error_response(f"invalid pattern {pattern!r}", status=400)
        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)
        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"traffic_profile_json": profile, "updated_at": TimestampService.now()},
        )
        logger.info("UE %s traffic_profile updated: %s", ue_id, profile)

        # 自動 ensure DU ready — 改 dropdown 即可開始, 不需先按 Start Sim.
        # 只在啟用 traffic 時 (pattern != idle) 觸發, idle 跳過避免無謂 register.
        # 全 fire-and-forget, 失敗不擋 profile update 本身.
        # AG2 spec-alignment: 走 F1AP UE Context Setup 而不是 direct register_ue +
        # create_rlc_entity. 真實 OAI 流程 (3GPP TS 38.473 §8.3.1) — UE Context Setup
        # Request 的 DRBs-To-Be-Setup-List 攜帶每個 DRB 的 RLC mode/QoS, DU 收到後
        # 同時建 MAC UE state + RLC entity per DRB + RA + HARQ. 走這條 path 統一:
        #   1. demo_0508 type bug 不會再發生 (UE 任何路徑進來都會自動建 RLC)
        #   2. 對齊 RIC R4 RAN-swap-transparency — 換真機 OAI 同 endpoint 通
        if pattern != "idle" and ue.rrc_state == "CONNECTED" and ue.serving_cell:
            bearer_id = int(profile.get("bearer_id", 1))
            try:
                drbs = [{
                    "drb_id": bearer_id,
                    "qos_5qi": 9,        # 預設 non-GBR 9 (best-effort web)
                    "rlc_mode": "AM",
                }]
                DuClientBusinessService.post_ue_context_setup(
                    F1apHandler.build_ue_context_setup(
                        ue_id, drbs,
                        rrc_msg_b64="",   # profile-update 沒新 RRC msg, 空 b64
                        serving_cell_id=ue.serving_cell,
                    ),
                )
                DuClientBusinessService.post_tick_start()
                logger.info(
                    "UE %s DU auto-ready via F1AP UeCtxSetup (drbs=%s, cell=%s)",
                    ue_id, [d["drb_id"] for d in drbs], ue.serving_cell,
                )
            except Exception as exc:
                logger.warning("UE %s DU auto-ready failed (non-fatal): %s", ue_id, exc)
        return success_response(
            {"ue_id": ue_id, "traffic_profile": profile}, "traffic profile updated",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def get_state(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        serializer = GetStateWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)
        ue_id = serializer.validated_data["ue_id"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)
        out = UeStateReadSerializer({
            "ue_id": ue.ue_id,
            "rrc_state": ue.rrc_state,
            "serving_cell": ue.serving_cell,
            "rrc_ue_id": ue.rrc_ue_id,
            "amf_ue_ngap_id": ue.amf_ue_ngap_id,
            "ran_ue_ngap_id": ue.ran_ue_ngap_id,
            "gnb_du_id": ue.gnb_du_id,
            "last_measurement_at": ue.last_measurement_at,
        }).data
        return success_response(out)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def handover(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        serializer = HandoverWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        ue_id = serializer.validated_data["ue_id"]
        target_cell = serializer.validated_data["target_cell"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)

        now = TimestampService.now()
        ho_uuid = UUIDService.random_uuid()
        SqlDbBusinessService.create_entity(HandoverEvent, {
            "ho_uuid": ho_uuid,
            "ue_id": ue_id,
            "source_cell": ue.serving_cell or "",
            "target_cell": target_cell,
            "trigger": "MANUAL",
            "status": "PREP",
            "started_at": now,
        })
        DuClientBusinessService.post_ue_context_modification(
            F1apHandler.build_ue_context_modification(ue_id, target_cell),
        )
        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"serving_cell": target_cell, "updated_at": now},
        )
        logger.info("Manual HO requested: UE %s → %s", ue_id, target_cell)
        return success_response({"ho_uuid": ho_uuid, "ue_id": ue_id, "target_cell": target_cell})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def release_stale(request: HttpRequest):
        """Release UEs not in keep_ue_ids — Dashboard 在 Start Sim 前清舊 attach 用。

        body: {"keep_ue_ids": ["UE1", "UE2"], "force": false}
          - force=false（預設）→ rrc_state='IDLE', serving_cell=''（保留 row 與 history）
          - force=true → 直接刪 UeContext row
        空 keep_ue_ids 拒絕（避免誤呼一鍵清光）。
        """
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        keep = body.get("keep_ue_ids") or []
        force = bool(body.get("force", False))

        if not keep:
            return error_response("keep_ue_ids must not be empty", status=400)

        stale_qs = UeContext.objects.exclude(ue_id__in=keep)
        stale_ids = list(stale_qs.values_list("ue_id", flat=True))

        if not stale_ids:
            return success_response(
                {"released": [], "deleted": [], "force": force, "kept": keep},
                "no stale UEs",
            )

        now = TimestampService.now()
        if force:
            count, _ = stale_qs.delete()
            logger.info("release_stale force-deleted %d UEs: %s", count, stale_ids)
            return success_response(
                {"released": [], "deleted": stale_ids, "force": True, "kept": keep},
                f"deleted {count} stale UEs",
            )

        updated = stale_qs.update(rrc_state="IDLE", serving_cell="", updated_at=now)
        logger.info("release_stale marked %d UEs IDLE: %s", updated, stale_ids)
        return success_response(
            {"released": stale_ids, "deleted": [], "force": False, "kept": keep},
            f"released {updated} stale UEs to IDLE",
        )
