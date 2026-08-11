# KPM 零值欄位筆記 — 官方定義 × 平台缺口 × 實踐可行性

> 姊妹篇:`kpm_field_notes.md`(有值欄位)。本篇涵蓋 pm 190 欄中恆為 `"0"` 的 62 欄。
> 每族三段:**官方定義**(意義、能判斷什麼)/ **為何在平台是 0**(缺什麼)/
> **實踐可行性**(做法、工作量、值不值得)。
> 依「離有值多遠」排序:條件性零(零開發)→ 待接線(小工程)→ 需建模(大工程)。

**可行性評級**:🟢 零開發~半天 / 🟡 1~3 天 / 🔴 需新建流程模型(週級)/ ⚫ 對模擬平台無意義,不建議做

---

## 甲、條件性零 —— 程式邏輯是活的,配置到位自動有值

### 1. 5QI1 / 5QI4 流量分桶(12 欄)🟢

`cu_DRB.PdcpSduVolume{DL,Ul}_5QI{1,4}`、`cu_gnb.DRB.SdapSduVolume*.5QI{1,4}`、
`cu_DRB.InitialEstabAtt.5QI1`、`du_DRB.AirIfDelayDlAvg.5QI1`、`du_DRB.AirIfDelayUlAvg.5QI1`

**官方定義**(3GPP TS 28.552;5QI = 5G QoS Identifier,TS 23.501 表 5.7.4-1)
按 QoS 等級分桶的流量/延遲統計。5QI1 = 會話語音(GBR、100ms 延遲預算)、5QI4 = 非會話影音、5QI9 = 盡力而為數據(預設)。
能判斷:各業務類別的流量占比與服務品質 —— 真網路用它驗證「語音有沒有被數據擠壓」(QoS 隔離是否生效)。

**為何是 0**:分桶機制已實作(DU `pm_aggregator.pdcp_bytes_dl` 是 per-5QI dict,`qos_5qi` 一路從 traffic profile 傳到記帳),但目前所有 UE 的 traffic profile 都建 5QI9。

**實踐可行性 🟢(零開發)**:劇本或 Dashboard 掛一條 `{"qos_5qi": 1, "pattern": "cbr", "rate_mbps": 0.1}` 的語音型流量即自動有值。
**但要誠實**:有值 ≠ 有意義 —— 目前 PF 排程器**不區分 5QI 優先權**(GBR 語音不會被優先排),分桶數字是真的,「QoS 隔離」的行為是假的。要讓 5QI1 數字有研究價值,需同步給排程器加優先權邏輯(升級為 🟡,約 2 天)。

### 2. PEE 溫度(3 欄)🟢(換環境)

`du_169:PEE.AvgTemperature`、`du_170:Min`、`du_171:Max`

**官方定義**(3GPP TS 28.552 PEE 家族)
BBU 硬體溫度統計,節能與散熱管理用。

**為何是 0**:程式正常(psutil `sensors_temperatures()`),本機是 KubeVirt VM,無溫度感測器可讀。

**實踐可行性 🟢**:搬裸機自動有值;或 VM 裡用「CPU 使用率 → 合成溫度」模型(⚫ 不建議 —— 合成值對 ES xApp 是誤導,不如誠實 0)。Min/Max 目前三值同源,要真 min/max 需在 CU 加滾動窗追蹤(🟡 半天,搬裸機後才值得)。

---

## 乙、待接線 —— 資料已存在於平台某處,缺一條上報鏈

### 3. cu_DRB.PdcpPacketDiscardDL.5QI9(1 欄)🟢【性價比最高】

**官方定義**(3GPP TS 28.552)
PDCP 層因壅塞/逾時**主動丟棄**的下行封包數。與 delay 互補:delay 是「等多久」,discard 是「等不到直接放棄」。
能判斷:過載的嚴重等級 —— delay 高但 discard=0 是「慢」;discard>0 是「已經在丟資料」,QoS 崩潰的鐵證。

**為何是 0**:DU **已經在算**(AK10:RLC tx buffer 滿 → reject,`rlc_drop_sdus`/`rlc_drop_bytes`,對齊 OAI `sdu_rejected`),但刻意只留 DU 本地 log,沒上 F1AP 報告鏈(壓測時 log 狂噴的 `[RLC-DROP]` 就是它)。

**實踐可行性 🟢(半天)**:`GnbDuMeasurementReport` 加 `rlc_drop_sdus` 欄 → CU MeasurementLog 加欄 → FullReporter 按 cell 加總填入。全鏈路現成,純接線。**建議第一個做** —— 它讓「過載」從推測(delay 高)變成實錘(丟包數)。

