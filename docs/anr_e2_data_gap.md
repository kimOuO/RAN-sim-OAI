# ANR情境_v8 × 平台 E2 Data 覆蓋對照

> 對象:`docs/ANR情境_v8.docx` 資料格式定義(參章)的四大 E2 資料塊 + 量測對照表。
> 對照基準:平台現有 E2 data(FULLKPM 190 欄、9-metric wire、`E2/NodeInfo/read`、CU DB)。
> 判定:✅ 已有 / 🟡 原料現成缺加工 / ❌ 需建模 / ⚪ 非 E2(卷面紅字,xApp 端自理)。
> 實測日期:2026-08-11(對 live 平台逐欄驗證,非紙上對照)。

## 結論一句話

**四大塊裡:e2NodeInformation 幾乎全有(9.3.38 含卷面延伸欄全數實測返回);
kpmIndication 的 9 個量測有 1 個現成、2 個半天可推導、6 個卡在同一個缺口 —— RLF/重建模型;
鑽取類(訊息聚合、CGI 解析)原料 100% 現成、缺聚合查詢層。**

---

## 一、e2NodeInformation(E2SM-RC §9.3.38)— 大致 ✅

| 卷面欄位 | 平台狀態 |
|---|---|
| `servingCells[]`:ncgi / physicalCellId / arfcn / radioAccessTechnology | ✅ 實測返回,4 欄全有 |
| `neighbourCellRelations[]`:sourceCellNcgi / targetCellGlobalId / targetPhysicalCellId / targetArfcn / targetRadioAccessTechnology | ✅ 實測返回 |
| 同上,卷面延伸 3 欄:isHoAllowed / isRemoveAllowed / isXnAllowed | ✅ 實測返回(還多給 `flags` 細節) |
| 同上,9.3.38 正式欄:xnX2Established / hoValidated / version | ✅ 實測返回 |
| `frequencyRelations[]`(RAT / arfcn) | ❌ 未實作 —— 但平台單頻(全 cell 同 arfcn 633333),補一條靜態記錄即可(🟡 十分鐘) |
| `relationChangeEvents[]`(action / target / by / at) | ❌ 未實作 —— ANR add/remove 需落事件表;卷面標「需要時列出」,做 ANR 動作審計時才需要(🟡 半天) |

## 二、kpmIndication — 核心缺口區

### cellLevel 量測(9 個)

| 量測 | 平台狀態 | 說明 |
|---|---|---|
| `RRU.PrbTotDl`(currentPct) | ✅ | 現成,連 % 語意都一致(注意 ×10 校正的 ±50% 爭議,見 kpm_field_notes C 級)|
| `MM.HoExeAttRatePerMin` | 🟡 半天 | HandoverEvent 表有每筆事件+時間戳,rate/min 是查詢層加工 |
| `MM.HoExeSuccRatio_last50` | 🟡 半天 | 同上,取最近 50 筆算比率(卷面 `_last50` 語意直接可實作)|
| `RRC.ConnReEstabInboundRatePerMin` | ❌ | 無 RRC 重建流程(zero notes §5)|
| `RLF.DetectedRate` | ❌ | 無 RLF 模型(同上)|
| `RLF.DropWithoutReestablishmentRate` | ❌ | 同上(且需「重建失敗」子狀態)|
| `HO.IntraSys.TooEarlyRate` | ❌ | MRO 歸因 —— 前置是 RLF+重建 context(比 RLF 更上一層)|
| `HO.IntraSys.TooLateRate` | ❌ | 同上 |
| `HO.IntraSys.ToWrongCellRate` | ❌ | 同上 |

⚪ 各量測的 `baseline*` / `trendLast30Min`:卷面紅字明示**非 E2 即時觀測**(歷史聚合)—— xApp 端自算,平台只需資料連續(InfluxDB/FULLKPM 歷史已具備)。

### perNeighbourRelation(依關係細分)

