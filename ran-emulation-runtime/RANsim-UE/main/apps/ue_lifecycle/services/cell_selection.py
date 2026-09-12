"""IDLE 態選網(TS 38.304)—— 掉話的 UE 自己量、自己決定、自己重新發起連線。

為什麼決策在 UE 端:
  RLF → 重建失敗 → UE 進 RRC_IDLE。IDLE 態**沒有 RRC 連線、沒有 measConfig**,
  所以它不會回報任何量測給網路 —— 網路端根本不知道這台 UE 在哪、訊號多少。
  真實流程是 UE 自行量 SSB → 選 suitable cell → RACH → RRCSetupRequest
  (TS 38.304 選網 + TS 38.331 連線建立),**全程由 UE 發起**。

  2026-08-20 曾把重連掛在 CU 的量測回報上,結果 hook 永遠不觸發 ——
  正因為 IDLE UE 不產生量測回報。實測:掉話後 ue_1 的 MeasurementLog 凍結在
  273 筆不再增加,而正常的 ue_2 是 2576 筆持續成長。方向錯了就做不出來。

這裡用 Physics 的 PathSolver 當「UE 量 SSB」——它算的就是該位置對各 cell 的
path gain,和 UE 天線收到的東西同源。
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 5.0


def _tx_power_dbm() -> float:
    """SSB 發射功率。理想上該從 SIB 讀,sim 沒有 SIB —— 用場景的 gNB 功率。"""
    return float(getattr(settings, "CAMP_TX_POWER_DBM", 30.0))


def measure_cells(ue_id: str, position: tuple[float, float, float]) -> dict[str, float]:
    """在 position 量各 cell 的 RSRP(dBm)。回 {cell_id: rsrp_dbm},失敗回 {}。"""
    url = f"{settings.SIM_PHYSICS_URL.rstrip('/')}/api/v0.1/Physics/RanCalc/PathSolver/compute"
    body = {"ue_positions": [{
        "id": ue_id,
        "position": [float(position[0]), float(position[1]), float(position[2])],
        "velocity": [0.0, 0.0, 0.0],
    }]}
    try:
        r = requests.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return {}
        gains: dict[str, Any] = ((r.json() or {}).get("data") or {}).get("path_gain") or {}
    except (requests.RequestException, ValueError) as exc:
        logger.debug("cell_selection measure failed ue=%s: %s", ue_id, exc)
        return {}

    per_cell = gains.get(ue_id) or {}
    tx = _tx_power_dbm()
    out: dict[str, float] = {}
    for cell, g in per_cell.items():
        try:
            gl = float(g)
        except (TypeError, ValueError):
            continue
        if gl <= 0.0:
            continue                      # 無路徑 = 收不到
        out[str(cell)] = tx + 10.0 * math.log10(gl)
    return out


_LABEL_RE = re.compile(r"^(?P<gnb>.+)#(?P<idx>\d+)$")


def to_cu_cell_id(label: str, known: set[str], by_pci: dict[int, str] | None = None) -> str:
    """Physics scene 的 gNB 標籤 → CU 的 cell_id。

    Physics 回 "gnb1#0",CU 認的是 "gnb1_c0" —— 兩邊命名不同源。直接拿去 attach
    會被 phantom cell 防呆擋掉,更糟的是 force_serving_cell 沒有那道防呆,
    會把 "gnb1#0" 寫進 serving_cell,之後 traffic / 量測全部找不到 cell。
    對不到既有 cell 就回 "",寧可不駐留也不要寫壞 context。
    """
    if label in known:
        return label
    m = _LABEL_RE.match(label)
    if m:
        cand = f"{m.group('gnb')}_c{m.group('idx')}"
        if cand in known:
            return cand
        # "#" 後綴實為 PCI(SionnaEngine tx 命名)→ 以 PCI 反查 CU cell
        if by_pci:
            hit = by_pci.get(int(m.group("idx")))
            if hit:
                return hit
    return ""


def select_cell(
    ue_id: str,
    position: tuple[float, float, float],
    *,
    min_rsrp_dbm: float,
) -> tuple[str, float]:
    """選一個可駐留的 cell。回 (cell_id, rsrp);沒有合格的回 ("", -140.0)。

    min_rsrp_dbm 應該比重建門檻再高一點(遲滯),否則 UE 會在覆蓋邊緣
    反覆 attach → 掉話 → attach,把 CU 的 session 記錄洗爆。
    """
    meas = measure_cells(ue_id, position)
    if not meas:
        return "", -140.0
    from main.apps.ue_lifecycle.services import cu_client
    cells = cu_client.list_cells()
    # TS 38.304 §5.2.4.1:barred cell 不得駐留(量測照收、只是不能選它)。
    # CU 的 RRC 重建一直有排除,IDLE 選網漏了(2026-08-26 第 3 題 fixture 抓到)。
    cells = [c for c in cells if not c.get("barred")]
    known = {c.get("ncgi") for c in cells if c.get("ncgi")}
    # 2026-08-26:physics 標籤是 "{name}#{PCI}" 不是 "#{索引}" —— PCI≠索引的場景
    # (幾乎所有 ANR 劇本)舊映射拼出不存在的 cell_id,recamp 全滅。加 PCI 反查。
    by_pci = {}
    for c in cells:
        p = c.get("physicalCellId")
        if p is not None:
            by_pci.setdefault(int(p), c.get("ncgi"))
    best, best_rsrp = "", -140.0
    for label, rsrp in meas.items():
        cid = to_cu_cell_id(label, known, by_pci)
        if not cid or rsrp <= best_rsrp:
            continue
        best, best_rsrp = cid, rsrp
    if not best or best_rsrp < min_rsrp_dbm:
        return "", best_rsrp
    return best, best_rsrp
