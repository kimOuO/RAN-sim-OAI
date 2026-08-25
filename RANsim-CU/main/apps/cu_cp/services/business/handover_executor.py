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
    # 防呆: target_cell 必須是 sim 註冊過的 CellConfig.cell_id, 否則 reject 不下 F1AP.
    # 之前曾經看 RU 把 Sionna scene gNB 名 (e.g., gNB_Macro_NW) leak 進 neighbors,
    # A3 評到後 trigger HO 把 UE.serving_cell 寫成 phantom, 整條 traffic pipeline 卡死.
    from main.apps.cu_cp.models.cell_config import CellConfig
    if not CellConfig.objects.filter(cell_id=target_cell).exists():
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
    elif target_rsrp is not None and float(target_rsrp) < _RA_MIN_RSRP:
        fail_cause = "RandomAccessProblem"
    # ANR 第6題 Xn-C TNL 探索失敗:關係存在但 Xn 傳輸從未建立(xnX2Established=false)
    #   → 換手準備逾時 TXnRELOCprepExpiry(TS 38.423)。這是物理正確的:沒有 Xn 傳輸
    #   就無法送 Handover Request,準備階段必然逾時。xApp 不得自動修 —— Xn 建立屬管理面。
    if not fail_cause:
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as _R0
        _rel0 = _R0.objects.filter(source_cell_id=source_cell, target_cgi=target_cell).first()
        if _rel0 is not None and not _rel0.xn_x2_established:
            fail_cause = "TXnRELOCprepExpiry"
            logger.info("HO Xn-not-established: %s→%s xnX2Established=False → TXnRELOCprepExpiry",
                        source_cell, target_cell)

    # v10 第6題:xnBlocklist = Xn 換手路徑被禁用(TS 28.313 §6.4.1.3.7,不拆線)。
    # A3 已會跳過,但 RC 直接下令仍會走到這裡 —— 路徑禁用時準備階段必然逾時。
    if not fail_cause:
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
        })
        logger.warning("F1 Handover FAILED [%s]: UE %s %s → %s cause=%s",
                       trigger, ue_id, source_cell, target_cell, fail_cause)
        # 失敗不改 serving_cell(UE 留原 cell,後續可能觸發 RLF)
        return {"ho_uuid": ho_uuid, "ue_id": ue_id, "source_cell": source_cell,
                "target_cell": target_cell, "failed": True, "failure_cause": fail_cause}

    SqlDbBusinessService.create_entity(HandoverEvent, {
        "ho_uuid": ho_uuid,
        "ue_id": ue_id,
        "source_cell": source_cell,
        "target_cell": target_cell,
        "trigger": trigger,
        "status": "SUCC",
        "started_at": now,
        "completed_at": now,
    })
    try:
        DuClientBusinessService.post_ue_context_modification(
            F1apHandler.build_ue_context_modification(ue_id, target_cell),
        )
    except Exception as e:
        logger.warning("F1AP UE Context Modification push failed: %s", e)
    SqlDbBusinessService.update_entity(
        UeContext, "ue_id", ue_id,
        {"serving_cell": target_cell, "updated_at": now},
    )
    logger.info("F1 Handover [%s]: UE %s  %s → %s  (ho_uuid=%s)",
                trigger, ue_id, source_cell, target_cell, ho_uuid[:8])
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
