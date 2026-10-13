"""RRC Re-establishment 決策 — P1-2(2026-08-12)。

DU 通報 RLF → CU 決定重建落點與結果,對齊 3GPP TS 38.331 §5.3.7:
  1. 落點 = DU 報的最強鄰 cell(strongest_cell / strongest_rsrp)。
  2. 最強 cell RSRP < REESTAB_MIN_RSRP → 無處可去 → DROP(掉話)。
  3. 落點是本網受控 cell:
     - source→target 有 NrCellRelation 且 xnX2Established → 可經 Xn 取 UE context
       → REESTAB_WITH_CTX(快速路徑,保 session)。
     - 否則 → REESTAB_WITHOUT_CTX(context 不可得,退回完整建立)。
  4. 落點非受控 cell → 也算 WITHOUT_CTX(視同陌生 cell 完整接入)。

**ANR 關鍵**:缺漏鄰區時 source→target 沒有 relation → WITHOUT_CTX,且落點記
previous_pci = source pci → 這就是 reestablishmentInboundByPreviousPci 的證據鏈。

計數(對齊 pm 欄位 / ANR 卷):
  RLF.DetectedRate            = RlfEvent 總數 / 時間
  DropWithoutReestablishment  = outcome=DROP 數
  ReEstabSuccWithUeContext    = REESTAB_WITH_CTX 數
  ReEstabSuccWithoutUeContext = REESTAB_WITHOUT_CTX 數
"""
from __future__ import annotations

from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.models.rlf_event import RlfEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.utils.env_loader import get_float
from main.utils.logger import get_logger
from main.apps.cu_cp.services.optional import scene_clock

logger = get_logger(__name__)

# 重建可行的最低 RSRP — 低於此視為無 cell 可接入 → DROP(掉話)
_REESTAB_MIN_RSRP = get_float("REESTAB_MIN_RSRP_DBM", -120.0)



def _select_suitable(ue_id: str, du_best: str, du_best_rsrp: float) -> tuple[str, float]:
    """挑合格重建落點(TS 38.331 suitable cell):排除 barred / 未啟用 cell。

    DU 只送最強一個。若它合格就直接用;不合格才回頭查該 UE 最近的鄰區量測,
    依 RSRP 由強到弱挑第一個合格者。都不合格 → 回空字串(caller 判 DROP)。
    """
    def _ok(cid: str) -> bool:
        c = CellConfig.objects.filter(cell_id=cid).first()
        if c is None:
            # 多 gNB:鄰 gNB 的 cell(Xn Setup 交換來的)也可以是重建落點
            from main.apps.cu_cp.services.business import xn
            f = xn.foreign_cell(cid)
            return bool(f and f.is_active and not f.is_barred)
        from main.apps.cu_cp.services.common.fixture_state import admission_blocked
        return bool(c.is_active and not admission_blocked(c.cell_id, c.is_barred))

    if du_best and _ok(du_best):
        return du_best, du_best_rsrp

    try:
        from main.apps.cu_cp.models.measurement_log import MeasurementLog
        m = (MeasurementLog.objects.filter(ue_id=ue_id)
             .order_by("-recorded_at").only("neighbor_cells_json").first())
        cands = sorted((m.neighbor_cells_json or []) if m else [],
                       key=lambda n: float(n.get("rsrp_dbm", -999.0)), reverse=True)
        for n in cands:
            cid = n.get("cell_id") or ""
            if cid and _ok(cid):
                logger.info("[REESTAB] ue=%s strongest=%s 不合格(barred/inactive)→ 改選 %s",
                            ue_id, du_best or "none", cid)
                return cid, float(n.get("rsrp_dbm", -140.0))
    except Exception:
        logger.exception("suitable-cell 選擇失敗,回退 DU 最強")
        return du_best, du_best_rsrp

    logger.info("[REESTAB] ue=%s 無合格落點(strongest=%s barred/inactive)", ue_id, du_best or "none")
    return "", -140.0


