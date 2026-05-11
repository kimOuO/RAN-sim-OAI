# KPM 欄位筆記 — 計算公式 + 流量/移動關聯

| 文件 | 用途 |
|:---|:---|
| 對象 | spec `intents-interface.md §2` 列出的 KPM fields |
| 範圍 | sim 端如何算 + 哪些因子驅動數值跳動 |
| 更新時間 | 2026-05-11 |

---

## 0. 整體 KPM 流向

```
UE 位置 (Omniverse Kit / setup_multi_ue)
  ↓
RU dl_tti_pipeline → 呼 Physics_sim Sionna ray-trace
  ↓
Sionna 算 path_gain per (UE × TX cell), AK7 後 per-cell granularity
  ↓
RU 算 RSRP / SINR → CqiIndication 送 DU
  ↓
DU tick_runner (每 500ms 1 tick):
  ① RLC.buffer_status() 收 BO
  ② SINR → MCS (mcs_controller IIR filter)
  ③ MCS + PRB allocation → TBS budget
  ④ RLC.generate_pdu(budget) → actual drained bytes
  ⑤ HoL delay sample 從 segmenter
  ⑥ 累計到 pm_aggregator (per-UE window)
  ↓
每 5 tick (~2.5s): flush_ue_report()
  → 計算 window average / sum, reset window
  → MeasurementLog DB insert
  → F1AP measurement_report POST 給 CU
  ↓
CU kpm_reporter.read():
  → 取 latest MeasurementLog per UE
  → 組 ue_status[] 給 e2adapter
  ↓
e2adapter 按 cell 分組 → 編 E2SM-KPM Indication → SCTP 給 RIC
```

---

## 1. RRU.PrbTotDl — DL PRB 使用率 %

### 公式
```python
# DU pm_aggregator.py:85
avg_prb_dl = prb_dl_sum / samples   # window 內平均

# CU kpm_indication.py:45-47
RRU.PrbTotDl = (avg_prb_dl / 273.0) * 100.0
```
273 = 100 MHz BW, SCS=30 kHz 的 PRB 數 (3GPP TS 38.101 Table 5.3.2-1)

### 計算來源
- **DU pf_scheduler.py:49-82** 用 PF (Proportional Fair) 算法分配 PRB:
  ```
  ue_weight = inst_rate / avg_rate    (instantaneous over average)
  rb_alloc[ue] = n_prb_total × ue_weight / sum_weights
  ```
- **PRB quota cap**: xApp 透過 Style 2/6 set_prb_quota 設 `max_prb` (%), DU scheduler 把 `n_prb_total` 預先乘上 cap_factor

### 影響因素
| 因子 | 怎麼影響 |
|:---|:---|
| UE SINR | SINR 高 → MCS 高 → inst_rate 高 → PF weight 高 → 拿更多 PRB |
| UE buffer (BO) | RLC queue 有東西才被算進 ues_with_bo, scheduler 才分 PRB 給它. idle UE 不分. |
| 同 cell 上 UE 數量 | 4 UE × 68 PRB ≈ 270 (拿滿). 9 UE × 30 PRB ≈ 270 (也拿滿). PF 公平分 |
| xApp PRB quota cap | max_prb=50% 直接砍一半 capacity |
| UE 位置 (透過 SINR) | 位置變 → ray-trace path_gain 變 → SINR 變 → 上面那條鏈 |

### 為什麼會跳動
- **UE 移動** → Sionna 重算 path_gain → SINR 波動 ±5 dB → MCS jump → PF weight 重排
- **Fast fading** (sionna_engine.py:273-278) 每 tick 隨機相位旋轉, 即使 UE 不動 SINR 也會 ±2 dB
- **Traffic 不均** → 某 UE 突然有 burst → BO 升 → PF 把 PRB 偏向它
- **新 UE 進來 / 出去 (HO)** → PF 重新公平分配

---

## 2. RRU.PrbTotUl — UL PRB 使用率 %

### 公式 (synthetic, 不準)
```python
# DU tick_runner.py:332
prb_ul = rb_alloc[ue_id] // 5  # 寫死 1/5 比例
```

### 為什麼**永遠不準** (spec 自己標 "rfsim 常 0")
- **UE container 沒 UL traffic generator** — UE 只 inject_sdu (DL 方向)
- **DU 沒 UL scheduler** — tick_runner 不收 UL entities
- **synthetic 1/5 比例 hard-coded**, 不是真實量測

### 不影響 3 case 觸發
所有 IM / CCO / ES strategy 都看 DL field, UL 是 spec extension scope。

