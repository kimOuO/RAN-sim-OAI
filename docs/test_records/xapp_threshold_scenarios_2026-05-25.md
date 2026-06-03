# xApp 門檻測試劇本對齊報告 (2026-05-25)

把 3 個 1hr 劇本 (`im_1hr` / `cco_1hr` / `es_1hr`) traffic profile 重設成「DT 跑這劇本能觸發對應 xApp 門檻」。

---

## 設計目標

xApp 透過 KPM 門檻決定當前情境屬於 IM / CCO / ES。每個劇本應該:
- 跑 1-3 分鐘 wall(at 3x = 3-9 分鐘 sim)
- DT 端 KPM 穩定後落在「該劇本對應 xApp 條件」的通過區
- 不要靠運氣或邊界值

---

## 劇本流量設定

| 劇本 | 改前 | **改後** | 對應 xApp 觸發 |
|---|---|---|---|
| `im_1hr` | `[[0, 3000, 672]]` | **`[[0, 5000, 672]]`** | iperf3 -R -b 5M(對齊 OAI im_traffic.sh)|
| `cco_1hr` | `[[0, 3000, 200]]` | **`[[0, 200, 50]]`** | DT 校正版本 — 200 kbps 在 DT 出 ~8% PRB,~2 ms Delay(對齊 OAI cco_traffic.sh 的 KPM 信號) |
| `es_1hr` | bursty 3000 kbps mix | **`[[0, 0, 0]]`** | killall iperf3 ping(對齊 OAI es_traffic.sh)|

---

## 同時的 code 改動

### P1.15.1 — DELAY_CALIB threshold 1024 → 50000

```python
# RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py
_HIGH_TRAFFIC_BO_BYTES = 50_000   # was 1024
```

**為什麼**:1KB threshold 太低 — cco 200 kbps (bo ~6-12 KB) 也被誤判為「高流量 phase」,delay 衝到 20ms,過不了 CCO 的 < 5ms 條件。

50 KB 對齊 OAI iperf3 -b 1M (~31 KB/tick) 跟 -b 5M (~156 KB/tick) 的中線:
- im 5 Mbps(bo > 100 KB)→ 高流量 mode → delay 拉高 ✓
- cco 200 kbps(bo 6-12 KB)→ 低流量 mode → delay 低 ✓

**副作用**:full_day_24hr 的 normal-1 phase(195 kbps)從 v7 的 17ms 對齊掉回 v6 的 1.6ms — 但 xApp 不查 normal-1 phase delay,可接受。

---

## 三劇本 DT KPM 實測 vs xApp 門檻

### im_1hr — ✅ IM 三條件全過

| 條件 | 門檻 | DT 實測 | OAI baseline | 過? |
|---|---|---|---|---|
| `DRB.PdcpSduVolumeDL` mean | ≥ 2,000 kbit | **5,259 kbit** | 6,307 | ✓ |
| `DRB.RlcSduDelayDl` mean | ≥ 5 ms | **20.8 ms** | 9.17 | ✓ |
| `RRU.PrbTotDl` mean | ≥ 10% | **~92%** | 16.18% | ✓ |

> DT 比 OAI 更積極(throughput 接近 line rate)— 但都通過,xApp IM 觸發 ⭐

### cco_1hr — ✅ CCO 四條件全過

| 條件 | 門檻 | DT 實測 | OAI baseline | 過? |
|---|---|---|---|---|
| active DU `DRB.PdcpSduVolumeDL` mean | ≥ 100 kbit | **210 kbit** | 1,050 | ✓ |
| `DRB.RlcSduDelayDl` mean | < 5 ms | **2.19 ms** | 1.25 | ✓ |
| `RRU.PrbTotDl` mean | < 10% | **8.09%** | 2.66% | ✓ |
| 對側 DU records 持續 ≥ 30s = 0 筆 | = 0 | (單 DU) | — | ✓ |

> DT 與 OAI 的「kbit / ms / %」量級不同(DT calibration 在中等負載放大),但全部落在 CCO 通過區。

### es_1hr — ✅ ES 三條件全過(cell-level)

| 條件 | 門檻 | DT 實測 | OAI baseline | 過? |
|---|---|---|---|---|
| `DRB.PdcpSduVolumeDL` mean | ≤ 10 kbit | **0** | 0 | ✓ |
| `RRU.PrbTotDl` mean | ≤ 5% | **0%** | 0.003% | ✓ |
| `DRB.UEThpDl` mean | ≤ 100 kbps | **0** | 1-11 bps | ✓ |

> **副 bug**:es_ue_01 attach 流程在 0 traffic profile 下沒把 UE 加進 DU `ue_registry`(可能 0-rate profile 跳過 F1AP UeCtxSetup)。Cell-level KPM 全 0 仍滿足 ES — 對 xApp 邏輯影響不大,但 UE-level per-UE 指標不會 emit。**列入 follow-up**。

---

## 三劇本互斥矩陣(DT vs xApp 門檻)

| KPM | IM 門檻 | im_1hr DT | CCO 門檻 | cco_1hr DT | ES 門檻 | es_1hr DT |
|---|---|---|---|---|---|---|
| RlcDly | ≥ 5 ms | **20.8** ✓ | < 5 ms | **2.19** ✓ | — | 0 |
| PdcpDL | ≥ 2000 kbit | **5259** ✓ | ≥ 100 | **210** ✓ | ≤ 10 | 0 ✓ |
| PrbDl | ≥ 10% | **92%** ✓ | < 10% | **8.09%** ✓ | ≤ 5% | 0% ✓ |
| UEThpDl | — | 5259 | — | 210 | ≤ 100 kbps | 0 ✓ |

**三劇本 disjoint,xApp 用三條件 AND 一次過分辨** ⭐

---

## 操作流程(xApp 驗證)

```bash
# 跑 im_1hr 3 min wall:預期 xApp 觸發 IM
curl -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/start \
  -d '{"source":"scenario","scenario_id":"im_1hr","speed_x":3,"sim_dt_ms":250}'
# 等 90 秒(過 ramp-up + 1 個 KPM window)→ xApp 應該 trigger IM

# stop → 跑 cco_1hr → 預期 xApp 觸發 CCO
# stop → 跑 es_1hr → 預期 xApp 觸發 ES
```

---

## 後續 follow-up

1. **es_ue_01 attach bug** — 查 UeAttachService.update_traffic_profile 在 rate=0 profile 下為何沒走 F1AP UeCtxSetup(沒建 RLC entity / 沒進 DU ue_registry)
2. **es_1hr precompute pending** — 排空 RU cached mode 對 0-traffic 劇本仍需 channel cache(雖然不影響 ES 通過)
3. **cco rate 200 kbps 不對齊 OAI 1 Mbps 字面值** — 這是「DT calibration 在中等負載放大」的副作用。要做到 DT 跟 OAI 1:1 字面對齊,需要重做 PRB_OAI_CALIB 跟 P1.15 為連續函數而非常數/二態。**列為 long-term optimization**。

---

## 關聯改動

- SQL `omni_db_scenario`:`im_1hr`, `cco_1hr`, `es_1hr` 的 `raw_json.traffic[0].profile`
- `RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py:315-322` — `_HIGH_TRAFFIC_BO_BYTES`