def handle_rlf(report: dict[str, Any]) -> dict[str, Any]:
    """處理一筆 DU RLF 通報 → 落 RlfEvent + 執行重建決策。回傳 outcome dict。"""
    now = TimestampService.now()
    ue_id = report.get("ue_id", "")
    source_cell = report.get("serving_cell", "")
    source_pci = int(report.get("serving_pci", -1))
    strongest = report.get("strongest_cell", "") or ""
    strongest_rsrp = float(report.get("strongest_rsrp", -140.0))

    evt = SqlDbBusinessService.create_entity(RlfEvent, {
        "ue_id": ue_id,
        "source_cell": source_cell,
        "source_pci": source_pci,
        "sinr_at_rlf": float(report.get("sinr_at_rlf", 0.0)),
        "t310_ms": float(report.get("t310_ms", 0.0)),
        "reason": report.get("reason", "T310_EXPIRY"),
        "outcome": "DECLARED",
        "detected_at": now,
        # DU 報告自己帶的時間優先(開場的 RLF 早於第一份量測報告,CU 那時還沒有時鐘)
        "scene_sim_ms": report.get("scene_sim_ms") or scene_clock.now_ms(),
    })

    ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)

    # ── 決策 ──────────────────────────────────────────────────────
    # TS 38.331:重建須選 **suitable cell**,而不是單純的「最強」。
    # DU 只回報最強一個;若它不合格(barred / inactive),CU 用該 UE 最近一次量測
    # 的鄰區清單挑次佳者 —— 這樣「量得到但不收 UE」的鄰居才不會把 UE 吸走。
    strongest, strongest_rsrp = _select_suitable(ue_id, strongest, strongest_rsrp)
    target = CellConfig.objects.filter(cell_id=strongest).first() if strongest else None

    # 多 gNB P6:落點在鄰 gNB → 由對端 gNB 做重建(Retrieve UE Context 取不取得到由 Xn 與關係決定)
    if target is None and strongest and strongest_rsrp >= _REESTAB_MIN_RSRP:
        from main.apps.cu_cp.services.business import xn
        f = xn.foreign_cell(strongest)
        if f is not None:
            outcome = _reestablish_at_peer(ue, report, evt, f, strongest_rsrp, source_cell, source_pci, now)
            _mro_report(ue, source_cell, strongest)
            return outcome

    if not strongest or strongest_rsrp < _REESTAB_MIN_RSRP or target is None:
        # 無處可去 → 掉話
        outcome = "DROP"
        if ue is not None:
            # A(2026-08-12):掉話 = 釋放,session 存活秒數落帳
            try:
                from main.apps.cu_cp.services.business.cell_counters import add_session_time
                add_session_time(source_cell, (now - ue.created_at).total_seconds())
            except Exception:
                logger.exception("session-time on RLF drop failed")
            SqlDbBusinessService.update_entity(
                UeContext, "ue_id", ue_id,
                {"rrc_state": "IDLE", "serving_cell": "", "updated_at": now})
        logger.warning("[REESTAB] ue=%s DROP (strongest=%s rsrp=%.1f < %.1f)",
                       ue_id, strongest or "none", strongest_rsrp, _REESTAB_MIN_RSRP)
    else:
        # 有落點 — 判 with/without context(source→target 是否有 Xn 關係)
        rel = NrCellRelation.objects.filter(
            source_cell_id=source_cell, target_cgi=target.cell_id).first()
        # 也接受用 target NCGI hex 對(seeder 用 hex)
        if rel is None and target.nr_cellid:
            rel = NrCellRelation.objects.filter(
                source_cell_id=source_cell,
                target_cgi=f"{int(target.nr_cellid):015x}").first()
        # 同一個 gNB 內重建:UE context 就在本 CU,一定取得到(多 gNB 改版,計畫 4.2)。
        # 跨 gNB 才要經 Xn Retrieve UE Context,那時才看關係與 Xn 是否建立。
        _src_gnb = CellConfig.objects.filter(cell_id=source_cell).values_list("gnb_id", flat=True).first() or ""
        same_gnb = bool(_src_gnb) and _src_gnb == (target.gnb_id or "")
        has_ctx = same_gnb or bool(rel and rel.xn_x2_established)
        outcome = "REESTAB_WITH_CTX" if has_ctx else "REESTAB_WITHOUT_CTX"
        from main.apps.cu_cp.services.business.du_client_operations import du_of_ue
        src_du = du_of_ue(ue_id)
        tgt_du = target.served_by_du_id
        if ue is not None:
            SqlDbBusinessService.update_entity(
                UeContext, "ue_id", ue_id,
                {"rrc_state": "CONNECTED", "serving_cell": target.cell_id,
                 "gnb_du_id": tgt_du, "updated_at": now})
        # P1-2 修補(2026-08-12):重建成功 → 把 UE 用新 serving_cell 註冊回 DU tick
        # 迴圈,並重置該 UE 的 RLF 狀態。否則 UE 掉出量測、後續走過凹陷不再觸發 RLF
        # (掉話 UE 永久沉默,ES 懲罰信號只算一次)。真實:重建後 UE 在新 cell 上活著。
        try:
            from main.apps.cu_cp.services.business.du_client_operations import (
                DuClientBusinessService,
            )
            if src_du is not None and tgt_du is not None and src_du != tgt_du:
                # 重建到同 gNB 的另一個 DU:目標 DU 建 UE context(含 DRB),來源 DU 釋放
                from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
                prof = (ue.traffic_profile_json if ue is not None else None) or {}
                drbs = [] if (prof.get("pattern") or "idle") == "idle" else [{
                    "drb_id": int(prof.get("bearer_id", 1) or 1),
                    "qos_5qi": int(prof.get("qos_5qi", 9) or 9), "rlc_mode": "AM"}]
                DuClientBusinessService.post_ue_context_setup(
                    F1apHandler.build_ue_context_setup(ue_id, drbs, serving_cell_id=target.cell_id),
                    gnb_du_id=tgt_du)
                DuClientBusinessService.post_ue_context_release({"ue_id": ue_id, "cause": "rlf"}, gnb_du_id=src_du)
            else:
                DuClientBusinessService.post_register_ue(
                    ue_id, target.cell_id,
                    sinr_db=15.0, rsrp_dbm=float(strongest_rsrp))
            from main.apps.cu_cp.services.business import ue_notify
            ue_notify.path_update(ue_id, target.cell_id)
        except Exception:
            logger.exception("re-register UE to DU after reestab failed: %s", ue_id)
        logger.info("[REESTAB] ue=%s %s → %s (%s, prevPci=%d, rel=%s)",
                    ue_id, source_cell, target.cell_id,
                    "WITH_CTX" if has_ctx else "WITHOUT_CTX", source_pci,
                    "yes" if rel else "MISSING")

    if outcome != "DROP" and target is not None:
        _mro_report(ue, source_cell, target.cell_id)
    SqlDbBusinessService.update_entity(
        RlfEvent, "id", evt.id,
        {"outcome": outcome,
         "reestab_cell": target.cell_id if (target and outcome != "DROP") else "",
         "reestab_pci": target.pci if (target and outcome != "DROP") else -1,
         "resolved_at": now})

    return {
        "ue_id": ue_id, "source_cell": source_cell, "source_pci": source_pci,
        "outcome": outcome,
        "reestab_cell": target.cell_id if (target and outcome != "DROP") else "",
        "strongest_rsrp": strongest_rsrp,
    }


