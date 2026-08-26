# KPM 實值欄位筆記 — 官方定義 × 平台實作

> 範圍:平台**有真實計算值**的 KPM 欄位(填 0 的欄位不在此列,見 `E2_full_kpm_fields.md` §4.7)。
> 順序:照數值在平台裡**實際產生的順序**排 —— 物理層 → 排程層 → 傳輸層 → 控制面事件 → 主機遙測。
> 每欄兩段:**官方定義**(名稱、規格出處、意義、能判斷什麼)/ **平台實作**(哪裡算、怎麼算、注意事項)。

共同時間語意:除特別註明外,數值代表**過去 1 個模擬秒的量測窗口**
(DU `PM_WINDOW_SEC=1.0`,每 2 tick × sim_dt 500ms flush 一次),不是瞬時值。
加速跑(2x)時窗口以 sim-time 度量,KPM 時間軸不失真。

---

## 第一階段:物理層 —— 電波打到 UE 的那一刻

數值誕生地:Physics 容器(Sionna RT 光追)→ RU 搬運 → DU 暫存。

### 1. RSRP — Reference Signal Received Power

**官方定義**(3GPP TS 38.215,SS-RSRP;單位 dBm)
UE 量到的 serving cell 參考訊號接收功率 —— 「基站的聲音傳到我耳朵還剩多大聲」。
只看訊號本身強度,**不含干擾與雜訊**。
能判斷:覆蓋好壞、UE 離站遠近、是否該換手(A3 事件的比較基準)。
典型值域:-44(貼著基站)~ -140(收不到)dBm。

**平台實作**
- `Physics_sim/main/apps/ran_signal/`:Sionna RT 對場景(建築 mesh + ITU 材質)做真實光線追蹤,每個 cell 是一支獨立 TX(`{gnb}#{pci}`,有位置/方位角/功率)。RSRP = TX 功率 + 天線增益 − 光追算出的路徑損耗(含反射/繞射/遮蔽)。
- RU 每 tick 拉「每 UE × 每 cell」的量測 → CqiIndication 推 DU → `tick_runner._ue_registry`。
- DU `PmAggregator._UeWindowAccumulator` 窗口內逐 tick 累加,flush 時取算術平均。
- 上 E2 wire 時量化:`編碼值 = round(RSRP + 156)`(ASN.1 欄位只吃非負整數,RIC 端減回)。
- 鄰區的 RSRP 同一套光追順便算好,放進 `neighbors` 清單(A3 演算法與 FULLKPM 的 neighbors 欄位同源)。

### 2. SINR — Signal to Interference plus Noise Ratio

**官方定義**(3GPP TS 38.215,SS-SINR;單位 dB)
訊號功率 ÷(干擾功率 + 熱雜訊)。**真正決定傳輸品質的量** —— RSRP 是「聲音多大」,SINR 是「吵雜環境裡聽不聽得清楚」。
能判斷:RSRP 高 + SINR 低 → 干擾問題(該做干擾協調);兩者皆低 → 覆蓋問題(該換手/補站)。
典型值域:>20 極佳、10~20 好、0~10 普通、<0 差。

**平台實作**
- 與 RSRP 同一次 Sionna 光追:serving cell 功率 S;**其他所有 cell 打到該 UE 的功率總和** = 干擾 I(所以多 cell 場景干擾是真算的,劇本要 `inter_freq=true` 干擾才成立);加熱雜訊 N。`SINR = 10·log10(S/(I+N))`。
- DU 窗口平均;wire 量化 `+23`。
- 下游兩個消費者:link adaptation 選 MCS(→ 第二階段)、FULLKPM 的 `interfered` 旗標(任一鄰區 RSRP 進 serving 10dB 內 → 1)。

### 3. RSRQ — Reference Signal Received Quality(FULLKPM 專屬)

**官方定義**(3GPP TS 38.215;單位 dB)
`N × RSRP / RSSI` —— RSRP 佔整體接收能量(含所有 cell + 雜訊)的比例。介於「純強度 RSRP」和「純品質 SINR」之間的綜合指標。
能判斷:負得越多 = 環境越擁擠;-3~-10 乾淨、-10~-15 中等、<-15 高干擾。

