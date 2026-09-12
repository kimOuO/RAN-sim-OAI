"""per-MCS 的 SINR → BLER —— 直接複用現役 PHY 層的 BLER 來源,非 fudge。

舊版(Phase 0 初期)用亂猜的 sigmoid(_SINR_AT_BLER50 = -6 + mcs),operating point
落在 ~50% BLER → retx 爆 → delay 灌水。已棄用。

現在直接呼叫 ldpc_abstract.estimate_bler():它先查 SIM_BLER_CURVE_PATH 的
bler_curve.csv(mcs,sinr_db,bler 三欄,線性插值),沒有該 MCS 就用內建
_MCS_SINR_REQUIRED_DB(真實每-MCS 需求 SINR)的 erfc 公式 fallback。

★ 這是全 DU 共用的物理 ground-truth(現役 LDPC abstraction 也用同一條),
  一條曲線跨所有 phase,retx 自然變對、delay 自己長對 —— 不是 /30 那種輸出後處理。
"""
from __future__ import annotations

from main.apps.phy_high.services.optional.coding.ldpc_abstract import estimate_bler


def bler(mcs: int, sinr_db: float) -> float:
    """回傳該 MCS 在此 SINR 的首傳 BLER (0..1) —— 複用 PHY 層 bler_curve.csv + 物理 fallback。"""
    return estimate_bler(sinr_db, mcs)