def _reestablish_at_peer(ue, report, evt, foreign, rsrp: float, source_cell: str, source_pci: int, now) -> dict[str, Any]:
    """UE 在鄰 gNB 的 cell 重建(TS 38.331 §5.3.7 + TS 38.423 Retrieve UE Context)。

    取得回 context 的條件與同 gNB 時的舊語意一致:source→target 有關係且 xnX2Established,
    再加上兩個 gNB 之間的 Xn 確實已建立。取得回 → REESTAB_WITH_CTX(Path Switch 接續 NG 關聯);
    取不回 → REESTAB_WITHOUT_CTX(對端走完整接入)。對端拒收 → DROP。
    """
    from main.apps.cu_cp.services.business import xn
    from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
    ue_id = report.get("ue_id", "")
    rel = NrCellRelation.objects.filter(source_cell_id=source_cell, target_cgi=foreign.cell_id).first()
    with_ctx = bool(rel and rel.xn_x2_established and not rel.xn_blocklist) and xn.xn_available(foreign.gnb_id)
    me = xn.self_gnb()
    outcome, reestab_cell, reestab_pci = "DROP", "", -1
    try:
        xn._post(xn.peer_url_for_gnb(foreign.gnb_id), "rrc_reestablishment", {
            "ue_id": ue_id, "source_gnb_id": me.gnb_id if me else None, "source_cell": source_cell,
            "source_pci": source_pci, "target_cell": foreign.cell_id, "with_ctx": with_ctx,
            "ue_context": {"traffic_profile": (ue.traffic_profile_json if ue is not None else None) or {},
                           "amf_ue_ngap_id": int(ue.amf_ue_ngap_id or 0) if ue is not None else None}})
        outcome = "REESTAB_WITH_CTX" if with_ctx else "REESTAB_WITHOUT_CTX"
        reestab_cell, reestab_pci = foreign.cell_id, foreign.pci
    except Exception as exc:  # noqa: BLE001
        logger.warning("[REESTAB] ue=%s → 鄰 gNB 0x%06x %s 失敗,判掉話: %s", ue_id, foreign.gnb_id, foreign.cell_id, exc)
    if ue is not None:
        # UE 已不在本 gNB:釋放來源 DU 的 context(RLF 時 DU 已停排程,這裡清 MAC/RLC)
        DuClientBusinessService.post_ue_context_release({"ue_id": ue_id, "cause": "rlf"}, gnb_du_id=ue.gnb_du_id)
        if outcome == "DROP":
            SqlDbBusinessService.update_entity(UeContext, "ue_id", ue_id, {"rrc_state": "IDLE", "serving_cell": "", "updated_at": now})
        else:
            UeContext.objects.filter(ue_id=ue_id).delete()
    logger.info("[REESTAB] ue=%s %s → %s @gNB 0x%06x (%s, prevPci=%d, rel=%s)", ue_id, source_cell, foreign.cell_id,
                foreign.gnb_id, outcome, source_pci, "yes" if rel else "MISSING")
    SqlDbBusinessService.update_entity(RlfEvent, "id", evt.id, {
        "outcome": outcome, "reestab_cell": reestab_cell, "reestab_pci": reestab_pci, "resolved_at": now})
    return {"ue_id": ue_id, "source_cell": source_cell, "source_pci": source_pci, "outcome": outcome,
            "reestab_cell": reestab_cell, "strongest_rsrp": rsrp, "reestab_gnb": foreign.gnb_id}