**平台實作**(2026-08-11 升級為 3GPP 真實版)
- CU 端由真實原料計算(`full_kpm_reporter._derive_rsrq()`),對齊 3GPP 定義 `RSRQ = N·RSRP/RSSI`:
  `RSSI = 12·Σ_cells[P_cell × (1/6 + 5/6·load_cell)] + P_noise`,`RSRQ = 10·log10(P_target/RSSI)`
- 三樣原料全為平台真值:per-cell RSRP(Sionna 光追)、load = 該 cell PrbTot%(DU 真實排程負載)、noise = `RU_NOISE_FLOOR_DBM`(與 SINR 同尺度,-98)
- **負載感知**:鄰站空閒時只發參考訊號(α=1/6),干擾貢獻低 → RSRQ 變好;這是 legacy 公式(假設全滿載)抓不到的維度
- 錨點驗證:單 cell 滿載 → -11(理論 -10.8)、空閒 → -3、等強滿載鄰站 → -14(理論 -13.8)全命中;輸出 clamp 3GPP SS-RSRQ 值域 [-43, 20]
- legacy 公式(`10log10(P/ΣP)−10.8`)已棄用;在「全滿載+忽略雜訊」極限下新公式收斂回 legacy 值,語意連續

---

## 第二階段:排程層 —— DU 拿訊號品質換算成資源分配

數值誕生地:DU `tick_runner`(每 tick)+ `PmAggregator` 記帳。

### 4. CARR.WBCQIDist — 寬頻 CQI 分布(16 bins,FULLKPM)

**官方定義**(3GPP TS 28.552,CQI 分布計數器)
UE 回報的 Channel Quality Indicator(0~15)出現次數直方圖。CQI 是 UE 對通道的「打分數」。
能判斷:整個 cell 服務品質的**分布形狀** —— 平均值會騙人(一半極好一半極差平均看起來普通),直方圖不會。右偏 = 通道普遍好;雙峰 = 有一群邊緣 UE。

**平台實作**
- DU 每 tick 對每個 UE:`sinr_to_cqi(sinr_db)` 查表(`link_adaptation/cqi_table.py`)→ 對應 bin +1。
- 存在 `_GnbAccumulator.cqi_bins[16]`,**session 起累計**(Start 歸零,不隨窗口重置)。
- CU 經 DU `dump_pm` 端點撈取(非破壞性 snapshot,不干擾每秒的窗口 flush)。

### 5. CARR.PDSCHMCSDist / PUSCHMCSDist — MCS 分布(各 32 bins,FULLKPM)

**官方定義**(3GPP TS 28.552)
排程器實際選用的 Modulation and Coding Scheme(0~31)次數直方圖。MCS 越高 = 調變越激進 = 每 PRB 載越多 bytes,但要求通道越好。
能判斷:頻譜效率的實況 —— MCS 都擠在低段 = 通道差,同樣流量要吃掉更多 PRB;分布 = cell 的「檔位使用紀錄」。

**平台實作**
- link adaptation 每 tick 依 SINR 選定 MCS(這是**真決策**,直接影響後續 drain 量)→ `mcs_dl_bins[mcs] += 1`(UL 同)。
- session 累計、`dump_pm` 撈取,同 CQI。

### 6. RRU.PrbTotDl / PrbTotUl — PRB 使用率(%,E2 wire 9 metrics 之一)

**官方定義**(3GPP TS 28.552 §5.1.1.2,DL/UL Total PRB Usage)
`使用中的 PRB ÷ 可用 PRB 總數 × 100`。PRB(Physical Resource Block)是 5G 頻譜資源的最小分配單位(40MHz ≈ 106 個)。
能判斷:**cell 容量水位** —— >70% 接近滿載該分流;xApp 的 CCO 看它挑換手目標、ES 看它挑可關閉的閒 cell。

