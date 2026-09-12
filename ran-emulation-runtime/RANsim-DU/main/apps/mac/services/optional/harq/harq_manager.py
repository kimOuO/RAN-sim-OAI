"""HARQ Manager — 每 UE 16 個 HARQ process per direction。

State machine (對齊 OAI):
  NEW → (排程 TX) → WAIT_FEEDBACK → (CRC ind) → DONE | RETX → WAIT_FEEDBACK ...

OAI 對應:
  - openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c  (HARQ process pool)
  - feedback list / retrans_dl_harq list 在 NR_UE_sched_ctrl_t
"""
from __future__ import annotations

from dataclasses import dataclass, field

from main.utils.logger import get_logger

logger = get_logger(__name__)

NUM_HARQ_PROCESSES = 16
MAX_RETX = 4


@dataclass
class HarqProcessState:
    pid: int
    direction: str  # "DL" | "UL"
    state: str = "NEW"  # NEW / WAIT_FEEDBACK / RETX / DONE
    retx_count: int = 0
    last_tbs_bytes: int = 0


@dataclass
class _UeHarqPool:
    dl: list[HarqProcessState] = field(default_factory=list)
    ul: list[HarqProcessState] = field(default_factory=list)


class HarqManager:
    """所有 UE 的 HARQ pool;tick runner 使用。"""

    def __init__(self) -> None:
        self._pools: dict[str, _UeHarqPool] = {}

    def reset(self) -> None:
        self._pools.clear()

    def _pool_for(self, ue_id: str) -> _UeHarqPool:
        pool = self._pools.get(ue_id)
        if pool is None:
            pool = _UeHarqPool(
                dl=[HarqProcessState(pid=i, direction="DL") for i in range(NUM_HARQ_PROCESSES)],
                ul=[HarqProcessState(pid=i, direction="UL") for i in range(NUM_HARQ_PROCESSES)],
            )
            self._pools[ue_id] = pool
        return pool

    def add_ue(self, ue_id: str) -> None:
        self._pool_for(ue_id)

    def remove_ue(self, ue_id: str) -> None:
        self._pools.pop(ue_id, None)

    def acquire_process(self, ue_id: str, direction: str, tbs_bytes: int) -> HarqProcessState | None:
        """從 pool 找一個 NEW 或 RETX 的 HARQ process,設成 WAIT_FEEDBACK。"""
        pool = self._pool_for(ue_id)
        procs = pool.dl if direction == "DL" else pool.ul
        for p in procs:
            if p.state in ("NEW", "RETX"):
                p.state = "WAIT_FEEDBACK"
                p.last_tbs_bytes = tbs_bytes
                return p
        return None

    def handle_feedback(self, ue_id: str, harq_pid: int, direction: str, success: bool) -> HarqProcessState | None:
        pool = self._pool_for(ue_id)
        procs = pool.dl if direction == "DL" else pool.ul
        if harq_pid < 0 or harq_pid >= len(procs):
            logger.warning("invalid harq_pid=%s ue=%s dir=%s", harq_pid, ue_id, direction)
            return None
        p = procs[harq_pid]
        if success:
            p.state = "DONE"
            p.retx_count = 0
        else:
            p.retx_count += 1
            if p.retx_count >= MAX_RETX:
                logger.info("ue=%s harq_pid=%s direction=%s exhausted retx, drop", ue_id, harq_pid, direction)
                p.state = "DONE"
                p.retx_count = 0
            else:
                p.state = "RETX"
        return p

    def snapshot(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for ue, pool in self._pools.items():
            out[ue] = {
                "dl": [(p.pid, p.state, p.retx_count) for p in pool.dl],
                "ul": [(p.pid, p.state, p.retx_count) for p in pool.ul],
            }
        return out


_singleton: HarqManager | None = None


def get_harq_manager() -> HarqManager:
    global _singleton
    if _singleton is None:
        _singleton = HarqManager()
    return _singleton
