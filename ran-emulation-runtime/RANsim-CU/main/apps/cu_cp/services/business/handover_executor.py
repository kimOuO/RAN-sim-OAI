"""F1-based handover executor — 共用給 SessionController / E2 control / A3 auto trigger。

對齊 OAI: openair2/RRC/NR/rrc_gNB_mobility.c::nr_rrc_trigger_f1_ho()
F1-based handover: source CU → F1AP UE Context Modification → DU 換 cell；不經 AMF（intra-CU）。
"""
from __future__ import annotations

from typing import Any

from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.omniverse_push import push_handover_event
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.utils.logger import get_logger
from main.apps.cu_cp.services.optional import scene_clock


logger = get_logger(__name__)


def execute_f1_handover(
    *, ue_id: str, target_cell: str, trigger: str = "MANUAL",
    target_rsrp: float | None = None,
) -> dict[str, Any] | None:
    """Run F1-based handover for ue_id → target_cell.

    Reusable by:
      • SessionControllerActor.handover (trigger="MANUAL")
      • E2ControlActor._handle_handover (trigger="E2_RIC_CONTROL")
      • F1ApRouterActor.measurement_report A3 auto trigger (trigger="A3_TTT")

    Returns dict with ho_uuid/source/target on success, None if UE not found
    or target_cell does not exist in CellConfig (defensive guard against phantom
    cell names — e.g., Sionna scene gNB labels leaking through neighbor list).
    """
    ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
    if ue is None:
        return None
    # 換到自己身上不是換手,不該留下換手事件。
    # 2026-08-27 中性場煙霧測試前抓到:UE 已經駐留在該 cell 時仍被要求 MANUAL 換手
    # (佈場與維持條件都會無條件下指令),留下一批 source==target、卡在 PREP 的事件,
    # 於是觀測面出現一條 h1_c0→h1_c0「關係」,成功率 0.0 —— 在 xApp 眼裡
    # 那就是一條有害鄰居。病是我方自己造的,而且會出現在每一個中性場。
    if ue.serving_cell == target_cell:
        logger.debug("execute_f1_handover skipped: ue=%s 已在 %s", ue_id, target_cell)
        return None

    # 防呆: target_cell 必須是 sim 註冊過的 CellConfig.cell_id, 否則 reject 不下 F1AP.
    # 之前曾經看 RU 把 Sionna scene gNB 名 (e.g., gNB_Macro_NW) leak 進 neighbors,
    # A3 評到後 trigger HO 把 UE.serving_cell 寫成 phantom, 整條 traffic pipeline 卡死.
    from main.apps.cu_cp.models.cell_config import CellConfig
    if not CellConfig.objects.filter(cell_id=target_cell).exists():
        # 多 gNB P6:目標是 Xn 鄰居 gNB 的 cell → 跨 gNB 換手(Xn,或沒有 Xn 時 NG)
        from main.apps.cu_cp.services.business import xn as _xn
        _f = _xn.foreign_cell(target_cell)
        if _f is not None:
            return execute_inter_gnb_handover(ue=ue, foreign=_f, trigger=trigger, target_rsrp=target_rsrp)
        logger.warning(
            "execute_f1_handover refused: target_cell=%r not in CellConfig (phantom?). "
            "ue=%s trigger=%s — keeping current serving_cell=%s",
            target_cell, ue_id, trigger, ue.serving_cell,
        )
        return None
    source_cell = ue.serving_cell or ""
    if source_cell == target_cell:
        # 已在 target，不重複 trigger
        return {"ho_uuid": "", "ue_id": ue_id, "source_cell": source_cell, "target_cell": target_cell, "skipped": True}

    now = TimestampService.now()
    ho_uuid = UUIDService.random_uuid()

    # P2-2(2026-08-12):HO 失敗原因判定(依平台真實狀態,不合成)。
    #   CellNotAvailable    — target cell is_active=false(CCC cell off)
    #   RandomAccessProblem — target RSRP < 接入門檻(caller 有帶量測時才判)
    from main.apps.cu_cp.models.cell_config import CellConfig as _CC
    from main.utils.env_loader import get_float as _gf, get_str as _gs
    _RA_MIN_RSRP = _gf("HO_RA_MIN_RSRP_DBM", -115.0)
    fail_cause = ""
    tgt = _CC.objects.filter(cell_id=target_cell).first()
    if tgt is not None and not tgt.is_active:
        fail_cause = "CellNotAvailable"
    # barred cell 不得作為換手目標(TS 38.304 §5.3.1:barred = 不准接入,
    # 對 IDLE 選網與 CONNECTED 換手一體適用)。
    # 2026-08-29 Q3 對接輪抓到:barred 原本只擋選網/重建,沒擋換手 ——
    # RIC ADD 補上關係後,A3 立刻把五台 UE 全部換進 barred 的 n91,
    # 深邊緣場景當場瓦解,hoValidated 還翻真、可能連帶觸發對方的行為類告警。
    elif tgt is not None and __import__("main.apps.cu_cp.services.common.fixture_state",
            fromlist=["admission_blocked"]).admission_blocked(tgt.cell_id, getattr(tgt, "is_barred", False)):
        fail_cause = "CellNotAvailable"
        logger.info("HO target %s is barred → CellNotAvailable(擋在執行端)", target_cell)
    elif target_rsrp is not None and float(target_rsrp) < _RA_MIN_RSRP:
        fail_cause = "RandomAccessProblem"
    # Xn 相關的判定只適用跨 gNB 的換手(多 gNB 改版,計畫 4.2):同一個 gNB 內的 cell
    # 之間走 F1,與 Xn 是否建立、是否被 blocklist 無關。cell 的 gnb_id = registry gNB 名稱。
    _src_gnb = _CC.objects.filter(cell_id=source_cell).values_list("gnb_id", flat=True).first() or ""
    _cross_gnb = bool(tgt is not None and _src_gnb and tgt.gnb_id and tgt.gnb_id != _src_gnb)
    # ANR 第6題 Xn-C TNL 探索失敗:關係存在但 Xn 傳輸從未建立(xnX2Established=false)
    #   → 換手準備逾時 TXnRELOCprepExpiry(TS 38.423)。這是物理正確的:沒有 Xn 傳輸
    #   就無法送 Handover Request,準備階段必然逾時。xApp 不得自動修 —— Xn 建立屬管理面。
    if not fail_cause and _cross_gnb:
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as _R0
        _rel0 = _R0.objects.filter(source_cell_id=source_cell, target_cgi=target_cell).first()
        if _rel0 is not None and not _rel0.xn_x2_established:
            fail_cause = "TXnRELOCprepExpiry"
            logger.info("HO Xn-not-established: %s→%s xnX2Established=False → TXnRELOCprepExpiry",
                        source_cell, target_cell)

    # v10 第6題:xnBlocklist = Xn 換手路徑被禁用(TS 28.313 §6.4.1.3.7,不拆線)。
    # A3 已會跳過,但 RC 直接下令仍會走到這裡 —— 路徑禁用時準備階段必然逾時。
    if not fail_cause and _cross_gnb:
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as _RX
        _relx = _RX.objects.filter(source_cell_id=source_cell, target_cgi=target_cell).first()
        if _relx is not None and _relx.xn_blocklist:
            fail_cause = "TXnRELOCprepExpiry"
            logger.info("HO xnBlocklist: %s→%s Xn 換手路徑已禁用 → TXnRELOCprepExpiry",
                        source_cell, target_cell)

    # ANR 第10題 過期對應(stale PCI mapping):relation 存的 target_pci 與 cell 實際 pci 不符
    #   → 依組態(舊 PCI)尋找目標而不獲 → CellNotAvailable。同站換 PCI 後未更新關係即此症。
    #   xApp 處置=先刪後建(REMOVE 舊 + ADD 新 pci)。env ANR_STALE_PCI_CHECK=off 可停用。
    if not fail_cause and tgt is not None and _gs("ANR_STALE_PCI_CHECK", "on") != "off":
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as _R
        rel = _R.objects.filter(source_cell_id=source_cell, target_cgi=target_cell).first()
        if (rel is not None and rel.target_pci is not None
                and tgt.pci is not None and int(rel.target_pci) != int(tgt.pci)):
            fail_cause = "CellNotAvailable"
            logger.info("HO stale-PCI: rel %s→%s target_pci=%s ≠ cell.pci=%s → CellNotAvailable",
                        source_cell, target_cell, rel.target_pci, tgt.pci)
    # ANR Case#2 有害鄰區注入:指定 target cell 的 HO 一律失敗(模擬「訊號看似 OK
    # 但接入失敗」的有害鄰居 —— sim 的 RSRP 模型做不出,靠此旗標忠實重現第7題)。
    # env HO_FORCE_FAIL_TARGET="nbr_c0" 或 "cell_a,cell_b";cause 由 HO_FORCE_FAIL_CAUSE 定(預設 RandomAccessProblem)。
    if not fail_cause:
        _force = {t.strip() for t in (_gs("HO_FORCE_FAIL_TARGET", "") or "").split(",") if t.strip()}
        _cause = _gs("HO_FORCE_FAIL_CAUSE", "RandomAccessProblem") or "RandomAccessProblem"
        # 熱開關(2026-08-25 第 7 題 L4 staging):env 改動要重啟 CU,而中場重啟
        # 會殺 UE 量測流(坑7)且打斷 xApp L4 探測計時 —— 改讀 bind-mount 檔案,
        # 每次換手評估時讀,寫檔即生效。格式:每行 "target[,cause]";空檔/無檔=不注入。
        try:
            with open("/app/tmp/ho_force_fail.txt") as _f:
                for _ln in _f:
                    _ln = _ln.strip()
                    if not _ln or _ln.startswith("#"):
                        continue
                    _parts = [x.strip() for x in _ln.split(",")]
                    _force.add(_parts[0])
                    if len(_parts) > 1 and _parts[1]:
                        _cause = _parts[1]
        except FileNotFoundError:
            pass
        if target_cell in _force:
            fail_cause = _cause

    if fail_cause:
        SqlDbBusinessService.create_entity(HandoverEvent, {
            "ho_uuid": ho_uuid, "ue_id": ue_id,
            "source_cell": source_cell, "target_cell": target_cell,
            "trigger": trigger, "status": "FAIL", "failure_cause": fail_cause,
            "started_at": now, "completed_at": now,
            "scene_sim_ms": scene_clock.now_ms(), **_ho_fields(ue, source_cell, target_cell),
        })
        logger.warning("F1 Handover FAILED [%s]: UE %s %s → %s cause=%s",
                       trigger, ue_id, source_cell, target_cell, fail_cause)
        # 失敗不改 serving_cell(UE 留原 cell,後續可能觸發 RLF)
        return {"ho_uuid": ho_uuid, "ue_id": ue_id, "source_cell": source_cell,
                "target_cell": target_cell, "failed": True, "failure_cause": fail_cause}

    # ── F1 執行(TS 38.401 §8.2.1):同 DU 用 UE Context Modification 換 cell;
    #    同 gNB 跨 DU 先在目標 DU 建 UE context(帶 SpCell 與 DRB),成功後釋放來源 DU 的 context。
    from main.apps.cu_cp.services.business.du_client_operations import du_of_cell, du_of_ue
    src_du, tgt_du = du_of_ue(ue_id), du_of_cell(target_cell)
    inter_du = src_du is not None and tgt_du is not None and src_du != tgt_du
    ho_type = "inter-DU" if inter_du else "intra-DU"
    if inter_du:
        prof = ue.traffic_profile_json or {}
        drbs = [] if (prof.get("pattern") or "idle") == "idle" else [{
            "drb_id": int(prof.get("bearer_id", 1) or 1),
            "qos_5qi": int(prof.get("qos_5qi", 9) or 9), "rlc_mode": "AM"}]
        setup = DuClientBusinessService.post_ue_context_setup(
            F1apHandler.build_ue_context_setup(ue_id, drbs, rrc_msg_b64="", serving_cell_id=target_cell),
            gnb_du_id=tgt_du)
        from main.apps.cu_cp.services.business.du_client_operations import du_ok
        if not du_ok(setup):
            SqlDbBusinessService.create_entity(HandoverEvent, {
                "ho_uuid": ho_uuid, "ue_id": ue_id, "source_cell": source_cell, "target_cell": target_cell,
                "trigger": trigger, "status": "FAIL", "failure_cause": "UeContextSetupFailure", "ho_type": ho_type,
                "started_at": now, "completed_at": now, "scene_sim_ms": scene_clock.now_ms()})
            logger.warning("inter-DU HO FAILED [%s]: UE %s %s → %s,目標 DU#%s UE Context Setup 失敗: %s",
                           trigger, ue_id, source_cell, target_cell, tgt_du, setup)
            return {"ho_uuid": ho_uuid, "ue_id": ue_id, "source_cell": source_cell,
                    "target_cell": target_cell, "failed": True, "failure_cause": "UeContextSetupFailure"}
        DuClientBusinessService.post_ue_context_release({"ue_id": ue_id, "cause": "handover"}, gnb_du_id=src_du)
    else:
        try:
            DuClientBusinessService.post_ue_context_modification(
                F1apHandler.build_ue_context_modification(ue_id, target_cell),
            )
        except Exception as e:
            logger.warning("F1AP UE Context Modification push failed: %s", e)
    SqlDbBusinessService.update_entity(
        UeContext, "ue_id", ue_id,
        {"serving_cell": target_cell, "gnb_du_id": tgt_du if tgt_du is not None else ue.gnb_du_id, "updated_at": now},
    )
    from main.apps.cu_cp.services.business import ue_notify
    ue_notify.path_update(ue_id, target_cell)

    SqlDbBusinessService.create_entity(HandoverEvent, {
        "ho_uuid": ho_uuid,
        "ue_id": ue_id,
        "source_cell": source_cell,
        "target_cell": target_cell,
        "trigger": trigger,
        "status": "SUCC",
        "ho_type": ho_type,
        "started_at": now,
        "completed_at": now,
        "scene_sim_ms": scene_clock.now_ms(),
        **_ho_fields(ue, source_cell, target_cell),
    })
    # 2026-08-26(RIC 第三十七輪):換手成功 = 該鄰區關係已驗證(TS 38.300 §15.3.3;
    # E2SM-RC §9.3.38 hoValidated)。此前全網恆 false,第 12 題的鑑別線是死的,
    # 導致每條新生關係都被稽核分支指控成「無據封鎖」(今日 68 筆假陽性)。
    #   · 單向:只設正向,反向由對端 gNB 自行驗證(同 Xn 反向自建原則)
    #   · 持久:True 不再翻回 false —— 它是歷史事實不是即時狀態;關係刪除重建才歸零
    #   · 不計 MANUAL —— 理由是**語意**而非測試環境(2026-08-27 RIC 第六十三輪更正):
    #     MANUAL 換手成功其實也證明這條路可用,所以「污染 fixture」不是正確理由。
    #     正確理由是 hoValidated 服務第 12 題的封鎖推論,而那個推論問的是
    #     「有沒有人**想去**卻去不成」—— 屬於「使用者要不要」的問題,佈場搬 UE 不算需求。
    #     分界線(對兩邊都適用):判準問「使用者要不要」→ MANUAL 是雜訊;
    #                             判準問「這條路通不通」→ MANUAL 是有效實驗
    #                             (第 6 題 Xn 恢復、第 7 題探測都採計 MANUAL)。
    #     理由寫錯會讓下一個人在別的地方套錯,所以結論不變但理由必須改。
    if trigger != "MANUAL":
        try:
            from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as _R
            _R.objects.filter(source_cell_id=source_cell, target_cgi=target_cell,
                              ho_validated=False).update(ho_validated=True, updated_at=now)
        except Exception:
            logger.exception("mark hoValidated failed %s→%s", source_cell, target_cell)
    logger.info("F1 Handover [%s/%s]: UE %s  %s → %s  (ho_uuid=%s)",
                trigger, ho_type, ue_id, source_cell, target_cell, ho_uuid[:8])
    # 2026-05-17 #1: fire-and-forget 推給 Omniverse,playback 能把 HO 切回 frame_ts
    push_handover_event(
        ho_uuid=ho_uuid,
        ue_id=ue_id,
        source_cell=source_cell,
        target_cell=target_cell,
        trigger=trigger,
        status="SUCC",
        event_ts=now.isoformat() if hasattr(now, "isoformat") else None,
    )
    return {
        "ho_uuid": ho_uuid,
        "ue_id": ue_id,
        "source_cell": source_cell,
        "target_cell": target_cell,
        "trigger": trigger,
    }


