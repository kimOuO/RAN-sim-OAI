# OAI PM / bbu_status 產生機制研究筆記

**撰寫日期**：2026-04-18
**研究目的**：搞清楚真 OAI 的 pm 和 bbu_status 欄位從哪算出來，判斷 ranp-sim 能不能/怎麼模擬。
**參考來源**：OAI GitLab、3GPP TS 28.552、arXiv 2503.12177 (Open Wireless Digital Twin)、O-RAN WG3 E2SM-KPM v03.00、OAI 2021-06 Summer Workshop

---

## 1. OAI 架構：PM 從哪冒出來

### 1.1 資料來源層級

OAI 的 KPM 計數器分散在 4 層，每層都有自己的 stats struct：

| 協議層 | 主要 struct | 位置 | 負責欄位 |
|---|---|---|---|
| **MAC** | `mac_ue_stats_impl_t` | `openair2/LAYER2/NR_MAC_gNB/` | RSRP、MCS、BLER、PRB 分配、HARQ |
| **RLC** | `rlc_radio_bearer_stats_t` | `openair2/LAYER2/nr_rlc/` | RlcSduDelay、retransmission |
| **PDCP** | `pdcp_radio_bearer_stats_t` | `openair2/LAYER2/nr_pdcp/` | PdcpSduVolumeDL/UL |
| **GTP** | `gtp_ngu_t_stats_t` | `openair3/GTPV1-U/` | N3 介面 byte count |

### 1.2 產生流程時序

```
每個 TTI (= 1 slot = 0.5 ms for 30 kHz SCS)，gNB MAC 排程器：
  ├─ 收 UE CSI / SRS → 量 SNR / CQI
  ├─ 跑 PF scheduler (proportional fair)
  │   └─ get_mcs_from_bler() 決定 MCS
  ├─ 分配 PDSCH/PUSCH PRB
  ├─ 等 HARQ ACK/NACK
  │   └─ 更新 dlsch_rounds, ulsch_errors
  └─ 累積到 mac_ue_stats_impl_t

每 256 frame (= 2.56 秒) 輸出一次週期統計 log：
  UE RNTI f777 CU-UE-ID 1 in-sync PH 48 dB PCMAX 20 dBm, average RSRP -44
  dlsch_rounds 1183/0/0/0 dlsch_errors 0 BLER 0.00000 MCS 0
  ulsch_rounds 11816/0/0/0 SNR 50.5 dB NPRB 5
  MAC: TX 20094 RX 200962 bytes

E2 Agent (獨立 thread，openair2/E2AP/) 訂閱生效後：
  訂閱週期到（例如 1 秒）：
    ├─ Poll mac_ue_stats_impl_t + rlc_* + pdcp_*
    ├─ 計算 delta (since last report)
    ├─ 按 E2SM-KPM v03.00 ASN.1 schema 打包
    └─ 透過 SCTP 傳給 Near-RT RIC
```

### 1.3 關鍵演算法

#### MCS 選擇（`get_mcs_from_bler()` in `gNB_scheduler_primitives.c`）

```
每 50 ms 視窗計算:
  BLER = (first-round HARQ failures) / (total transmissions)

if BLER > 0.15 (dl_bler_target_upper):   MCS -= 1
if BLER < 0.05 (dl_bler_target_lower):   MCS += 1
else:                                     MCS 維持
```

初始 MCS 由 UE 送上來的 **CQI (0~15)** 決定，透過 3GPP TS 38.214 Table 5.2.2.1 對應。

#### RSRP（PUSCH/SRS 估計）

gNB 端 RSRP 不是量 UE 回報，而是從**上行參考信號 RE 能量平均**：
```
RSRP_dBm = mean_power( DMRS REs of PUSCH )  在 OFDM 符號層級
```
程式碼在 `openair1/PHY/NR_ESTIMATION/` 目錄。

#### BLER（實際計數）

HARQ 收到 ACK/NACK 後：
```
dlsch_rounds[round_idx]++  每次 retx round 的成功計數
dlsch_errors++             如果四輪都沒成功
BLER = sum(errors) / sum(rounds)
```

#### 吞吐量（實際通過的 byte）

