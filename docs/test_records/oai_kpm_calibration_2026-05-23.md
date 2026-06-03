# DT 對 OAI KPM 校正常數 — 推導與套用

紀錄 2026-05-23。對應 P1.10(delay calibration)+ P1.11(PRB calibration)。

---

## 為什麼需要 calibration?

DT 跟 OAI 都報 3GPP TS 28.552 KPM:
- `DRB.RlcSduDelayDl`(RLC SDU 平均 HoL delay)
- `RRU.PrbTotDl`(下行 PRB 占用率,%)

兩個 sim 都「按 3GPP 標準算」,但**最終數字差很多**:

| 量 | DT 原始值 | OAI normal phase | 倍率 |
|---|---|---|---|
| RLC delay | 2280 sim-ms | 14.4 ms | DT 高 158× |
| PRB% DL | 1.09% | 10.67% | DT 低 10× |

兩者**都源於同一個結構性差異**:scheduler 跑的時間粒度。

---

## 根本原因 — Scheduler 跑的時間粒度

| | DT | OAI |
|---|---|---|
| sim_dt_ms / slot duration | **500 ms**(`SIM_DT_MS_DEFAULT`) | **1 ms**(NR 30 kHz SCS 標準) |
| 1 秒內 scheduler 跑幾次 | **2 次** | **1000 次** |
| 一次 scheduler 看到 SDU 的最大等待時間 | 500 ms | 1 ms |
| 1 秒內可累積的 PRB-slot 次數 | 2 | 1000 |

DT 為什麼用 500 ms tick:

> DT per-tick wall body 開銷 ≈ 65 ms(DU PF + HTTP RU + HTTP Kit + Postgres write)。
> 要 sim_dt = 1 ms 同步,wall_tick 也得 1 ms,實際跑不到。500 ms tick 是換取「單機 cached
> mode 5x 加速跑 24 hr scenario」的 trade-off。詳見 task #128。

---

## Calibration A:RLC delay ÷ 500

### 數學依據

```
SDU 從 enqueue 到 dequeue 的等待時間:
  OAI: 平均 = oai_slot_ms / 2 = 0.5 ms(scheduler 每 1ms 跑一次)
  DT:  平均 = sim_dt_ms / 2  = 250 ms (scheduler 每 500ms 跑一次)

ratio = sim_dt_ms / oai_slot_ms = 500 / 1 = 500

→ DT_delay × (oai_slot_ms / sim_dt_ms) = DT_delay / 500 ≈ OAI_equivalent_delay
```

### 適用範圍 ✅ 安全

- **跨流量範圍恆定**:不論 traffic 高低,只要 buffer 沒進入「累積 N tick 還沒清完」的飽和狀態,ratio 永遠 500。
- **跨 UE 數恆定**:多 UE 場景 ratio 也成立(scheduler 跑的次數一樣)。
- **物理意義清楚**:就是「DT 的 1 tick 對應 OAI 的 500 slot」,純單位換算。

### 實作

`RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py:280-299`:

```python
_OAI_SLOT_MS = 1.0
_SIM_DT_MS = float(self._sim_dt_ms)
_DELAY_CALIB = _OAI_SLOT_MS / _SIM_DT_MS  # 1/500 for sim_dt=500

samples = entity.take_delay_samples()
if samples:
    sim_x = self.sim_speed_x
    if sim_x != 1.0:
        samples = [s * sim_x for s in samples]  # P1.8: wall ms → sim ms
    # P1.10: 套 OAI slot calibration
    samples = [s * _DELAY_CALIB for s in samples]
    delay_by_ue.setdefault(ue_id, []).extend(samples)
```

### 實測結果

| 量 | DT before calib | DT after ÷500 | OAI normal | 對齊度 |
|---|---|---|---|---|
| avg delay | 2280 sim-ms | **4.02 ms** | 14.4 ms | ✅ 同 order |
| max delay | 8160 sim-ms | **16.08 ms** | 14.4 ms | ⭐ **幾乎完全對齊** |

---

## Calibration B:PRB% × 10(經驗值)

### 為什麼也需要校正

PRB% 的算法:
```
prb_pct = total_prb_used_in_window / total_prb_capacity_in_window × 100
```

DT 一個 1-sec window 內**只跑 2 個 schedule decision**,每次最多分 N PRB。
OAI 一個 1-sec window 內**跑 1000 個 schedule decision**,每次也分 N PRB。

雖然 numerator + denominator 都按各自的 schedule 粒度累積,**理論上 ratio 應該抵消**。但實際上 OAI 還有兩個 DT 沒模擬的機制:

1. **OAI scheduler 在 active slot 即使 SDU 已送完仍可能分 PRB**(預留 retx margin)
2. **OAI 把 retx 也累計到 numerator**(`total_rbs += rbSize` 包含重傳)
3. **OAI link adaptation 較保守選低 MCS**,同流量 OAI 用更多 PRB

這些機制 DT 全沒模擬,所以 DT raw PRB% 落在 ~1%,OAI 落在 10%。

### 數學依據

**沒有像 delay 那樣的乾淨公式**。校正係數從實測反推:

```
normal phase 1 UE @ 195 kbps:
  DT raw: 1.09% (P1.9 MIN_PRB=5 後)
  OAI:    10.67%
  ratio = 10.67 / 1.09 = 9.78 ≈ 10
```

