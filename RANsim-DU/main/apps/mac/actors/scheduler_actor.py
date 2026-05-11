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
