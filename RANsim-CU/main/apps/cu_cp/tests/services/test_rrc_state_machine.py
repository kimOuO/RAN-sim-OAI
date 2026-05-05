"""RRC SM transition rules."""
from __future__ import annotations

import pytest

from main.apps.cu_cp.services.optional.rrc.state_machine import (
    RrcStateError, RrcStateMachine,
)


def test_idle_to_setup_allowed():
    assert RrcStateMachine.transition("IDLE", "SETUP") == "SETUP"


def test_setup_to_connected_allowed():
    assert RrcStateMachine.transition("SETUP", "CONNECTED") == "CONNECTED"


def test_idle_to_connected_forbidden():
    with pytest.raises(RrcStateError):
        RrcStateMachine.transition("IDLE", "CONNECTED")


def test_release_to_idle_only():
    assert RrcStateMachine.transition("RELEASE", "IDLE") == "IDLE"
    with pytest.raises(RrcStateError):
        RrcStateMachine.transition("RELEASE", "CONNECTED")


def test_can_handover_only_when_connected():
    assert RrcStateMachine.can_handover("CONNECTED") is True
    assert RrcStateMachine.can_handover("IDLE") is False
    assert RrcStateMachine.can_handover("SETUP") is False
