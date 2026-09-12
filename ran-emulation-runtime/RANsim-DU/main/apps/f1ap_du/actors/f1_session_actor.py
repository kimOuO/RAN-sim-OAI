"""F1SessionController — 查 DU 與 CU 之間的 F1 連線狀態。

回傳 DB 的 F1Session 列(歷史 / 目前)+ in-memory bootstrap state(thread 內最新進度)。
URL: /api/v0.1/DU/F1AP/F1SessionController/read
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.f1ap_du.models.f1_session import F1Session
from main.apps.f1ap_du.serializers.f1_session_serializers import F1SessionReadSerializer
from main.apps.f1ap_du.services.business.relational_db_operations import (
    RelationalDbBusinessService,
)
from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import (
    get_state,
    is_setup_done,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _bootstrap_state_dict() -> dict:
    s = get_state()
    return {
        "state": s.state,
        "transaction_id": s.transaction_id,
        "attempts": s.attempts,
        "is_setup_done": is_setup_done(),
    }


def _served_cells_from_state() -> list[dict]:
    """從 DU 的 CellState 表組目前 serving 的 cells（給前端 RanArchitecture 用）。"""
    try:
        from main.apps.mac.models.cell_state import CellState
        return [
            {
                "cell_id": c.cell_id,
                "pci": c.pci,
                "frequency_ghz": c.freq_ghz,
                "bandwidth_mhz": c.bw_mhz,
                "served_plmn": c.served_plmn,
                "gnb_id": c.gnb_id or "",
            }
            for c in CellState.objects.all()
        ]
    except Exception:
        return []


class F1SessionController:
    """Component: /api/v0.1/DU/F1AP/F1SessionController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        gnb_du_id = payload.get("gnb_du_id")
        if gnb_du_id is not None:
            obj = RelationalDbBusinessService.get_entity(F1Session, "gnb_du_id", gnb_du_id)
            if obj is None:
                return error_response("F1Session not found", http_status=404)
            data = F1SessionReadSerializer(obj.__dict__).data
            return success_response(
                {"session": data, "bootstrap_state": _bootstrap_state_dict()},
                "OK",
            )

        rows = RelationalDbBusinessService.list_entities(F1Session)
        served_cells = _served_cells_from_state()
        return success_response(
            {
                "sessions": [
                    {
                        **F1SessionReadSerializer(r.__dict__).data,
                        # 把目前 DU CellState 串進來方便前端按 gnb_id 拆 column
                        "served_cells_json": served_cells,
                    }
                    for r in rows
                ],
                "bootstrap_state": _bootstrap_state_dict(),
            },
            "OK",
        )
