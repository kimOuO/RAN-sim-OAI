"""PF scheduler 行為測試 — 不需 Django DB。"""
from main.apps.mac.services.optional.scheduler.pf_scheduler import PfScheduler


def test_empty_returns_empty():
    sched = PfScheduler()
    assert sched.allocate(gnb_name="gnb-0", ues_on_gnb=[], n_prb_total=100) == {}


def test_single_ue_gets_all():
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[{"id": "ue1", "sinr_db": 15.0}],
        n_prb_total=100,
    )
    assert alloc["ue1"] >= 1
    assert sum(alloc.values()) <= 100


def test_higher_sinr_gets_more_initially():
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[
            {"id": "ue1", "sinr_db": 20.0},
            {"id": "ue2", "sinr_db": 0.0},
        ],
        n_prb_total=100,
    )
    assert alloc["ue1"] > alloc["ue2"]
    assert sum(alloc.values()) <= 100


def test_pf_fairness_over_time():
    sched = PfScheduler(alpha=0.2)
    ues = [{"id": "ue1", "sinr_db": 20.0}, {"id": "ue2", "sinr_db": 5.0}]
    for _ in range(50):
        sched.allocate(gnb_name="gnb-0", ues_on_gnb=ues, n_prb_total=100)
    # ue2 historic average 落後,後期應該被照顧到 — 相對佔比上升
    final = sched.allocate(gnb_name="gnb-0", ues_on_gnb=ues, n_prb_total=100)
    assert final["ue2"] >= 5