**平台實作**
- DU 每 tick 每 cell 呼 `accumulate_cell_tick(prb_used, n_prb_total)`(`_CellWindowAccumulator`),窗口 flush 時 `Σ used ÷ Σ total × 100`。
- **三個關鍵設計**(都是踩坑後定案):
  1. **cell 級獨立累計,不從 per-UE 加總** —— UE 樣本數不齊會算出 >100% 假象;
  2. 分母用**物理容量**(未被 RC quota cap 的值)—— 否則 xApp 下 `max_prb=3` 後立刻看到 100%,違反 28.552 語意;
  3. **×10 OAI 校正**(`PRB_OAI_CALIB` env)—— DT 每 500ms 排程一次 vs OAI 每 1ms,取樣密度差使 raw 值偏低 ~10 倍,係數由實測反推(DT 1.09% vs OAI 10.67%),出口再 clamp ≤100%。
- 路徑:DU cell_measurement_report → CU `CellMeasurementLog` → adapter 編碼(單位 ‱)。
- 實測特性:是**對 SINR 最敏感的 KPM**(SINR 差 → MCS 低 → 同流量吃更多 PRB)。

### 7. CARR.PRBUsageDLNbr / ULNbr — PRB 累計個數(FULLKPM)

**官方定義**(3GPP TS 28.552)
配出去的 PRB **原始累計顆數**(不是百分比)。
能判斷:與 PrbTot% 互補 —— % 看水位,Nbr 看總消耗量;跨 cell 比較「誰吃掉最多資源」。

**平台實作**
- `_GnbAccumulator.prb_used_dl/ul` 每 tick 累加排程器實配數,session 累計,`dump_pm` 撈取。**未做 ×10 校正**(原始 tick 計數,語意與 legacy 一致)。

---

## 第三階段:傳輸層 —— 資源分配變成實際送出的資料

數值誕生地:RLC entity(buffer + 時間戳)+ PF 排程器 drain。

### 8. DRB.UEThpDl / UEThpUl — UE 吞吐量(bps,E2 wire)

**官方定義**(3GPP TS 28.552 §5.1.1.3,UE Throughput)
單位時間內**實際成功傳輸**的資料量。注意是「達成量」不是「需求量」。
能判斷:使用者體驗的直接量;對比注入需求可判斷 cell 是否供不應求;換手決策正確與否的最終驗收指標(CCO demo:換手後 Thp 回升)。

**平台實作**
- 流量源:UE 容器 `traffic_gen` 按 profile(cbr/bursty)注入 SDU → CU → DU RLC buffer。
- DU PF 排程器每 tick:看各 UE 的 buffer 深度 + 歷史吞吐(比例公平),分 PRB → 按 MCS 換算 drain bytes —— **這是實際送出的量**,buffer 空了就是 0,通道差就 drain 不動。
- 窗口 flush:`Σ drain bytes × 8 ÷ 窗口秒數` → bps。
- 注入端有 P0a/P1 修正:按 `achieved_speed_x`(實際達成倍速)注入而非設定倍速,避免超載時過量注入失真。

### 9. DRB.PdcpSduVolumeDL / UL — PDCP 資料量(kbit,E2 wire)

**官方定義**(3GPP TS 28.552,PDCP SDU Volume)
量測期間流過 PDCP 層的資料**總量**。與吞吐同源不同義:Thp 是速度(平均斜率),Volume 是總量(積分)。
能判斷:流量分佈 → 找 hot cell(負載均衡的依據);計費/容量規劃視角的量。

**平台實作**
- 與 Thp 同一份 `dl_bytes_sum`(RLC SDU bytes 當 PDCP proxy,差幾個 header byte 不影響統計)。
- 窗口 flush:`bytes × 8 ÷ 1000` → **kbit**(對齊 OAI 慣例;cco demo 時特地從 byte 改過)。
- adapter 端 indication **按 serving_cell 分組**送(senderName 帶 `cell_id/0x{nci}`),讓 mobiflow 能在 InfluxDB GROUP BY cell 算 per-cell volume —— hot/cold cell 判定就靠這個。
- FULLKPM 的 `PdcpSduVolumeDL_5QI9`/`SdapSduVolume` 是**同源的 session 累計版**(per-5QI 分桶,自 `_GnbAccumulator.pdcp_bytes_dl` 經 dump_pm)。

