"""FapiRouter — 對 DU 的主入口（rule §13）。

  POST /api/v0.1/RU/FAPI/FapiRouter/dl_tti_request
  POST /api/v0.1/RU/FAPI/FapiRouter/ul_tti_request
"""
import json
import os

from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ran_sim_protocol.fapi import DlTtiRequest, UlTtiRequest
from ran_sim_protocol.serde import from_dict, to_dict

from main.apps.fapi_south.models.last_tti import LastTti
from main.apps.fapi_south.serializers.fapi_serializers import (
    DlTtiRequestSerializer,
    UlTtiRequestSerializer,
)
from main.apps.fapi_south.services.business.relational_db import SqlDbBusinessService
from main.apps.fapi_south.services.common.timestamp_service import TimestampService
from main.apps.fapi_south.services.common.uuid_service import UUIDService
from main.apps.fapi_south.services.optional import dl_tti_pipeline, du_callback, ul_tti_pipeline
from main.apps.phy_low.models.ru_state import RuState
from main.apps.phy_low.services.business.relational_db import (
    SqlDbBusinessService as PhyLowSql,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


from django.db.utils import OperationalError

logger = get_logger(__name__)

# RU → DU 的逐 UE 同步回呼(舊路徑)。預設關:DU 直接吃 dl/ul_tti 回應本體的 indications。
_LEGACY_DU_CALLBACK = os.environ.get("RU_LEGACY_DU_CALLBACK", "0").strip().lower() in ("1", "true", "on")


def _parse(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _record_dl(ue_id: str, sfn: int, slot: int, sinr_db: float, cqi: int, rank: int, pmi: int):
    now = TimestampService.get_current_timestamp()
    SqlDbBusinessService.upsert_entity(
        LastTti,
        lookup={"ue_id": ue_id, "direction": "DL"},
        defaults={
            "last_tti_uuid": UUIDService.generate_uuid("last_tti", f"DL:{ue_id}"),
            "sfn": sfn, "slot": slot,
            "sinr_db": float(sinr_db), "cqi": int(cqi), "rank": int(rank), "pmi": int(pmi),
            "harq_pid": 0, "success": True,
            "last_tti_created_at": now, "last_tti_updated_at": now,
        },
    )


def _record_ul(ue_id: str, sfn: int, slot: int, harq_pid: int, success: bool):
    now = TimestampService.get_current_timestamp()
    SqlDbBusinessService.upsert_entity(
        LastTti,
        lookup={"ue_id": ue_id, "direction": "UL"},
        defaults={
            "last_tti_uuid": UUIDService.generate_uuid("last_tti", f"UL:{ue_id}"),
            "sfn": sfn, "slot": slot,
            "sinr_db": 0.0, "cqi": 0, "rank": 1, "pmi": 0,
            "harq_pid": int(harq_pid), "success": bool(success),
            "last_tti_created_at": now, "last_tti_updated_at": now,
        },
    )


def _bump_ru_state(sfn: int, slot: int):
    state = RuState.objects.first()
    if state is None:
        return
    state.sfn_counter = sfn
    state.slot_counter = slot
    state.last_tick_at = timezone.now()
    state.ru_state_updated_at = state.last_tick_at
    state.save(update_fields=["sfn_counter", "slot_counter", "last_tick_at", "ru_state_updated_at"])


class FapiRouter:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def dl_tti_request(request):
        try:
            payload = _parse(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = DlTtiRequestSerializer(data=payload)
        if not ser.is_valid():
            logger.warning(
                "dl_tti_request validation failed: errors=%s payload_keys=%s payload_sample=%s",
                ser.errors, list(payload.keys()) if isinstance(payload, dict) else "non-dict",
                str(payload)[:500],
            )
            return error_response("Validation failed", ser.errors, 400)

        req = from_dict(DlTtiRequest, payload)
        # P6 cell_ul_load:2026-09-16 起不再每 tick 落 DB(每 cell 一個 UPDATE transaction,postgres CPU 大戶);
        # pipeline 直接用這個請求帶的值,DB 的 Cell.ul_load 只在請求沒帶時當後備。
        cqi_list = dl_tti_pipeline.run(req)

        # 推回 DU + 寫入 LastTti
        # 先全部送回 DU,再寫 LastTti(觀測用):DU 非阻塞併發送 dl_tti 時 upsert 會互相死結,
        # 以前寫表失敗會中斷迴圈 → 後面 UE 這輪的 CQI 回報全丟
        # 2026-09-22:逐 UE 同步回呼 DU 預設關閉 —— DU 改從本回應的 cqi_indications 套用。
        # 回呼是 RU↔DU 互等的根源(DU 單 process 忙 tick 時 RU 兩個 worker 全卡在等它,
        # DU 又等 RU 的回應而逾時 → 假 RLF)。RU_LEGACY_DU_CALLBACK=1 可回到舊行為。
        if _LEGACY_DU_CALLBACK:
            for cqi in cqi_list:
                du_callback.send_cqi_indication(cqi)
        try:
            for cqi in cqi_list:
                _record_dl(cqi.ue_id, req.sfn, req.slot, cqi.sinr_db, cqi.cqi, cqi.rank, cqi.pmi)
            _bump_ru_state(req.sfn, req.slot)
        except OperationalError as e:
            logger.debug("LastTti upsert skipped (%s)", e)
        logger.debug("dl_tti sfn=%d slot=%d pdus=%d", req.sfn, req.slot, len(req.pdus))

        return success_response(
            {
                "accepted_pdus": len(req.pdus),
                "cqi_indications": [to_dict(c) for c in cqi_list],
            },
            "DL TTI processed",
            200,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ul_tti_request(request):
        try:
            payload = _parse(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = UlTtiRequestSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        req = from_dict(UlTtiRequest, payload)
        crc_list = ul_tti_pipeline.run(req)

        if _LEGACY_DU_CALLBACK:
            for crc in crc_list:
                du_callback.send_crc_indication(crc)
            _record_ul(crc.ue_id, req.sfn, req.slot, crc.harq_pid, crc.success)

        _bump_ru_state(req.sfn, req.slot)
        logger.info("ul_tti sfn=%d slot=%d pdus=%d ok=%d",
                    req.sfn, req.slot, len(req.pdus), sum(1 for c in crc_list if c.success))

        return success_response(
            {
                "accepted_pdus": len(req.pdus),
                "crc_indications": [to_dict(c) for c in crc_list],
            },
            "UL TTI processed",
            200,
        )
