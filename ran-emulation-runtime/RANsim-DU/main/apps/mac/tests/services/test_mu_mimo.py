"""MU-MIMO 配對(階段 D)。"""
import math

from main.apps.mac.services.optional.scheduler import mu_mimo as mu


def _ue(uid, beam, sinr, top, bo=1000):
    return {"id": uid, "beam_id": beam, "sinr_db": sinr, "beam_top": top, "buffer_occupancy": bo}


def test_mu_sinr_formula():
    # 無洩漏:功率減半 → −3 dB
    assert math.isclose(mu.mu_sinr_db(20.0, -300.0), 20.0 - 10 * math.log10(2), abs_tol=1e-6)
    # 洩漏 −15 dB、SU 20 dB:1/(2/100 + 10^-1.5)
    assert math.isclose(mu.mu_sinr_db(20.0, -15.0), 10 * math.log10(1 / (0.02 + 10 ** -1.5)), abs_tol=1e-9)


def test_leakage_uses_top_list_or_conservative_floor():
    u = _ue("a", 1, 20, [(1, 0.0), (2, -6.0), (5, -18.0)])
    assert mu.leakage_db(u, 2) == -6.0
    assert mu.leakage_db(u, 9) == -21.0
    assert mu.leakage_db({"id": "x"}, 2) is None


def test_well_separated_beams_pair():
    a = _ue("a", 1, 18, [(1, 0.0), (2, -3.0), (9, -20.0)], bo=5000)
    b = _ue("b", 9, 15, [(9, 0.0), (8, -4.0), (1, -22.0)])
    pairs, singles = mu.pair([a, b])
    assert len(pairs) == 1 and singles == []
    u, v, su, sv = pairs[0]
    assert {u["id"], v["id"]} == {"a", "b"}
    assert su < 18 and sv < 15


def test_same_beam_or_high_leakage_not_paired():
    a = _ue("a", 1, 18, [(1, 0.0), (2, -3.0)])
    b = _ue("b", 1, 18, [(1, 0.0)])
    c = _ue("c", 2, 18, [(2, 0.0), (1, -2.0)])
    pairs, singles = mu.pair([a, b, c])
    assert pairs == [] and len(singles) == 3


def test_ceiling_limited_pair_rejected_when_not_worth_it():
    # SINR 很高、洩漏剛好在門檻上:MU SINR 被洩漏壓住,只有總速率真的比 SU 各拿一半 PRB 高才配
    a = _ue("a", 1, 29, [(1, 0.0), (2, -10.0)])
    b = _ue("b", 2, 29, [(2, 0.0), (1, -10.0)])
    pairs, _ = mu.pair([a, b])
    su = mu._rate(29) * 0.5 * 2
    mu_rate = 2 * mu._rate(mu.mu_sinr_db(29, -10.0))
    assert (len(pairs) == 1) == (mu_rate > su)


def test_virtual_ue_takes_max_buffer_and_mean_sinr():
    a = _ue("a", 1, 18, [], bo=100)
    b = _ue("b", 2, 10, [], bo=900)
    v = mu.virtual_ue(a, b, 14.0, 8.0)
    assert v["id"] == "mu:a+b" and v["buffer_occupancy"] == 900 and v["sinr_db"] == 11.0
