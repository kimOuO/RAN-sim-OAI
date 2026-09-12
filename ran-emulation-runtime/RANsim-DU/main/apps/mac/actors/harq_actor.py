"""HARQ process 查詢 endpoint — 從 in-memory HarqManager 拿 snapshot。

HARQ state 不寫 DB（per-tick 高頻變化），由 mac.services.optional.harq.harq_manager
singleton 維護；本 endpoint 直接 expose snapshot。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
from main.utils.response import error_response, success_response


class MacHarqController:
    """Component: /api/v0.1/DU/MAC/MacHarqController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        snap = get_harq_manager().snapshot()
        ue_filter = payload.get("ue_id")
        direction_filter = payload.get("direction")

        out = []
        for ue_id, pool in snap.items():
            if ue_filter and ue_id != ue_filter:
                continue
            for direction in ("dl", "ul"):
                if direction_filter and direction.upper() != direction_filter.upper():
                    continue
                for pid, state, retx in pool[direction]:
                    out.append({
                        "ue_id": ue_id,
                        "direction": direction.upper(),
                        "harq_pid": pid,
                        "state": state,
                        "retx_count": retx,
                    })
        return success_response(out, "OK")
