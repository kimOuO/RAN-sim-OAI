# Output 欄位真值分類表

**撰寫日期**：2026-04-19
**用途**：把 `/compute` 回傳的每個欄位分類成「實際算 / 模擬推 / 沒法算」，誠實標註每個數字的由來。

---

## 📋 Table 1：**實際的值**（真實計算或真實探測）

這些欄位的數字**可信度最高**，是物理光追、3GPP 公式或系統真實探測的結果。

| 欄位 | 是什麼 | 透過什麼算 | 代表什麼 |
|---|---|---|---|
| **`e2[].cells[].ues[].rsrp`** | UE 收到 serving gNB 的訊號強度（dBm） | Sionna PathSolver 算所有 path 複數增益 → `tx_power + 10·log10(Σ|a_i|²)` | UE 離基站多遠、被什麼擋、訊號多強 |
| **`rsrq`** | 訊號相對乾淨度（dB） | 3GPP TS 38.215：`-10·log10(12) - 10·log10(1+1/SINR)` | 訊號被干擾的程度 |
| **`sinr`** | 訊號對干擾+雜訊比（dB） | `serving_RSRP / (Σ 鄰居 RSRP + kTB·NF)` | 通訊品質 |
| **`neighbors[].rsrp`** | 鄰居 gNB 訊號強度 | Sionna 同時對所有 gNB 算 path_gain | Handover 決策、干擾源辨識 |
| **`neighbors[].rsrq`** | 鄰居訊號品質 | 把該鄰居當 serving 重算 RSRQ | 鄰居品質評估 |
| **`interfered`** | 是否被鄰居強干擾（0/1） | 任一 neighbor RSRP > serving−6 dB → 1 | cell edge 標記 |
| **`dl_throughput`** | UE 下行吞吐（Mbps） | MCS × N_RB × 12 × N_symbols × slots_per_sec × overhead（3GPP 標準公式） | 實際下載速度 |
| **`rb_width`** | UE 實際分到的 PRB 數 | PF scheduler 按 `inst_rate / avg_rate` 比例分配 | 頻寬分配公平性 |
| **`mcs_dl`** | UE 當下使用的 MCS index | BLER 閉環：SINR 估 BLER → 50ms 窗 → 調整 MCS（對齊 OAI）| link adaptation 實況 |
| **`quality`** | UE 品質分級（excellent/good/fair/poor） | SINR > 20/10/0 分層 | UI 顯示用 |
| **`cu_DRB.PdcpSduVolumeDL_5QI1/4/9`** | 累積下行 PDCP bytes（分 QoS） | `throughput_Mbps × tick_ms × 125000` 累加 | 累積流量統計（分語音/影片/資料） |
| **`cu_DRB.PdcpSduVolumeUl_5QI*`** | 累積上行 PDCP bytes | 同上（UL throughput）| UL 流量 |
| **`cu_gnb.DRB.SdapSduVolumeDL/Ul.5QI*`** | SDAP byte volume | 等同 PDCP（SDAP 在 PDCP 之上） | 5G QoS flow 流量 |
| **`du_CARR.PDSCHMCSDist.BinTable2.BinMCS0~31`** | DL MCS 分佈直方圖 | 每 tick 各 UE MCS 計數累加到對應 bin | gNB 服務 UE 的 MCS 分佈 |
| **`du_CARR.PUSCHMCSDist.BinTable1.BinMCS0~31`** | UL MCS 分佈 | 同 | UL 品質分佈 |
| **`du_CARR.WBCQIDist.BinCQI0~15.BinTable2`** | CQI 分佈直方圖 | SINR → CQI (3GPP TS 38.214) 累加 | UE 回報品質分佈 |
| **`du_CARR.PRBUsageDLNbr`** | DL PRB 累積使用 | `rb_width_dl` 跨 tick 累加 | 基站頻寬負載 |
| **`du_CARR.PRBUsageULNbr`** | UL PRB 累積使用 | 同（UL 版）| UL 負載 |
| **`du_169:PEE.AvgTemperature`** | 基站平均溫度（°C） | 從 bbu_status 的 cpu_temp 借 | 硬體熱狀況 |
| **`bbu_status.cpu`** | 基站主機 CPU 使用率（%） | `psutil.cpu_percent()` 真讀 host | host 真實負載 |
| **`bbu_status.cpu_temp`** | CPU 溫度（°C） | `psutil.sensors_temperatures()` 讀 sysfs | 硬體熱狀況 |
| **`bbu_status.load_average`** | 系統 load avg (1-min) | `os.getloadavg()[0]` | Linux 核心負載 |
| **`bbu_status.mem`** | 記憶體使用率（%） | `psutil.virtual_memory().percent` | host 記憶體壓力 |
| **`compute_ms`** | 本 tick compute 花的毫秒 | wall clock 量 actor 進出時間差 | 後端效能監控 |
| **`timestamp`, `tick_ms`** | 時間戳 / tick 間隔 | 透傳 / 跨 tick 時間差 | 同步 / 效能 |