---

## 3. DRB.UEThpDl — DL Throughput per UE (kbps)

### 公式
```python
# DU pm_aggregator.py:87
throughput_dl_mbps = (dl_bytes_sum * 8) / window_seconds / 1e6
# CU kpm_indication.py:29-30 轉 kbps: × 1000
```

`dl_bytes_sum` = window 內 RLC `generate_pdu()` 回的「真實 drained bytes」(AK3 後對齊 OAI dlsch_total_bytes).

### 真實 drain 怎麼來的
```python
# DU tick_runner.py:255-275
for ue in ues_with_bo:
    budget = tbs_map[uid]   # MCS + PRB 算出的 TBS 預算
    actual = rlc_entity.generate_pdu(budget)
    actual_drained_map[uid] = actual
```
`actual ≤ budget` 因為:
- RLC buffer 可能不夠裝滿 budget (低 demand UE)
- Segmenter header overhead (AM 3 bytes/PDU)
- 退避 mechanism (status PDU, retx)

### 影響因素
| 因子 | 怎麼影響 |
|:---|:---|
| MCS | SINR 17 dB → MCS 22 → bps_re 4.5 → 高 throughput |
| PRB allocation | PF 分多少 PRB 給這個 UE |
| UE demand | UE 沒灌 traffic → buffer 空 → drain 0 → thp 0 |
| Cell 內共享 | 13 UE 擠 c0, cell 容量 ~100 Mbps, 每人 ~7.7 Mbps |

### 為什麼跳動
- **UE 移動**: 位置變 → SINR 變 → MCS 跳 (e.g. MCS 22 → 16 throughput 降 30%)
- **Traffic 變化**: UE 從 idle 變 active, BO 從 0 變 high, thp 從 0 起跳
- **Cell 上其他 UE**: 新 UE attach 增加分母, 每人 throughput 降; HO 走的話增加
- **xApp 套 PRB cap**: max_prb 從 100 → 50, throughput 直接砍半

---

## 4. DRB.UEThpUl — UL Throughput per UE

### 同 RRU.PrbTotUl, synthetic
```python
# DU tick_runner.py:334
ul_bytes = actual_dl // 5
```
不是真量測, 不影響任何 case。

---

## 5. DRB.RlcSduDelayDl — RLC SDU 延遲 (ms)

### 公式
```python
# DU segmenter.py:55-58 — SDU fully delivered (bytes_remaining=0) 時 emit
if item.bytes_remaining == 0:
    if item.enqueue_ts_ms:
        delivered_delays.append(now_ms - item.enqueue_ts_ms)

# DU pm_aggregator.py:94-97 — window 平均
rlc_sdu_delay_dl_ms = sum(samples) / len(samples) if samples else 0.0
```

對齊 3GPP TS 28.552 DRB.RlcSduDelayDl 語意 — "SDU 從進 MAC buffer 到完全 deliver 出去的時間"。

### 影響因素
| 因子 | 怎麼影響 |
|:---|:---|
| RLC buffer 大小 | buffer 6 GB → 排隊很久 → delay 60 秒+ |
| Drain rate | drain 越慢 (低 MCS / 少 PRB), delay 越長 |
| SDU 大小 | sim UE 一次 inject 3-10 MB (累計 tick 量), drain 30 KB/tick → 一顆 SDU 需 ~130 tick (~65s) |
| UE 數量分享 | 共享 cell, 每人分到的 PRB 越少, drain 越慢 |

### 為什麼會看到「秒級」delay 而非「毫秒級」
這是 sim 結構性問題:
- 真實 5G: PDCP packet 1500 byte, MAC 1 tick 就能 drain → delay ms 級
- 我們 sim: UE container 為了減 HTTP 開銷, 把整個 tick 該注的 byte 包成 1 個大 SDU → 「邏輯 SDU」是 MB 級
- 加上偶爾 PRB cap 期間 drain 慢, buffer 累積 GB 級 → head SDU wait 數十秒
- **本身語意對 (對齊 spec), 數值大小不真實**

### 為什麼會跳動
- **Inject rate vs drain rate 不平衡**: inject > drain → buffer 累積 → delay 升; drain > inject → buffer 減 → delay 降
- **HO 後**: UE 換 cell, RLC 重建 → delay 重設 0
- **SINR 突降**: MCS 降, drain 降, buffer 累積, delay 暴升

---

## 6. DRB.PdcpSduVolumeDL — DL 累計傳輸量 (bytes)

