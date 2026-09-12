"""RRC state machine — IDLE → SETUP → CONNECTED → RELEASE.

OAI ref: openair2/RRC/NR/rrc_gNB.c (rrc_gnb_task switch dispatch at L3030).
This is a simplified linear FSM; real OAI tracks security/PDCP activation
implicitly via xids[] table. We model only the externally-visible state.
"""
from __future__ import annotations


class RrcStateError(ValueError):
    """Raised on illegal state transition."""


_ALLOWED: dict[str, set[str]] = {
    "IDLE":      {"SETUP", "RELEASE"},
    "SETUP":     {"CONNECTED", "IDLE", "RELEASE"},
    "CONNECTED": {"RELEASE", "INACTIVE"},
    "INACTIVE":  {"CONNECTED", "RELEASE"},
    "RELEASE":   {"IDLE"},
}


class RrcStateMachine:
    @staticmethod
    def can_transition(from_state: str, to_state: str) -> bool:
        return to_state in _ALLOWED.get(from_state, set())

    @staticmethod
    def transition(from_state: str, to_state: str) -> str:
        if not RrcStateMachine.can_transition(from_state, to_state):
            raise RrcStateError(f"illegal transition {from_state} → {to_state}")
        return to_state

    @staticmethod
    def can_handover(rrc_state: str) -> bool:
        return rrc_state == "CONNECTED"
