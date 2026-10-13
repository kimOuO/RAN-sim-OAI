"""首傳 BLER 曲線 —— DU 內唯一的 BLER 模型。

來源
----
OAI 官方 NR AWGN 鏈路層模擬結果,MCS 0–28(TS 38.214 MCS 表 1):
    openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/AWGN_results/mcs{N}_awgn_5G.csv
取其首傳(err0 / trials0)錯誤率。匯入工具:``RANsim-DU/tools/import_oai_bler.py``。
衰落通道的多個 SINR 分量先以 EESM(``eesm.py``)壓成等效 SINR,再查這條 AWGN 曲線 ——
這是 OAI 在該目錄 README 中說明的預期用法。

誰在用
------
* ``mcs_controller``:外迴路鏈路適應(OAI ``get_mcs_from_bler`` 的等價實作)
* ``mcs_table.sinr_to_mcs``:依操作點選 MCS(排程器估算 PRB 需求、上行)
* ``slot_engine``:逐 slot 重傳模擬(RLC 延遲 KPM)
* PM 的 HARQ 輪次統計、``tools/derive_cqi_thresholds.py`` 的 CQI 切點推導

2026-09-26 之前 MCS 控制器另有一套無出處的 erfc 公式,與這條曲線在中高階 MCS
相差約 10 dB;已移除。曲線讀不到或 MCS 不齊全時直接拋錯,不再默默退回公式 ——
路徑設錯時整個 DU 的鏈路層數字都會錯,寧可起不來。
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CURVE_PATH = Path(__file__).resolve().parent / "data" / "bler_curve.csv"
MAX_MCS = 28          # TS 38.214 MCS 表 1 的最大可用索引(OAI dl_max_mcs 預設亦為 28)

# 操作點 BLER:TS 38.214 §5.2.2.1 的 CQI 定義(「傳輸區塊錯誤率不超過 0.1」)。
# OAI 的外迴路以 0.05 / 0.15 為上下門檻(MACRLC dl_bler_target_lower / upper 預設值),
# 0.1 恰在兩者之間。
OPERATING_POINT_BLER = 0.1

_curve: dict[int, list[tuple[float, float]]] | None = None


def curve_path() -> Path:
    """曲線檔位置。``SIM_BLER_CURVE_PATH`` 可覆寫(實驗用),預設為本模組旁的 data/。"""
    raw = get_str("SIM_BLER_CURVE_PATH", "")
    return Path(raw) if raw else DEFAULT_CURVE_PATH


def _load() -> dict[int, list[tuple[float, float]]]:
    global _curve
    if _curve is not None:
        return _curve
    path = curve_path()
    if not path.is_file():
        raise RuntimeError(f"BLER 曲線檔不存在:{path}(SIM_BLER_CURVE_PATH 設錯?)")
    table: dict[int, list[tuple[float, float]]] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                table.setdefault(int(row["mcs"]), []).append((float(row["sinr_db"]), float(row["bler"])))
            except (KeyError, ValueError):
                continue
    missing = [m for m in range(MAX_MCS + 1) if not table.get(m)]
    if missing:
        raise RuntimeError(f"BLER 曲線檔 {path} 缺少 MCS {missing};需涵蓋 0–{MAX_MCS}")
    for pts in table.values():
        pts.sort()
    _curve = table
    logger.info("BLER 曲線載入:MCS 0–%d,%d 點,來源 %s",
                MAX_MCS, sum(len(v) for v in table.values()), path)
    return table


def reset_cache() -> None:
    """測試用:改了 SIM_BLER_CURVE_PATH 後重新載入。"""
    global _curve
    _curve = None


def bler(mcs: int, sinr_db: float) -> float:
    """該 MCS 在此 SINR 的首傳 BLER(0..1)。曲線點之間線性插值,範圍外取端點值。"""
    m = max(0, min(MAX_MCS, int(mcs)))
    pts = _load()[m]
    if sinr_db is None or math.isnan(sinr_db):
        return 1.0
    if sinr_db <= pts[0][0]:
        return pts[0][1]
    if sinr_db >= pts[-1][0]:
        return pts[-1][1]
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= sinr_db:
            lo = mid
        else:
            hi = mid
    (x0, y0), (x1, y1) = pts[lo], pts[hi]
    t = (sinr_db - x0) / (x1 - x0) if x1 != x0 else 0.0
    return max(0.0, min(1.0, y0 + t * (y1 - y0)))


def sinr_at_bler(mcs: int, target: float = OPERATING_POINT_BLER) -> float:
    """BLER 最後一次降到 target 以下的 SINR(dB)—— 之後的 SINR 都不超過 target。

    曲線尾端偶有模擬雜訊造成的回彈,取「最後一次」而非「第一次」穿越才保守。
    整條曲線都高於 target 回 +inf;都不高於回曲線起點。
    """
    m = max(0, min(MAX_MCS, int(mcs)))
    pts = _load()[m]
    last_above = -1
    for i, (_, b) in enumerate(pts):
        if b > target:
            last_above = i
    if last_above == -1:
        return pts[0][0]
    if last_above == len(pts) - 1:
        return math.inf
    (x0, y0), (x1, y1) = pts[last_above], pts[last_above + 1]
    return x0 + (y0 - target) / (y0 - y1) * (x1 - x0) if y0 != y1 else x1


def op_point_mcs(sinr_db: float, target: float = OPERATING_POINT_BLER, max_mcs: int = MAX_MCS) -> int:
    """首傳 BLER ≤ target 的最高 MCS;沒有任何 MCS 達標時回 0。

    逐一檢查每個 MCS,而非假設曲線隨 MCS 單調(OAI 原始資料的 MCS 1 並不單調)。
    """
    chosen = 0
    for m in range(0, max(0, min(MAX_MCS, max_mcs)) + 1):
        if bler(m, sinr_db) <= target:
            chosen = m
    return chosen


HARQ_MAX_ROUNDS = 4   # OAI MACRLC dl_harq_round_max 預設值


def harq_round_probs(mcs: int, sinr_db: float, max_rounds: int = HARQ_MAX_ROUNDS) -> tuple[list[float], float]:
    """一個傳輸區塊用到第 k 輪(k = 0..max_rounds-1)的機率,以及最終失敗的機率。

    重傳以 Chase combining 建模:第 k 輪時接收端合併了 k+1 份相同副本,等效 SINR 提高
    ``10·log10(k+1)`` dB(D. Chase, "Code Combining", IEEE Trans. Commun., 1985)。
    再以該等效 SINR 查同一條 AWGN 曲線。實際 NR 用 incremental redundancy,
    增益通常比 Chase 略高,故此為保守近似。
    """
    reach = 1.0
    out: list[float] = []
    for k in range(max(1, max_rounds)):
        out.append(reach)
        eff = sinr_db + 10.0 * math.log10(k + 1)
        reach *= bler(mcs, eff)
    return out, reach
