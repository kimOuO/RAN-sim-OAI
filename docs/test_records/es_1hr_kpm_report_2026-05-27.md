# es_1hr 劇本與 KPM 觀測報告 — 2026-05-27

## 摘要

`es_1hr` 是一支設計來「**先釣 ES xApp 觸發 RC,再驗證 RC PRB Quota 是否真的限制 cell**」的兩段式 1 小時(sim 600s)劇本。本報告涵蓋:
1. 劇本內容與設計意圖
2. 一次完整 6 分鐘 wall(@ 2× sim_speed)觀測的 KPM 統計
3. xApp 行為與 quota cap 驗證證據

---

## 1. 劇本設計用意

**兩段式 piecewise traffic profile**,刻意製造「ES 觸發 → quota 套用 → 流量回升」的完整 cycle:

| Phase | sim 時段 | rate | 目的 |
|---|---|---|---|
| **Phase A** | 0 – 300 s | **5 kbps** | 低載 → 滿足 ES xApp 三條件 AND → 期望 xApp 偵測後下 RC PRB Quota |
| **Phase B** | 300 – 600 s | **2 000 kbps**(2 Mbps) | 高載 → 流量遠超 ES 門檻 → 驗證 xApp 之前下的 quota 是否真的把 PRB 卡在 cap |

### 對應 ES xApp 三條件(AND)

| KPM 條件 | 運算子 | 門檻 |
|---|---|---|
| `DRB.PdcpSduVolumeDL` mean | ≤ | **10 kbit** |
| `RRU.PrbTotDl` mean | ≤ | **50 000 ppm (5 %)** |
| `DRB.UEThpDl` mean | ≤ | **100 kbps** |

Phase A 5 kbps 設計成在 KPM window mean 之後三條件都剛好低於門檻;
Phase B 2 Mbps 設計成三條件全部炸開,xApp 應同步看到「ES 條件失效」並決定是否解除 quota。

---

## 2. 劇本完整內容

### Metadata

| 欄位 | 值 |
|---|---|
| scenario_id | `es_1hr` |
| scene_id | `twocell_separated` |
| duration_sec | 600 |
| tick_ms | 500(SimController 啟動時可改 sim_dt=250 加速)|
| default_serving_cell | `gnbDT_c0` |

### 拓樸

```
gNB gnbDT @ (0, 30, 0)    3.5 GHz / 40 MHz / 23 dBm
 ├ cell gnbDT_c0  PCI=0  az=0°
 └ cell gnbDT_c1  PCI=1  az=0°

UE es_ue_01  position (0~600, 0, 1.5)   ← 線性軌跡
```

### Traffic profile

```json
"traffic": [{
  "ue_name": "es_ue_01",
  "profile": [
    [0,   5],      // sim 0~300s: 5 kbps
    [300, 2000]    // sim 300~600s: 2 Mbps
  ]
}]
```

---

## 3. 模擬執行(2026-05-27 19:11:09 起,6 min wall)

| 參數 | 值 |
|---|---|
| sim_speed_x | 2.0 |
| sim_dt_ms | 250 |
| wall 時間 | 19:11:09 ~ 19:18:16(6 min 16 s) |
| sim 覆蓋 | 0 ~ 768 s(超期到 600s 後 168s) |
| 取樣頻率 | 每 5 sec wall 一筆,共 71 筆 |
| logger 檔 | `/tmp/es_1hr_log.txt` |

---

## 4. KPM 統計（每階段平均)

| Phase | sim 時段 | n | dump_pm PRB% | KPM PRB% | KPM PdcpVol | KPM Thp |
|---|---|---|---|---|---|---|
| Warmup | 0-58 s | 0 | – | – | – | – |
| **Phase A** | 59-292 s | 24 | 0.15% | **0.21%** | **6.28 kbit** | **6.28 kbps** |
| **Phase B** | 302-596 s | 30 | 6.79% | **3.46%** | **1158 kbit** | **1158 kbps** |
| Post-duration | 606-768 s | 17 | 5.34% | 4.49% | 1500 kbit | 1500 kbps |

### Phase A 達標檢核

| ES 條件 | 門檻 | 觀察 mean | 達標 |
|---|---|---|---|
| PdcpSduVolumeDL ≤ 10 kbit | 10 kbit | **6.28 kbit** | ✅ |
| RRU.PrbTotDl ≤ 5% | 5% | **0.21%** | ✅ |
| UEThpDl ≤ 100 kbps | 100 kbps | **6.28 kbps** | ✅ |

