from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import PmAggregatorService


def _add(pm: PmAggregatorService, ue_id: str, **kw) -> None:
    defaults = dict(
        gnb_name="cell-0",
        ue_id=ue_id,
        mcs_dl=10,
        mcs_ul=8,
        sinr_db=10.0,
        rsrp_dbm=-80.0,
        prb_dl=20,
        prb_ul=4,
        dl_bytes=1000,
        ul_bytes=200,
        qos_5qi=9,
        rank=1,
    )
    defaults.update(kw)
    pm.accumulate_ue(**defaults)


def test_window_starts_empty():
    pm = PmAggregatorService()
    assert pm.flush_ue_report("ue-x", window_seconds=2.5) is None
    assert pm.active_ue_ids() == []


def test_window_averages_sinr_over_samples():
    pm = PmAggregatorService()
    _add(pm, "ue-1", sinr_db=10.0)
    _add(pm, "ue-1", sinr_db=20.0)
    _add(pm, "ue-1", sinr_db=15.0)
    rep = pm.flush_ue_report("ue-1", window_seconds=2.5)
    assert rep is not None
    assert abs(rep["avg_sinr_db"] - 15.0) < 1e-6
    assert rep["samples"] == 3


def test_throughput_uses_window_seconds():
    pm = PmAggregatorService()
    # 5 個 tick × 1000 bytes = 5000 bytes 在 2.5s 內 = 0.016 Mbps
    for _ in range(5):
        _add(pm, "ue-1", dl_bytes=1000, ul_bytes=200)
    rep = pm.flush_ue_report("ue-1", window_seconds=2.5)
    expected_dl_mbps = (5 * 1000 * 8) / 2.5 / 1e6
    expected_ul_mbps = (5 * 200 * 8) / 2.5 / 1e6
    assert abs(rep["throughput_dl_mbps"] - expected_dl_mbps) < 1e-9
    assert abs(rep["throughput_ul_mbps"] - expected_ul_mbps) < 1e-9


def test_flush_resets_window():
    pm = PmAggregatorService()
    _add(pm, "ue-1")
    pm.flush_ue_report("ue-1", window_seconds=1.0)
    # second flush 應 None(已 reset)
    assert pm.flush_ue_report("ue-1", window_seconds=1.0) is None


def test_per_gnb_counters_persist_after_window_flush():
    """per-gNB cumulative 不該因 ue window flush 被重置。"""
    pm = PmAggregatorService()
    _add(pm, "ue-1", mcs_dl=10, prb_dl=50)
    _add(pm, "ue-1", mcs_dl=12, prb_dl=30)
    pm.flush_ue_report("ue-1", window_seconds=1.0)
    # gnb side 應仍累積
    acc = pm._acc["cell-0"]
    assert acc.prb_used_dl == 80
    assert acc.mcs_dl_bins[10] == 1
    assert acc.mcs_dl_bins[12] == 1


def test_remove_ue_clears_window():
    pm = PmAggregatorService()
    _add(pm, "ue-1")
    pm.remove_ue("ue-1")
    assert pm.flush_ue_report("ue-1", 1.0) is None


def test_active_ue_ids_only_lists_ues_with_samples():
    pm = PmAggregatorService()
    _add(pm, "ue-a")
    _add(pm, "ue-b")
    pm.flush_ue_report("ue-a", 1.0)  # ue-a window 清空
    active = pm.active_ue_ids()
    assert "ue-b" in active
    assert "ue-a" not in active
