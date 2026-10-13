"""UserPlane — 下行資料的路由表(多 gNB,2026-09-27)。

  POST /api/v0.1/UE/UserPlane/path_update  {ue_id, cell_id}   CU 在 UE 換 cell 後通知
  POST /api/v0.1/UE/UserPlane/read                             目前每個 UE 的服務 cell

流量產生器扮演核心網,下行 SDU 送進 UE 服務 cell 所屬的 DU;UE 換手後由 CU 通知這裡改路由
(等同 CU-UP 切 F1-U / AMF Path Switch 後 UPF 改送新 gNB)。
"""
import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.ue_lifecycle.actors.lifecycle_actor import _err, _ok
from main.apps.ue_lifecycle.services import ran_endpoints


class UserPlaneController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def path_update(request):
        try:
            p = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return _err("Invalid JSON", str(exc), 400)
        ue_id, cell_id = str(p.get("ue_id") or ""), str(p.get("cell_id") or "")
        if not ue_id or not cell_id:
            return _err("ue_id and cell_id required", None, 400)
        t = ran_endpoints.topology()
        if t is not None and t.cell(cell_id) is None:
            return _err(f"unknown cell {cell_id}", None, 404)
        ran_endpoints.routes.set(ue_id, cell_id)
        return _ok({"ue_id": ue_id, "cell_id": cell_id,
                    "du_url": ran_endpoints.du_url_for_cell(cell_id)}, "path updated")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        return _ok({"routes": ran_endpoints.routes.snapshot()})
