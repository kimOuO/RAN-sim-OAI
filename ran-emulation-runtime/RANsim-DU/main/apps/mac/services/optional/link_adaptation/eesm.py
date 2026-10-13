"""EESM —— 把多個 SINR(per-RB 或 per-layer)壓成單一 effective SINR。

為什麼需要
----------
AWGN link-level BLER 曲線(`bler_curve.csv`,來自 OAI 官方 NR AWGN 模擬)的
輸入必須是**純量**。真實通道的 SINR 在頻率(per-RB)與空間(per-layer)上都不同,
直接取算術平均會**高估**(強的分量主導),因為 BLER 對弱分量遠比對強分量敏感。

OAI 自己的 BLER 表 README 明講了預期用法:
    "to evaluate the BLER of fading channel, we map the received SINR to an AWGN
     curve using these look-up tables. […] This requires the computation of AWGN
     equivalent SINR, also generally known as effective SINR, by mapping the
     individual symbol SINRs to a scalar" (EESM)
    — openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/README.md

公式(TS 提及、學界標準形式)
--------------------------
    SINR_eff = −β · ln( (1/N) · Σ_n exp(−SINR_n / β) )

    SINR_n 為線性(非 dB)域的第 n 個分量;β 為 per-MCS 校正參數。
    β 的定義:使「衰落通道量到的 BLER」等於「該 effective SINR 在 AWGN 曲線上的
    BLER」,即把衰落通道映射到等效 AWGN 通道。

β 來源
------
Lagén et al., *"New Radio Physical Layer Abstraction for System-Level Simulations
of 5G Networks"*, IEEE ICC 2020, arXiv:2001.10309 — Table II「Optimal β values
for each MCS」。該論文是 ns-3 **5G-LENA** NR 模組 PHY abstraction 的依據實作。
β 由 NR-compliant link-level simulator 以式 (5) 的誤差最小化校正,通道模型採
3GPP TR 38.901 的 TDL-A(NLOS)/ TDL-D(LOS),延遲擴展 30–316 ns。

論文 Remark 1:β 對 SCS(numerology)與載波頻率不敏感 → 本表適用所有 NR
frequency range 與 numerology,不需為 band78 重新校正。

⚠ 轉錄說明:下表由該論文 PDF 的 Table II 轉錄(雙欄表格)。一致性檢查已通過 ——
β 的兩個跳階恰好落在 MCS Table 1 的調變階數邊界(MCS 10 = QPSK→16QAM,
MCS 17 = 16QAM→64QAM),與 38.214 Table 5.1.3.1-1 相符,且全表單調遞增。
若要 bit-exact 驗證,對照 5G-LENA 原始碼 `model/nr-eesm-t1.cc` 的 β 表。
"""
from __future__ import annotations

import math

from main.utils.env_loader import get_bool

# MCS Table 1(38.214 Table 5.1.3.1-1,up to 64QAM,MCS 0..28)
# 調變邊界:QPSK 0-9 / 16QAM 10-16 / 64QAM 17-28 —— β 在 10 與 17 跳階。
BETA_TABLE1: tuple[float, ...] = (
    1.60, 1.61, 1.63, 1.65, 1.67, 1.70, 1.73, 1.76, 1.79, 1.82,   # QPSK
    3.97, 4.27, 4.71, 5.16, 5.66, 6.16, 6.50,                     # 16QAM
    9.95, 10.97, 12.92, 14.96, 17.06, 19.33, 21.85,               # 64QAM
    24.51, 27.14, 29.94, 32.05, 34.28,
)

# MCS Table 2(38.214 Table 5.1.3.1-2,up to 256QAM,MCS 0..27)
BETA_TABLE2: tuple[float, ...] = (
    1.60, 1.63, 1.67, 1.73, 1.79,
    4.27, 4.71, 5.16, 5.66, 6.16, 6.50,
    10.97, 12.92, 14.96, 17.06, 19.33, 21.85, 24.51, 27.14, 29.94,
    56.48, 65.00, 78.58, 92.48, 106.27, 118.74, 126.36, 132.54,
)