def _mro_report(ue, rlf_cell: str, reestab_cell: str) -> None:
    """跨 gNB MRO(TS 38.423 Handover Report):UE 經 Xn / NG 從鄰 gNB 換進來,T_SHORT 內就 RLF ——
    重建回原來源 cell = TooEarly,重建到第三個 cell = ToWrongCell;報給來源 gNB 回填它那筆換手事件。
    同 gNB 內的歸因仍由 mro.py 以本地事件推導。"""
    if ue is None or not ue.last_ho_source_gnb or not ue.last_ho_uuid or ue.last_ho_at is None:
        return
    from main.apps.cu_cp.services.business import mro, xn
    if (TimestampService.now() - ue.last_ho_at).total_seconds() > mro._T_SHORT_SEC:
        return
    if reestab_cell == rlf_cell:
        return   # 接回目標自己:覆蓋問題,不是行動性時序(與 mro._classify_one 相同)
    kind = "TooEarly" if reestab_cell == ue.last_ho_source_cell else "ToWrongCell"
    try:
        xn._post(xn.peer_url_for_gnb(int(ue.last_ho_source_gnb)), "handover_report",
                 {"ho_uuid": ue.last_ho_uuid, "ue_id": ue.ue_id, "type": kind, "rlf_cell": rlf_cell, "reestab_cell": reestab_cell})
        logger.info("Xn Handover Report → gNB 0x%06x: ue=%s %s", int(ue.last_ho_source_gnb), ue.ue_id, kind)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Xn Handover Report failed: %s", exc)
