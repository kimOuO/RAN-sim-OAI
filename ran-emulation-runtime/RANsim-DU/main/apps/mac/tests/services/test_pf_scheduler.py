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


# ── AL1: OAI-aligned per-UE demand cap + second-pass redistribute ─────────

def test_low_demand_leaves_leftover():
    """少量 buffer (~1 KB) MCS 高 — 1~2 PRB 就夠, 剩餘大量 PRB 必須留下 (不滿)."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[{
            "id": "ue1", "sinr_db": 20.0,
            "buffer_occupancy": 1024,  # 1 KB demand
        }],
        n_prb_total=273,
        tick_ms=500,
    )
    # 高 SINR 1 PRB 可載 ~10+ KB / 500ms → buffer 1KB 只需 1 PRB
    # 沒其他 UE 搶 — Pass 2 不會 redistribute, 剩餘留 unused
    assert alloc["ue1"] < 50, f"低 demand 不該吃滿 PRB, got {alloc['ue1']}"
    assert alloc["ue1"] >= 1
    # PRB% 應遠 < 100%
    assert sum(alloc.values()) / 273 < 0.20


def test_high_demand_uses_all_prb():
    """Demand 遠超 capacity — single UE 應拿到 n_prb_total."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[{
            "id": "ue1", "sinr_db": 20.0,
            "buffer_occupancy": 50 * 1024 * 1024,  # 50 MB demand 超過 273 PRB 能 drain
        }],
        n_prb_total=273,
        tick_ms=500,
    )
    # 50 MB / 500ms = 800 Mbps demand, 273 PRB capacity ~150 Mbps → 拿滿
    assert alloc["ue1"] == 273


def test_pass2_redistribute_leftover():
    """1 個低 demand + 1 個極高 demand — Pass 2 把 leftover 給 high UE 補滿."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[
            {"id": "low",  "sinr_db": 15.0, "buffer_occupancy": 2048},         # 2 KB
            {"id": "high", "sinr_db": 15.0, "buffer_occupancy": 20 * 1024 * 1024},  # 20 MB
        ],
        n_prb_total=273,
        tick_ms=500,
    )
    # low demand 1 PRB 解決, high demand 超過 fair share (~136) → Pass 2 補
    assert alloc["low"] <= 5
    assert alloc["high"] >= 250
    assert sum(alloc.values()) <= 273


def test_leftover_unused_when_demand_low():
    """所有 UE demand 都低 — leftover PRB 不該被硬塞 (對齊 OAI 不浪費 spec)."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[
            {"id": "ue1", "sinr_db": 20.0, "buffer_occupancy": 1024},   # 1 KB
            {"id": "ue2", "sinr_db": 20.0, "buffer_occupancy": 1024},   # 1 KB
            {"id": "ue3", "sinr_db": 20.0, "buffer_occupancy": 1024},   # 1 KB
        ],
        n_prb_total=273,
        tick_ms=500,
    )
    # 3 UE 每個 1 KB, 每 PRB MCS 26 容量 ~62 KB/tick → 每 UE 1 PRB 就夠
    # 真實 PRB usage 應 < 5% (3 / 273 ≈ 1%)
    used = sum(alloc.values())
    assert used <= 15, f"低 demand 不該吃滿 PRB, used={used}"


def test_no_buffer_info_falls_back_to_old_behavior():
    """向後相容: ue 沒給 buffer_occupancy → 視為無限 demand, 老 caller 不破."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[
            {"id": "ue1", "sinr_db": 20.0},   # 沒 buffer_occupancy
            {"id": "ue2", "sinr_db": 10.0},
        ],
        n_prb_total=100,
    )
    # 老 behavior — 加總接近 n_prb_total
    assert 95 <= sum(alloc.values()) <= 100


def test_zero_buffer_minimum_alloc():
    """buffer 為 0 (邊界 case, tick_runner 已 filter 過但防禦性處理) — 只分 1 PRB."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[{"id": "ue1", "sinr_db": 15.0, "buffer_occupancy": 0}],
        n_prb_total=100,
    )
    assert alloc["ue1"] == 1


def test_low_sinr_mcs0_still_gets_one_prb():
    """SINR < -6 (MCS 0, bps_re=0) — 給 1 PRB 試送, 不會分到 0."""
    sched = PfScheduler()
    alloc = sched.allocate(
        gnb_name="gnb-0",
        ues_on_gnb=[{
            "id": "ue1", "sinr_db": -15.0,
            "buffer_occupancy": 1024,
        }],
        n_prb_total=100,
    )
    assert alloc["ue1"] >= 1
