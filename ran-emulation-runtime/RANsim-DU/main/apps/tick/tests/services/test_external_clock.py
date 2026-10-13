"""外部時鐘(多 gNB D1):RU 每拍呼叫 step,DU 用 RU 的 tick / 劇本時鐘,DL TTI 交回不自己送。"""
from unittest.mock import patch

import pytest

from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.apps.tick.services.optional.runner import tick_runner as tr
from main.apps.tick.services.optional.runner.tick_runner import TickRunner

_RU_POST = "main.apps.fapi_north.services.business.ru_client_operations.RuClientBusinessService.post_dl_tti_request"
_CU_POST = "main.apps.f1ap_du.services.business.cu_client_operations.CuClientBusinessService.post_measurement_report"


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(tr, "_EXTERNAL_CLOCK", True)
    r = TickRunner()
    monkeypatch.setattr(tr, "_singleton", r)            # indication 套用走 get_tick_runner()
    r.status.is_running = True
    r.register_ue("ue-1", serving_cell="cell-0", sinr_db=15.0, rsrp_dbm=-80.0)
    ent = rlc_factory.make_entity("AM")
    rlc_factory.register("ue-1", "DRB", 1, ent)
    ent.recv_sdu(2000)
    yield r
    rlc_factory.unregister_ue("ue-1")


def test_step_uses_ru_tick_and_returns_dl_tti(runner):
    with patch(_RU_POST) as ru, patch(_CU_POST, return_value=True):
        out = runner.step(tick=41, scene_tick=7, sim_dt_ms=100, speed_x=5.0)
    assert out["ran"] and out["tick"] == 41
    assert runner.status.tick_count == 41 and runner.scene_tick == 7
    ru.assert_not_called()                              # 不自己送 RU
    dl = out["dl_tti"]
    assert dl["scene_sim_ms"] == 700
    assert [p["ue_id"] for p in dl["pdus"]] == ["ue-1"]
    assert runner.sim_dt_ms == 100 and runner.wall_tick_ms == 20


def test_global_load_overlaid_by_own(runner):
    with patch(_CU_POST, return_value=True):
        runner.step(tick=1, scene_tick=1, sim_dt_ms=100, speed_x=1.0,
                    cell_dl_load={"other-du-cell": 0.8, "cell-0": 0.0})
    load = runner.cell_dl_load
    assert load["other-du-cell"] == 0.8                 # 別的 DU 的 cell 來自 RU 合併
    assert "cell-0" in load                             # 自己的 cell 用自己的最新值
    out = runner.step(tick=2, scene_tick=2, sim_dt_ms=100, speed_x=1.0, cell_dl_load={"other-du-cell": 0.5})
    # 回報給 RU 的只有自己的 cell —— 別的 DU 的舊值若也報上去,RU 合併時會蓋掉那個 DU 的新值
    assert "other-du-cell" not in out["dl_tti"]["cell_dl_load"]
    assert "cell-0" in out["dl_tti"]["cell_dl_load"]


def test_indications_applied_before_tick(runner):
    ind = [{"ue_id": "ue-1", "sinr_db": 3.0, "cqi": 5, "rank": 1, "pmi": 0, "rsrp_dbm": -97.0}]
    with patch(_CU_POST, return_value=True):
        runner.step(tick=1, scene_tick=1, sim_dt_ms=100, speed_x=1.0, indications=ind)
    assert runner._ue_registry["ue-1"]["rsrp_dbm"] == -97.0


def test_not_running_does_nothing(runner):
    runner.status.is_running = False
    out = runner.step(tick=5, scene_tick=5, sim_dt_ms=100, speed_x=1.0)
    assert out == {"ran": False, "tick": 5, "dl_tti": None}


def test_start_external_does_not_spawn_thread(monkeypatch):
    monkeypatch.setattr(tr, "_EXTERNAL_CLOCK", True)
    r = TickRunner()
    assert r.start()
    assert r._thread is None and r.status.is_running
    r.stop()
