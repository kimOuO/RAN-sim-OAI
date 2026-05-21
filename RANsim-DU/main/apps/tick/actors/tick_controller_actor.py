"""TickController — start / stop / run_once / read。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.tick.serializers.tick_state_serializers import TickStateReadSerializer
from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


def _resolve_serving_cell(ue_id: str, fallback: str = "") -> str:
    """Serving cell 優先順序: payload > UeMacState (來自 F1AP UE Context Setup) > fallback.

    對齊真實 OAI: F1AP 是 serving cell 的 source of truth, Dashboard 的 register_ue
    只是運行控制 endpoint, 不該決定 serving cell.
    """
    if fallback:
        return fallback
    try:
        from main.apps.mac.models.ue_mac_state import UeMacState
        row = UeMacState.objects.filter(ue_id=ue_id).only("serving_cell_id").first()
        if row and row.serving_cell_id:
            return row.serving_cell_id
    except Exception:
        pass
    return ""

logger = get_logger(__name__)


class TickController:
    """Component name in URL: TickController"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        ok = get_tick_runner().start()
        # AG12: idempotent — 已 running 再 call 不再回 409, 前端 retry 不會 noise.
        if ok:
            logger.info("Tick driver started")
            return success_response(_status_dict(), "Started")
        return success_response(_status_dict(), "Already running (no-op)")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        ok = get_tick_runner().stop()
        # AG12: idempotent — 已 stopped 再 call 不再回 409.
        if ok:
            logger.info("Tick driver stopped")
            return success_response(_status_dict(), "Stopped")
        return success_response(_status_dict(), "Already stopped (no-op)")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def run_once(request):
        result = get_tick_runner().run_once()
        return success_response(result, "Tick executed once")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        return success_response(_status_dict(), "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def dump_pm(request):
        """Debug-only — dump PM aggregator non-destructive snapshot per gNB。

        snapshot() 從 _acc (cumulative per-gNB counters) 拉,不像 flush_ue_report() 是
        destructive,所以 periodic measurement_report 每秒 flush 不會清掉這份資料。
        用於 Phase A KPM 一致性測試:固定 SINR 餵進去,看 avg_sinr/rsrp 跨 tick_ms 是否一致。

        回傳 {tick_count, sim_tick_ms, ue_registry, gnbs: {gnb_id: {avg_sinr_db, avg_rsrp_dbm, ...}}}
        """
        from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import get_pm_aggregator
        runner = get_tick_runner()
        pm = get_pm_aggregator()
        # Phase B — 從 _ue_registry 撈每個 UE 的「上一 tick RU CqiIndication 推上來的瞬時值」
        # 這個比 pm.snapshot() 的累積平均更能反映 UE 即時移動造成的訊號變化。
        ue_latest: dict[str, dict] = {}
        for uid, ue in runner._ue_registry.items():
            ue_latest[uid] = {
                "serving_cell": ue.get("serving_cell", ""),
                "sinr_db": ue.get("sinr_db"),
                "rsrp_dbm": ue.get("rsrp_dbm"),
                "neighbors": ue.get("neighbors", []),
            }
        return success_response(
            {
                "tick_count": runner.status.tick_count,
                "wall_tick_ms": runner.wall_tick_ms,
                "sim_dt_ms": runner.sim_dt_ms,
                "sim_speed_x": runner.sim_speed_x,
                "report_every_n_ticks": runner.REPORT_EVERY_N_TICKS,
                "ue_registry": list(runner._ue_registry.keys()),
                "ue_latest": ue_latest,         # 瞬時 RSRP/SINR/neighbors
                "last_ue_stats": runner.last_ue_stats,      # ← per-tick 即時 throughput/delay/PRB/MCS
                "last_cell_stats": runner.last_cell_stats,  # ← per-tick 即時 cell PRB / %
                "gnbs": pm.snapshot(),          # 累積平均(舊行為,還在以避免破壞既有用例)
            },
            "PM dumped",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_speed(request):
        """Phase A — runtime 調整 sim_tick_ms (default 500). Clamp 10~500ms.

        Body: {"tick_ms": int}      # 例: 125 → 4x 壓縮
        Returns: 含 sim_tick_ms 的 status dict + 訊息。
        下一輪 tick 即生效 (不需 stop/start)。
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        tick_ms = payload.get("tick_ms")
        if tick_ms is None:
            return error_response("tick_ms required", http_status=400)
        try:
            tick_ms_int = int(tick_ms)
        except (TypeError, ValueError):
            return error_response("tick_ms must be int", http_status=400)
        actual = get_tick_runner().set_tick_ms(tick_ms_int)
        return success_response(_status_dict(), f"tick_ms set to {actual}")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def register_ue(request):
        """測試/開發用:手動把 UE 推進 tick registry。"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ue_id = payload.get("ue_id")
        if not ue_id:
            return error_response("ue_id required", http_status=400)
        serving_cell = _resolve_serving_cell(ue_id, payload.get("serving_cell", ""))
        get_tick_runner().register_ue(
            ue_id,
            serving_cell=serving_cell,
            sinr_db=float(payload.get("sinr_db", 10.0)),
            rsrp_dbm=float(payload.get("rsrp_dbm", -85.0)),
            qos_5qi=int(payload.get("qos_5qi", 9)),
        )
        return success_response({"ue_id": ue_id, "serving_cell": serving_cell}, "Registered")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def replace_ues(request):
        """全量替換 _ue_registry — Dashboard Start Sim 推新 UE list 用。

        body: {"ues": [{"ue_id": "...", "serving_cell": "...", ...}, ...]}
        效果：對於不在 incoming list 的舊 UE，呼 unregister_ue 移除；
              對於 incoming 的 UE，register_ue（同 id 會 overwrite）。
        空 list 拒絕（避免誤呼一鍵清庫）。
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ues_in = payload.get("ues") or []
        if not ues_in:
            return error_response("ues must not be empty", http_status=400)

        runner = get_tick_runner()
        incoming_ids = {u.get("ue_id") for u in ues_in if u.get("ue_id")}

        # AG10-extended: stale = (in-memory ∪ DB orphans) − incoming.
        # 不只清 _ue_registry, 也掃 MAC/RLC DB 把 orphans (從沒走 CU 路徑被別人手動建的)
        # 一併走完整 F1AP UE Context Release cleanup, 不再殘留。
        from main.apps.mac.models.ue_mac_state import UeMacState
        from main.apps.rlc.models.rlc_entity import RlcEntity
        from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
        from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import (
            get_pm_aggregator,
        )
        from main.apps.rlc.services.optional.entities import factory as rlc_factory

        existing_in_mem = set(runner._ue_registry.keys())
        existing_in_db = (
            set(UeMacState.objects.values_list("ue_id", flat=True)) |
            set(RlcEntity.objects.values_list("ue_id", flat=True))
        )
        stale = (existing_in_mem | existing_in_db) - incoming_ids

        for old_id in stale:
            # 對齊 f1ap_router_actor.ue_context_release 同條 path:
            UeMacState.objects.filter(ue_id=old_id).delete()
            RlcEntity.objects.filter(ue_id=old_id).delete()
            rlc_factory.unregister_ue(old_id)
            get_harq_manager().remove_ue(old_id)
            get_pm_aggregator().remove_ue(old_id)
            runner.unregister_ue(old_id)

        for u in ues_in:
            ue_id = u.get("ue_id")
            if not ue_id:
                continue
            serving_cell = _resolve_serving_cell(ue_id, u.get("serving_cell", ""))
            runner.register_ue(
                ue_id,
                serving_cell=serving_cell,
                sinr_db=float(u.get("sinr_db", 10.0)),
                rsrp_dbm=float(u.get("rsrp_dbm", -85.0)),
                qos_5qi=int(u.get("qos_5qi", 9)),
            )

        logger.info("replace_ues ok: kept=%d removed=%d", len(incoming_ids), len(stale))
        return success_response(
            {"kept": sorted(incoming_ids), "removed": sorted(stale)},
            f"Replaced UEs: kept={len(incoming_ids)} removed={len(stale)}",
        )


def _status_dict() -> dict:
    runner = get_tick_runner()
    s = runner.status
    return TickStateReadSerializer({
        "tick_count": s.tick_count,
        "sfn": s.sfn,
        "slot": s.slot,
        "started_at_ms": s.started_at_ms,
        "last_tick_ms": s.last_tick_ms,
        "is_running": s.is_running,
        "wall_tick_ms": runner.wall_tick_ms,
        "sim_dt_ms": runner.sim_dt_ms,
        "sim_speed_x": runner.sim_speed_x,
    }).data
