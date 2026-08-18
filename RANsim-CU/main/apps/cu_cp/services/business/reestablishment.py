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
        return bool(c and c.is_active and not c.is_barred)

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
    })

    ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)

    # ── 決策 ──────────────────────────────────────────────────────
    # TS 38.331:重建須選 **suitable cell**,而不是單純的「最強」。
    # DU 只回報最強一個;若它不合格(barred / inactive),CU 用該 UE 最近一次量測
    # 的鄰區清單挑次佳者 —— 這樣「量得到但不收 UE」的鄰居才不會把 UE 吸走。
    strongest, strongest_rsrp = _select_suitable(ue_id, strongest, strongest_rsrp)
    target = CellConfig.objects.filter(cell_id=strongest).first() if strongest else None

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
        has_ctx = bool(rel and rel.xn_x2_established)
        outcome = "REESTAB_WITH_CTX" if has_ctx else "REESTAB_WITHOUT_CTX"
        if ue is not None:
            SqlDbBusinessService.update_entity(
                UeContext, "ue_id", ue_id,
                {"rrc_state": "CONNECTED", "serving_cell": target.cell_id,
                 "updated_at": now})
        # P1-2 修補(2026-08-12):重建成功 → 把 UE 用新 serving_cell 註冊回 DU tick
        # 迴圈,並重置該 UE 的 RLF 狀態。否則 UE 掉出量測、後續走過凹陷不再觸發 RLF
        # (掉話 UE 永久沉默,ES 懲罰信號只算一次)。真實:重建後 UE 在新 cell 上活著。
        try:
            from main.apps.cu_cp.services.business.du_client_operations import (
                DuClientBusinessService,
            )
            DuClientBusinessService.post_register_ue(
                ue_id, target.cell_id,
                sinr_db=15.0, rsrp_dbm=float(strongest_rsrp))
        except Exception:
            logger.exception("re-register UE to DU after reestab failed: %s", ue_id)
        logger.info("[REESTAB] ue=%s %s → %s (%s, prevPci=%d, rel=%s)",
                    ue_id, source_cell, target.cell_id,
                    "WITH_CTX" if has_ctx else "WITHOUT_CTX", source_pci,
                    "yes" if rel else "MISSING")

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
