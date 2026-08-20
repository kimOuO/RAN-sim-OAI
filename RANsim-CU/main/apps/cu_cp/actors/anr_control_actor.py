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


def _record_change(action: str, source: str, target: str, detail: str = "",
                   by: str = "xapp") -> None:
    """P0-5:成功變更 NRT 落審計事件(9.3.38 relationChangeEvents 資料源)。"""
    try:
        from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
        NrRelationChangeEvent.objects.create(
            action=action, source_cell_id=source or "", target_cgi=target or "",
            by=by, detail=detail[:128], at=TimestampService.now(),
        )
    except Exception:  # 審計失敗不影響主流程
        logger.exception("record relation change event failed")




def _schedule_xn_setup(source: str, target_cgi: str) -> None:
    """延遲觸發 Xn Setup(XnAP Setup Request/Response 非瞬時,秒級)。

    不可同步阻塞 —— RIC Control ACK 有 ~5s 逾時,ADD 必須立刻回 ACK。
    故以背景 timer 執行;xApp 觀測 `xnX2Established` 會看到 false → true 的轉換。
    延遲秒數 env `ANR_XN_SETUP_DELAY_SEC`(預設 2.0)。
    """
    import threading
    from main.utils.env_loader import get_bool, get_float
    if not get_bool("ANR_XN_AUTO_REVERSE", default=True):
        return
    delay = max(0.0, get_float("ANR_XN_SETUP_DELAY_SEC", 2.0))

    def _run() -> None:
        from django.db import close_old_connections
        try:
            close_old_connections()   # timer 執行緒不可沿用主執行緒連線
            _establish_xn_reverse(source, target_cgi, TimestampService.now())
        except Exception:
            logger.exception("Xn setup (delayed) failed: %s → %s", source, target_cgi)
        finally:
            close_old_connections()

    logger.info("Xn Setup scheduled: %s ↔ %s in %.1fs (XnAP step 4c)", source, target_cgi, delay)
    t = threading.Timer(delay, _run)
    t.daemon = True
    t.start()

def _establish_xn_reverse(source: str, target_cgi: str, now) -> None:
    """gNB 側 Xn 建立 → 反向鄰區關係自動成立(TS 38.300 §15.3.3.2 步驟 4c + TS 38.423)。

    卷面紅線:xApp **禁止替對端寫反向關係**,反向由 Xn 交換產生。因此正向 ADD 落地後,
    由 sim 代表 gNB 自行建立反向關係並標 xnX2Established —— 否則 UE 換進新 cell 後
    無關係可換回,會滯留到 RLF(第4題乾淨驗測實測到的殘留 RLF 即此因)。

    由 `_schedule_xn_setup()` 延遲呼叫(XnAP Setup 非瞬時)。
    env `ANR_XN_AUTO_REVERSE`=off 可停用(保留舊行為)。
    """
    from main.utils.env_loader import get_bool
    if not get_bool("ANR_XN_AUTO_REVERSE", default=True):
        return
    from main.apps.cu_cp.models.cell_config import CellConfig
    # 反向來源必須是本 sim 註冊過的 cell(跨域對端無法代建)
    peer = CellConfig.objects.filter(cell_id=target_cgi).first()
    src_cell = CellConfig.objects.filter(cell_id=source).first()
    if peer is None or src_cell is None:
        return
    # 容量檢查:gNB 自建的反向關係同樣受 NRT 上限約束,否則會把對端推爆上限
    # (第9題重驗實測:n62 因反向關係變成 9/8)。超限就不建 —— 真實 gNB 也建不了。
    from main.utils.env_loader import get_int as _gi2
    _cap2 = _gi2("ANR_NRT_CAPACITY", 32)
    if (not NrCellRelation.objects.filter(source_cell_id=target_cgi, target_cgi=source).exists()
            and NrCellRelation.objects.filter(source_cell_id=target_cgi).count() >= _cap2):
        logger.warning("Xn reverse skipped: %s NRT capacity reached (%d/%d)",
                       target_cgi, NrCellRelation.objects.filter(source_cell_id=target_cgi).count(), _cap2)
        _record_change("ADD_REJECTED", target_cgi, source, "NRT_CAPACITY_REACHED", by="gnb-xn")
        return
    from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
    rev, rev_created = NrCellRelation.objects.get_or_create(
        source_cell_id=target_cgi, target_cgi=source,
        defaults={
            "target_pci": src_cell.pci or 0,
            "target_arfcn": nr_arfcn_from_ghz(src_cell.frequency_ghz),
            "target_rat": "NR", "target_plmn": "",
            "is_ho_allowed": True, "is_remove_allowed": True, "is_xn_allowed": True,
            "xn_x2_established": True, "ho_validated": False, "version": 1,
            "ho_blocklist": False, "no_remove": False, "xn_blocklist": False,
            "created_at": now, "updated_at": now,
        },
    )
    # 正向也標記 Xn 已建立
    NrCellRelation.objects.filter(source_cell_id=source, target_cgi=target_cgi).update(
        xn_x2_established=True, updated_at=now)
    if rev_created:
        logger.info("Xn established → reverse relation auto-created: %s → %s (gNB step 4c)",
                    target_cgi, source)
        _record_change("ADD", target_cgi, source, "xn-reverse(step4c)", by="gnb-xn")

