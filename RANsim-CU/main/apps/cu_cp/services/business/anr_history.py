"""ANR v10 的歷史統計層 —— baseline 與 trendLast30Min 的來源。

v10 幾乎每題的判準都是「相對 baseline 的變化」而非絕對值,並要求
`trendLast30Min` 六窗序列做持續性判定(全域限制 L4:不得由單一窗口值觸發)。
E2 本身只送當下快照,這兩者必須由 xApp 或 E2 節點側自行累積 ——
本卷把它放在觀測資料裡,所以 sim 要負責產生。

定義(本檔為權威,文件與此同步):
  trendLast30Min — 最近 6 個 5 分鐘窗的取樣值(舊→新)。不足 6 筆時補當前值,
                   讓 xApp 的持續性判定不會因為剛啟動就誤判「趨勢上升」。
  baseline       — 30 分鐘之前所有取樣的中位數;沒有更舊的樣本時退回最舊一筆。
                   用中位數不用平均:病發作時的尖峰不該把 baseline 一起拉高。
  baselineLong   — 4 小時之前所有取樣的中位數;樣本不夠舊時回 **None(JSON null)**。
                   為什麼要有第二個基準(RIC 第五十五~五十六輪,live 實據):
                   短窗基準只在「病灶持續時間 < 基準窗」時可靠。第 6 題病灶持續
                   40 分鐘後,RRU.PrbTotDl.s07_c0 的短窗基準從 12 漲到 100、
                   六窗全滿 —— 基準被病灶自己寫了進去,異常於是看起來像常態。
                   長短兩個基準的差距本身就是「病灶持續多久」的訊號:
                     long=13 / short=100 / current=100 → 慢性病灶已污染短窗
                     long=95 / short=100 / current=100 → 這是常態壅塞
                   單一基準分不開這兩種。
                   **null 語意**:「不知道」,不是 0。剛開場沒有 4 小時歷史時回 null,
                   消費端必須退回既有行為,不得把 null 當 0(否則開場全場報異常)。

取樣節流為每 _SAMPLE_INTERVAL_SEC 一筆 —— adapter 每秒拉一次 indication,
不節流的話 30 分鐘會存 1800 筆,而六窗只需要 6 筆。
"""
from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from typing import Any

# 取樣間隔改為可由劇本宣告(執行期覆寫,不必重啟)。
# 為什麼:卷面多題的恢復基準是「連續 6 窗維持」,6 × 5 分鐘 = 30 分鐘,
# 十二題各跑一次就是一整天。壓到 60 秒一窗後 6 窗只要 6 分鐘,
# 而**判定邏輯完全不變** —— 仍然是連續 6 窗,只是每窗代表的實際時間變短。
# 這與第 11 題把 6 小時雙歸零壓成 5 分鐘是同一種壓縮:縮的是時間尺度,不是條件。
# ⚠️ 壓縮後 baseline 的「30 分鐘以前」與長窗的「4 小時以前」會跟著等比縮短,
#    所以壓縮過的場次不能拿來當基準污染的證據。
def _sample_interval() -> float:
    from main.utils.env_loader import get_float as _gf
    return float(_gf("ANR_HISTORY_SAMPLE_SEC", default=300.0))


_SAMPLE_INTERVAL_SEC = 300.0     # 5 分鐘一窗(預設;實際取值走 _sample_interval())
_WINDOWS = 6                     # trendLast30Min = 6 窗 = 30 分鐘
_MAX_SAMPLES = 288               # 保 24 小時(288 × 5min),給 baseline 用
_BASELINE_AGE_SEC = 1800.0       # 30 分鐘之前的樣本才算「歷史」
# 長窗要「久到病灶蓋不住」。取 4 小時:比任何一題的病灶期都長(最長的第 11 題
# 壓縮後 300s、未壓縮 6h 也只在其中一段飽和),又短到 24 小時樣本池撐得住。
_BASELINE_LONG_AGE_SEC = 14400.0
_SNAPSHOT_PATH = "/app/tmp/anr_history.json"
_SNAPSHOT_MIN_INTERVAL_SEC = 60.0


_RESET_MARK = "/app/tmp/anr_history.reset"