### 10. DRB.RlcSduDelayDl — RLC SDU 延遲(μs,E2 wire)

**官方定義**(3GPP TS 28.552,RLC SDU Delay)
封包從進入 RLC 層到完成傳送的耗時 —— 排隊延遲。
能判斷:**壅塞的早期警報**(吞吐還沒掉,delay 先升);URLLC 類分析的核心量;ES xApp 關 cell 前確認剩餘容量的依據。

**平台實作**
- RLC entity:SDU 入 buffer 蓋入場時間戳,被排程 drain 完成時算 `離場 − 入場`,樣本存 `take_delay_samples()`。
- tick_runner 定期收樣本 → `accumulate_rlc_delay()`;窗口 flush 取**平均**。
- 語意注意:輕載 ≈ 0(即到即走)、過載時飆升;**不含**空口傳播與 HARQ 重傳(是排程佇列的量)。時間戳走 sim-time,校正細節見 `_OAI_SLOT_MS` 相關記錄(勿單獨改)。
- FULLKPM 的 `du_DRB.AirIfDelayDlAvg.5QI9` = 同源資料按 cell 取 UE 平均(ms)。

---

## 第四階段:控制面事件 —— CU 狀態機留下的足跡

數值誕生地:CU 的 RRC/HO 狀態機(不經 DU 窗口,事件發生即入表)。全部 FULLKPM 專屬。

### 11. RRC.ConnMean / ConnMax — RRC 連線數(現值/高水位)

**官方定義**(3GPP TS 28.552 §5.1.1.4,Mean/Max Number of RRC Connections)
量測期間 cell 上 RRC CONNECTED 的 UE 數之平均/最大值。
能判斷:cell 的連線負載;Max 用於容量規劃(尖峰),Mean 用於日常水位。

**平台實作**
- `full_kpm_reporter`:`UeContext.objects.filter(rrc_state="CONNECTED", serving_cell=cell)` 現數 = ConnMean;模組級 `_conn_max_seen` dict 追蹤 process 存活期間高水位 = ConnMax(CU 重啟歸零)。
- 只計 serving_cell 仍存在的 UE(fresh-only filter,防 stale context 污染)。

### 12. MM.HoPrepIntraReq/Succ、MM.HoExeIntraReq/Succ — 換手準備/執行計數

**官方定義**(3GPP TS 28.552 §5.1.1.6,Handover Preparation / Execution)
HO 兩階段:Prep(source 向 target 要資源)與 Exec(UE 實際切換)。Req/Succ 配對算成功率。
能判斷:**移動性健康度** —— Exec 成功率低 = 換手參數(offset/hysteresis/TTT)不當或目標 cell 過載;Req 數量 = 移動性活躍度;ping-pong(短時間內反覆 HO)也從這裡看。

**平台實作**
- 每次 HO(A3 觸發 / RIC RC 指令 / 手動)在 CU `HandoverEvent` 表留一列,狀態機 PREP→EXEC→SUCC/FAIL。
- `full_kpm_reporter` 按 source_cell 聚合:PrepReq = 事件總數(每次 HO 必經 PREP);PrepSucc = 進到 EXEC 以後的;ExecReq = 進入執行的;ExecSucc = status=SUCC。全 intra-freq(IntraFreq 與 Intra 兩組欄位同值)。
- **A3 演算法本體**在 CU mobility(offset/hys/TTT 可由 Dashboard `/Mobility/A3Controller/set` 調)。注意:**A3 預設關閉** —— 沒開的話這族永遠 0(2026-08-07 壓測踩過:開 A3 後 12 分鐘 182 次真實 HO,48/48 欄全亮)。

### 13. gnb.MR.Event.A3 — A3 量測事件計數