def apply_son_trigger(req: dict) -> dict:
    """套用單筆 SON 觸發請求 → NrCellRelation。回傳 outcome dict。"""
    now = TimestampService.now()
    rtype = req.get("requestType")
    source = req.get("sourceCellId")

    if rtype == "ADD":
        tgt = req.get("target") or {}
        cgi = tgt.get("cgi")
        # 卷面前置檢查:ANR 自動建立功能之部署組態。停用時 gNB 不得自動寫入 NRT,
        # xApp 只能通報管理面(SMO_NOTIFY)。停用 != 禁止改 NRT(REMOVE/FLAG 不受此限)。
        from main.utils.env_loader import get_bool as _gb
        if not _gb("ANR_INTRA_ENABLED", default=True):
            logger.warning("ANR ADD rejected: ANR_INTRA_ENABLED=false (自動建立功能停用)")
            return _outcome("ADD", source, cgi, "REJECTED_ANR_DISABLED", None,
                            "ANR_INTRA_ENABLED=false → 交管理面/人工建立(SMO_NOTIFY)")
        # 卷面第9題:NRT 每 cell 容量上限。滿載時新增條目被拒,並落一筆可觀測的
        # ADD_REJECTED / NRT_CAPACITY_REACHED 事件 —— xApp 據此判定「阻斷點在容量」
        # (偵測機制正常),進而修剪低價值條目後重試。既有條目的更新不受限。
        from main.utils.env_loader import get_int as _gi
        _cap = _gi("ANR_NRT_CAPACITY", 32)
        _used = NrCellRelation.objects.filter(source_cell_id=source).count()
        _exists = NrCellRelation.objects.filter(source_cell_id=source, target_cgi=cgi).exists()
        if not _exists and _used >= _cap:
            logger.warning("ANR ADD rejected: NRT capacity reached %s (%d/%d)", source, _used, _cap)
            _record_change("ADD_REJECTED", source, cgi, "NRT_CAPACITY_REACHED")
            return _outcome("ADD", source, cgi, "ADD_REJECTED", None,
                            "NRT_CAPACITY_REACHED (used=%d limit=%d)" % (_used, _cap))
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
        _record_change("ADD", source, cgi, "created" if created else "updated")
        if created:
            # cellBarred 語意是「尚未納入網路,UE 不得駐留」。ANR 一旦為它建立鄰區關係
            # (且 gNB 隨後建 Xn),該 cell 就已納入網路 —— 此時仍 barred 會造成矛盾:
            # UE 換得進去(連線態換手不歸 barred 管)卻不能在那裡重建,RLF 後必被判
            # ToWrongCell,backfill 再把那筆成功換手改寫成 FAIL/HandoverToWrongCell,
            # 於是「剛修好的關係」立刻看起來像有害鄰居(交叉測試輪3 實測)。
            from main.apps.cu_cp.models.cell_config import CellConfig as _CC2
            if _CC2.objects.filter(cell_id=cgi, is_barred=True).update(is_barred=False):
                logger.info("cellBarred cleared on %s — ANR 關係建立後即納入網路", cgi)
            _schedule_xn_setup(source, cgi)
        return _outcome("ADD", source, cgi,
                        "ADDED" if created else "UPDATED", rel.version)

    if rtype == "REMOVE":
        cgi = req.get("targetCgi")
        rel = NrCellRelation.objects.filter(source_cell_id=source, target_cgi=cgi).first()
        if rel is None:
            return _outcome("REMOVE", source, cgi, "NOT_FOUND")
        if not rel.is_remove_allowed or rel.no_remove:
            logger.warning("ANR REMOVE rejected (protected): %s → %s", source, cgi)
            # 被拒也要落審計 —— 與 ADD_REJECTED 對稱。少了這筆,「送了但被擋」
            # 在稽核面上與「根本沒送」無法區分;若 xApp 那端又不檢查 outcome 的
            # result,一筆被拒的 REMOVE 會在兩邊同時隱形(RIC 2026-08-20 於
            # Q11 拒絕路徑實測時指出他們 REMOVE 側有同款的洞)。
            _record_change("REMOVE_REJECTED", source, cgi, "PROTECTED_ENTRY")
            return _outcome("REMOVE", source, cgi, "REJECTED_PROTECTED",
                            rel.version, "is_remove_allowed=False or no_remove=True → SMO_NOTIFY")
        rel.delete()
        logger.info("ANR REMOVE: %s → %s (reason=%s)", source, cgi, req.get("reason", ""))
        _record_change("REMOVE", source, cgi, str(req.get("reason", ""))[:100])
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
        _record_change("FLAG", source, cgi, f"{req.get('flag')}={op == 'set'}")
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