# off 時 combine() 退回線性域算術平均(= 舊 RU estimate_sinr 行為),供 A/B 對照。
EESM_ENABLED = get_bool("NR_EESM_ENABLED", False)


def beta_for_mcs(mcs: int, table: int = 1) -> float:
    tbl = BETA_TABLE1 if table == 1 else BETA_TABLE2
    if mcs < 0:
        return tbl[0]
    if mcs >= len(tbl):
        return tbl[-1]
    return tbl[mcs]


def _db_to_lin(db: float) -> float:
    return 10.0 ** (db / 10.0)


def _lin_to_db(lin: float) -> float:
    return 10.0 * math.log10(max(lin, 1e-30))


def combine_db(sinrs_db, mcs: int, *, table: int = 1) -> float:
    """把一組 SINR(dB)壓成 effective SINR(dB)。

    sinrs_db 可以是 per-RB、per-layer,或兩者的聯集 —— 公式對「分量」不區分來源。
    """
    vals = [float(x) for x in sinrs_db if x is not None and math.isfinite(float(x))]
    if not vals:
        return -float("inf")
    if len(vals) == 1:
        return vals[0]

    lins = [_db_to_lin(v) for v in vals]
    if not EESM_ENABLED:
        # 舊行為:線性域算術平均(樂觀,強分量主導)
        return _lin_to_db(sum(lins) / len(lins))

    beta = beta_for_mcs(mcs, table)
    # 數值保護:SINR/β 過大時 exp(-x) 下溢為 0 → ln(0) 發散。
    # 以最小分量作為基準做位移,再還原(對數-和-指數穩定化)。
    scaled = [-x / beta for x in lins]
    m = max(scaled)                      # 最接近 0 的那個(= 最弱分量主導)
    acc = sum(math.exp(s - m) for s in scaled)
    ln_mean = m + math.log(acc / len(scaled))
    eff_lin = -beta * ln_mean
    return _lin_to_db(max(eff_lin, 1e-30))


def equal_power_split_db(sinr_db: float, n_layers: int) -> float:
    """SU-MIMO 等功率分配:總發射功率平分給 n 層 → 每層 SINR 下降 10log10(n)。

    38.214 §5.1.6.2 的 PDSCH 功率配置在無其他指示時為各層等分。
    沒有這一步,rank 提高等於免費多送資料(物理上錯),會讓天線選擇的結論
    系統性偏向「層數越多越好」。
    """
    n = max(1, int(n_layers))
    if n == 1:
        return sinr_db
    return sinr_db - 10.0 * math.log10(float(n))


def effective_sinr_for_layers(sinr_db: float, n_layers: int, sinr_layers=None, mcs: int | None = None) -> float:
    """rank 生效時,把「單層等效 SINR」還原成等功率分配後的每層 SINR。

    RU 回報的 SINR 未考慮發射功率要分給多層。若直接拿它配上 TBS×ν,等於憑空多送
    資料。本函式在 NR_MIMO_LAYERS_ENABLED=off 時原樣返回(舊行為)。

    RU 有回每層 SINR(``CqiIndication.sinr_per_layer_db``)時以 combine_db() 做 EESM;
    沒有(舊 RU、或 rank 1)才以等功率分配 ``equal_power_split_db`` 做一階修正。
    """
    from main.apps.mac.services.optional.link_adaptation import nr_resources
    if not nr_resources.MIMO_LAYERS_ENABLED:
        return sinr_db
    n = max(1, int(n_layers))
    # P5-4:RU 有回每層 SINR 就做 EESM(β 依目前 MCS;沒 MCS 用中間值 10)壓成一個等效 SINR,
    # 弱層會把等效值往下拉 —— 這才能分出「第二層其實很弱、不該開兩層」。
    if sinr_layers and len(sinr_layers) >= n and n > 1:
        return combine_db(list(sinr_layers)[:n], int(mcs) if mcs is not None else 10)
    return equal_power_split_db(sinr_db, n)
