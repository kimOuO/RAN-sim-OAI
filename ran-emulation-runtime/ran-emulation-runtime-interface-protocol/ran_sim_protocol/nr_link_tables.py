"""NR 鏈路層規範表 —— DU 與 RU 共用的唯一來源。

為什麼放在共用套件
------------------
CQI 由 UE 端量測後回報(本模擬由 RU 代算),gNB 端(DU)再依同一張表解讀。
2026-09-26 之前 RU 與 DU 各有一張 SINR→CQI 表,切點不同、兩張都沒有出處,
同一個 SINR 在兩端會得出不同 CQI。現在兩端都從這裡取值。

內容與出處
----------
* ``MCS_TABLE_1`` —— 3GPP TS 38.214 Table 5.1.3.1-1(PDSCH MCS index table 1,64QAM)。
  與 OAI ``openair2/LAYER2/NR_MAC_COMMON/nr_mac_common.c`` 的 ``Table_51311`` 逐列相同
  (OAI 以「碼率 × 10240」儲存,此處依規範原表用「碼率 × 1024」)。
  MCS 29–31 為重傳保留值,不列入。
* ``CQI_TABLE_1`` —— 3GPP TS 38.214 Table 5.2.2.1-2(CQI table 1)。
  與 OAI ``openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c`` 的 ``cqi_table1`` 逐列相同。
* ``CQI_SINR_THRESHOLDS_DB`` —— 依 TS 38.214 §5.2.2.1 的 CQI 定義推導:
  UE 回報「使單一 PDSCH 傳輸區塊的錯誤率不超過 0.1」的最高 CQI。
  對每個 CQI,取調變與碼率相同的 MCS,在 OAI 官方 AWGN 鏈路層 BLER 曲線上找
  BLER 首次降到 0.1 的 SINR。OAI 的 UE 實作(``openair1/PHY/NR_UE_TRANSPORT/csi_rx.c``
  ``nr_csi_rs_cqi_estimation``)用的是同一條規則,只是切點取整數 dB。
  推導程式:``RANsim-DU/tools/derive_cqi_thresholds.py``;
  DU 的單元測試會用目前的 BLER 曲線重算並比對本表,兩者不一致時測試失敗。

已知近似(推導程式與文件 ``docs/architecture/phy_fidelity_sources.md`` 皆有記載)
------------------------------------------------------------------------
* CQI 1(QPSK,碼率 78/1024)在 MCS 表 1 中沒有同碼率的 MCS。以 MCS 0 的切點減去
  ``10·log10(0.2344 / 0.1523)`` dB 近似(頻譜效率比)。
* OAI 原始資料中 MCS 1 的 10% BLER 切點(−2.3 dB)低於 MCS 0(−0.3 dB)與 MCS 2(−0.2 dB),
  是來源資料本身的非單調。CQI 切點取累計最大值,保證 CQI 隨 SINR 單調不減。
"""
from __future__ import annotations

import math

# (調變階數 Q_m, 碼率 × 1024),索引 = MCS 0..28
MCS_TABLE_1: tuple[tuple[int, int], ...] = (
    (2, 120), (2, 157), (2, 193), (2, 251), (2, 308), (2, 379), (2, 449), (2, 526),
    (2, 602), (2, 679), (4, 340), (4, 378), (4, 434), (4, 490), (4, 553), (4, 616),
    (4, 658), (6, 438), (6, 466), (6, 517), (6, 567), (6, 616), (6, 666), (6, 719),
    (6, 772), (6, 822), (6, 873), (6, 910), (6, 948),
)
MAX_MCS_TABLE_1 = len(MCS_TABLE_1) - 1   # 28

# (調變階數 Q_m, 碼率 × 1024),索引 = CQI 0..15;CQI 0 = out of range
CQI_TABLE_1: tuple[tuple[int, int], ...] = (
    (0, 0),
    (2, 78), (2, 120), (2, 193), (2, 308), (2, 449), (2, 602),
    (4, 378), (4, 490), (4, 616),
    (6, 466), (6, 567), (6, 666), (6, 772), (6, 873), (6, 948),
)


def spectral_efficiency(mcs: int) -> float:
    """MCS 表 1 的頻譜效率 Q_m × R(bit/RE)。超出範圍夾到邊界。"""
    m = max(0, min(MAX_MCS_TABLE_1, int(mcs)))
    qm, r1024 = MCS_TABLE_1[m]
    return qm * r1024 / 1024.0


def cqi_spectral_efficiency(cqi: int) -> float:
    """CQI 表 1 的頻譜效率;CQI 0 回 0。"""
    c = max(0, min(15, int(cqi)))
    qm, r1024 = CQI_TABLE_1[c]
    return qm * r1024 / 1024.0


def mcs_for_cqi(cqi: int) -> int | None:
    """調變與碼率完全相同的 MCS(表 1);沒有對應(CQI 0、CQI 1)回 None。"""
    c = max(0, min(15, int(cqi)))
    if c == 0:
        return None
    target = CQI_TABLE_1[c]
    for m, row in enumerate(MCS_TABLE_1):
        if row == target:
            return m
    return None


# CQI_SINR_THRESHOLDS_DB[i] = 回報 CQI ≥ i 所需的最低 SINR(dB)。
# 由 RANsim-DU/tools/derive_cqi_thresholds.py 自 OAI AWGN BLER 曲線產生,勿手改。
CQI_SINR_THRESHOLDS_DB: tuple[float, ...] = (
    -math.inf,
    -2.20, -0.33, -0.26, 0.36, 2.24, 4.17, 7.14, 8.66,
    10.48, 12.69, 14.63, 16.15, 17.77, 20.84, 21.88,
)


def sinr_to_cqi(sinr_db: float) -> int:
    """SINR(dB)→ CQI 0..15:達到 10% BLER 條件的最高 CQI(TS 38.214 §5.2.2.1)。"""
    if sinr_db is None or math.isnan(sinr_db):
        return 0
    cqi = 0
    for i, th in enumerate(CQI_SINR_THRESHOLDS_DB):
        if sinr_db >= th:
            cqi = i
        else:
            break
    return min(cqi, 15)
