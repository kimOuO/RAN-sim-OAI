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

def resolve_cell_ref(ref: str) -> str:
    """xApp 帶來的目標識別 → 平台 cell_id。接受 cell_id 本身,或 D2 格式的 ncgi 字串
    (<PLMN 6 位>-<NCI 9 位十六進位>);ncgi 依 NCI 查本 gNB 的 cell 或 Xn 鄰居的 cell。查不到原樣回。"""
    if not ref:
        return ref
    try:
        from ran_sim_protocol.e2_identity import parse_ncgi
    except ImportError:
        return ref
    parsed = parse_ncgi(ref)
    if parsed is None:
        return ref
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.services.business import xn
    local = CellConfig.objects.filter(nr_cellid=parsed[1]).values_list("cell_id", flat=True).first()
    if local:
        return local
    f = xn.foreign_cell_by_nci(parsed[1])
    return f.cell_id if f is not None else ref


def _cell_ident(cell_id: str):
    """(pci, arfcn, 是否本 gNB)。本 gNB 查 CellConfig,鄰 gNB 查 Xn 外部鄰區表;都沒有回 None。"""
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.services.business import xn
    from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
    c = CellConfig.objects.filter(cell_id=cell_id).first()
    if c is not None:
        return c.pci or 0, nr_arfcn_from_ghz(c.frequency_ghz), True
    f = xn.foreign_cell(cell_id)
    if f is not None:
        return f.pci, f.arfcn, False
    return None


def establish_reverse_local(local_cell: str, peer_cell: str) -> bool:
    """在本 gNB 建反向關係 local_cell → peer_cell(peer_cell 可以是本 gNB 或鄰 gNB 的 cell)。

    gNB 側 Xn 建立 → 反向鄰區關係自動成立(TS 38.300 §15.3.3.2 步驟 4c + TS 38.423)。
    卷面紅線:xApp **禁止替對端寫反向關係**,反向由 Xn 交換產生。回傳是否新建。
    """
    from main.utils.env_loader import get_bool as _gbx
    from main.apps.cu_cp.models.cell_config import CellConfig
    if not _gbx("ANR_XN_AUTO_REVERSE", default=True):
        return False
    if not CellConfig.objects.filter(cell_id=local_cell).exists():
        return False
    ident = _cell_ident(peer_cell)
    if ident is None:
        return False
    # ANR_XN_REVERSE=off:劇本可暫停 gNB Xn 反向自建(Q5 owned 唯一性保護 ——
    # 對方 missing 的 ADD 本身不破 owned,是本反向 +2s 補出 mid→west 才破;
    # 2026-08-28 Q5 二輪實錄,B4 fail-closed 靠考點先落袋才沒事)。預設開。
    if not _gbx("ANR_XN_REVERSE", default=True):
        logger.info("Xn reverse suppressed by scenario (ANR_XN_REVERSE=off): %s→%s", local_cell, peer_cell)
        return False
    # 容量檢查:gNB 自建的反向關係同樣受 NRT 上限約束,否則會把對端推爆上限
    # (第9題重驗實測:n62 因反向關係變成 9/8)。超限就不建 —— 真實 gNB 也建不了。
    from main.utils.env_loader import get_int as _gi2
    _cap2 = _gi2("ANR_NRT_CAPACITY", 32)
    if (not NrCellRelation.objects.filter(source_cell_id=local_cell, target_cgi=peer_cell).exists()
            and NrCellRelation.objects.filter(source_cell_id=local_cell).count() >= _cap2):
        logger.warning("Xn reverse skipped: %s NRT capacity reached (%d/%d)",
                       local_cell, NrCellRelation.objects.filter(source_cell_id=local_cell).count(), _cap2)
        _record_change("ADD_REJECTED", local_cell, peer_cell, "NRT_CAPACITY_REACHED", by="gnb-xn")
        return False
    now = TimestampService.now()
    pci, arfcn, _ = ident
    rev, rev_created = NrCellRelation.objects.get_or_create(
        source_cell_id=local_cell, target_cgi=peer_cell,
        defaults={
            "target_pci": pci, "target_arfcn": arfcn,
            "target_rat": "NR", "target_plmn": "",
            "is_ho_allowed": True, "is_remove_allowed": True, "is_xn_allowed": True,
            "xn_x2_established": True, "ho_validated": False, "version": 1,
            "ho_blocklist": False, "no_remove": False, "xn_blocklist": False,
            "created_at": now, "updated_at": now,
        },
    )
    if rev_created:
        logger.info("Xn established → reverse relation auto-created: %s → %s (gNB step 4c)", local_cell, peer_cell)
        _record_change("ADD", local_cell, peer_cell, "xn-reverse(step4c)", by="gnb-xn")
    return rev_created