### 4. cu_DRB.SessionTime.5QI9 / RelActNbr.5QI9(4 欄)🟡

**官方定義**(3GPP TS 28.552)
SessionTime:DRB 存活總秒數(所有 UE 加總)。RelActNbr:釋放時**仍在活躍傳輸**的 DRB 數(異常釋放指標)。
能判斷:session 時長分布(短連線風暴 vs 長連線)、掉話品質(活躍中被釋放 = 體驗中斷)。

**為何是 0**:UeContext 有 `created_at`(時長可算),但 FullReporter 沒填;釋放路徑沒有「釋放當下是否活躍」的判斷。

**實踐可行性 🟡(1 天)**:SessionTime = Σ(now − created_at) 直接可填(但要決定語意:目前連線的累計 vs 含歷史 —— 含歷史需釋放時落帳,連動第 6 項);RelActNbr 在 release 路徑查「最近 window 有無流量」即可判。價值中等 —— 主要對「UE 動態進出」型劇本有用,目前劇本 UE 都是常駐。

---

## 丙、需建模 —— 模擬器裡沒有這個世界

### 5. RRC 重建家族(10 欄)🔴

`cu_RRC.ConnReEstabSetup.sum`、`ReEstabAtt(.otherFailure)`、`ReEstabSuccWith(out)UeContext.*`、
`cu_gnb.RRC.ConnReEstab.*`、`ConnReEstabSetup.otherFailure`

**官方定義**(3GPP TS 28.552;流程見 TS 38.331 §5.3.7)
RRC Re-establishment:UE 無線鏈路失敗(RLF)後嘗試「不重跑完整註冊、快速接回」的救援流程。WithUeContext = 網路還記得它(快速路徑);WithoutUeContext = 記憶已失,退回完整建立。
能判斷:網路穩定性的核心 KPI —— ReEstab 頻繁 = 覆蓋破洞/干擾突發/參數失當;真網路優化團隊天天盯。

**為何是 0**:模擬器 UE 不會「無線電失聯」—— SINR 再差也只是吞吐歸零,連線本身永不斷裂。沒有 RLF 就沒有重建。

**實踐可行性 🔴(3~5 天,有研究價值)**:需要三件事:
1. **RLF 判定**:DU 對 UE 加「SINR < 門檻持續 N 秒 → 宣告 RLF」(對齊 38.331 的 T310/N310 計時器語意)—— 平台有真 SINR,判定條件是現成原料;
2. **UE 端反應**:UE thread 收到 RLF → 進 re-establishment 狀態 → 對最強 cell 重試;
3. **CU 端流程**:收 ReEstabRequest → 查 UeContext 存在與否 → 走 With/Without 兩條路 → 計數。
做完的副產品很值錢:**平台從此有「掉話」概念**,ES xApp 關 cell 太激進會製造 RLF —— 這是目前平台無法呈現的懲罰信號,對 xApp 訓練是質變。**建議列為丙類第一優先。**

### 6. 釋放計數家族(9 欄)🟡

`cu_UECNTX.Release.5GCinit.{NASCause,RNCause,sum}`、`cu_gnb.UECNTX.Release.gNBinit.*`、
`cu_gnb.SM.PDUSessionRelease.Att/Succ`、`cu_gnb.RRC.ConnRelease.{Other,sum}`

**官方定義**(3GPP TS 28.552)
連線/session 釋放的計數,按發起方(5GC 核網 vs gNB)與原因分類。
能判斷:連線生命週期的「死亡統計」—— 誰殺的、為什麼殺;異常釋放率是投訴預警指標。

**為何是 0**:平台有釋放動作(Stop Sim、detach、release_stale),但釋放路徑沒做 per-cell 計數,也沒有原因分類。

**實踐可行性 🟡(1~2 天)**:在 CU release 路徑(session_controller / ue_context 刪除處)加 per-cell counter + 簡單原因標籤(user-stop / stale / RLF)。與第 5 項合做最划算(RLF 就是最重要的釋放原因)。單獨做價值偏低 —— 目前的釋放都是「管理操作」不是「網路事件」。

### 7. QF QoS Flow 家族(12 欄)🔴/⚫

`cu_QF.EstabAttNbr.*`、`EstabSuccNbr.*`、`InitialEstab*`、`RelActNbr.*`、`ReleaseAttNbr.*`(各 .5QI.sum/.5QI9)

**官方定義**(3GPP TS 28.552;架構見 TS 23.501 §5.7)
QoS Flow 是 5G QoS 的最小單位:一個 PDU session 可含多條 QoS flow,多條 flow 可映射到一個 DRB。這族統計 flow 層級的建立/釋放。
能判斷:業務級 QoS 管理的細節(如同一 session 裡影音 flow 建立失敗但數據 flow 正常)。

