"""MCS ↔ 頻譜效率 ↔ 吞吐量。

* 頻譜效率 Q_m × R:TS 38.214 MCS 表 1(``ran_sim_protocol.nr_link_tables``,
  與 OAI ``Table_51311`` 相同)。
* SINR → MCS:OAI AWGN BLER 曲線上首傳 BLER ≤ 0.1 的最高 MCS(``bler_curve.op_point_mcs``)。
* 每 PRB 位元數與 TDD 比例:``nr_resources``(DU 唯一真值來源;``NR_TBS_SPEC_MODE``
  決定走 TS 38.214 §5.1.3.2 或舊常數)。

2026-09-26 之前這裡有一張無出處的 SINR→(MCS, bit/RE) 表(註解寫 Table 5.1.3.1-2,
即 256QAM 表,但數值兩者都對不上;MCS 28 被給到 7.41 bit/RE,超過 64QAM 上限 5.55),
且吞吐量自帶一份 0.80 overhead 與 0.72 TDD 常數,與 ``nr_resources`` 重複。已移除。
"""
from __future__ import annotations

from ran_sim_protocol.nr_link_tables import spectral_efficiency

from main.apps.mac.services.optional.link_adaptation import bler_curve, nr_resources

__all__ = ["spectral_efficiency", "sinr_to_mcs", "mcs_to_throughput_mbps", "goodput_efficiency"]


def sinr_to_mcs(sinr_db: float) -> tuple[int, float]:
    """SINR → (操作點 MCS, 有效頻譜效率 bit/RE)。

    有 MCS 達到 10% 首傳 BLER 時,回該 MCS 與其表列頻譜效率。
    連 MCS 0 都達不到時回 (0, SE_0 × (1 − BLER_0)):仍以 MCS 0 傳送,但扣掉失敗的部分,
    SINR 越差越趨近 0(舊表在 −6 dB 以下直接回 0,之上則無論成敗都給滿額)。
    """
    mcs = bler_curve.op_point_mcs(sinr_db)
    b = bler_curve.bler(mcs, sinr_db)
    if b <= bler_curve.OPERATING_POINT_BLER:
        return mcs, spectral_efficiency(mcs)
    return 0, spectral_efficiency(0) * max(0.0, 1.0 - b)


def mcs_to_throughput_mbps(
    *,
    mcs: int,
    n_rb: int,
    bps_re: float | None = None,
    n_layers: int = 1,
    uplink: bool = False,
) -> float:
    """n_rb 個 PRB 以此 MCS 傳送一秒的位元數(Mbps)。

    ``bps_re`` 不給時取 MCS 表 1 的頻譜效率;``sinr_to_mcs`` 回的有效頻譜效率可直接傳入。
    每 PRB 的 RE 數與 overhead、TDD 比例一律取自 ``nr_resources``。
    """
    eff = spectral_efficiency(mcs) if bps_re is None else float(bps_re)
    ratio = nr_resources.tdd_ul_ratio() if uplink else nr_resources.tdd_dl_ratio()
    bits = nr_resources.bits_per_prb_slot(eff, n_layers) * max(0, int(n_rb)) \
        * nr_resources.SLOTS_PER_SEC * ratio
    return max(0.0, bits / 1e6)


def goodput_efficiency(mcs: int, sinr_db: float) -> float:
    """扣掉首傳失敗後的有效頻譜效率 SE(mcs) × (1 − BLER)。

    HARQ 最終多半會送達,但每個重傳都佔用一次傳輸機會;穩態下單位資源實際送出的
    資料量約為 SE × (1 − 首傳 BLER)。鏈路適應把 BLER 維持在 5%–15%,此項約扣 10%。
    """
    return spectral_efficiency(mcs) * max(0.0, 1.0 - bler_curve.bler(mcs, sinr_db))