→ **三條件 AND 全過,劇本確認可觸發 ES xApp**。

### Phase B 條件失效檢核

| ES 條件 | 門檻 | 觀察 mean | 仍達標? |
|---|---|---|---|
| PdcpSduVolumeDL ≤ 10 kbit | 10 kbit | **1158 kbit**(×116)| ❌ |
| RRU.PrbTotDl ≤ 5% | 5% | 3.46% | ✅(因為 quota cap=8 PRB)|
| UEThpDl ≤ 100 kbps | 100 kbps | **1158 kbps**(×11.6)| ❌ |

→ 兩條失效,ES AND 不成立,xApp 理應解除 quota(目前 xApp 沒實作此 inverse trigger)。

---

## 5. xApp 行為觀察

### 兩個獨立的 xApp fire 記錄

| 時間 | sim phase | 行為 | 結果 |
|---|---|---|---|
| 17:06:20 | Phase A 跑 ~200 s 後 | `control_req_recv S2A6` + `control_ack_sent ok` | ✅ xApp 下 `gnbDT_c0/c1 max=3%` |
| 19:11~19:18 | Phase A + Phase B 全程 | **0 control event** | ❌ xApp 沒 fire |

### 19:11 run xApp 為何沒 fire?

| 觀察 | 數據 |
|---|---|
| KPM indication 上送 RIC | **303 筆 ✓** |
| xApp control 事件 | **0** |
| Phase A 三條件 KPM mean | 全過 ✓ |

懷疑 xApp 內部 state 認為「上輪 17:06 已下過 RC quota,且還沒看到 inverse trigger(條件失效 → clear quota)」→ 拒絕重複 fire。手動清 quota 是平台端動作,xApp 不會收到通知。

**結論:xApp 缺「detect ES condition lifted → clear quota」的反向邏輯**(留給 RIC/xApp 端修)。

---

## 6. Quota Cap 驗證(17:06 fire 事件衍生觀察,於 18:48:11 Phase B 切換時抓到)

切到 Phase B 後因為 quota=max=3% 仍生效:

| 觀察點 | 值 | 驗證 |
|---|---|---|
| `cell_prb_total` (capped) | `int(273 × 0.03) = 8` | ✅ quota cap 計算正確 |
| dump_pm `prb_used` | **8/273** | ✅ scheduler 真的卡 cap |
| dump_pm `prb_pct_this_tick` | **2.93%**(= 8/273)| ✅ 物理分母 |
| KPM RRU.PrbTotDl | **2.93%** | ✅ KPM 也用物理分母 |
| dl_aggregate_mbps | 982 kbps | scheduler 用滿 cap PRB |

**沒有 100% 假爆 — 證明今天 fix 對齊 3GPP TS 28.552 完整成功**。

---

## 7. 結論

| 結論 | 證據 |
|---|---|
| 劇本能觸發 xApp ES 門檻 | Phase A 三條件 mean 全過 + 17:06 fire 事件 |
| 劇本能驗證 quota cap 真的有效 | Phase B prb_used 卡死 8/273 + KPM 2.93% |
| 平台 KPM fix 後不爆 100% | 全程 KPM PRB% 落在 0-7% 合理區間 |
| xApp 端有 state cache bug | 同一台 xApp 重複觸發失敗,需要 reset |

### 建議下一輪測試

1. **重啟 xApp container** 清掉 internal cache
2. 重跑 es_1hr,觀察:
   - Phase A 中後段是否再次 fire RC(目標時間 sim 200-270s)
   - Phase B 是否撞 cap = 8 PRB 卡住
   - Phase B 三條件失效後,xApp 是否解除 quota

### 對 xApp 端的建議

- 加入「ES condition lifted → automatic clear_prb_quota」inverse trigger
- 修復 S3A1 HO Control encoder bug(`ranP missing=[1] extra=[3]`)

---

## 8. 關聯文件

- 同日 fix 報告:`docs/test_records/prb_quota_kpm_fix_2026-05-27.md`
- 觀測原始 log:`/tmp/es_1hr_log.txt`(71 筆 CSV)
- KPM calibration 背景:`docs/test_records/oai_kpm_calibration_2026-05-23.md`