**數量**：**~90 個欄位**（占總欄位 ~40%）

---

## 📋 Table 2：**虛擬的值**（有模擬但不是真實協議行為）

這些欄位有數字，**但不是從真實 RAN 信令算出來的**，我們用「狀態機推論」或「簡化模型」逼近。

| 欄位 | 是什麼 | 為什麼不能真算 | 我們怎麼模擬 |
|---|---|---|---|
| **`ul_throughput`** | UE 上行吞吐 | 真實要 Sionna 再跑一次反向（UE→gNB），compute × 2 | **Reciprocity 定律**：channel 互易 → UL SINR = DL SINR − 19 dB（UE 功率 20 dBm vs gNB 43 dBm + gNB NF 3 vs UE 7 dB）→ 再查 MCS 表 |
| **`cu_RRC.ConnEstabAtt.sum`, `ConnEstabSucc.sum`** | RRC 連線建立次數 | 沒真實 RRCSetupRequest / RRCSetupComplete 信令 | UE id **首次**出現在 `ue_positions` → +1（假設都 mo-Data、假設 100% 成功）|
| **`cu_RRC.ConnEstab*.mo-Data`** | mo-Data 類型的連線 | 沒區分 mo-Data / mo-Signalling / Emergency | 全部假設成 mo-Data |
| **`cu_RRC.ConnMax`** | 同時連線最大 UE 數 | 需追蹤 UE 連線狀態機 | 跨 tick 觀察 `len(ues_on_gnb)` 取 max |
| **`cu_RRC.ConnMean`** | 連線數 EWMA 平均 | 同上 | EWMA：`0.9·prev + 0.1·current` |
| **`cu_UECNTX.ConnEstab*`** | UE context 建立 | 沒真 UE context 管理 | 跟 RRC.ConnEstab 同步 |
| **`cu_UECNTX.Release.5GCinit.sum`** | CN 主動釋放 UE | 沒真 NAS / AMF 釋放信令 | UE id 從 `ue_positions` **消失** → +1 |
| **`cu_MM.HoExeIntraFreqReq`** | 同頻 handover 執行請求 | 沒真 HandoverCommand 信令 | **A3 event 持續 TTT (160 ms) 真觸發** → +1（對齊 3GPP TS 38.331）|
| **`cu_MM.HoExeIntraFreqSucc`** | 同上但成功 | 沒真 HandoverComplete | HO 執行後 SINR > 3 dB 視為 Succ |
| **`cu_MM.HoPrepIntraReq/Succ`** | HO 準備階段 | 沒真 preparation 訊息 | 和 HoExe 同步 +1 |
| **`cu_gnb.MR.Event.A3`** | A3 事件觸發次數 | 沒真 UE Measurement Report | 每 tick 檢查 neighbor RSRP > serving + 3 dB 持續 160 ms → +1 |
| **`cu_SM.PDUSessionSetupReq/Succ`** | PDU Session 建立 | 沒真 NAS PDU Session Establishment | 跟 RRC.ConnEstab 同步（假設每 UE 有 1 session） |
| **`cu_DRB.EstabAtt/Succ.5QI9`**, **`.sum`** | DRB 建立 | 沒真 DRB add flow | 跟 ConnEstab 同步（假設每 UE 1 DRB，預設 5QI9） |
| **`cu_DRB.InitialEstab*`** | 初始 DRB 建立 | 同上 | 同上 |
| **`cu_gnb.RRC.ConnEstabSetup.sum`** | RRC 連線建立完成 | 沒真 setup complete 信令 | 跟 ConnEstabSucc 同步 |
| **`bbu_status.cpu_power`** | CPU 功耗（W） | 容器通常讀不到 Intel RAPL | Fallback: `CPU% × TDP(65W) / 100` 估算 |
| **`bbu_status.tot_power`** | 總功耗（W） | 容器讀不到完整硬體功耗 | GPU 功耗（pynvml 真值）+ CPU 功耗（上面估算） |
| **`rb_start`** | UE 分到的 PRB 起始位置 | 沒做 frequency-domain 排程 | 固定 0（從 PRB 0 開始）|
| **`cu_CU_Capability`** | CU 能力旗標 | 沒能力協商邏輯 | 固定 `"1"` |
| **`cu_DRB.PdcpReordDelayUl`** | PDCP 重排序延遲 | 沒真 PDCP buffer | 固定 `"3"` ms |
| **HARQ rounds 期望值**（內部用於 pm） | 各 HARQ 輪次成功計數 | 沒真 HARQ decoder | 從 BLER 機率累加期望值：`rounds[i] += (1-b)·b^i` |

