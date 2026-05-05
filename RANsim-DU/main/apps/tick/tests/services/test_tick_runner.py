"""Tick runner 流程測試 — mock CU/RU client 出去的 HTTP。"""
from unittest.mock import patch

from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.apps.tick.services.optional.runner.tick_runner import TickRunner


def _setup_ue_with_data():
    runner = TickRunner()
    runner.register_ue("ue-1", serving_cell="cell-0", sinr_db=15.0, rsrp_dbm=-80.0)
    ent = rlc_factory.make_entity("AM")
    rlc_factory.register("ue-1", "DRB", 1, ent)
    ent.recv_sdu(2000)
    return runner


def teardown_function(_):
    rlc_factory.unregister_ue("ue-1")


def test_run_once_schedules_ue():
    runner = _setup_ue_with_data()
    with patch(
        "main.apps.fapi_north.services.business.ru_client_operations.RuClientBusinessService.post_dl_tti_request",
        return_value=True,
    ), patch(
        "main.apps.f1ap_du.services.business.cu_client_operations.CuClientBusinessService.post_measurement_report",
        return_value=True,
    ):
        result = runner.run_once()
    assert result["tick_count"] == 1
    assert "ue-1" in result["scheduled_ues"]


def test_sfn_slot_advance():
    runner = _setup_ue_with_data()
    with patch(
        "main.apps.fapi_north.services.business.ru_client_operations.RuClientBusinessService.post_dl_tti_request",
        return_value=True,
    ), patch(
        "main.apps.f1ap_du.services.business.cu_client_operations.CuClientBusinessService.post_measurement_report",
        return_value=True,
    ):
        for _ in range(25):
            runner.run_once()
    assert runner.status.tick_count == 25
    # 跑 25 個 tick 應跨過一個 frame (20 slot)
    assert runner.status.sfn == 1