```
DRB.PdcpSduVolumeDL_5QI9 = sum(bytes 通過 PDCP DL 給 UE 的 SDUs)
DRB.UEThpDl               = 每次 DL buffer 清空時採樣 (bytes / empty_interval)
RRU.PrbTotDl              = 該 slot 配給 DL 的 PRB 數量
```

---

## 2. bbu_status — **不是 3GPP 的，是 vendor 的**

**重要發現**：`bbu_status` (`cpu`, `cpu_power`, `cpu_temp`, `load_average`, `mem`, `tot_power`) **不在 3GPP TS 28.552 規範**，也不是 OAI E2AP 原生產出的欄位。

它是**貴司自訂的硬體遙測區塊**，真實來源通常是：

| 欄位 | 真 RAN 怎麼拿 | 機制 |
|---|---|---|
| `cpu` | `/proc/stat` 或 IPMI DCMI | OS 或 BMC |
| `cpu_power` | Intel RAPL (`/sys/class/powercap/intel-rapl/`) 或 IPMI | CPU 封裝功耗感測器 |
| `cpu_temp` | `lm-sensors` / `/sys/class/thermal/thermal_zone*` | 主機板 / 核溫感測 |
| `load_average` | `uptime` / `os.getloadavg()` | Linux kernel |
| `mem` | `free` / `/proc/meminfo` | Linux kernel |
| `tot_power` | Redfish / SNMP / PDU | 機架層 BMC |

**OAI 不生這些**。通常由旁邊的 `node_exporter` / `ipmi_exporter` / vendor DMS 往 JSON 注入。

---

## 3. arXiv 2503.12177 (Open Wireless Digital Twin) 的做法

這篇論文正好做我們類似架構：**OAI + Sionna RT 整合**。關鍵引用：

> *"Sionna RT supplies: Pre-computed CIRs (sorted by power, top 28 taps selected for real-time execution)"*
>
> *"OAI applies: Convolution via BLIS library at baseband level: y[n] = Σ s·h̄[k]·x_k[n-k] + σ·w[n]"*
>
> *"OAI measures: Signal quality metrics from resulting IQ samples"*

### 關鍵觀察

**Sionna 只算 CIR**。CIR 丟進 OAI 的 rfsimulator，OAI chanmod 用 convolution 套在 I/Q 上，**之後所有 RSRP/SINR/MCS/BLER/throughput 都是 OAI 從 I/Q 重新量的**——不是 Sionna 算完給 OAI。

這就是為什麼他們可以產出完整 E2SM-KPM v03.00 counters——真實 OAI 協議棧在跑。

---

## 4. 我們 ranp-sim 相對於真 OAI 的 mapping

我們是 **compute-only 純 Python**，沒 MAC layer、沒 HARQ、沒 RRC 狀態機。所以只能算「真 OAI 從 I/Q 量完的**最終數值**」，不能算「過程 counter」。

### 4.1 可以模擬的欄位對應

| 真 OAI 來源 | OAI 算法 | ranp-sim 對應做法 | 準確度 |
|---|---|---|---|
| RSRP (PUSCH DMRS 能量) | 平均 RE 功率 | `tx_power + 10·log10(path_gain_linear)` | ✅ 數學等價 |
| SINR (PUSCH 解碼後) | 實量 S/(N+I) | `signal_lin / (Σ其他RSRP_lin + noise_lin)` | ✅ 近似 |
| CQI | UE 送 CSI report | SINR → CQI table (TS 38.214) | 🟡 近似 |
| MCS | `get_mcs_from_bler()` | SINR → MCS table | 🟡 不含 BLER 回授調整 |
| BLER | HARQ 實計 | 從 SINR 查 BLER-curve | 🟡 近似，無真實重傳 |
| DL throughput | PDCP SDU volume | MCS × N_RB × 12 × slots × overhead | ✅ 理論峰值 |
| PRB 分配 | scheduler 累積 | `rb_width` = 全部給單 UE | ❌ 我們沒多 UE 競爭排程 |
| PDCP Volume | byte 累加器 | `throughput_Mbps × tick_s × 125_000` | 🟡 stub |

### 4.2 不能模擬的欄位（需真 OAI）