**官方定義**(廠商延伸欄位,對齊 3GPP TS 38.331 的 A3 event:鄰區比 serving 好過門檻)
能判斷:A3 觸發頻率 vs HO 執行數的比值 → 換手參數的靈敏度是否恰當。

**平台實作**
- `HandoverEvent.trigger == "A3_TTT"` 的計數(RIC 下的 RC HO、手動 HO 不算)。

### 14. RRC.ConnEstab* / UECNTX.* / SM.PDUSession* / DRB.Estab*(⚠ 代理值)

**官方定義**(3GPP TS 28.552)
連線建立、UE context 建立、PDU session 建立、DRB 建立的歷史累計嘗試/成功數。
能判斷:接入成功率、拒絕率(真網路中是 KPI 紅線)。

**平台實作(代理)**
- 平台未持久化 per-cell 的歷史 attach 事件,以「**當下 CONNECTED 於該 cell 的 UE 數**」代理(每個連線中的 UE 必然完成過一次成功 attach;模擬器每 UE 恰建 1 個 5QI9 session/DRB,故四族同值)。
- 語意差異:標準是歷史累計,我們是現值 —— HO 後 UE 移走,計數跟著移。要變真累計需在 CU attach 路徑加 per-cell 持久計數器(未做,見 fields 報告 §7)。

---

## 第五階段:主機遙測 —— BBU 狀態(⚠ 代理值)

### 15. bbu_status:cpu / cpu_power / mem / load_average / tot_power

**官方定義**(對齊 3GPP TS 28.552 PEE(Power, Energy, Environment)家族精神)
基地台運算單元(BBU)的 CPU 使用率、功耗、記憶體、負載。
能判斷:ES(節能)xApp 的輸入 —— 關 cell 能省多少電、BBU 是否過熱過載。

**平台實作(代理)**
- `BbuTelemetryService`(CU):psutil 讀**模擬主機**的 CPU%/mem/loadavg;功耗 = `CPU% × 65W TDP` 估算;GPU 功耗 pynvml 讀 A40(CU 容器沒掛 GPU 時為 0)。
- per-gNB 值 = host 量測 ÷ gNB 數均攤(legacy 同款做法)。
- **語意:量的是跑模擬器的 server,不是被模擬的 gNB 硬體** —— 格式可餵 ES xApp,論文中須註明 proxy。
- 兩個實作坑(2026-08-07 修):CU 容器要裝 psutil(已入 requirements);`cpu_percent(interval=None)` 一個 snapshot 只能呼一次然後共用(連續呼第二次區間趨近 0 恆回 0)。
- `cpu_temp` 在本機恆 0:KubeVirt VM 無溫度感測器(誠實 0,非 bug)。

---

## 附:一條因果鏈把 15 個欄位串起來

```
【物理】RSRP、SINR、RSRQ          ← Sionna 光追(每 tick)
   ↓ sinr_to_cqi / link adaptation
【排程】CQI 分布、MCS 分布          ← 選檔的足跡(session 累計)
   ↓ PF 排程分 PRB
【資源】PrbTot%、PRBUsageNbr        ← 分配的帳(窗口% / 累計顆)
   ↓ 按 MCS drain RLC buffer
【傳輸】UEThp、PdcpVolume、RlcDelay ← 實際送出的量與排隊時間
【事件】ConnMean/Max、HoPrep/Exec、A3 ← CU 狀態機足跡(事件驅動)
【主機】bbu_status                  ← psutil(代理)
```

閱讀順序即除錯順序:體驗差(Thp 低)→ 看資源(PRB 滿?)→ 看效率(MCS 低?)→
看訊號(SINR 差?)→ 干擾還是覆蓋(RSRP 高低?)→ 需不需要換手(HO/A3 計數)。

---

## 附二:真值可信度四級分類(引用前必讀)

「有值」不等於「同等可信」。四級,嚴格程度遞減:

### A 級 — 直接量測,無爭議