def _establish_xn_reverse(source: str, target_cgi: str, now) -> None:
    """正向 ADD 落地後(延遲)做的事:正向標 xnX2Established、反向關係由「目標 cell 所屬的 gNB」建。

    目標是本 gNB 的 cell → 本地直接建反向(與改版前相同);
    目標是鄰 gNB 的 cell → 經 Xn 請對端 CU 自己建(本端不代寫對端的 NRT)。
    由 `_schedule_xn_setup()` 延遲呼叫(XnAP Setup 非瞬時)。env `ANR_XN_AUTO_REVERSE`=off 可停用。
    """
    from main.utils.env_loader import get_bool
    if not get_bool("ANR_XN_AUTO_REVERSE", default=True):
        return
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.services.business import xn
    if not CellConfig.objects.filter(cell_id=source).exists():
        return
    f = xn.foreign_cell(target_cgi)
    if f is not None:
        if not xn.xn_available(f.gnb_id):
            logger.info("Xn to gNB 0x%06x not established — %s → %s 維持 xnX2Established=false", f.gnb_id, source, target_cgi)
            return
        try:
            xn._post(xn.peer_url_for_gnb(f.gnb_id), "anr_reverse", {"source_cell": source, "target_cell": target_cgi})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Xn anr_reverse → gNB 0x%06x failed: %s", f.gnb_id, exc)
            return
    elif CellConfig.objects.filter(cell_id=target_cgi).exists():
        establish_reverse_local(target_cgi, source)
    else:
        return
    # 正向也標記 Xn 已建立
    NrCellRelation.objects.filter(source_cell_id=source, target_cgi=target_cgi).update(
        xn_x2_established=True, updated_at=now)


def apply_son_trigger(req: dict) -> dict:
    """套用單筆 SON 觸發請求 → NrCellRelation。回傳 outcome dict。"""
    now = TimestampService.now()
    rtype = req.get("requestType")
    source = req.get("sourceCellId")
    # 目標可以是 cell_id 或 ncgi 字串(D2 格式),一律換成平台 cell_id
    if req.get("targetCgi"):
        req = {**req, "targetCgi": resolve_cell_ref(str(req["targetCgi"]))}
    if (req.get("target") or {}).get("cgi"):
        req = {**req, "target": {**req["target"], "cgi": resolve_cell_ref(str(req["target"]["cgi"]))}}
    # 2026-09-23:source cell 一定要是這顆 gNB 的 cell。以前不驗,RIC 自測用掃錯的假名
    # (gnbDT_c0>gnbDT_c1)下 anr-add 也被回 ADDED —— 對不存在的 cell 建了關係,還回成功。
    from main.apps.cu_cp.models.cell_config import CellConfig as _CC
    if source and not _CC.objects.filter(cell_id=source).exists():
        logger.warning("ANR %s rejected: source cell %s 不存在", rtype, source)
        return _outcome(str(rtype), source, req.get("targetCgi") or (req.get("target") or {}).get("cgi") or "",
                        "NOT_FOUND", None, "source cell 不在本 gNB")
    if rtype == "ADD":
        _tcgi = (req.get("target") or {}).get("cgi")
        # 目標可在本 gNB,或是 Xn 鄰居 gNB 的 cell(C11 跨 gNB ANR)
        if _tcgi and _cell_ident(_tcgi) is None:
            logger.warning("ANR ADD rejected: target %s 不存在", _tcgi)
            return _outcome("ADD", source, _tcgi, "NOT_FOUND", None, "target cell 不在本 gNB,也不在 Xn 鄰居的 served cells")

    if rtype == "ADD":
        tgt = dict(req.get("target") or {})
        # 2026-09-23:xApp / Agent 的 ADD 常只帶 cgi。以前 pci/arfcn 缺就寫 0,
        # 但 E2 上鄰區改以 (pci, arfcn) 查 NRT 解 ncgi,寫 0 的關係永遠解不出來 ——
        # 等於「加了關係卻沒效」。目標是本 gNB 的 cell 時直接用它的設定補齊。
        _tid = _cell_ident(tgt.get("cgi")) if tgt.get("cgi") else None
        if _tid is not None:
            if tgt.get("pci") is None:
                tgt["pci"] = _tid[0]
            if tgt.get("arfcn") is None:
                tgt["arfcn"] = _tid[1]
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
        # 動作名直接帶 set/clear,並在 detail 放旗標名 —— xApp 重啟後要能只靠
        # relationChangeEvents 重建「我設過哪些旗標」。v10 旗標不可觀測之後,
        # 這是唯一的真相來源;記成同一個 "FLAG" 會讓 set 與 clear 分不出來
        # (RIC 2026-08-25 §4.1 的孤兒旗標問題)。
        _record_change(f"FLAG_{op.upper()}", source, cgi, str(req.get("flag") or ""))
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
