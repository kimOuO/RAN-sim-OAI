"""ANR / E2 Node Information 查詢端點(RC_E2NODEINFO_QUERY 落地).

M0:CU 端 HTTP 觀測 API,回 E2SM-RC §9.3.38 格式的 neighbourCellRelations,
讓 xApp 拉得到 NRT。之後 M1 才經 E2SM-ANR/adapter 對 RIC。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.business.anr_seeder import (
    nr_arfcn_from_ghz,
    seed_from_cells,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _relation_to_ie(r: NrCellRelation) -> dict:
    """NrCellRelation → E2SM-RC §9.3.38 neighbourCellRelation IE(+卷面延伸)。"""
    return {
        "sourceCellNcgi": r.source_cell_id,
        "targetCellGlobalId": r.target_cgi,
        "targetPhysicalCellId": r.target_pci,
        "targetArfcn": r.target_arfcn,
        "targetRadioAccessTechnology": r.target_rat,
        # 卷面延伸(管理面視圖)
        "isHoAllowed": r.is_ho_allowed,
        "isRemoveAllowed": r.is_remove_allowed,
        "isXnAllowed": r.is_xn_allowed,
        # §9.3.38 正式
        "xnX2Established": r.xn_x2_established,
        "hoValidated": r.ho_validated,
        "version": r.version,
        # 旗標(封而不刪)
        "flags": {
            "hoBlocklist": r.ho_blocklist,
            "noRemove": r.no_remove,
            "xnBlocklist": r.xn_blocklist,
        },
    }


class AnrQueryActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def node_info(request):
        """RC_E2NODEINFO_QUERY(cellId) → {servingCells, neighbourCellRelations}.

        Body(可選):{cell_id}。給了就只回該 source cell 的關係,否則回全部。
        關係表為空時自動種子(冪等,防禦性)。
        """
        cell_id = None
        if request.body:
            try:
                cell_id = (json.loads(request.body) or {}).get("cell_id")
            except json.JSONDecodeError as e:
                return error_response("invalid JSON", str(e), status=400)

        if not NrCellRelation.objects.exists():
            seed_from_cells()

        cells_qs = CellConfig.objects.filter(is_active=True)
        if cell_id:
            cells_qs = cells_qs.filter(cell_id=cell_id)
        serving = [
            {
                "ncgi": c.cell_id,
                "physicalCellId": c.pci,
                "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
                "radioAccessTechnology": "NR",
            }
            for c in cells_qs
        ]

        rel_qs = NrCellRelation.objects.all()
        if cell_id:
            rel_qs = rel_qs.filter(source_cell_id=cell_id)
        relations = [_relation_to_ie(r) for r in rel_qs]

        return success_response({
            "servingCells": serving,
            "neighbourCellRelations": relations,
        }, "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def reseed(request):
        """手動(重)種子 NRT + CGI 解析。"""
        stats = seed_from_cells()
        return success_response(stats, "ANR seeded")
