# KPM 零值轉真 × ANR E2 指標補齊 — 統一實作計畫

> 2026-08-11 規劃。輸入:`kpm_field_notes_zero.md`(零值可行性)+ `anr_e2_data_gap.md`(ANR 卷缺口)。
> 兩件事共享同一個樞紐:**RLF / RRC 重建模型** —— 它同時是零值筆記的丙類第一優先,
> 也是 ANR 卷 11 個 ❌ 量測裡 7 個的解鎖鑰匙。因此統一排程,不分開做。
> 原則:只做「真值」(實際量測或由真值運算),不做合成數字;O1 類資料(baseline/trend)不在範圍(xApp 自理)。

---

## 總覽:三期路線

```
P0 快贏期(~1 週):零建模 —— 接線 + 查詢加工 + 場景配置
   └ 產出:零值 →真 8 欄;ANR 卷第 1/3/4/5/9 題資料面可運轉

P1 核心建模期(~1 週):RLF + RRC 重建
   └ 產出:零值 →真 +10 欄;ANR RLF/ReEstab 量測解鎖;平台獲得「掉話」概念

P2 歸因期(~3 天,於 P1 之上):MRO 三聯 + HO 失敗原因
   └ 產出:ANR 全卷 10 題資料面完整;MRO 語意可驗證
```

---

## P0 快贏期(零建模,~1 週)

### P0-1 RLC drop 接線 →「PdcpPacketDiscardDL」轉真 🟢 半天

- DU `GnbDuMeasurementReport` 加 `rlc_drop_sdus`/`rlc_drop_bytes` → CU `MeasurementLog` 加欄 → migration → FullReporter 按 cell 加總填 `cu_DRB.PdcpPacketDiscardDL.5QI9`
- 資料現成(AK10 已在算),純接線
- **驗收**:重載場景(8Mbps×N)下該欄 >0,且與 DU `[RLC-DROP]` log 數量吻合

### P0-2 HO 速率/成功比加工層(ANR 核心 KPI)🟡 1 天

- 新查詢服務(CU):由 `HandoverEvent`(有 timestamp/source/target/status)計算:
  - cell 級:`MM.HoExeAttRatePerMin`、`MM.HoExeSuccRatio_last50`
  - **關係級**(ANR 卷 perNeighbourRelation):GROUP BY (source_cell, target_cell) 同兩指標
  - `handoverFailureCauseRatePerMin` 先回 `{}`(P2 前的合法空值,卷面第 1 題有先例)
- **驗收**:開 A3 跑跨區場景,rate 與事件表人工計數一致;_last50 在事件 <50 時標示樣本數

### P0-3 量測報告聚合端點(ANR 鑽取資料)🟡 1 天

- 新查詢服務(CU):由 `MeasurementLog.neighbor_cells_json`(每秒全鄰區 RSRP 真值)聚合:
  - 依 reported PCI:`sampleRatePerMin`、`rsrpPercentile50/90Dbm`、`rsrpStandardDeviationDb`、`servingRsrpPercentile50Dbm`
- 輸出結構對齊卷面 `e2MessageCopyAggregate.measurementReportAggregate`
- **驗收**:與離線用 pandas 對同一批 MeasurementLog 算的百分位一致(±0.1dB)

### P0-4 CGI 解析端點 + PCI confusion 能力 🟡 半天

- 新端點:輸入 (pci, arfcn) → 查 CellConfig → 回 `{NCGI: 次數}`;同 PCI 多 cell 時回多結果(confusion)
- 建一個同 PCI 測試場景存為劇本(`anr_pci_confusion.json`)
- **驗收**:唯一 PCI 回單一 NCGI;刻意重複 PCI 回兩個(卷面第 5 題可運轉)

### P0-5 NodeInfo 補全 🟢 半天

- `frequencyRelations[]`:由 CellConfig 聚合(單頻平台 = 一條 NR/633333;多頻場景自動多條)
- `relationChangeEvents[]`:ANR add/remove 動作落事件表(action/target/by/at)
- **驗收**:ANR reseed 後 changeEvents 有記錄

### P0-6 5QI1 語音場景 + 排程器 5QI 優先權 🟡 2 天(可與上並行)

- 劇本掛 `qos_5qi:1` 低速率 CBR → 12 個分桶欄自動有值
- PF 排程器加簡單優先權:5QI1 GBR 先配滿再 PF 分剩餘(否則數字真、QoS 隔離語意假)
- **驗收**:壅塞場景下 5QI1 delay 顯著低於 5QI9(隔離生效的證據)

### P0-7 ROP 週期收割 🟡 1~2 天(選配,建議做)

- pm_aggregator session 累計族(MCS/CQI bins、PRBUsageNbr、PdcpVol 累計)改為可設週期收割(`PM_ROP_SEC`,預設 900 sim-秒);`timestamp_start/end` 填真實週期邊界
- 一石三鳥:對齊 28.552 語意、合成 timestamp 轉真、長跑不膨脹
- 注意:`dump_pm`(debug snapshot)與收割分離,不互清
- **驗收**:跑 >2 個週期,pm 值上限有界、兩份快照的 start/end 銜接無縫

**P0 結算**:零值 →真 8 欄(discard 1 + 5QI 分桶 12 的實質啟用 + timestamps 4);ANR 🟡 區全清。

---

## P1 核心建模期:RLF + RRC 重建(~1 週)

平台獲得「掉話」概念 —— 這是兩份文件共同指向的最高價值建模。

### P1-1 RLF 判定(DU)~2 天

- 對齊 TS 38.331 T310/N310 語意的簡化版:per-UE 狀態機
  `SINR < RLF_THRESHOLD_DB(預設 -8)持續 RLF_T310_MS(預設 2000 sim-ms)→ 宣告 RLF`
