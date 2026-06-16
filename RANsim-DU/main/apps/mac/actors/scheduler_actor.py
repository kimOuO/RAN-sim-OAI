"""MAC Scheduler controller — set/get/clear PRB quota per cell。

對應 xApp E2 Control Style 2 / Action 6 `control_slice_level_prb_quota`。
URL: /api/v0.1/DU/MAC/MacScheduler/<element>
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.models.cell_state import CellState
from main.apps.mac.services.common.timestamp_service import TimestampService
from main.apps.mac.services.optional.scheduler.prb_quota import get_store
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _validate_pct(name: str, value, default=None) -> tuple[int | None, str | None]:
    if value is None:
        return default, None
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None, f"{name} must be int 0-100"
    if v < 0 or v > 100:
        return None, f"{name} must be 0-100"
    return v, None


class MacSchedulerController:
    """Component: /api/v0.1/DU/MAC/MacScheduler/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def get_runtime_phys(request):
        """回傳目前生效的 per-scenario 物理旋鈕現值 + 與預設的差異。
        前端「Sim Runtime Knobs」面板用,讓使用者看到「非 xApp」的 DU 調整
        (劇本/手動套的 tx_power / inter_freq / discard / rlc_delay)是否影響 KPM。"""
        from main.apps.fapi_north.services.optional.channel_cache_du import (
            get_inter_freq, get_tx_power_dbm, get_noise_floor_dbm,
        )
        from main.apps.tick.services.optional.runner.tick_runner import (
            get_discard_timer_ms, get_rlc_delay_model, get_slot_engine_takeover,
        )
        # 預設值(set_runtime_phys 缺欄位時的還原值 / 模組 env 預設)
        defaults = {
            "inter_freq": False, "discard_timer_ms": 300,
            "tx_power_dbm": 23.0, "rlc_delay_model": "calib",
        }
        current = {
            "inter_freq": get_inter_freq(),
            "discard_timer_ms": get_discard_timer_ms(),
            "tx_power_dbm": get_tx_power_dbm(),
            "rlc_delay_model": get_rlc_delay_model(),
            "noise_floor_dbm": get_noise_floor_dbm(),
            "slot_engine_takeover": get_slot_engine_takeover(),
        }
        adjusted = [k for k, dv in defaults.items() if current.get(k) != dv]
        return success_response(
            {**current, "defaults": defaults, "adjusted": adjusted},
            "runtime phys current",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_runtime_phys(request):
        """劇本 start 時套用的 per-scenario 物理參數(免 DU 專用 env):
        body: {"inter_freq": bool, "discard_timer_ms": int, "tx_power_dbm": float}
        缺欄位 → 還原預設(co-channel / 300ms / 23dBm)讓上一場 CCO 設定不殘留。"""
        try:
            p = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        from main.apps.fapi_north.services.optional.channel_cache_du import (
            set_inter_freq, set_tx_power_dbm,
        )
        from main.apps.tick.services.optional.runner.tick_runner import (
            set_discard_timer_ms, set_rlc_delay_model,
        )
        inter = bool(p.get("inter_freq", False))
        disc = int(p.get("discard_timer_ms", 300))
        txp = float(p.get("tx_power_dbm", 23.0))
        rlc_mode = str(p.get("rlc_delay_model", "calib"))
        set_inter_freq(inter)
        set_discard_timer_ms(disc)
        set_tx_power_dbm(txp)
        set_rlc_delay_model(rlc_mode)
        logger.info("set_runtime_phys: inter_freq=%s discard_ms=%s tx_power=%s rlc_delay_model=%s",
                    inter, disc, txp, rlc_mode)
        return success_response(
            {"inter_freq": inter, "discard_timer_ms": disc, "tx_power_dbm": txp,
             "rlc_delay_model": rlc_mode}, "runtime phys applied")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_prb_quota(request):
        """Set per-cell PRB quota.

        body: {"cell_id": str, "min_prb": int, "max_prb": int, "dedicated_prb": int}
        all percentages 0-100.

        效果：tick_runner 下個 tick 起把該 cell 的 PRB pool × max_prb/100 才丟給 scheduler。
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        cell_id = payload.get("cell_id")
        if not cell_id:
            return error_response("cell_id required", http_status=400)

        # Cell 必須存在（避免 typo 把 quota 設在不存在的 cell）
        if not CellState.objects.filter(cell_id=cell_id).exists():
            return error_response(f"cell_id {cell_id} not found in CellState", http_status=404)

        min_prb, err = _validate_pct("min_prb", payload.get("min_prb"), default=0)
        if err: return error_response(err, http_status=400)
        max_prb, err = _validate_pct("max_prb", payload.get("max_prb"), default=100)
        if err: return error_response(err, http_status=400)
        dedicated, err = _validate_pct("dedicated_prb", payload.get("dedicated_prb"), default=100)
        if err: return error_response(err, http_status=400)

        if min_prb > max_prb:
            return error_response(
                f"min_prb ({min_prb}) must be <= max_prb ({max_prb})", http_status=400,
            )

        q = get_store().set_quota(
            cell_id=cell_id,
            min_prb=min_prb, max_prb=max_prb, dedicated_prb=dedicated,
            set_at_ms=TimestampService.now_ms(),
            set_by=payload.get("set_by", "xApp"),
        )
        logger.info(
            "MacScheduler.set_prb_quota cell=%s min=%s max=%s dedicated=%s (cap %.0f%%)",
            cell_id, min_prb, max_prb, dedicated, q.cap_factor() * 100,
        )
        return success_response(
            {"cell_id": q.cell_id, "min_prb": q.min_prb, "max_prb": q.max_prb,
             "dedicated_prb": q.dedicated_prb, "cap_factor": q.cap_factor(),
             "set_at_ms": q.set_at_ms, "set_by": q.set_by},
            f"PRB quota set on {cell_id}",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def clear_prb_quota(request):
        """Remove quota (restore to 100% — same as no cap)."""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        cell_id = payload.get("cell_id")
        if not cell_id:
            return error_response("cell_id required", http_status=400)
        get_store().clear(cell_id)
        logger.info("MacScheduler.clear_prb_quota cell=%s", cell_id)
        return success_response({"cell_id": cell_id}, f"PRB quota cleared on {cell_id}")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list_prb_quota(request):
        """List all active quotas (debug / observability)."""
        return success_response({"quotas": get_store().list_all()}, "OK")
