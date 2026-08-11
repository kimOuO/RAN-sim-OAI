"""ANR SON 觸發控制(E2SM-ANR ADD/REMOVE/FLAG)落地.

對應 xApp 命令(ANR情境_v8.docx §貳C):
  SONTRIG_ANR_ADD_REQUEST    → requestType=ADD    → 新增/更新鄰區關係
  SONTRIG_ANR_REMOVE_REQUEST → requestType=REMOVE → 移除鄰區關係(保護條目拒絕)
  SONTRIG_ANR_FLAG_REQUEST   → requestType=FLAG   → set/clear hoBlocklist/noRemove/xnBlocklist

共通語意:非同步請求、gNB 保留裁量;生效以 version 變化 / 條目出現消失判定(confirm 慣用式)。
每次成功變更 version+1。REMOVE 命中 is_remove_allowed=False 或 no_remove=True → 拒絕(保護條目,
應升 SMO_NOTIFY;此處回 rejected 讓 xApp 處置)。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

_VALID_FLAGS = {"hoBlocklist": "ho_blocklist",
                "noRemove": "no_remove",
                "xnBlocklist": "xn_blocklist"}


def _outcome(request_type: str, source: str, target: str, result: str,
             version: int | None = None, detail: str = "") -> dict:
    return {"requestType": request_type, "sourceCellId": source,
            "targetCgi": target, "result": result,
            "version": version, "detail": detail}


def apply_son_trigger(req: dict) -> dict:
    """套用單筆 SON 觸發請求 → NrCellRelation。回傳 outcome dict。"""
    now = TimestampService.now()
    rtype = req.get("requestType")
    source = req.get("sourceCellId")

    if rtype == "ADD":
        tgt = req.get("target") or {}
        cgi = tgt.get("cgi")
        rel, created = NrCellRelation.objects.get_or_create(
            source_cell_id=source, target_cgi=cgi,
            defaults={
                "target_pci": tgt.get("pci") or 0,
                "target_arfcn": tgt.get("arfcn") or 0,
                "target_rat": tgt.get("rat", "NR"),
                "target_plmn": tgt.get("plmn", ""),
                "is_ho_allowed": True, "is_remove_allowed": True, "is_xn_allowed": True,
                "xn_x2_established": False, "ho_validated": False, "version": 1,
                "ho_blocklist": False, "no_remove": False, "xn_blocklist": False,
                "created_at": now, "updated_at": now,
            },
        )
        if not created:
            # 已存在 → 更新目標識別 + 補齊(冪等,不動 flag)
            if tgt.get("pci") is not None:
                rel.target_pci = tgt["pci"]
            if tgt.get("arfcn") is not None:
                rel.target_arfcn = tgt["arfcn"]
            rel.version += 1
            rel.updated_at = now
            rel.save(update_fields=["target_pci", "target_arfcn", "version", "updated_at"])
        logger.info("ANR ADD: %s → %s (%s, v%d)", source, cgi,
                    "created" if created else "updated", rel.version)
        return _outcome("ADD", source, cgi,
                        "ADDED" if created else "UPDATED", rel.version)

    if rtype == "REMOVE":
        cgi = req.get("targetCgi")
        rel = NrCellRelation.objects.filter(source_cell_id=source, target_cgi=cgi).first()
        if rel is None:
            return _outcome("REMOVE", source, cgi, "NOT_FOUND")
        if not rel.is_remove_allowed or rel.no_remove:
            logger.warning("ANR REMOVE rejected (protected): %s → %s", source, cgi)
            return _outcome("REMOVE", source, cgi, "REJECTED_PROTECTED",
                            rel.version, "is_remove_allowed=False or no_remove=True → SMO_NOTIFY")
        rel.delete()
        logger.info("ANR REMOVE: %s → %s (reason=%s)", source, cgi, req.get("reason", ""))
        return _outcome("REMOVE", source, cgi, "REMOVED")

    if rtype == "FLAG":
        cgi = req.get("targetCgi")
        field = _VALID_FLAGS.get(req.get("flag"))
        op = req.get("op")
        rel = NrCellRelation.objects.filter(source_cell_id=source, target_cgi=cgi).first()
        if rel is None:
            return _outcome("FLAG", source, cgi, "NOT_FOUND")
        setattr(rel, field, (op == "set"))
        rel.version += 1
        rel.updated_at = now
        rel.save(update_fields=[field, "version", "updated_at"])
        logger.info("ANR FLAG: %s → %s %s=%s (v%d)", source, cgi, req.get("flag"),
                    op == "set", rel.version)
        return _outcome("FLAG", source, cgi, f"FLAG_{op.upper()}", rel.version,
                        f"{req.get('flag')}={op == 'set'}")

    return _outcome(str(rtype), source, req.get("targetCgi", ""), "UNSUPPORTED")


class AnrControlActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def control(request):
        """adapter → CU:E2SM-ANR SON 觸發。
        Body: {sim_action:'anr_son_trigger', request:{requestType, sourceCellId, ...}}
              或直接 {requestType, sourceCellId, ...}
        """
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("invalid JSON", str(e), status=400)

        req = body.get("request") or body
        if not req.get("requestType") or not req.get("sourceCellId"):
            return error_response("requestType + sourceCellId required", status=400)

        outcome = apply_son_trigger(req)
        ok = outcome["result"] not in ("NOT_FOUND", "UNSUPPORTED")
        return success_response(outcome, "ANR SON trigger applied" if ok else outcome["result"])