### 公式
```python
# DU pm_aggregator.py:91 — window 內累計 (flush 後 reset)
pdcp_sdu_volume_dl = dl_bytes_sum
```
跟 DRB.UEThpDl 用同個 `dl_bytes_sum`, 只是不除時間。Window 大小 ~2.5 sec。

### 影響因素 / 跳動原因
跟 DRB.UEThpDl 完全一樣 (drain rate × 2.5 sec window)。

### 為什麼 spec 把它跟 PRB 一起當 ES 主指標
- vol 量「cell 真的有沒有送 traffic」, 比 PRB 更直接
- Cell 可能 PRB 很高 (idle UE measurement-only) 但 vol 是 0 (沒真 data)
- ES 兩條件同時 (PRB+vol 都低) 才算「真的閒」

---

## 7. DRB.PdcpSduVolumeUL — UL 累計傳輸量

同 ThpUl, synthetic 1/5 DL, 不準, 沒 case 用到。

---

## 8. (Bonus) rsrp_dbm / sinr_db / mcs_dl — Per-UE 量測 (A3/CQI 用)

### RSRP 公式
```python
# RU dl_tti_pipeline.py:97-113
RSRP = TX_power_dBm (23) + antenna_gain_dBi (14) + 10*log10(path_gain_linear) - scene_loss_dB (50)
```
- `path_gain_linear` 從 Sionna ray-trace 回的 per-(UE, TX cell) 值 (AK7 後 per-cell)

### SINR 公式
```python
# RU dl_tti_pipeline.py:297-301 (簡化)
SINR = sinr_estimator(channel_matrix H, noise_floor=-95 dBm)
SINR -= 20  # interference penalty (沒 model 真實 cell 間干擾, 一律扣 20 dB)
```

### MCS 公式
```python
# DU mcs_controller (IIR filter, link adaptation)
mcs_ctl.update(ue_id, sinr_db, timestamp)
mcs = mcs_ctl.get_mcs(ue_id)
# 然後 sinr_to_mcs(sinr_db) → (mcs_idx, bps_re) 查 _SINR_TO_MCS table
```

### 為什麼跳動
- **UE 位置**: Sionna 每 tick 重新 ray-trace, 不同位置 path_gain 不同
- **Fast fading**: 即使位置不動, 多徑相位每 tick 隨機 → SINR ±2 dB
- **Beam pattern**: UE 在 cell 主波束內 vs 側波束 vs 背面, RSRP 差 20 dB+
- **Building shadowing**: scene 裡有建築物時 ray-trace path 會被遮擋

---

## 9. 大局 — 流量 / UE 移動 → KPM 因果鏈

```
UE 位置變化
   ↓ (Sionna ray-trace 重算)
path_gain_linear 變
   ↓
RSRP / SINR 變
   ↓
MCS 變 (透過 mcs_controller IIR 平滑)
   ↓
TBS_per_tick = f(MCS, PRB) 變
   ↓
RLC drain rate 變 (actual_drained_map)
   ↓
若 drain < inject: buffer 累積 → vol 不變 (cap 在 drain rate) + delay 暴升
若 drain ≥ inject: buffer 消化 → vol = inject rate, delay 穩定低

Traffic profile 變化 (idle ↔ cbr 30 Mbps):
   ↓
inject rate 變
   ↓
buffer 累積/消化速度變
   ↓
vol / thp / delay 都跟著變

UE attach / detach / HO:
   ↓
cell 內 UE 數量變
   ↓
PF scheduler 重新分 PRB
   ↓
每個 UE 的 PRB allocation 變
   ↓
個別 UE 的 thp / vol / delay 都被影響
```

## 10. 觀察點建議

跑 demo 看 KPM 數據不對勁時, 順序檢查:

1. **UE 位置對嗎?** `docker exec ransim-ue curl /UE/Status/read` 看 position
2. **SINR 合理嗎?** `CU /E2/E2KpmReporter/read` 看 sinr_db, 應該 0~20 dB
3. **MCS 跳哪?** DU log "DRAIN TRACE" 有 mcs=
4. **PRB allocation 對嗎?** CU KPM rb_width_dl, 加總應該 ≈ 273 (或 cap × 273)
5. **Drain 正常嗎?** `docker exec ransim-du curl /RLC/RlcDataController/read_buffer_status` 看 buffer 是不是死卡
6. **Inject 有嗎?** `docker exec ransim-ue curl /UE/Status/read` 看 injected_sdu_count 有沒有跳

任一層怪了, 順著鏈反推回去通常能找到 root cause。