**數量**：**~60 個欄位**（占總欄位 ~27%）

**共同特徵**：
- 數字有**合理量級**（不會亂跳）
- 但**不代表真實 RAN 協議事件**（不能做 bit-accurate 信令對齊）
- 用於 demo / 研究整體行為時**足夠真實**

---

## 📋 Table 3：**沒法算的值**（永遠輸出 `"0"` 或空）

這些欄位 schema 保留，但**我們的架構根本做不出來**，需要真 OAI / RRC 狀態機 / 真 HARQ decoder 才有意義。

| 欄位 | 是什麼 | 為什麼不能算 |
|---|---|---|
| **`cu_RRC.ConnReEstab.ReEstab.sum`**, **`.otherFailure`** | RRC 重建連線次數 | **沒模擬 UE 掉線又重連事件**。我們的 UE 只是位置移動，沒有「斷線」概念 |
| **`cu_RRC.ReEstabAtt`**, **`.otherFailure`** | RRC 重建嘗試 | 同上 |
| **`cu_RRC.ReEstabSuccWithUeContext.sum/otherFailure`** | 重建（保留 UE context）成功 | 沒 UE context 狀態機 |
| **`cu_RRC.ReEstabSuccWithoutUeContext.sum/otherFailure`** | 重建（無 UE context）成功 | 同上 |
| **`cu_RRC.ConnReEstabSetup.sum`** | RRC 重建設置完成 | 沒真信令交換 |
| **`cu_gnb.RRC.ConnReEstab.ReEstab.sum`**, **`.otherFailure`** | 同 RRC 類 | 同 |
| **`cu_gnb.RRC.ConnReEstabSetup.otherFailure`** | 重建失敗 | 沒失敗模擬 |
| **`cu_gnb.RRC.ConnRelease.Other`**, **`.sum`** | 「其他原因」釋放 | **沒 RRC 狀態機追 release reason**（只有 UE 消失算 5GCinit，分不出 gNBinit / Other） |
| **`cu_gnb.UECNTX.Release.gNBinit.RNCause/sum`** | gNB 主動釋放 | 沒 gNB-side 主動釋放邏輯（timeout、overload）|
| **`cu_UECNTX.Release.5GCinit.NASCause/RNCause`** | 釋放原因碼 | **沒 NAS 訊息**，無從得知是哪種 cause |
| **`cu_gnb.RRC.ConnReConfigAtt`**, **`ConnReConfigSucc`** | RRC 重配置 | **沒模擬 RRCReconfiguration**（改 BWP / 改 measurement / 改 HARQ config）|
| **`cu_gnb.RRC.SigTimeSetup.Avg/Max`** | 連線建立訊息交換時間 | **沒真信令傳輸延遲**（要 RRC 訊息在真 air interface 傳才有）|
| **`cu_gnb.RRC.SigTimeReEstab.Avg/Max`** | 重建訊息時間 | 同上 |
| **`cu_gnb.RRC.SigTimeReconfig.Avg/Max`** | 重配置訊息時間 | 同上 |
| **`du_DRB.AirIfDelayDlAvg.5QI1/9`** | DL 空介面平均延遲 | **沒真 HARQ retransmission 時序**（延遲 = HARQ RTT × 重傳次數，要真 MAC 排程）|
| **`du_DRB.AirIfDelayUlAvg.5QI1/9`** | UL 空介面平均延遲 | 同上 |
| **`du_TB.TotNbrDl`**, **`TotNbrUl`** | Transport Block 總數 | **沒模擬每 slot 的 TB 傳輸**（要真 MAC per-slot scheduler）|
| **`cu_gnb.SM.PDUSessionRelease.Att/Succ`** | PDU Session 主動釋放 | 沒真 NAS PDU Session Release 訊息 |
| **`cu_DRB.PdcpPacketDiscardDL.5QI9`** | PDCP 封包丟棄數 | **沒 PDCP buffer 模擬**（要有真實 buffer overflow 才會丟）|
| **`cu_DRB.RelActNbr.5QI9/sum`** | 活躍 DRB 釋放次數 | 沒 DRB 釋放事件 |
| **`cu_DRB.SessionTime.5QI9/sum`** | Session 持續時間累積 | 沒 session 起訖時間追蹤 |
| **`cu_QF.EstabAttNbr/EstabSuccNbr.5QI9/sum`** | QoS Flow 建立 | **沒 QFI 管理層**（QoS Flow 細於 DRB） |
| **`cu_QF.InitialEstabAttNbr/SuccNbr.*`** | 初始 QoS Flow | 同 |
| **`cu_QF.RelActNbr.Qos9/sum`** | 活躍 QoS Flow 釋放 | 同 |
| **`cu_QF.ReleaseAttNbr.5QI9/sum`** | QoS Flow 釋放嘗試 | 同 |
| **`cu_RRC.ConnEstabAtt.mo-Signalling`**, **`ConnEstabSucc.mo-Signalling`** | 信令類連線 | 我們假設所有 UE 都是 mo-Data，沒區分 |
| **`cu_RRC.ConnEstabSucc.emergency`** | 緊急呼叫連線 | 沒模擬 emergency call |
| **`cu_gnb.RRC.ConnEstabSetup.emergency/mo-Signalling/mo-Data`** | 同上分類 | 同 |
| **`cu_DRB.InitialEstabAtt.5QI1`** | 語音 DRB 初始建立 | 我們主要建 5QI9；5QI1 / 5QI4 跟 UE input 的 qos_5qi 相關 |
| **`du_CARR.PDSCHMCSDist.BinTable1.BinMCS0~31`** | 舊 64QAM-only hardware 的 DL MCS 分佈 | 我們預設用 Table 2（256QAM），Table 1 欄位沒觸發 |
| **檔名欄位** `cu_filename`, `du_filename`, `du_timestamp_end` | XML 檔名 / 時間標記 | 我們不寫 XML 檔（真 OAI 會定期 flush XML 給 NMS） |