def _ho_fields(ue, source_cell: str, target_cell: str) -> dict[str, Any]:
    """C14:換手事件帶 AMF UE NGAP ID、兩端 ncgi;RIC 控制觸發的另帶 RIC 請求編號與標籤。"""
    from main.apps.cu_cp.services.business import xn
    from main.apps.cu_cp.services.common import ric_context
    return {"amf_ue_ngap_id": int(ue.amf_ue_ngap_id or 0) or None,
            "source_ncgi": xn.ncgi_of(source_cell), "target_ncgi": xn.ncgi_of(target_cell),
            **ric_context.event_fields()}


def execute_inter_gnb_handover(*, ue, foreign, trigger: str, target_rsrp: float | None = None) -> dict[str, Any]:
    """跨 gNB 換手(多 gNB P6)。

    Xn 可用 → Xn 換手(TS 38.423 §8.2.1):Handover Request → Ack → SN Status Transfer →
              來源 DU 釋放;目標收到 SN Status Transfer 後送 Path Switch 給 AMF、回送 UE Context Release。
    Xn 不可用(對端 Xn 沒建立、關係 xnX2Established=false、xnBlocklist):
      env HO_NG_FALLBACK=on 且有 AMF → NG 換手(TS 38.413 §8.4.1,經 AMF);
      否則換手準備逾時 TXnRELOCprepExpiry(與改版前 ANR 第 6 題語意相同)。
    """
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    from main.apps.cu_cp.services.business import amf_client, xn
    from main.utils.env_loader import get_bool as _gb, get_float as _gf, get_str as _gs
    now = TimestampService.now()
    ho_uuid = UUIDService.random_uuid()
    source_cell = ue.serving_cell or ""
    target_cell = foreign.cell_id
    rel = NrCellRelation.objects.filter(source_cell_id=source_cell, target_cgi=target_cell).first()
    xn_ok = xn.xn_available(foreign.gnb_id) and not (rel is not None and (not rel.xn_x2_established or rel.xn_blocklist))
    via = "Xn" if xn_ok else ("NG" if (_gb("HO_NG_FALLBACK", False) and amf_client.enabled()) else "Xn")

    fail_cause = ""
    if not foreign.is_active or foreign.is_barred:
        fail_cause = "CellNotAvailable"
    elif target_rsrp is not None and float(target_rsrp) < _gf("HO_RA_MIN_RSRP_DBM", -115.0):
        fail_cause = "RandomAccessProblem"
    elif via == "Xn" and not xn_ok:
        fail_cause = "TXnRELOCprepExpiry"   # 沒有 Xn 傳輸就送不出 Handover Request,準備必然逾時
    elif (rel is not None and rel.target_pci is not None and _gs("ANR_STALE_PCI_CHECK", "on") != "off"
          and int(rel.target_pci) != int(foreign.pci)):
        fail_cause = "CellNotAvailable"     # 過期 PCI 對應(ANR 第 10 題)
    if not fail_cause:
        _force = {t.strip() for t in (_gs("HO_FORCE_FAIL_TARGET", "") or "").split(",") if t.strip()}
        if target_cell in _force:
            fail_cause = _gs("HO_FORCE_FAIL_CAUSE", "RandomAccessProblem") or "RandomAccessProblem"

    def _fail(cause: str) -> dict[str, Any]:
        SqlDbBusinessService.create_entity(HandoverEvent, {
            "ho_uuid": ho_uuid, "ue_id": ue.ue_id, "source_cell": source_cell, "target_cell": target_cell,
            "trigger": trigger, "status": "FAIL", "failure_cause": cause, "ho_type": via,
            "started_at": now, "completed_at": now, "scene_sim_ms": scene_clock.now_ms(),
            **_ho_fields(ue, source_cell, target_cell)})
        logger.warning("%s Handover FAILED [%s]: UE %s %s → %s cause=%s", via, trigger, ue.ue_id, source_cell, target_cell, cause)
        return {"ho_uuid": ho_uuid, "ue_id": ue.ue_id, "source_cell": source_cell, "target_cell": target_cell,
                "failed": True, "failure_cause": cause, "ho_type": via}

    if fail_cause:
        return _fail(fail_cause)

    me = xn.self_gnb()
    src_du = ue.gnb_du_id
    ctx = {"traffic_profile": ue.traffic_profile_json or {}}
    if via == "Xn":
        try:
            xn._post(xn.peer_url_for_gnb(foreign.gnb_id), "handover_request", {
                "ue_id": ue.ue_id, "amf_ue_ngap_id": int(ue.amf_ue_ngap_id or 0), "source_gnb_id": me.gnb_id if me else None,
                "source_cell": source_cell, "target_cell": target_cell, "ue_context": ctx, "ho_uuid": ho_uuid, "cause": trigger})
        except xn.XnError as exc:
            return _fail(exc.cause if exc.cause in ("CellNotAvailable", "RadioResourcesNotAvailable") else "HandoverPreparationFailure")
        except Exception:  # noqa: BLE001 — 對端沒回應 = 準備逾時
            return _fail("TXnRELOCprepExpiry")
        try:
            xn._post(xn.peer_url_for_gnb(foreign.gnb_id), "sn_status_transfer",
                     {"ue_id": ue.ue_id, "ho_uuid": ho_uuid, "source_gnb_id": me.gnb_id if me else None})
        except Exception as exc:  # noqa: BLE001
            logger.warning("SN Status Transfer → gNB 0x%06x failed for %s: %s", foreign.gnb_id, ue.ue_id, exc)
        # UE 已離開本 gNB:釋放來源 DU 的 context;本地 context 等對端的 UE Context Release 再刪
        DuClientBusinessService.post_ue_context_release({"ue_id": ue.ue_id, "cause": "handover"}, gnb_du_id=src_du)
        UeContext.objects.filter(ue_id=ue.ue_id).update(rrc_state="RELEASE", serving_cell=target_cell, updated_at=now)
    else:
        try:
            amf_client.post("handover_required", {
                "gnb_id": amf_client.gnb_id(), "ran_ue_ngap_id": int(ue.ran_ue_ngap_id), "amf_ue_ngap_id": int(ue.amf_ue_ngap_id),
                "target_gnb_id": foreign.gnb_id, "target_cell_id": target_cell, "cause": trigger, "ue_state": ctx})
        except Exception as exc:  # noqa: BLE001
            logger.warning("NG Handover preparation failed for %s: %s", ue.ue_id, exc)
            return _fail("HandoverPreparationFailure")
        DuClientBusinessService.post_ue_context_release({"ue_id": ue.ue_id, "cause": "handover"}, gnb_du_id=src_du)
        UeContext.objects.filter(ue_id=ue.ue_id).delete()   # NG 換手:AMF 已把 UE 交給目標,本地 context 釋放

    SqlDbBusinessService.create_entity(HandoverEvent, {
        "ho_uuid": ho_uuid, "ue_id": ue.ue_id, "source_cell": source_cell, "target_cell": target_cell,
        "trigger": trigger, "status": "SUCC", "ho_type": via, "started_at": now, "completed_at": now,
        "scene_sim_ms": scene_clock.now_ms(), **_ho_fields(ue, source_cell, target_cell)})
    if trigger != "MANUAL":   # hoValidated:見 execute_f1_handover 的說明(MANUAL 不採計)
        NrCellRelation.objects.filter(source_cell_id=source_cell, target_cgi=target_cell,
                                      ho_validated=False).update(ho_validated=True, updated_at=now)
    logger.info("%s Handover [%s]: UE %s  %s → %s (gNB 0x%06x, ho_uuid=%s)", via, trigger, ue.ue_id,
                source_cell, target_cell, foreign.gnb_id, ho_uuid[:8])
    push_handover_event(ho_uuid=ho_uuid, ue_id=ue.ue_id, source_cell=source_cell, target_cell=target_cell,
                        trigger=trigger, status="SUCC", event_ts=now.isoformat() if hasattr(now, "isoformat") else None)
    return {"ho_uuid": ho_uuid, "ue_id": ue.ue_id, "source_cell": source_cell, "target_cell": target_cell,
            "trigger": trigger, "ho_type": via}