class _Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._d: dict[str, deque[tuple[float, float]]] = {}
        self._last_snap = 0.0
        self._seen_reset = 0.0

    def _sync_reset(self) -> None:
        """跨行程的清除。

        2026-08-27:時間軸是獨立行程,它呼叫 reset() 只清得掉自己的記憶體;
        web worker 各有一份,原封不動。於是「清場」之後觀測面仍帶著上一場的樣本,
        而且因為那些樣本夠舊,長窗基準算得出 0.0 —— 本該是 null(沒有歷史)。
        `0` 與 `null` 在這裡差別很大:baselineLong=0 會讓「current ≫ 長窗基準」
        恆真,慢性病灶那一支永遠走不到,而且不會報錯。
        用一個標記檔傳遞清除:誰清都寫時戳,各行程在讀寫前比對自己看過的時戳。
        """
        import os as _o
        try:
            m = _o.stat(_RESET_MARK).st_mtime
        except OSError:
            return
        if m > self._seen_reset:
            self._d.clear()
            self._last_snap = 0.0
            self._seen_reset = m

    def observe(self, key: str, value: float, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        with self._lock:
            self._sync_reset()
            dq = self._d.get(key)
            if dq is None:
                dq = self._d[key] = deque(maxlen=_MAX_SAMPLES)
            fresh = not (dq and (now - dq[-1][0]) < _sample_interval())
            if fresh:                       # 節流:同一窗內只留第一筆
                dq.append((now, float(value)))
        # 落盤的節流獨立於取樣的節流:一次 indication 會依序 observe 幾十個鍵,
        # 若只在「有新樣本」時落盤,同一批的第一個鍵寫完就把後面全擋掉,
        # 快照會缺鍵直到下一個 5 分鐘窗。
        self._maybe_snapshot(now)

    def trend(self, key: str, current: float) -> list[float]:
        with self._lock:
            dq = self._d.get(key)
            vals = [v for _t, v in dq][-_WINDOWS:] if dq else []
        # 不足六窗補當前值(舊→新);避免剛啟動時被讀成「從 0 爬升」
        while len(vals) < _WINDOWS:
            vals.insert(0, round(float(current), 3))
        return [round(v, 3) for v in vals]

    def baseline(self, key: str, current: float, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._d.get(key)
            if not dq:
                return round(float(current), 3)
            scale = _sample_interval() / 300.0
            old = [v for t, v in dq if (now - t) >= _BASELINE_AGE_SEC * scale]
            if old:
                return round(statistics.median(old), 3)
            return round(dq[0][1], 3)       # 還沒有夠舊的 → 用最舊一筆

    def baseline_long(self, key: str, now: float | None = None) -> float | None:
        """長窗基準 —— 沒有夠舊的樣本就回 None,**不回 0、也不退回當前值**。

        短窗基準在樣本不足時退回當前值(讓判準有東西可用);長窗刻意不這樣做,
        因為它的用途正是「跟短窗比對」——若也退回當前值,兩個基準就永遠相等,
        那個比對就失去意義,而且會安靜地失去,沒有人看得出來。
        """
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._d.get(key)
            if not dq:
                return None
            scale = _sample_interval() / 300.0
            old = [v for t, v in dq if (now - t) >= _BASELINE_LONG_AGE_SEC * scale]
        return round(statistics.median(old), 3) if old else None

    # ── 落盤 ────────────────────────────────────────────────────────────
    # 為什麼需要:樣本原本只存在記憶體,CU 一重啟就全部歸零,基準的「歷史」
    # 於是只回溯到上次重啟。2026-08-26 第 6 題實錄:CU 15:33 重啟,RIC 16:20
    # 讀到 baselinePct=100 —— 當下我方歸因為「病灶持續 40 分鐘把 30 分鐘的
    # 基準窗填滿」,查證後**是錯的**:短窗基準取的是 30 分鐘以前「所有」樣本的
    # 中位數(最多回溯 24 小時),40 分鐘的病灶蓋不過一整天的正常樣本。
    # 真正的原因是重啟把歷史清空,剩下的 47 分鐘樣本剛好整段都在病中。
    # 結論不變(長期病灶會污染基準),但機制不同 —— 而機制決定修法:
    # 要修的是歷史的存活期,不是基準窗的長度。
    def _maybe_snapshot(self, now: float) -> None:
        if (now - self._last_snap) < _SNAPSHOT_MIN_INTERVAL_SEC:
            return
        self._last_snap = now
        import json, os, tempfile
        with self._lock:
            data = {k: list(v) for k, v in self._d.items()}
        try:
            os.makedirs(os.path.dirname(_SNAPSHOT_PATH), exist_ok=True)
            # 先寫暫存再改名:重啟時序不巧的話,半寫的檔會讓整段歷史讀不回來
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_SNAPSHOT_PATH))
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp, _SNAPSHOT_PATH)
        except OSError:
            pass          # 落盤失敗不該影響觀測面

    def load_snapshot(self, now: float | None = None) -> int:
        """啟動時把歷史讀回來,順手丟掉超過 24 小時的樣本。回傳復原的鍵數。"""
        import json
        now = now if now is not None else time.time()
        try:
            with open(_SNAPSHOT_PATH) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        with self._lock:
            for k, pairs in data.items():
                keep = [(float(t), float(v)) for t, v in pairs
                        if (now - float(t)) < _MAX_SAMPLES * _sample_interval()]
                if keep:
                    self._d[k] = deque(keep[-_MAX_SAMPLES:], maxlen=_MAX_SAMPLES)
                    n += 1
        return n

    def reset(self) -> None:
        import os as _o
        with self._lock:
            self._d.clear()
            self._last_snap = 0.0
            try:
                _o.makedirs(_o.path.dirname(_RESET_MARK), exist_ok=True)
                with open(_RESET_MARK, "w") as f:
                    f.write(str(time.time()))
                self._seen_reset = _o.stat(_RESET_MARK).st_mtime
            except OSError:
                pass
            # 快照也要一起清,否則行程重啟又把舊樣本讀回來
            try:
                _o.remove(_SNAPSHOT_PATH)
            except OSError:
                pass


_store = _Store()
_store.load_snapshot()


def get_store() -> _Store:
    return _store


def metric(key: str, current: float | None, unit: str) -> dict[str, Any]:
    """把一個純量包成 v10 的指標物件。

    unit ∈ {PerMin, Pct, Mbps, Mbit, Ms} —— v10 的鍵名字尾隨單位變化
    (currentPerMin / currentPct / currentMbps / currentMbit / currentMs),
    速率語意的定義域由頂層 granularityPeriod 給定。
    """
    if current is None:
        current = 0.0
    cur = round(float(current), 3)
    _store.observe(key, cur)
    return {
        f"current{unit}": cur,
        f"baseline{unit}": _store.baseline(key, cur),
        # 可能是 None(JSON null)= 尚無 4 小時歷史,見檔頭 null 語意
        f"baselineLong{unit}": _store.baseline_long(key),
        "trendLast30Min": _store.trend(key, cur),
    }
