"""live 模式 path gain 時間平滑(2026-09-19)。

live 每個 tick 都重新光追一次,射線取樣雜訊讓同一位置相鄰 tick 的 path gain 跳十幾 dB;
RLF 偵測吃瞬時 SINR,兩次 < −6 dB 就起 T310 → 實測 OSM 場景 1× 3 分鐘 11 次 RLF。
cached 模式在載入 cache 時做 10 s 移動平均(channel_cache_loader.smooth_path_gain),這裡是 live 的對應:
每 (UE, tx) 在 dB 域做指數移動平均,時間常數以劇本模擬時間計(與倍速、worker 數無關)。

- 某 tx 這個 tick 沒路徑:沿用上次平滑值,超過 HOLD_SEC 才放掉(短暫漏追不等於沒訊號)
- gunicorn 多 worker 時每個 process 各自一份狀態;時間常數按模擬時間算,效果一致
"""
from __future__ import annotations

import math
import os
import threading

TAU_SEC = float(os.environ.get("RU_LIVE_SMOOTH_TAU_SEC", "5"))     # 0 = 不平滑
HOLD_SEC = float(os.environ.get("RU_LIVE_SMOOTH_HOLD_SEC", "10"))

_lock = threading.Lock()
_state: dict[tuple[str, str], tuple[float, float]] = {}   # (ue, tx) → (平滑後 dB, 最後更新的模擬秒)


def smooth(ue_id: str, gains_linear: dict[str, float], now_sec: float | None) -> dict[str, float]:
    """gains_linear {tx: 線性 path gain} → 平滑後的同格式 dict。now_sec 為 None(舊 DU 沒帶劇本時鐘)就原樣回。"""
    if TAU_SEC <= 0 or now_sec is None:
        return gains_linear
    out: dict[str, float] = {}
    with _lock:
        for tx, g in gains_linear.items():
            if not isinstance(g, (int, float)) or g <= 0:
                continue
            db = 10.0 * math.log10(g)
            prev = _state.get((ue_id, tx))
            if prev is None or now_sec < prev[1] or now_sec - prev[1] > HOLD_SEC:
                s = db                                  # 第一次、劇本重來、或斷太久:直接採用
            else:
                a = 1.0 - math.exp(-(now_sec - prev[1]) / TAU_SEC)
                s = prev[0] + a * (db - prev[0])
            _state[(ue_id, tx)] = (s, now_sec)
            out[tx] = 10.0 ** (s / 10.0)
        # 這 tick 沒路徑的 tx:HOLD_SEC 內沿用上次值
        for (u, tx), (s, t) in list(_state.items()):
            if u == ue_id and tx not in out and 0 <= now_sec - t <= HOLD_SEC:
                out[tx] = 10.0 ** (s / 10.0)
    return out


def reset() -> None:
    with _lock:
        _state.clear()