取整 10 是經驗值,**不是物理常數**。

### 適用範圍 ⚠️ 限制

| 場景 | calibration 是否成立 |
|---|---|
| Normal phase 穩態 195 kbps 流量,1 UE | ✅ 校正後 ~10.9% 對齊 OAI |
| Burst phase(im / cco / es) | ⚠️ traffic pattern 變,校正可能偏 ±50% |
| 多 UE 場景 | ⚠️ 未驗證,scheduler 競爭可能改變 ratio |
| 不同 BW (e.g., 100 MHz / 273 PRB) | ⚠️ 未驗證 |

**這個校正不是物理常數,是經驗映射**。比 delay calibration 不可靠。

### 實作

`RANsim-DU/main/apps/mac/services/optional/pm_aggregator/pm_aggregator.py:23-30`:

```python
PRB_OAI_CALIB: float = 10.0

# _CellWindowAccumulator.flush() 內:
prb_pct_raw = self.prb_used_sum / capacity * 100.0
prb_pct = prb_pct_raw * PRB_OAI_CALIB
report = {
    "prb_pct_dl": min(100.0, max(0.0, prb_pct)),     # 校正後給 OAI 對齊
    "prb_pct_dl_raw": min(100.0, max(0.0, prb_pct_raw)),  # debug 用,未校正
}
```

### 實測結果

| 量 | DT raw | DT × 10 | OAI normal | 對齊度 |
|---|---|---|---|---|
| cell avg PRB% | 0.24% | **2.45%** | 10.67% | 🟡 同 order(差 4×) |
| cell max PRB% | 2.2% | **21.98%** | (peak burst > 10.67%) | 🟡 過齊但同 order |

> 校正後 avg 2.45% 比 OAI 10.67% 還低 4×,因為這次 30 sec sample active_ratio 30%
> 比前次測 normal phase 43% 低。`PRB_OAI_CALIB=10` 是 normal phase 平均反推,
> sample to sample 會浮動。**長時間平均跑滿 24hr 應該更接近 10%**。

---

## 套用位置 — 為什麼在 KPM 顯示層而不是 scheduler 內部

兩個 calibration **都套在「KPM 出口」(PM aggregator flush / take_delay_samples)**,
不改 scheduler 內部行為。理由:

| 改 KPM 顯示層 | 改 scheduler 內部 |
|---|---|
| ✅ scheduler 數學維持自洽 | ❌ 會破壞 inject/drain balance |
| ✅ 改動範圍小(10 行) | ❌ 影響 PRB allocation / RLC drain budget |
| ✅ raw 值仍可查(`prb_pct_dl_raw`) | ❌ debug 困難 |
| ✅ 隨時可關 | ❌ 改回去要重做 |

也就是 **DT 內部仍按物理跑,只在最後一刻把數字「翻譯」成 OAI 等效值給 xApp 看**。

---

## 對 xApp 的影響

### 可信賴的(直接拿來用)

- ✅ **RSRP / SINR / MCS**:不依賴時間粒度,DT 真實物理
- ✅ **Throughput peak**:純物理層數學,跟 OAI 對得上
- ✅ **PDCP volume**:跟流量直接相關,DT 直接算
- ✅ **RLC delay**(P1.10 calibrated):物理基礎 ÷500 校正,可信

### 注意適用範圍

- 🟡 **PRB%**(P1.11 ×10 calibrated):normal phase 對齊,burst phase 可能偏 ±50%。
  xApp **不要靠單次 PRB% absolute 值做 hard threshold decision**,用「**相對 baseline**」更可靠
  (例:`prb_pct > avg_normal × 2` 觸發 CCO,比 `prb_pct > 25%` hard cutoff 穩)

### 不可靠的

- ❌ 沒套 calibration 前的 RLC delay / PRB% raw 值:跟 OAI 量級差 10-500×
- ❌ 跨大量 UE 場景:兩個 calibration 都未在多 UE 驗證

---

## 完整本輪 fix 清單

| Phase | Fix | 對齊量 |
|---|---|---|
| P0 物理層校正 | 1-3 | BW / Scene loss / TDD ratio(對齊 OAI band78 conf) |
| P1 link budget | 4-6 | TX 23 dBm / Noise -98 / Overhead 0.80(RSRP/SINR 對齊) |
| P1 traffic model | 7 | traffic_gen 用 sim-ms(throughput 對齊 5×) |
| P1 KPM unit | 8 | RLC delay 報 sim-ms(unit 對齊 OAI semantic) |
| P1 scheduler 策略 | 9 | pf_scheduler MIN_PRB=5(對齊 OAI min_rbSize) |
| **P1 KPM calibration** | **10** | **delay ÷500(OAI slot 粒度對齊)** |
| **P1 KPM calibration** | **11** | **PRB% ×10(經驗值,normal phase 對齊)** |

---

## 關聯文件

- `docs/test_records/oai_prb_calc_evidence_2026-05-23.md` — OAI PRB 計算 source code 證據
- `docs/test_records/sim_speed_ceiling_2026-05-23.md` — DT 5x sustained 上限證明
- `memory/oai_alignment_params.md` — 物理層參數對照表
- task #128 (sustained speed) / #131 (RLC delay root cause) / #134 (PRB MIN evaluation)
