"""下行外迴路鏈路適應 —— OAI ``get_mcs_from_bler()`` 的等價實作。

OAI 原始碼(openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c)
-----------------------------------------------------------------
* ``init_bler_stats``:新 UE 的 MCS = ``dl_min_mcs``,平滑 BLER = (lower + upper) / 2
* ``get_mcs_from_bler``:每 ``BLER_UPDATE_FRAME`` = 10 個 frame(100 ms)更新一次
      bler_window = 本期重傳數 / 本期首傳數
      bler = BLER_FILTER × bler + (1 − BLER_FILTER) × bler_window,BLER_FILTER = 0.9
      bler < lower 且 mcs < max → mcs + 1;bler > upper → mcs − 1;下限 min_mcs
* 門檻預設(openair2/GNB_APP/MACRLC_nr_paramdef.h):
      dl_bler_target_upper = 0.15、dl_bler_target_lower = 0.05、
      dl_min_mcs = 0、dl_max_mcs = 28

本模擬與 OAI 的差異
------------------
* **bler_window 用期望值**:本模擬沒有逐 TB 的 HARQ 解碼結果,改用 OAI AWGN 曲線上
  「目前 MCS、目前 SINR」的首傳 BLER(``bler_curve.bler``)。
* **不做「無排程就降 MCS」**:OAI 在一期內首傳 ≤ 3 次時也會降一階,閒置 UE 的 MCS
  會一路掉到下限。本模擬不跟,因為閒置 UE 的 MCS 仍會出現在 KPM 裡,掉到 0 會誤導分析。
* **時間用模擬時間**:呼叫端傳入 sim-time(ms)。一個 tick(預設 500 ms)內補跑應有
  的更新次數,所以倍速不影響收斂速度。2026-09-26 之前用牆鐘,且每 tick 被呼叫兩次、
  每次都可能動一階,10 倍速下收斂比 1 倍速慢 10 倍。

2026-09-26 之前 BLER 用一張無出處的 erfc 公式估算(``_MCS_SINR_REQUIRED_DB``),
中高階 MCS 比 OAI 曲線悲觀約 10 dB,導致回報的 MCS 與吞吐量系統性偏低;已移除。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from main.apps.mac.services.optional.link_adaptation import bler_curve
from main.utils.env_loader import get_float, get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)

BLER_UPDATE_MS = 100          # OAI BLER_UPDATE_FRAME = 10 frame × 10 ms
BLER_FILTER = 0.9             # OAI BLER_FILTER
# 門檻:registry DU 模板的 target_bler 經編排器注入為 TARGET_BLER,語意是「目標值」(中心)。
# 上下門檻取中心的 1.5 倍與 0.5 倍 —— 即 OAI 預設 0.15 / 0.05 相對其中點 0.1 的比例,
# 所以 target_bler = 0.1(registry「OAI 對齊」模板)時門檻恰為 OAI 預設。
# 2026-09-26 前把 TARGET_BLER 當上門檻、下門檻取其 1/3,該模板實際跑的是 0.1 / 0.033。
# 需要不對稱門檻時可直接設 TARGET_BLER_UPPER / TARGET_BLER_LOWER。
_TARGET = get_float("TARGET_BLER", 0.1)
BLER_UPPER = get_float("TARGET_BLER_UPPER", 1.5 * _TARGET)
BLER_LOWER = get_float("TARGET_BLER_LOWER", 0.5 * _TARGET)
MIN_MCS = get_int("DL_MIN_MCS", 0)
MAX_MCS = min(bler_curve.MAX_MCS, get_int("DL_MAX_MCS", 28))
_MAX_CATCHUP = 100            # 單次呼叫最多補跑的更新期數(防長時間停頓後一次跑太久)


@dataclass
class _UeMcsState:
    mcs: int = MIN_MCS
    bler: float = (BLER_LOWER + BLER_UPPER) / 2.0
    last_update_ms: float | None = None
    # 最近一次推進時,各 100 ms 更新期「期間」實際使用的 MCS(每期結束才調整,所以是調整前的值)
    period_mcs: list[int] = field(default_factory=list)


class MCSController:
    """所有 UE 的外迴路鏈路適應(singleton)。"""

    def __init__(self) -> None:
        self.ue_state: dict[str, _UeMcsState] = {}

    def reset(self) -> None:
        self.ue_state.clear()

    def remove(self, ue_id: str) -> None:
        self.ue_state.pop(ue_id, None)

    def update(self, ue_id: str, sinr_db: float, now_sim_ms: float) -> tuple[int, float]:
        """推進到 now_sim_ms,回 (MCS, 平滑 BLER)。同一時間點重複呼叫不會重複更新。"""
        st = self.ue_state.get(ue_id)
        if st is None:
            st = self.ue_state[ue_id] = _UeMcsState(last_update_ms=float(now_sim_ms))
            st.period_mcs = [st.mcs]
            return st.mcs, st.bler
        elapsed = float(now_sim_ms) - float(st.last_update_ms or 0.0)
        if elapsed < 0:                      # 時鐘重設(場次重啟)→ 重新起算,不倒退
            st.last_update_ms = float(now_sim_ms)
            return st.mcs, st.bler
        n = int(elapsed // BLER_UPDATE_MS)
        if n <= 0:
            if elapsed > 0:   # 不足一期(tick 短於 100 ms):這段時間都用目前的 MCS;同一時間點重複呼叫則保留上次結果
                st.period_mcs = [st.mcs]
            return st.mcs, st.bler
        st.last_update_ms = float(st.last_update_ms) + n * BLER_UPDATE_MS
        st.period_mcs = []
        for _ in range(min(n, _MAX_CATCHUP)):
            st.period_mcs.append(st.mcs)
            window = bler_curve.bler(st.mcs, sinr_db)
            st.bler = BLER_FILTER * st.bler + (1.0 - BLER_FILTER) * window
            if st.bler < BLER_LOWER and st.mcs < MAX_MCS:
                st.mcs += 1
            elif st.bler > BLER_UPPER:
                st.mcs -= 1
            st.mcs = max(MIN_MCS, min(MAX_MCS, st.mcs))
        return st.mcs, st.bler

    def period_mcs(self, ue_id: str) -> list[int]:
        """最近一次 ``update`` 推進過的各更新期所用的 MCS。

        一個 tick(預設 500 ms)內會跑約 5 期。呼叫端計算本 tick 出貨量時應取各期的平均,
        而不是只用 ``update`` 回傳的期末 MCS —— 否則外迴路擺盪到高 BLER 那一階時,
        OAI 只停留 100 ms,這裡會被放大成整個 tick。
        """
        st = self.ue_state.get(ue_id)
        return list(st.period_mcs) if st and st.period_mcs else [self.get_mcs(ue_id)]

    def get_mcs(self, ue_id: str) -> int:
        st = self.ue_state.get(ue_id)
        return st.mcs if st else MIN_MCS

    def get_bler(self, ue_id: str) -> float:
        st = self.ue_state.get(ue_id)
        return st.bler if st else (BLER_LOWER + BLER_UPPER) / 2.0

    def snapshot(self) -> dict[str, dict]:
        return {
            uid: {"mcs": st.mcs, "bler": st.bler}
            for uid, st in self.ue_state.items()
        }


_singleton: MCSController | None = None


def get_mcs_controller() -> MCSController:
    global _singleton
    if _singleton is None:
        _singleton = MCSController()
    return _singleton
