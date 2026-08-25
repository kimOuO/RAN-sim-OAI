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
        if pattern not in ("cbr", "idle", "bursty", "piecewise"):
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
                    # P0-6(2026-08-11):吃 traffic profile 的 5QI(預設 9 best-effort);
                    # 5QI 1~4 會讓 DU PF 排程器走 GBR-first 優先權
                    "qos_5qi": int(profile.get("qos_5qi", 9) or 9),
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
    def release_all(request: HttpRequest):
        """Mark every CONNECTED UE as IDLE — Stop Sim 用,讓 CU indication_producer
        看到沒 active UE 就停 emit,避免 Influx 在 sim 停止後還持續收到 stale KPM.

        body 可選 {"force": false}; force=true 時直接刪 UeContext row.

        Internally fan-outs F1AP UE Context Release to DU 對齊 DU 端 _ue_registry.
        """
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        force = bool(body.get("force", False))

        all_qs = UeContext.objects.all()
        ue_ids = list(all_qs.values_list("ue_id", flat=True))

        if not ue_ids:
            return success_response({"released": [], "deleted": [], "force": force},
                                    "no UEs to release")

        # Fan-out F1AP release to DU (best-effort, 不擋 CU 側 IDLE)
        from main.apps.cu_cp.services.business.du_client_operations import (
            DuClientBusinessService,
        )
        du_ok = du_fail = 0
        for uid in ue_ids:
            try:
                DuClientBusinessService.post_ue_context_release({"ue_id": uid})
                du_ok += 1
            except Exception as exc:
                du_fail += 1
                logger.warning("release_all DU fan-out failed ue=%s: %r", uid, exc)

        # Zero Drb counters (對齊 release_stale 的清理)
        try:
            from main.apps.cu_up.models.drb import Drb
            Drb.objects.filter(ue_id__in=ue_ids).update(dl_packets=0, ul_packets=0)
        except Exception as exc:
            logger.warning("release_all Drb counter zero failed: %r (continuing)", exc)

        if force:
            count, _ = all_qs.delete()
            logger.info("release_all force-deleted %d UEs", count)
            return success_response(
                {"released": [], "deleted": ue_ids, "force": True,
                 "du_release_ok": du_ok, "du_release_fail": du_fail},
                f"deleted {count} UEs",
            )

        now = TimestampService.now()
        # A(2026-08-12):釋放前把各 UE session 存活秒數落帳到 serving cell(真累計)
        try:
            from main.apps.cu_cp.services.business.cell_counters import add_session_time
            for _u in all_qs.filter(rrc_state="CONNECTED").exclude(serving_cell=""):
                add_session_time(_u.serving_cell, (now - _u.created_at).total_seconds())
        except Exception:
            logger.exception("session-time accounting on release failed")
        updated = all_qs.update(rrc_state="IDLE", serving_cell="", updated_at=now)
        logger.info("release_all marked %d UEs IDLE", updated)
        return success_response(
            {"released": ue_ids, "deleted": [], "force": False,
             "du_release_ok": du_ok, "du_release_fail": du_fail},
            f"released {updated} UEs to IDLE",
        )

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

        # AK12: 偵測 kept UE 裡 serving_cell 指到「已經不存在的 cell」的情況。
        # 過去 Build Scene 改 gNB 命名後，CU 端 UeContext.serving_cell 永遠停在
        # 舊 cell（如 gnb4_c0），但 DU 端早已換成 gnbDT_c0 → CellStatusGrid 用
        # serving_cell 對 DU cell list 做 filter 永遠 0 match，整個 grid 空白。
        # 這裡向 DU 查 current cells，把 kept UE 裡 orphan 的也降回 IDLE 讓下一輪
        # Start Sim 重新 attach，serving_cell 會被填正確。
        orphan_kept_ids: list[str] = []
        try:
            from main.apps.cu_cp.services.business.du_client_operations import (
                DuClientBusinessService,
            )
            du_cell_ids = set(DuClientBusinessService.read_mac_cells())
            if du_cell_ids:
                kept_qs = UeContext.objects.filter(ue_id__in=keep).exclude(serving_cell="")
                for u in kept_qs:
                    if u.serving_cell and u.serving_cell not in du_cell_ids:
                        orphan_kept_ids.append(u.ue_id)
                if orphan_kept_ids:
                    logger.warning(
                        "release_stale: %d kept UE 的 serving_cell 已不存在於 DU "
                        "(cells=%s) → 降回 IDLE 重 attach: %s",
                        len(orphan_kept_ids), sorted(du_cell_ids), orphan_kept_ids,
                    )
        except Exception as exc:
            logger.warning("release_stale orphan-detect failed: %r (continuing)", exc)

        if not stale_ids and not orphan_kept_ids:
            return success_response(
                {"released": [], "deleted": [], "force": force, "kept": keep,
                 "orphan_reset": []},
                "no stale UEs",
            )

        # AG10: fan-out F1AP UE Context Release to DU (對齊 3GPP TS 38.473 §8.3.3).
        # 失敗 best-effort, 不阻擋 CU 側 mark IDLE/delete — DU 的 MAC/RLC/tick_registry
        # 一條 path 統一清, 不再留殭屍。
        from main.apps.cu_cp.services.business.du_client_operations import (
            DuClientBusinessService,
        )
        du_release_ok = 0
        du_release_fail = 0
        for ue_id in stale_ids:
            try:
                DuClientBusinessService.post_ue_context_release({"ue_id": ue_id})
                du_release_ok += 1
            except Exception as exc:
                du_release_fail += 1
                logger.warning(
                    "release_stale DU fan-out failed ue=%s: %r (continuing)", ue_id, exc,
                )
        logger.info(
            "release_stale DU fan-out: ok=%d fail=%d", du_release_ok, du_release_fail,
        )

        now = TimestampService.now()
        # AK10: 清掉這些 stale UE 在 CU-UP 端的 Drb packet counter，避免下次同 ue_id
        # re-attach 時數字繼續往上加，KPM 看起來像「上一次模擬封包還沒清乾淨」。
        # 對應 DU 側 tick_runner.start() 的 rlc_factory.clear_all() — 兩邊一起乾淨。
        try:
            from main.apps.cu_up.models.drb import Drb
            drb_zeroed = Drb.objects.filter(ue_id__in=stale_ids).update(
                dl_packets=0, ul_packets=0,
            )
            if drb_zeroed:
                logger.info("release_stale zeroed dl/ul packet counters on %d Drbs", drb_zeroed)
        except Exception as exc:
            # 表不存在或欄位 schema 不同時別擋主流程
            logger.warning("release_stale Drb counter zero failed: %r (continuing)", exc)

        if force:
            count, _ = stale_qs.delete()
            logger.info("release_stale force-deleted %d UEs: %s", count, stale_ids)
            return success_response(
                {"released": [], "deleted": stale_ids, "force": True, "kept": keep,
                 "du_release_ok": du_release_ok, "du_release_fail": du_release_fail},
                f"deleted {count} stale UEs",
            )

        # A(2026-08-12):釋放前 session 秒數落帳
        try:
            from main.apps.cu_cp.services.business.cell_counters import add_session_time
            for _u in stale_qs.filter(rrc_state="CONNECTED").exclude(serving_cell=""):
                add_session_time(_u.serving_cell, (now - _u.created_at).total_seconds())
        except Exception:
            logger.exception("session-time on release_stale failed")
        updated = stale_qs.update(rrc_state="IDLE", serving_cell="", updated_at=now)
        logger.info("release_stale marked %d UEs IDLE: %s", updated, stale_ids)

        # AK12: 把 orphan kept UE 也降回 IDLE — 它們會在下一輪 Start Sim 重新 attach
        # 拿到正確的 serving_cell。同時對 DU 發 UE Context Release 確保 DU 端
        # _ue_registry / RLC entity 清乾淨，避免「DU 還在排程舊 ue_id 但 CU 已重設」
        # 那種半新半舊的狀態。
        orphan_updated = 0
        orphan_du_ok = 0
        orphan_du_fail = 0
        if orphan_kept_ids:
            orphan_qs = UeContext.objects.filter(ue_id__in=orphan_kept_ids)
            orphan_updated = orphan_qs.update(
                rrc_state="IDLE", serving_cell="", updated_at=now,
            )
            for ue_id in orphan_kept_ids:
                try:
                    DuClientBusinessService.post_ue_context_release({"ue_id": ue_id})
                    orphan_du_ok += 1
                except Exception as exc:
                    orphan_du_fail += 1
                    logger.warning(
                        "release_stale orphan DU fan-out failed ue=%s: %r", ue_id, exc,
                    )
            logger.info(
                "release_stale marked %d orphan UEs IDLE (DU release ok=%d fail=%d): %s",
                orphan_updated, orphan_du_ok, orphan_du_fail, orphan_kept_ids,
            )

        return success_response(
            {"released": stale_ids, "deleted": [], "force": False, "kept": keep,
             "orphan_reset": orphan_kept_ids,
             "du_release_ok": du_release_ok, "du_release_fail": du_release_fail},
            f"released {updated} stale UEs to IDLE",
        )
