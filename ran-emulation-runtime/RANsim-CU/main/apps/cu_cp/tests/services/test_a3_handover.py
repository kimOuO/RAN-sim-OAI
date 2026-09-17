"""A3 TTT trigger logic."""
from __future__ import annotations

import time

import pytest

from main.apps.cu_cp.services.optional.mobility import a3_handover_calculation as a3mod
from main.apps.cu_cp.services.optional.mobility.a3_handover_calculation import (
    A3HandoverCalculation, A3UeState, reset_state,
)


@pytest.fixture(autouse=True)
def _no_l3_filter(monkeypatch):
    # 下面的觸發邏輯測試用瞬時值;L3 濾波另外測
    monkeypatch.setattr(a3mod, "L3_FILTER_K", 0)
    reset_state()


def test_no_trigger_below_offset():
    calc = A3HandoverCalculation()
    state = A3UeState()
    # neighbor better, but only by 1 dB — below offset (3) + hys (1)
    verdict = calc.evaluate(state, "c1", -90.0, [("c2", -89.0)])
    assert verdict.triggered is False


def test_trigger_after_ttt():
    calc = A3HandoverCalculation()
    state = A3UeState()
    # neighbor 10 dB better — well above offset+hys
    v1 = calc.evaluate(state, "c1", -90.0, [("c2", -80.0)])
    assert v1.triggered is False  # first sample starts pending
    time.sleep((calc.ttt_ms + 50) / 1000.0)
    v2 = calc.evaluate(state, "c1", -90.0, [("c2", -80.0)])
    assert v2.triggered is True
    assert v2.target_cell == "c2"


def test_pending_resets_when_condition_breaks():
    calc = A3HandoverCalculation()
    state = A3UeState()
    calc.evaluate(state, "c1", -90.0, [("c2", -80.0)])  # start pending
    assert "c2" in state.pending
    calc.evaluate(state, "c1", -75.0, [("c2", -80.0)])  # serving stronger now
    assert "c2" not in state.pending


def test_l3_filter_smooths_single_spike(monkeypatch):
    monkeypatch.setattr(a3mod, "L3_FILTER_K", 4)   # a = 0.5
    state = A3UeState()
    assert state.l3("c2", -90.0) == -90.0          # 第一筆直接採用
    assert state.l3("c2", -50.0) == -70.0          # 單次 +40 dB 尖峰只反映一半
    assert state.l3("c2", -90.0) == -80.0