- `cu_RRC.ConnMax`、`cu_RRC.ConnEstabAtt.sum` — RRC 狀態機事件
- `cu_MM.HoExeIntraFreqSucc` — Handover 執行結果
- `cu_SM.PDUSessionSetupSucc` — PDU Session 建立
- `cu_DRB.EstabSucc.5QI9` — DRB 建立成功
- `du_TB.TotNbrDl` — 實際 TB 傳輸次數（需 HARQ）
- 各類 PEE (Power, Energy, Environment) — 需實體硬體感測器

這些全由狀態機 / 信令實體產生，**純 compute 服務無能為力**。

### 4.3 bbu_status 模擬可行性

我們可以做，但準確度有限：

| 欄位 | 可模擬方法 | 準確度 |
|---|---|---|
| `cpu` | 容器內 `psutil.cpu_percent()` | ✅ host real |
| `cpu_power` | Intel RAPL (需 host `/sys` mount) | 🟡 host 值不是 gNB 值 |
| `cpu_temp` | `psutil.sensors_temperatures()` | 🟡 容器可能讀不到 |
| `load_average` | `os.getloadavg()` | ✅ |
| `mem` | `psutil.virtual_memory().percent` | ✅ |
| `tot_power` | `pynvml` 取 GPU 功耗 + 估 CPU | 🟡 混合 |

**一個硬限制**：我們容器跑 3 個 gNB，但 bbu_status 每 gNB 一份。所以只能把 host 指標**按 gNB 數分攤**，或三個 gNB 回傳相同值（誠實但看起來很假）。

---

## 5. 建議實作策略（如果要補 pm / bbu_status）

### Tier 1 ✅ 可行且誠實：`bbu_status` + PHY/MAC 類 pm

```python
# 每 tick compute 後呼叫:
PmAggregatorService.accumulate(
    ue_stats=[
        {"mcs": 19, "cqi": 11, "sinr": 21, "rb_width": 273},
        ...
    ],
    tick_ms=500,
)

# /ComputeRunner/compute 輸出加 pm 區塊:
pm = PmAggregatorService.build_kpm_report()
# 含 du_CARR.PDSCHMCSDist.BinTable2.BinMCS19 等 histogram
# 含 cu_DRB.PdcpSduVolumeDL_5QI9 = accumulated bytes

bbu_status = BbuTelemetryService.snapshot()
# cpu/mem/load/temp 真實；按 gNB 平均分配
```

**工程量**：~300 行 Python，半天。

### Tier 2 ❌ 需接 OAI：信令類 pm

走 Option B（ranp-sim 算 path gain → 透過 telnet 推給 OAI chanmod → OAI 自行上報）。參考 `LLM_learning/2026-04-18_simulated_ran_design_note.md`。

**工程量**：2~4 週 + OAI 硬體環境。

---

## 6. 關鍵參考連結

### OAI 源碼
- [openair2/E2AP/README.md](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/develop/openair2/E2AP/README.md) — E2 agent 集成指南
- [doc/MAC/mac-usage.md](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/MAC/mac-usage.md) — MAC scheduler 與 MCS 選擇
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c` — `get_mcs_from_bler()`
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c` — DL 排程 `pf_dl()`
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c` — UL 排程 `pf_ul()`

### 規範
- [3GPP TS 28.552](https://www.3gpp.org/dynareport/28552.htm) — 5G Performance Measurements
- [3GPP TS 38.214](https://www.etsi.org/deliver/etsi_ts/138200_138299/138214/) — MCS / CQI tables
- [3GPP TS 38.215](https://www.etsi.org/deliver/etsi_ts/138200_138299/138215/17.03.00_60/ts_138215v170300p.pdf) — 物理層量測 (RSRP/RSRQ/SINR 定義)
- [O-RAN WG3 E2SM-KPM v03.00](https://orandownloadsweb.azurewebsites.net/specifications) — KPM Service Model

### 論文
- [Open Wireless Digital Twin: OAI + Sionna RT (arXiv 2503.12177)](https://arxiv.org/html/2503.12177v3) — 最相近的參考實作

### FlexRIC
- [FlexRIC GitLab](https://gitlab.eurecom.fr/mosaic5g/flexric)
- [FlexRIC 教學 Lab1 PDF](https://openairinterface.org/wp-content/uploads/2021/12/Lab1.pdf)