**為何是 0**:平台的 QoS 架構是扁平的:1 UE = 1 session = 1 DRB,沒有獨立的 flow 層。

**實踐可行性 🔴 偏 ⚫(不建議單獨做)**:要有意義必須實作「多 flow 對一 DRB 的映射 + flow 級排程」——工程量週級,且對現有 xApp 用例(HO/CCO/ES 都是 cell/UE 級決策)沒有增益。**除非未來要做 network slicing 研究**,否則維持誠實 0。若只想「欄位不為 0」,可讓 QF = DRB 計數鏡像(1:1 映射下語意成立),🟢 十分鐘 —— 但這只是把 DRB 數字抄一份,自己要清楚沒有新資訊。

### 8. RRC 訊令耗時家族(6 欄)🔴/⚫

`cu_gnb.RRC.SigTime{Setup,Reconfig,ReEstab}.{Avg,Max}`

**官方定義**(vendor 延伸,對齊 TS 28.552 訊令延遲精神)
RRC 各流程(建立/重配/重建)從發起到完成的耗時統計。
能判斷:控制面效能 —— 訊令慢 = CPU 過載或傳輸壅塞,影響接入體驗(按下去多久連上)。

**為何是 0**:平台的 RRC 訊令是 HTTP 呼叫,「瞬時完成」,沒有耗時模型。

**實踐可行性**:兩條路 ——
- **量 HTTP 真實往返** 🟢(半天):把 CU↔DU↔UE 的實際呼叫延遲記下來填入。數字是真的,但量的是「模擬器的 HTTP 效能」不是「5G 訊令效能」,語意錯位(⚫ 性質);
- **建訊令延遲模型** 🔴:按 3GPP 流程步數 × 每步 RTT 合成 —— 是合成值,對 xApp 無增益。
**建議**:維持 0。這族在 DT 語境下沒有好答案。

### 9. 場景性零(6 欄)⚫

`cu_RRC.ConnEstabSucc.emergency`、`*.mo-Signalling`(×4)、`cu_gnb.RRC.ConnEstabSetup.{emergency,mo-Data,mo-Signalling}` 其中非 sum 欄

**官方定義**(3GPP TS 28.552)
連線建立的「動機分類」:emergency = 緊急呼叫、mo-Signalling = 純訊令(如位置更新)、mo-Data = 為傳資料而連。
能判斷:真網路用於緊急服務可用性稽核(法規要求)與訊令風暴偵測。

**為何是 0**:模擬 UE 只有一種動機 —— 傳資料(全記 mo-Data)。

**實踐可行性 ⚫**:技術上加 UE profile 欄位十分鐘就能「有值」,但模擬緊急呼叫/純訊令連線對本平台的研究目標(HO/PRB 決策驗證)零增益。維持誠實 0。

### 10. cu_RRC.ConnReConfig Att/Succ(2 欄)🟡

**官方定義**(3GPP TS 28.552;流程 TS 38.331 §5.3.5)
RRC Reconfiguration 計數 —— 換手、量測配置變更、DRB 修改都靠這個訊令載體。
能判斷:控制面活躍度;Succ/Att 比是訊令健康度。

**為何是 0**:平台的 HO 直接改狀態,沒有顯式的 Reconfig 訊令步驟。

**實踐可行性 🟡(半天)**:語意上每次 HO 執行 = 一次 Reconfig —— 在 HO 路徑同步計數即可(Att = HoExeReq、Succ = HoExeSucc 的鏡像 + 未來其他 reconfig 來源)。誠實度尚可(HO 確實隱含 reconfig),但短期內只是 HO 計數的別名。

### 11. cu_DRB.PdcpReordDelayUl(1 欄)🔴/⚫

**官方定義**(3GPP TS 28.552)
上行 PDCP 重排序延遲 —— 封包亂序到達時,等待補齊序號的時間(範例檔值為 3)。
能判斷:傳輸路徑的亂序程度(多路徑/HARQ 重傳造成)。

**為何是 0**:平台無 PDCP 層、無亂序機制(RLC drain 嚴格有序)。

**實踐可行性 ⚫**:亂序源於 HARQ 重傳與多路徑 —— 兩者都未建模;單獨為此欄建 PDCP 重排序機制不划算。若未來為第 5 項(RLF)做了 HARQ 模型,此欄可搭便車,屆時再議。

### 12. du_DRB.AirIfDelayUlAvg.5QI9(1 欄)🟡

