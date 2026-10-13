"""SINR → CQI —— 查表本體在共用套件 ``ran_sim_protocol.nr_link_tables``(DU 與 RU 共用)。

本模組負責**推導**那張表的切點,讓它可以從 BLER 曲線重現、被測試驗證:

TS 38.214 §5.2.2.1:UE 回報的 CQI 是「以該 CQI 對應的調變與碼率傳送單一 PDSCH
傳輸區塊時,錯誤率不超過 0.1」的最高索引。對 CQI 表 1(Table 5.2.2.1-2)的每一列,
取調變與碼率完全相同的 MCS(表 1),在 OAI AWGN BLER 曲線上找 BLER 最後一次降到
0.1 的 SINR,即為該 CQI 的切點。OAI UE 端 ``nr_csi_rs_cqi_estimation``
(``openair1/PHY/NR_UE_TRANSPORT/csi_rx.c``)依同一規則,但切點取整數 dB。

2026-09-26 之前這裡是一張註明「對齊 OAI cqi_table2」的手寫表;OAI 並無該表,
數值也與 OAI UE 端切點不符,已替換。
"""
from __future__ import annotations

import math

from ran_sim_protocol.nr_link_tables import (
    CQI_SINR_THRESHOLDS_DB,
    cqi_spectral_efficiency,
    mcs_for_cqi,
    sinr_to_cqi,
)

from main.apps.mac.services.optional.link_adaptation import bler_curve

__all__ = ["sinr_to_cqi", "derive_cqi_thresholds", "CQI_SINR_THRESHOLDS_DB"]


def derive_cqi_thresholds(target: float = bler_curve.OPERATING_POINT_BLER) -> tuple[float, ...]:
    """由目前的 BLER 曲線推導 CQI 0..15 的 SINR 切點(dB,取到 0.01)。

    * CQI 0 = −∞(out of range,永遠成立)。
    * CQI 1 在 MCS 表 1 沒有同碼率的 MCS:以 MCS 0 的切點減去兩者頻譜效率比
      ``10·log10(SE_MCS0 / SE_CQI1)`` 近似。
    * 取累計最大值,保證切點單調不減(OAI 原始資料 MCS 1 的切點低於 MCS 0)。
    """
    raw: list[float] = [-math.inf]
    for cqi in range(1, 16):
        mcs = mcs_for_cqi(cqi)
        if mcs is None:
            mcs0 = mcs_for_cqi(2)   # CQI 2 與 MCS 0 同為 QPSK 120/1024
            shift = 10.0 * math.log10(cqi_spectral_efficiency(2) / cqi_spectral_efficiency(cqi))
            raw.append(bler_curve.sinr_at_bler(mcs0, target) - shift)
        else:
            raw.append(bler_curve.sinr_at_bler(mcs, target))
    out: list[float] = [-math.inf]
    run = -math.inf
    for th in raw[1:]:
        run = max(run, th)
        out.append(round(run, 2))
    return tuple(out)
