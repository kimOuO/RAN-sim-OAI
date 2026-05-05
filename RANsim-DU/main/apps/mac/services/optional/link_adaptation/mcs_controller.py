"""MCS Controller — OAI `get_mcs_from_bler()` 等價,BLER 閉環 AMC。

OAI 邏輯 (gNB_scheduler_primitives.c):
  - 50ms 滾動窗 BLER
  - BLER > upper (0.15) → MCS -= 1
  - BLER < lower (0.05) → MCS += 1

我們無真 LDPC,用 3GPP AWGN BLER 曲線估:
  BLER ≈ Q((SINR - SINR_req[MCS]) / σ)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from main.utils.logger import get_logger

logger = get_logger(__name__)


# 3GPP AWGN 各 MCS 的 10% BLER SINR 門檻 (dB)。
_MCS_SINR_REQUIRED_DB = [
    -7.0, -5.0, -3.0, -1.0,  1.0,  3.0,  5.0,  7.0,
     9.0, 11.0, 13.0, 14.5, 16.0, 17.5, 19.0, 20.0,
    20.8, 21.5, 22.2, 22.9, 23.6, 24.3, 25.0, 25.7,
    26.5, 27.2, 28.0, 28.8,
]

SIGMA_DB = 1.5
BLER_UPPER = 0.15
BLER_LOWER = 0.05
WINDOW_MS = 50
INITIAL_MCS = 9
MAX_MCS = 27


def estimate_bler(sinr_db: float, mcs: int) -> float:
    if mcs < 0 or mcs >= len(_MCS_SINR_REQUIRED_DB):
        return 1.0
    margin = sinr_db - _MCS_SINR_REQUIRED_DB[mcs]
    q = 0.5 * math.erfc(margin / (SIGMA_DB * math.sqrt(2)))
    return max(0.0, min(1.0, q))


@dataclass
class _UeMcsState:
    mcs: int = INITIAL_MCS
    bler_window: list[tuple[int, float]] = field(default_factory=list)
    rounds: list[float] = field(default_factory=lambda: [0.0] * 8)
    errors: float = 0.0


class MCSController:
    """All-UE closed-loop AMC controller (singleton)。"""

    def __init__(self) -> None:
        self.ue_state: dict[str, _UeMcsState] = {}

    def reset(self) -> None:
        self.ue_state.clear()

    def update(self, ue_id: str, sinr_db: float, tick_ms_now: int) -> tuple[int, float]:
        st = self.ue_state.setdefault(ue_id, _UeMcsState())

        bler = estimate_bler(sinr_db, st.mcs)
        st.bler_window.append((tick_ms_now, bler))
        st.bler_window = [(t, b) for t, b in st.bler_window if tick_ms_now - t <= WINDOW_MS]
        smoothed_bler = sum(b for _, b in st.bler_window) / max(len(st.bler_window), 1)

        if smoothed_bler > BLER_UPPER and st.mcs > 0:
            st.mcs -= 1
        elif smoothed_bler < BLER_LOWER and st.mcs < MAX_MCS:
            margin = sinr_db - _MCS_SINR_REQUIRED_DB[min(st.mcs + 1, MAX_MCS)]
            if margin > -2.0:
                st.mcs += 1

        b = bler
        one_minus_b = 1 - b
        st.rounds[0] += one_minus_b
        st.rounds[1] += one_minus_b * b
        st.rounds[2] += one_minus_b * b * b
        st.rounds[3] += one_minus_b * b * b * b
        st.errors += b ** 4

        return st.mcs, smoothed_bler

    def get_mcs(self, ue_id: str) -> int:
        st = self.ue_state.get(ue_id)
        return st.mcs if st else INITIAL_MCS

    def snapshot(self) -> dict[str, dict]:
        return {
            uid: {"mcs": st.mcs, "rounds": list(st.rounds), "errors": st.errors}
            for uid, st in self.ue_state.items()
        }


_singleton: MCSController | None = None


def get_mcs_controller() -> MCSController:
    global _singleton
    if _singleton is None:
        _singleton = MCSController()
    return _singleton