| 欄位 | 為什麼硬 |
|---|---|
| RSRP、SINR | Sionna 光追直接輸出 |
| UEThp、PdcpVolume(bytes 本體)| RLC 真實 drain 的位元組數 |
| MM.Ho\*、MR.Event.A3 | 狀態機事件計數,發生一次記一次 |
| ConnMean | 當下 CONNECTED 數,直接 count |
| PRBUsageNbr(顆數版)| 排程器實配 PRB 原始累計,無校正 |
| **RLF.\* / ReEstab\* / 釋放計數(gNBinit)**(P1/P2)| RlfEvent 真事件計數:掉線、重建、gNB 發起釋放皆真狀態轉移(Sionna SINR 驅動)|
| **RRC.ConnEstabAtt/Succ 四族**(2026-08-12 轉真)| RrcEstabCounter:InitialCtxSetup 事件 +1,只加不減、HO 不搬家(真歷史累計);平台 attach 無失敗模型 → Att=Succ |
| **SessionTime / ConnMean / ConnMax**(2026-08-12 轉真)| CellCumCounter:釋放時落帳(含歷史)/ 取樣真平均 / 持久高水位(CU 重啟不歸零)|
| **AirIfDelayDlAvg per-5QI**(2026-08-12)| MeasurementLog 帶 qos_5qi → delay 按業務分桶,5QI1(語音)delay 可直接量測 |
| **RelActNbr**(掉話時活躍 DRB)| = RLF 掉話數(掉話 UE 必在傳輸中)|

三個註記:
- **position 上帝視角**(見下)
- **Volume PDCP 名義為 RLC 代理**(見下)
- **釋放計數只涵蓋 gNB 發起(=RLF 掉話)**;核網發起(`Release.5GCinit.*`)平台無此流程 → 維持誠實 0,不列入

- **UE position 已於 2026-08-12 移除**(原為 legacy 範例格式帶入)—— 真實 E2/KPM 不攜帶 UE 位置(真網路需定位技術估算),送出會給 xApp 現實中拿不到的資料
- **Volume 的 PDCP 名義實為 RLC bytes 代理**(無 PDCP 層,差 header 數 byte)

### B 級 — 有值且真,但是**計算/推導**,不是獨立量測(原料真、函數是自選的)
| 欄位 | 計算 | 引用注意 |
|---|---|---|
| RSRQ | 3GPP 公式(RSRP+PRB 負載+噪聲)| 不帶新資訊,是既有量的函數 |
| **CQI 分布** | `sinr_to_cqi(SINR)` 確定性查表 | **雷區**:真網路 CQI 是 UE 獨立回報(有誤差有延遲),我們與 SINR 完全相關 —— 拿 CQI 與 SINR「交叉驗證」是自我循環 |
| interfered | 鄰區進 serving 10dB 內 → 1 | 10dB 門檻自定義,非標準 |
| quality | SINR 門檻分級 | 分級線自定義 |
| rb_start | 同 cell 按 rb_width 虛擬疊排 | 寬度真、起點是表示法 |
| cpu_power | CPU% × 65W TDP | 65W 是假設,非功率計 |

| **MRO 三聯 / HO failureCause** | RLF+HO 時序推導分類（TooEarly/Late/WrongCell）| 真事件時序,但分類門檻（T_SHORT 5s 等)自定義 |

### C 級 — 有真實基礎,但**有已知爭議**(絕對值須帶不確定性說明)
| 欄位 | 爭議 |
|---|---|
| PrbTot% | ×10 為單點標定;burst 流量誤差 ±50%~2 倍(full_day EVE 相位實測 209%);對 SINR 高度敏感。趨勢可信、絕對值打折 |
| **RlcSduDelay** | 三重失真:只含排程佇列(無空口/HARQ)、粗 tick 時基失真(granularity bottleneck 未解)、OAI 對照低載重尾為 artifact。**全 KPM 最不宜引用絕對值的欄位** |
| MCS 分布 | 決策真,但無 OLLA/BLER 回饋迴路 —— 分布比真基站「乾淨」,缺探索震盪 |
| session 累計族(MCS/CQI bins、PRBUsageNbr、PdcpVol 累計版)| 無 15min ROP 週期重置,偏離 28.552 語意;絕對值隨 session 膨脹,增量(兩時點相減)仍正確 |
| HoPrepReq/Succ | 從單一 status 欄反推兩階段,近似;無獨立 Prep 失敗原因碼 |