**官方定義**(3GPP TS 28.552)
上行空口延遲(DL 版我們有值,見有值筆記 §10)。

**為何是 0**:UL 方向只有流量比例模型,封包沒有時間戳生命週期(DL 的 RLC delay 機制沒有 UL 對應物)。

**實踐可行性 🟡(1~2 天)**:給 UL 流量加同款「入 buffer 蓋章 → drain 結帳」機制。做之前先想清楚:目前 UL 流量本身是簡化模型(比例注入),在簡化流量上量出的 delay 精度有限 —— 建議等 UL 流量模型升級時一起做,否則是在沙上蓋樓。

---

## 總結:如果要提高覆蓋率,建議路線圖

| 順位 | 項目 | 評級 | 工作量 | 拿到什麼 |
|---|---|---|---|---|
| 1 | PdcpPacketDiscard 接線(§3)| 🟢 | 半天 | 過載鐵證,ES/CCO xApp 直接受益 |
| 2 | 5QI1 語音流量劇本(§1)| 🟢 | 零開發 | 分桶欄位活起來(注意排程器不分優先權的限制)|
| 3 | RLF + RRC 重建(§5)| 🔴 | 3~5 天 | **平台獲得「掉話」概念** —— xApp 訓練的質變 |
| 4 | 釋放計數(§6,搭 §5 做)| 🟡 | +1 天 | 連線生命週期完整 |
| 5 | ConnReConfig 鏡像(§10)| 🟡 | 半天 | 低成本補全 |
| — | QF/SigTime/emergency/ReordDelay | ⚫ | — | 維持誠實 0,填值無研究增益 |

---

## 附:合成佔位欄位(有值但非真實,每 cell 7 欄)

不是零、也不是量測 —— 是**模仿 legacy/3GPP 格式的合成內容**,引用時視同無資訊量:

### cu/du_timestamp_start、cu/du_timestamp_end(4 欄)

**官方語意**(3GPP TS 28.550):PM 量測週期(granularity period,典型 15 分鐘)的起訖邊界 —— 「這份計數涵蓋哪段時間」。

**平台現況**:四欄全填 **snapshot 當下時刻**(格式 `YYYYMMDD.HHMM+0000` 是對的,內容是假的)—— 我們沒有週期收割制,start=end=現在,不代表任何量測區間。時間戳本身是真時鐘,但**週期語意是假的**。

**實踐可行性 🟡**:實作 ROP 週期收割(pm_aggregator 每 N 模擬秒收割歸零)後,這四欄自動變真 —— 與「session 累計族偏離 28.552」是同一個修正(見有值筆記 C 級),一石二鳥。

### cu_filename、du_filename(2 欄)

**官方語意**(3GPP TS 28.550/32.432):PM 檔案的標準命名 `A<日期>.<起始>-<結束>_<單位>.xml` —— 真網路的計數器是落成 XML 檔由 OSS 收走的,這欄是檔案指標。

**平台現況**:照格式**合成字串,檔案不存在** —— 平台的 PM 走 HTTP JSON,沒有 XML 檔產物。純粹為了欄位架構 1:1 對齊範例。

**實踐可行性 ⚫**:真的產 XML PM 檔技術上可行(做了 ROP 之後順手落檔),但平台的消費者(xApp/RIC)都走 JSON/E2,產檔案沒有讀者。維持合成字串即可,引用時忽略此欄。

### cu_CU_Capability(1 欄)

**官方語意**(vendor 欄位):CU 能力等級宣告。

**平台現況**:硬編碼 `"1"` —— 宣告性常數,不對應任何量測或動態狀態。

**實踐可行性 ⚫**:本質是設定檔資訊,無「實作」可言,維持常數。

---

## 完整帳目(與姊妹篇合計 = full KPM 全欄位)

```
pm 每 cell 190 欄 = 有值(A~C 級量測/計數,姊妹篇 1~15 節)
                  + 代理(D 級:ConnEstab 四族/BBU/PEE,姊妹篇附二)
                  + 零值(本篇甲乙丙,~60 欄)
                  + 合成佔位(本篇附,7 欄:timestamps×4 + filenames×2 + CU_Capability)
                  + 真實識別欄(cell_id,姊妹篇附三)
e2[] / ue_status[] / top-level / bbu_status = 量測欄(姊妹篇 1~15 節)
                  + 真實識別中繼資料 25 欄(姊妹篇附三)
兩篇聯集 = full KPM 全欄位;逐欄精確歸類以 E2_full_kpm_fields.md 總表為準。
```

*姊妹篇:`kpm_field_notes.md`(有值欄位 + 可信度四級 + 識別中繼資料附三)。*