- 參數走 env + 劇本可覆寫(不同題型需要不同靈敏度)
- 事件:DU → CU `rlf_report`(ue_id, cell, sinr_at_rlf, timestamp)→ 新表 `RlfEvent`
- **對應指標**:`RLF.DetectedRate`(per cell / per min)

### P1-2 UE 重建行為(UE/CU)~2 天

- UE 收 RLF → 進 RE_ESTABLISHING:對「當下最強 cell」(真實 rsrp_map 決定)發 ReEstabRequest
- CU 收 ReEstabRequest:
  - UeContext 存在 → `ReEstabSuccWithUeContext`(快速路徑,保 session)
  - 不存在/逾時 → `WithoutUeContext` → 退回完整 attach
  - 最強 cell RSRP < 門檻(無處可去)→ 重建失敗 → DROP(掉話)
- 新計數(全真值):`RRC.ReEstabAtt`、`ReEstabSuccWith(out)UeContext.sum`、`ConnReEstabSetup.sum`
- **對應 ANR 指標**:`RRC.ConnReEstabInboundRatePerMin`(依「重建進入的 cell」計 —— inbound 語意)、
  `RLF.DropWithoutReestablishmentRate`、`reestablishmentInboundByPreviousPci[]`(重建時帶前 serving PCI —— ANR 缺漏鄰區偵測的直接證據鏈)
- **驗收場景**:「缺漏鄰區」劇本 —— 兩個 cell 覆蓋相鄰但 NRT 無關係 + A3 對該對關閉 → UE 走過去必 RLF → 重建進入鄰 cell 且 previousPci = 原 serving。**這正是 ANR 卷第 2 題的完整重現**

### P1-3 釋放計數搭車 ~1 天

- release 路徑加 per-cell 計數 + 原因標籤(user-stop / stale / RLF-drop)
- 零值 →真:`UECNTX.Release.*`、`ConnRelease.*`、`SM.PDUSessionRelease.*`(9 欄)

**P1 結算**:零值 →真 +19 欄(重建 7 + 釋放 9 + ReEstab 相關 3);ANR ❌ 區解鎖 7/11;
獲得新驗收能力:ES xApp 關 cell 過激會製造真實 RLF/掉話(懲罰信號)。

---

## P2 歸因期:MRO 三聯 + HO 失敗原因(~3 天,於 P1 之上)

### P2-1 MRO 歸因引擎(CU)~2 天

標準 MRO 分類(TS 28.552 §5.1.1.25.1 語意),原料 = P1 的 RlfEvent + 重建落點 + HandoverEvent 時間線:

| 歸因 | 判定(全部由真實事件時序推導)|
|---|---|
| `TooEarlyRate` | HO 完成後 T_short(預設 5s)內 RLF,且重建回 **source** cell |
| `TooLateRate` | RLF 發生於無 HO 進行時,且重建進入 **非 serving** cell(該換沒換)|
| `ToWrongCellRate` | HO 完成後 T_short 內 RLF,且重建進入 **第三** cell |

- **驗收場景**:調 A3 參數製造三種病態(offset 過小 → TooEarly;TTT 過長 → TooLate;
  兩鄰區 RSRP 交錯 + 錯誤 offset → ToWrongCell),各自只點亮對應歸因

### P2-2 HO 失敗原因值 ~1 天

在 HandoverEvent 加 `failure_cause`,依真實條件填(不合成):

| Cause | 觸發源(平台真實狀態)|
|---|---|
| `CellNotAvailable` | target cell `is_active=false`(CCC cell off —— 平台已有此機制)|
| `RandomAccessProblem` | HO 當下 target RSRP < 接入門檻(真量測判)|
| `TXnRELOCprepExpiry` | prep 階段逾時(給 prep 加真實計時器 + 可注入延遲)|
| `HandoverToWrongCell` | 由 P2-1 ToWrongCell 歸因回填 |

- `handoverFailureCauseRatePerMin` / `Cumulative` 從恆空 `{}` 變真值

**P2 結算**:ANR 全卷 10 題資料面完整,每個問題種類(缺漏鄰區/PCI confusion/MRO 三型/負載型/既有關係故障)都有真實資料鏈可判別。

---

## 明確不做(維持誠實 0)

`QF.*` 12 欄(需 flow 層,對 ANR/HO/CCO 無增益)、`SigTime*` 6 欄(HTTP 耗時語意錯位)、
`emergency`/`mo-Signalling` 動機分類、`PdcpReordDelayUl`(無亂序機制)、
`AirIfDelayUl`(等 UL 流量模型升級)、PEE 溫度合成(裸機再說)。

## 交付與驗收總表

| 期 | 工時 | 零值→真 | ANR 題面 | 關鍵驗收 |
|---|---|---|---|---|
| P0 | ~1 週 | +8 欄 | 第 1/3/4/5/9 題可運轉 | HO rate 對事件表、聚合對 pandas、confusion 場景重現 |
| P1 | ~1 週 | +19 欄 | 第 2/6/12 題症狀源就位 | 缺漏鄰區劇本完整重現卷面第 2 題證據鏈 |
| P2 | ~3 天 | (歸因/原因非 pm 欄)| 全卷 10 題 | 三種 A3 病態各自點亮對應 MRO 歸因 |

所有新指標的曝光面:① FullReporter(pm 對應欄轉真)② 新 ANR 查詢端點(對齊卷面四大塊 JSON 結構)
③ 視需要上 FULLKPM wire(func 5 自動帶出,RIC 無感)。每項完成同步更新
`kpm_field_notes*.md` 分級與 `docs/api/e2_supported_commands.md`。