| 欄位 | 平台狀態 |
|---|---|
| targetCellGlobalId + 每關係 HoExeAttRate / SuccRatio_last50 | 🟡 半天 —— HandoverEvent 有 source_cell + target_cell,GROUP BY 即得 |
| `handoverFailureCauseRatePerMin` / `CumulativeSinceCreation` | ❌ —— 平台 HO FAIL 無原因值。四個 cause(TXnRELOCprepExpiry / CellNotAvailable / RandomAccessProblem / HandoverToWrongCell)各需對應失敗模型(Xn 計時器 / cell 不可用 / RACH / 錯誤落點),目前一個都沒有。**短期可先回恆空 `{}`(卷面第 1 題本身就有空 `{}` 的合法案例)** |

## 三、e2MessageCopyAggregate(鑽取)— 原料全有,缺聚合層

| 欄位 | 平台狀態 |
|---|---|
| `measurementReportAggregate[]`:依 reported PCI 聚合的 sampleRatePerMin / rsrpPercentile50/90Dbm / rsrpStandardDeviationDb / servingRsrpPercentile50Dbm | 🟡 1 天 —— **原料 100% 現成**:MeasurementLog 每秒每 UE 都有全鄰區 RSRP(光追真值),缺的只是「依 PCI 分組算百分位/標準差/速率」的查詢端點 |
| `trendLast30Min` / `hourlyProfile` | ⚪ 歷史聚合,xApp 端自理 |
| `reestablishmentInboundByPreviousPci[]` | ❌ —— 需重建模型(與二節同一缺口)|

## 四、cgiResolutionSampling(PCI→CGI 解析)

| 欄位 | 平台狀態 |
|---|---|
| physicalCellId / arfcn / attempts / results{NCGI\|FAIL: 次數} | 🟡 半天 —— CellConfig 有 pci↔nr_cellid 全對照,做一個「解析」端點回確定性結果即可 |
| PCI confusion 情境(解析非唯一,卷面第 5 題)| ✅ 場景可造 —— 平台 PCI 手動指定,建兩個同 PCI cell 即重現 |

---

## 五、總帳與建議路線

### 覆蓋統計

```
✅ 已有       :9.3.38 全欄位(含延伸)、PrbTotDl、PCI confusion 場景能力
🟡 缺加工(原料現成,合計 ~3 天):HO rate/ratio(cell 級+關係級)、量測報告聚合、
              CGI 解析端點、frequencyRelations、relationChangeEvents
❌ 需建模     :RLF 家族(2)、重建家族(2)、MRO 三聯(3)、HO 失敗原因(4 值)
              —— 全部收斂到同一個根:**RLF / RRC 重建模型**
⚪ 非 E2      :baseline / trend / hourlyProfile(卷面紅字,xApp 自理)
```

### 關鍵判讀

ANR 卷 10 題的敘事引擎是「**用戶以重建代替換手**」這條症狀鏈(RLF↑ + ReEstab↑ + HO 歸因持平 → 缺漏鄰區)。
平台目前有這條鏈的「果」(HO 事件、RSRP 量測、PRB)但沒有「因」(RLF/重建)——
**zero notes 路線圖把「RLF + RRC 重建」列為丙類第一優先(3~5 天),這份對照讓它的必要性加倍**:
做完它,❌ 區的 11 個量測裡 7 個直接解鎖(RLF×2、ReEstab×2、reestablishmentInboundByPreviousPci,
加上 MRO 三聯的地基),HO 失敗原因也有了掛載點(RLF-during-HO = TooEarly/ToWrongCell 的判源)。

### 建議順序

1. 🟡 全清(~3 天,零建模):HO rate/_last50(cell+關係)、量測聚合端點、CGI 解析、freqRel/changeEvents —— 做完卷面第 1/3/4/5/9 題的資料面即可運轉(用恆空 failureCause)
2. ❌ RLF + 重建模型(3~5 天)—— 解鎖 RLF/ReEstab 量測,卷面第 2/6/12 題的症狀源
3. ❌ MRO 歸因 + HO 失敗原因(在 2 之上再 +2~3 天)—— 完整覆蓋全卷

*相關:`kpm_field_notes.md` / `kpm_field_notes_zero.md`(欄位真實性)、`api/e2sm_fullkpm.md`(取用方式)。*