**數量**：**~120 個欄位**（占總欄位 ~55%，最大宗）

**共同特徵**：
- 都是真 **RRC / NAS / HARQ 狀態機 / 信令訊息** 層級的 counter
- 我們的 **compute-only 架構**本質上產不出
- 想補齊要接 **OAI** 或寫**簡化 RRC 狀態機**（FUTURE_WORK #10 / #15）

---

## 🎯 三張表總計

| 分類 | 欄位數 | 占比 | 可信度 |
|---|---|---|---|
| 🟢 **實際算 / 真值** | ~90 | 40% | ★★★★★ 物理 / 規格真實 |
| 🟡 **虛擬模擬** | ~60 | 27% | ★★★ 量級合理、非真信令 |
| 🔴 **沒法算（占位）** | ~120 | 55% | ★ 只有 schema 對齊，沒語意 |

**核心**：**RSRP / RSRQ / SINR / Throughput / MCS / 覆蓋圖** 這些 RAN 最核心的 KPI **都在 Table 1**（真算）。

**外圍信令計數器**（ReEstab、SigTime、AirIfDelay 等）在 Table 3，**要真 OAI 才有**。

**介於兩者之間**的 RRC 事件 / HO 決策 / PDCP volume 在 Table 2，用**狀態機推論**得到合理近似值。

---

## 💡 如何「填滿」Table 3 的空欄位

要把 Table 3 欄位變有值，按 FUTURE_WORK.md 排序：

1. **#15 簡化 RRC 狀態機**（2 天）→ 補 ~30 個 ReEstab / Release.Other / ConnReConfig 相關
2. **#12 真 HARQ + BLER 閉環 MCS**（已做完 50%，但沒補 AirIfDelay）→ 補 ~10 個 AirIf / TB.TotNbr
3. **#10 真 E2AP over SCTP + 接真 OAI**（1-2 週）→ 補 **剩下 ~80 個**（SigTime / QoS Flow / 5QI1 語音等）
4. **#17 MCS Table 1 支援**（1 小時）→ 補 32 個 BinTable1 欄位

做完 #15 + #12 + #17 → **Table 3 剩 ~50 個空**，覆蓋率 **55% → 78%**。
做到 #10 → **接近 95%**（極少數 OEM 特殊欄位除外）。
