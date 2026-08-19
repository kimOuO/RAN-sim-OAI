"""MRO 歸因引擎 — P2-1(2026-08-12)。

Mobility Robustness Optimization:把每個 RLF 事件依「與最近一次 HO 的時序關係」
歸因為三類換手病態(對齊 3GPP TS 28.552 §5.1.1.25.1 語意 + TS 38.300 MRO):

  TooEarly   — HO 完成後 T_SHORT 內就 RLF,且**重建回 source cell**。
               「太早切走 → 目標訊號不夠 → 掉回原 cell」。offset 過小 / hysteresis 不足。
  ToWrongCell— HO 完成後 T_SHORT 內 RLF,但**重建進第三個 cell**(非 source 非 target)。
               「切錯家 → 該去的是別人」。鄰區 RSRP 交錯 + 錯誤 offset。
  TooLate    — RLF 發生時**近期無 HO**,且重建進**非原 serving 的 cell**。
               「早該切沒切 → 撐到掉線才被動接到別人」。TTT 過長 / offset 過大。

純推導:輸入全是既有真實事件(RlfEvent 落點 + HandoverEvent 時間線),不新增量測。
歸因結果回填 RlfEvent.mro 語意(此處算速率;可選同步回填 HandoverEvent.mro_class)。

速率化(對齊卷面 HO.IntraSys.*Rate):每分鐘各類事件數。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.rlf_event import RlfEvent
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_float

# HO 後多久內的 RLF 算「與該 HO 相關」(TooEarly/ToWrongCell 的時間窗)
_T_SHORT_SEC = get_float("MRO_T_SHORT_SEC", 5.0)
_DEFAULT_WINDOW_MIN = 10.0


def _classify_one(rlf: RlfEvent, recent_ho: HandoverEvent | None) -> str | None:
    """單一 RLF → MRO 類別(或 None = 無法歸因,不計入 SON.*)。"""
    reestab = rlf.reestab_cell
    if rlf.outcome == "DROP" or not reestab:
        return None  # 掉話無落點,不做 MRO 歸因(反映於 RLF.Drop,不是 MRO)

    if recent_ho is not None:
        # 近期有 HO(在 T_SHORT 內完成)→ TooEarly 或 ToWrongCell
        if reestab == recent_ho.source_cell:
            return "TooEarly"      # 掉回原 cell
        if reestab != recent_ho.target_cell:
            return "ToWrongCell"   # 進了第三 cell
        # 2026-08-19:重建回 **target 自己** → 不做 MRO 歸因。
        # TS 28.313 的 TooEarly 定義是「換手後 RLF 且 UE **退回 source cell**」;
        # 接回 target 表示換手目標選對了,只是在該 cell 發生無線失效 ——
        # 那是覆蓋/無線問題,不是行動性時序錯誤。
        # 原本把它當「TooEarly 邊界」硬歸,是 TooEarly 虛高的主要來源
        # (交叉測試輪2:src_c0 64 筆中有 45 筆屬此類),會讓「MRO 平坦」
        # 這條排除條件在有無線失效的場景永遠不成立。
        return None

    # 近期無 HO → 重建進非原 serving = 該切沒切
    if reestab != rlf.source_cell:
        return "TooLate"
    return None


def mro_kpm(window_min: float = _DEFAULT_WINDOW_MIN, *, backfill: bool = True) -> dict[str, Any]:
    """對齊卷面 HO.IntraSys.{TooEarly,TooLate,ToWrongCell}Rate(cell 級 + 全網)。"""
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    active = set(CellConfig.objects.values_list("cell_id", flat=True))

    rlfs = list(RlfEvent.objects.filter(detected_at__gte=win_start).order_by("detected_at"))
    # 每個 UE 的 HO 時間線(找 RLF 前最近一次已完成的 HO)
    hos = list(
        # 2026-08-19:只有**成功完成**的換手才能構成 MRO 歸因基礎(TS 28.313)。
        # TooEarly/ToWrongCell 的定義都是「HO 完成後短時間內 RLF」;準備階段就失敗的換手
        # (TXnRELOCprepExpiry / CellNotAvailable / RandomAccessProblem)語意上不可能是
        # 「太早」或「切錯」—— 它們有自己的 handoverFailureCause。
        # 不濾會讓「換手失敗型」疾病(第6/7/10題)自我污染 MRO,使「MRO 平坦」這條
        # 排除條件永遠不成立,正確診斷出不來(RIC 於第6題實測指出)。
        HandoverEvent.objects.filter(status="SUCC",
                                     started_at__gte=win_start - timedelta(seconds=_T_SHORT_SEC))
        .order_by("started_at")
    )
    ho_by_ue: dict[str, list[HandoverEvent]] = {}
    for h in hos:
        ho_by_ue.setdefault(h.ue_id, []).append(h)

    # 2026-08-19(交叉測試輪2 發現):只濾成功換手還不夠。
    # 若 RLF 之前**更接近**的行動事件是一次「失敗的換手嘗試」,那次 RLF 的肇因是該失敗
    # (它有自己的 handoverFailureCause),不該歸給更早、不相干的成功換手。
    # 不處理的話:換手失敗型疾病(第6/7/10題)造成的 RLF 會被算到同 cell 上正常的
    # 換手循環頭上 → TooEarly 虛高 → 「MRO 平坦」這條排除條件永遠不成立 →
    # 病越嚴重越修不了(交叉測試輪2 實測 harmful 被自家 MRO 閘門鎖死半小時)。
    fails = list(
        HandoverEvent.objects.filter(status="FAIL",
                                     started_at__gte=win_start - timedelta(seconds=_T_SHORT_SEC))
        .exclude(failure_cause="")
        .order_by("started_at")
    )
    fail_by_ue: dict[str, list[HandoverEvent]] = {}
    for h in fails:
        fail_by_ue.setdefault(h.ue_id, []).append(h)

    # per-cell(以 RLF 的 source_cell 計)counters
    counters: dict[str, dict[str, int]] = {}
    totals = {"TooEarly": 0, "TooLate": 0, "ToWrongCell": 0}

    for r in rlfs:
        # 找該 UE 在 RLF 前 T_SHORT 內完成的最近 HO
        recent = None
        for h in ho_by_ue.get(r.ue_id, []):
            dt = (r.detected_at - h.started_at).total_seconds()
            if 0 <= dt <= _T_SHORT_SEC:
                recent = h  # 取最後一個符合的(最接近 RLF)
        # 更近的失敗嘗試 → 該 RLF 歸因於那次失敗,不做 MRO 歸因
        recent_fail = None
        for h in fail_by_ue.get(r.ue_id, []):
            dt = (r.detected_at - h.started_at).total_seconds()
            if 0 <= dt <= _T_SHORT_SEC:
                recent_fail = h
        if recent_fail is not None and (
                recent is None or recent_fail.started_at >= recent.started_at):
            continue  # 肇因是換手失敗(有自己的 failureCause),非 MRO
        cls = _classify_one(r, recent)
        if cls:
            src = r.source_cell if r.source_cell in active else "_other"
            d = counters.setdefault(src, {"TooEarly": 0, "TooLate": 0, "ToWrongCell": 0})
            d[cls] += 1
            totals[cls] += 1
            if backfill and recent is not None and recent.mro_class != cls:
                recent.mro_class = cls
                if cls == "ToWrongCell":
                    recent.failure_cause = recent.failure_cause or "HandoverToWrongCell"
                    recent.status = "FAIL"
                recent.save(update_fields=["mro_class", "failure_cause", "status"])

    def _r(n: int) -> float:
        return round(n / max(window_min, 1e-9), 3)

    return {
        "windowMin": window_min,
        "tShortSec": _T_SHORT_SEC,
        "cellLevel": {
            cell: {
                "HO.IntraSys.TooEarlyRate": _r(d["TooEarly"]),
                "HO.IntraSys.TooLateRate": _r(d["TooLate"]),
                "HO.IntraSys.ToWrongCellRate": _r(d["ToWrongCell"]),
            } for cell, d in counters.items()
        },
        "total": {
            "HO.IntraSys.TooEarlyRate": _r(totals["TooEarly"]),
            "HO.IntraSys.TooLateRate": _r(totals["TooLate"]),
            "HO.IntraSys.ToWrongCellRate": _r(totals["ToWrongCell"]),
        },
    }
