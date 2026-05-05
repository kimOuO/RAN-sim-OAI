"""簡化版 4-step Random Access — 不模擬 PRACH preamble,直接用 ue_id 註冊。

對應 OAI: gNB_scheduler_RA.c 的 nr_schedule_RA() 狀態機。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from main.utils.logger import get_logger

logger = get_logger(__name__)


RA_STATES = ("MSG1_DETECTED", "MSG2_SENT", "WAIT_MSG3", "MSG4_SENT", "CONNECTED")


@dataclass
class RaState:
    ue_id: str
    tc_rnti: int
    state: str = "MSG1_DETECTED"
    started_at_ms: int = 0


class RaManager:
    """所有 UE 的 RA 狀態管理(in-memory)。"""

    def __init__(self) -> None:
        self._procs: dict[str, RaState] = {}
        self._next_tc_rnti = 0x4601  # OAI 預設 TC-RNTI 起點

    def reset(self) -> None:
        self._procs.clear()
        self._next_tc_rnti = 0x4601

    def msg1_detected(self, ue_id: str, ts_ms: int) -> RaState:
        if ue_id in self._procs:
            return self._procs[ue_id]
        tc_rnti = self._next_tc_rnti
        self._next_tc_rnti += 1
        st = RaState(ue_id=ue_id, tc_rnti=tc_rnti, state="MSG1_DETECTED", started_at_ms=ts_ms)
        self._procs[ue_id] = st
        logger.info("RA Msg1 detected ue=%s tc_rnti=0x%x", ue_id, tc_rnti)
        return st

    def advance(self, ue_id: str, target: str) -> RaState | None:
        if target not in RA_STATES:
            raise ValueError(f"unknown RA state: {target}")
        st = self._procs.get(ue_id)
        if st is None:
            return None
        st.state = target
        return st

    def finalize(self, ue_id: str) -> None:
        """RA 完成,UE 進入 CONNECTED;從 RA pool 移除。"""
        st = self._procs.pop(ue_id, None)
        if st:
            logger.info("RA finalized ue=%s tc_rnti=0x%x", ue_id, st.tc_rnti)

    def in_progress(self) -> Iterable[RaState]:
        return self._procs.values()


_singleton: RaManager | None = None


def get_ra_manager() -> RaManager:
    global _singleton
    if _singleton is None:
        _singleton = RaManager()
    return _singleton
