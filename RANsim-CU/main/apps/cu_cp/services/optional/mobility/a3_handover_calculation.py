"""A3 event handover with TimeToTrigger — TS 38.331 §5.5.4.4.

Adapted from XAPP_DT/Physics_sim/_legacy/cu_candidates/rrc_event_tracker.py.
The original was a per-tick stateful tracker; here we expose a stateless
``evaluate()`` that takes the prior pending-state map and returns a verdict
and the new state. This lets cu_cp persist the state per UE (in-memory dict
is enough — the same UE always hits the same Django process).

Trigger:  Mn − hys > Mp + offset    (equivalently: nb_rsrp − hys > serving_rsrp + offset)
TTT:      condition must hold for at least ``ttt_ms`` to fire.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_float, get_int

A3_OFFSET_DEFAULT = 3.0
A3_HYS_DEFAULT = 1.0
TTT_DEFAULT = 160


@dataclass
class A3PendingState:
    neighbor_cell: str
    first_met_ms: int


@dataclass
class A3UeState:
    serving_cell: str = ""
    pending: dict[str, A3PendingState] = field(default_factory=dict)


@dataclass
class A3Verdict:
    triggered: bool
    target_cell: str = ""
    elapsed_ms: int = 0


class A3HandoverCalculation:
    def __init__(self) -> None:
        self.offset_db = get_float("HO_A3_OFFSET_DB", default=A3_OFFSET_DEFAULT)
        self.hys_db = get_float("HO_A3_HYSTERESIS_DB", default=A3_HYS_DEFAULT)
        self.ttt_ms = get_int("HO_TTT_MS", default=TTT_DEFAULT)

    def evaluate(
        self,
        ue_state: A3UeState,
        serving_cell: str,
        serving_rsrp: float,
        neighbors: list[tuple[str, float]],
    ) -> A3Verdict:
        """Update ``ue_state`` in place and return whether HO fires *this call*.

        ``neighbors``: list of (cell_id, rsrp_dbm) excluding serving.
        """
        now_ms = TimestampService.now_ms()
        ue_state.serving_cell = serving_cell
        verdict = A3Verdict(triggered=False)

        for nb_cell, nb_rsrp in neighbors:
            if nb_cell == serving_cell:
                continue
            condition_met = (nb_rsrp - self.hys_db) > (serving_rsrp + self.offset_db)
            pending = ue_state.pending.get(nb_cell)

            if condition_met:
                if pending is None:
                    ue_state.pending[nb_cell] = A3PendingState(nb_cell, now_ms)
                else:
                    elapsed = now_ms - pending.first_met_ms
                    if elapsed >= self.ttt_ms and not verdict.triggered:
                        verdict.triggered = True
                        verdict.target_cell = nb_cell
                        verdict.elapsed_ms = elapsed
                        ue_state.pending.clear()
                        return verdict
            else:
                ue_state.pending.pop(nb_cell, None)

        return verdict


# Per-process UE-state registry (process-local, mirrors OAI _ue_ho_state).
_UE_STATE_REGISTRY: dict[str, A3UeState] = {}


def get_ue_state(ue_id: str) -> A3UeState:
    return _UE_STATE_REGISTRY.setdefault(ue_id, A3UeState())


def reset_state() -> None:
    _UE_STATE_REGISTRY.clear()