### D 級 — 代理值(引用必須聲明 proxy)

| 欄位 | 代理方式 |
|---|---|
| bbu_status 全族 | 量測對象是模擬主機,不是被模擬的 gNB 硬體 |
| PEE 溫度 | VM 無感測器,恆 0 |
| **ConnReConfigAtt/Succ**（2026-08-12）| HO 執行鏡像 —— 換手是真的,但「Reconfig」欄位在借 HO 的數(真實 Reconfig 還含量測配置變更,平台只有 HO 一來源)|

**使用鐵則**:相對比較(cell 間、換手前後、趨勢)→ 四級全可用;
絕對值入報告 → A 直接用、B 註明推導、C 帶不確定性、D 聲明 proxy。

---

## 附三:識別與中繼資料欄位(真實,25 欄)

不是量測值,但都是**真實的系統狀態/身分**,非合成。分四組:

### Top-level(4 欄)
| 欄位 | 來源 |
|---|---|
| `timestamp_ms` | snapshot 產生時刻(epoch ms,真時鐘)|
| `compute_ms` | 本次 collect() 實際耗時(monotonic 計時,壓測實測 32~180ms)|
| `tick_ms` | DU dump_pm 的 `wall_tick_ms` —— 當下 tick 真實牆鐘耗時(可看出 sim 忙不忙)|
| `warnings` | 組裝期間資料源異常清單(DU/UE 連不上時有內容),真實健康訊號 |

### e2[] 身分欄(5 欄)
| 欄位 | 來源 |
|---|---|
| `gnb_id` / `ran_name` | Omniverse 建立的 gNB 名稱(CellConfig.gnb_id;兩欄同值)|
| `cell_id` | CellConfig.nr_cellid 的 15 位 hex(36-bit NCI,OAI 對齊的真實 cell 識別);無 nr_cellid 退回字串 id |
| `pci` | CellConfig.pci —— 建 cell 時指定的真實 Physical Cell ID,Sionna TX 命名(`{gnb}#{pci}`)同源 |
| `timestamp` | epoch 秒 |

### ue_status[] 身分欄(5 欄)
| 欄位 | 來源 |
|---|---|
| `ue_id` | UE 名稱(E2 wire 上對應 SHA-1 決定性 ngap_id,可離線對照)|
| `serving_gnb` / `serving_pci` | UeContext.serving_cell 反查 CellConfig —— CU 狀態機的真實歸屬 |
| `role` | 恆 1 —— 但語意真實:報告只收 RRC=CONNECTED 的 UE,role=1 是這個過濾的如實陳述 |
| `qos_5qi` | UeContext.traffic_profile 的真實設定(未指定預設 9)|

### 量測重組欄(1 欄)
| 欄位 | 來源 |
|---|---|
| `all_rsrp` | serving + 鄰區 RSRP(全為光追真值)按 gNB 重新分組,同 gNB 多 cell 取最強 —— 是第 1 節 RSRP 的**視圖**,不是新量測 |

另:FULLKPM 走 E2 wire 時 indication header 的 `sn / part / parts / raw_bytes / encoding` 是傳輸信封欄位(真實序號與分塊資訊),屬協定層不屬資料內容,見 `api/e2sm_fullkpm.md`。

*合成的 7 個檔頭欄位(timestamp_start/end、filename、CU_Capability)不在本篇 —— 見 `kpm_field_notes_zero.md` 附「合成佔位欄位」。*

---

*相關文件:`kpm_field_notes_zero.md`(零值+合成欄位)、`E2_full_kpm_fields.md`(190 欄總表)、`api/e2sm_fullkpm.md`(RIC 訂閱取得方式)、`test_records/oai_kpm_calibration_2026-05-23.md`(PRB ×10 校正依據)。*
