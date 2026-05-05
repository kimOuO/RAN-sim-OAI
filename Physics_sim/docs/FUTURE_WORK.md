# ranp-sim 未來待辦（物理保真度 / 升級項目）

**撰寫日期**：2026-04-19
**用途**：記錄**現在沒做、但真實 RAN 有**的物理模擬項目。當 demo 需求升級、或轉做論文/商用驗證時，照此清單依優先級做。

> **前提**：ranp-sim 目前的設計目標是 **MVP + 3GPP UMi demo**，很多真 RAN 物理細節被簡化或略過。以下是清單。

---

## 優先級索引

| 優先 | 項目 | 影響面 | 觸發時機 |
|---|---|---|---|
| P1 | [MIMO / Beamforming 升級](#1-mimo--beamforming-升級) | 絕對 RSRP ±15~20 dB、Throughput ×2~×8 | 要展示「真 5G 速度」/ 對標 AODT |
| P2 | [大氣衰減（氣體吸收）](#2-大氣吸收-itu-r-p676) | mmWave 以上才顯著 | 跑 28 GHz 以上頻段 |
| P2 | [雨衰 / 天氣模型](#3-雨衰-itu-r-p838) | 天氣 demo、mmWave | 要做「雨天覆蓋下降」demo |
| P3 | [雲霧衰減](#4-雲霧-itu-r-p840) | 特定高緯度/高海拔 | 極少情境 |
| P3 | [高階繞射（>1st order）](#5-高階繞射) | 深 NLOS 陰影區 | 精度要求極高 |
| P3 | [Fast fading（Rician/Rayleigh 快衰落）](#6-fast-fading-快衰落) | ms 級 RSRP 抖動 | 做 link adaptation / HARQ 研究 |
| P3 | [上行（UL）真實模擬](#7-ul-真實模擬) | UL 目前是 DL÷5 近似 | UL 是研究重點時 |
| P3 | [Doppler 效應（相位利用）](#8-doppler-效應) | 高移動 UE 的 CIR 相位 | 車聯網 / 高鐵 / HARQ 研究 |
| P2 | [Coverage Map / RadioMapSolver](#9-coverage-map--radiomapsolver) | 全區 RSRP heatmap | UI 熱圖 / 基站位置最佳化 |
| **P1** | [真 E2AP / ASN.1 over SCTP](#10-真-e2ap--asn1-over-sctp) | 接真 RIC / FlexRIC xApp | 要對接標準 O-RAN xApp 生態 |
| **P1** | [A3 TTT handover 邏輯](#11-a3-ttt-handover-邏輯) | HO 判定符合 3GPP | 避免 HO ping-pong 假警報 |
| P2 | [真 HARQ + BLER 閉環 MCS](#12-真-harq--bler-閉環-mcs) | MCS 數字真實 | 做 link adaptation 研究 |
| P2 | [多 QoS（5QI）類型](#13-多-qos5qi類型) | E2 欄位完整分 5QI | demo 語音/影片混合流量 |
| P2 | [PRB 排程爭用（multi-UE PF scheduler）](#14-prb-排程爭用) | throughput 反映搶資源 | 做多 UE 容量研究 |
| P3 | [簡化 RRC 狀態機（ReEstab / Release reason）](#15-簡化-rrc-狀態機) | 填 ConnReEstab / ConnRelease.Other | 連線穩定性分析 |
| P3 | [Slot-level 時間精度](#16-slot-level-時間精度) | 0.5 ms TTI、即時排程 | HARQ / scheduler timing 研究 |
| P4 | [MCS table1（64QAM only）支援](#17-mcs-table1-支援) | PDSCHMCSDist.BinTable1.* 欄位 | 模擬舊 hardware |
| P1 | [Coverage summary 塞進 /compute](#18-coverage-summary-塞進-compute) | 不畫也能拿覆蓋率 % 做決策 | 不想畫熱圖但要統計 |
| **P1** | [Sionna 可微分 → gNB 自動位置最佳化](#19-sionna-可微分--gnb-位置最佳化) | 自動找最佳 gNB 擺放 | **Sionna 殺手鐧，還沒用到** |
| P2 | [E2 RC（Radio Control）反向控制 channel](#20-e2-rc-反向控制) | xApp 發指令改 gNB 功率 | 閉環 AI-RAN 研究 |
| P2 | [Observability / Prometheus metrics](#21-observability--prometheus-metrics) | 生產監控 / SLO | 要 deploy 到 production |
| P2 | [Network Slicing（多 slice）](#22-network-slicing-多-slice) | 3GPP slice SLA demo | 展示 eMBB/URLLC/mMTC 分流 |
| P3 | [Integration test suite（E2E scenarios）](#23-integration-test-suite) | 自動化場景回歸 | 長期維護品質 |

---

## 1. MIMO / Beamforming 升級

### 🔍 現狀
- `PlanarArray(num_rows=1, num_cols=1, pattern="tr38901", polarization="V")`
- gNB 單天線、UE 單天線，**無 beamforming、無 spatial multiplexing**
- Sionna RT CIR shape: `(num_rx, 1, num_tx, 1, num_paths, 1)` → num_rx_ant=num_tx_ant=1

### 📊 影響（跟真 5G 64T64R MU-MIMO 比）
| KPI | 現狀 | 真 5G gNB | 偏差 |
|---|---|---|---|
| RSRP（beam-aligned UE）| 基礎值 | **+15~20 dB** | 🔴 顯著低估 |
| DL throughput（rank ≤4）| 基礎值 | **×2~×8** | 🔴 顯著低估 |
| Cell edge SINR | 基礎值 | **+3~6 dB** | 🟡 中等 |
| 鄰 cell 干擾 | 全向發 | 能量集中、干擾小 | 🔴 顯著 |
| Serving cell 選擇 | ✓ | ✓ | 無（相對比較對）|
| Handover 判定 | ✓ | ✓ | 無 |

### 🛠️ 實作三個層級

| 層級 | 做法 | 程式改動 | VRAM | 工時 |
|---|---|---|---|---|
| **A. Fake beam gain**（5 行）| `e2_formatter.py` 對 serving RSRP 加 `+15 dB` | 5 行 | 無增 | 15 分 |
| **B. 真 4×4 SU-MIMO** | `PlanarArray(num_rows=4, num_cols=4)` tx/rx 同改 | ~20 行 | +~4 GB | 2 小時 |
| **C. 真 64T64R MU-MIMO** | 大陣列 + 波束賦形邏輯（需自寫 precoder）| ~200 行 | **+16 GB**（需 24 GB 卡）| 1 週 |

### 🟢 層級 A 具體做法（quick win）
```python
# services/optional/ran_calculation/e2_formatter.py
BEAM_GAIN_DB = 15.0   # 模擬 4T4R~64T64R 等效增益
rsrp_serving_with_beam = rsrp_serving + BEAM_GAIN_DB
```
換來的價值：**數字量級接近真實 5G**，沒 MIMO 物理但 KPI dashboard 看起來正常。

### ⚠️ 需要新增的 input（層級 B/C）
```json
"gnbs[]": {
  "mimo": {"n_rows": 4, "n_cols": 4, "polarization": "cross"},
  "beamforming_mode": "grid_of_beams" | "codebook" | "digital"
}
```

### 🎯 觸發條件
- 要展示「5G 跑 1 Gbps」類 demo
- 寫論文比較 MIMO rank 對 throughput 的影響
- 對標 AODT 官方結果

---

## 2. 大氣吸收 (ITU-R P.676)

### 🔍 現狀
Sionna RT 只算幾何反射/繞射，**不模擬大氣氣體吸收**（O₂、水氣）。ranp-sim 也沒外掛補。

### 📊 影響（依頻率）
| 頻段 | 吸收率 | 對 100m 路徑影響 | 現在在乎？|
|---|---|---|---|
| 3.5 GHz（我們預設）| ~0.01 dB/km | **0.001 dB** | ❌ 完全可忽略 |
| 28 GHz mmWave | 0.3 dB/km | 0.03 dB | 🟡 略有影響 |
| **60 GHz**（O₂ 吸收峰）| **15 dB/km** | **1.5 dB** | ✅ 必算 |
| 73 GHz | 0.5 dB/km | 0.05 dB | 🟡 |
| **183 GHz**（H₂O 吸收峰）| **30 dB/km** | 3 dB | ✅ 必算 |
| 0.3+ THz（6G 目標）| **>100 dB/km** | 10+ dB | ✅ 絕對必算 |

### 🛠️ 實作
```bash
pip install itur   # 已實作 ITU-R P 系列
```

```python
# services/optional/ran_calculation/atmosphere.py (新增)
import itur

def gas_attenuation_db(freq_ghz, path_length_m, temp_c=25, humidity_pct=60, pressure_hpa=1013):
    γ = itur.gaseous_attenuation_slant_path(...)   # dB/km
    return γ * path_length_m / 1000

# e2_formatter.build() 對每條 path 疊加:
extra_att = gas_attenuation_db(scene.frequency_ghz, path.length_m, ...)
path.gain_db -= extra_att
```

### ⚠️ 需要新增的 input
```json
"environment": {
  "temperature_c": 25,
  "humidity_pct": 60,
  "pressure_hpa": 1013
}
```
皆可選，有合理預設（25°C / 60% RH / 海平面氣壓）。

### 📏 工程量
- 新增 `atmosphere.py` ~50 行
- `e2_formatter.py` 加 3 行 path 衰減疊加
- Serializer 加 optional `environment` 區塊 ~20 行
- 總計 **~80 行，半天**

### 🎯 觸發條件
- 頻率切到 24 GHz 以上
- 6G 研究
- 要做「同軌道不同頻段覆蓋比較」

---

## 3. 雨衰 (ITU-R P.838)

### 🔍 現狀
不模擬降雨。

### 📊 影響
| 頻段 | 10 mm/hr 中雨 衰減 | 50 mm/hr 豪雨 衰減 |
|---|---|---|
| 3.5 GHz | 0.01 dB/km | 0.1 dB/km |
| 28 GHz | **2 dB/km** | **10 dB/km** |
| 60 GHz | 5 dB/km | 20 dB/km |
| 80 GHz | 8 dB/km | 30 dB/km |

Sub-6 基本不影響；mmWave 雨天可能**覆蓋半徑減半**。

### 🛠️ 實作（同 ITU-R P.676）
```python
import itur

def rain_attenuation_db(freq_ghz, path_length_m, rain_rate_mmhr, elevation_deg=0, polarization="V"):
    γ = itur.rain_attenuation(...)  # dB/km
    return γ * path_length_m / 1000
```

### ⚠️ 需要新增的 input
```json
"environment": {
  "rain_rate_mmhr": 10     // 0 = 晴天
}
```

### 🎯 觸發條件
- **「天氣影響覆蓋」demo**（這是最常見的 RAN digital twin 賣點）
- 運營商評估 mmWave 在特定地區可行性

### 📏 工程量
和 ITU-R P.676 同一個 `atmosphere.py` 模組，**+30 行就能加**。

---

## 4. 雲霧 (ITU-R P.840)

### 🔍 現狀
不模擬。

### 📊 影響
小於雨衰，大約 0.1~2 dB/km 在 mmWave。多數應用可忽略。

### 🎯 何時做
- 極少需要
- 優先級最低

---

## 5. 高階繞射

### 🔍 現狀
Sionna RT 只支援**一階繞射**（Keller cone）。

### 📊 影響
- 單層建築遮擋：一階繞射夠
- 多層遮擋（例：UE 站在兩棟大樓中間深巷）：**可能低估訊號 5-15 dB**（實際有多次繞射可達）

### 🛠️ 實作
- Sionna 官方未來版本可能支援
- 目前可自寫 Monte Carlo ray shooting 疊加多次繞射 → 但這等於重寫 Sionna RT
- 或接 Wireless InSite / Remcom 等商業工具（付費）

### 🎯 觸發條件
- 深 NLOS 場景精度不夠（實測 vs 模擬差 >10 dB）
- 做論文要 bit-accurate

### 📏 工程量
**大**（>2 週），不建議自己做。

---

## 6. Fast fading 快衰落

### 🔍 現狀
Sionna 算出的 CIR 是**相干**（coherent）——同個位置算多次得到一樣的複數增益。現實中因為散射體微小變動、反射面粗糙度等，RSRP 會在 ms 級抖動 ±10 dB。

### 📊 影響
- 靜態 RSRP 正確
- 但缺少 **Rician / Rayleigh 快衰落 overlay**，無法 demo HARQ 重傳、link adaptation 實況

### 🛠️ 實作
在 Sionna CIR 外疊加隨機快衰落：
```python
# 每 tick 對 path coefficient 做 Rician / Rayleigh 抽樣
k_rician = los_power / nlos_power  # 從幾何判斷
fast_fade = rician_sample(k_rician) if has_los else rayleigh_sample()
rsrp_with_fade = rsrp + 10*log10(fast_fade)
```

### 🎯 觸發條件
- 要 demo HARQ 重傳次數隨 fading 變化
- Link adaptation / MCS 波動分析
- 論文要和實測抖動比較

### 📏 工程量
**~80 行，1 天**。放 `ran_calculation/fast_fading.py`。

---

## 7. UL 真實模擬

### 🔍 現狀
UL throughput 直接用 `DL ÷ 5` 近似（假設 TDD 4:1）。

### 📊 影響
- UL 數字**完全不是從 Sionna 算來的**，只是估算
- 不能反映 UE 發射功率限制（PCMAX 20 dBm）、Power Headroom 動態
- Noise figure 估計在 gNB 側（~7 dB）跟 UE 側不同

### 🛠️ 實作
雙向 compute：
```python
# 當前：只算 gNB (TX) → UE (RX)
# 升級：再算一次 UE (TX) → gNB (RX)，用 UE 功率上限
paths_ul = solver(scene, tx=ues, rx=gnbs, ...)
rsrp_ul = ue_power_dbm + 10*log10(path_gain)   # UE 20 dBm vs gNB 43 dBm
# gNB 側 noise figure ~3 dB 比 UE 側好
```

### 🎯 觸發條件
- 做 UL 瓶頸研究
- 模擬 PUSCH scheduler

### 📏 工程量
~100 行 + Sionna 多算一次（compute_ms 變 2x）。

---

## 8. Doppler 效應

### 🔍 現狀：**半做**
`sionna_engine.py::compute_paths` 有把 UE velocity 傳給 Sionna Receiver：
```python
rx.velocity = u.get("velocity", [0.0, 0.0, 0.0])
```
Sionna 內部**會**算出 Doppler phase shift 並寫進 CIR 複數相位。**但我們下一步只取 `sum(|a|²)` 當 path gain，只看 magnitude，相位資訊丟掉**。

### 📊 影響
- RSRP / SINR / throughput：**Doppler 不影響瞬時功率**，數字 = 沒 Doppler 一樣
- 需要 Doppler 的情境：
  - HARQ 成功率（相位變化太快影響 channel estimation）
  - Link adaptation 反應速度
  - OFDM ICI（Inter-Carrier Interference）分析
  - 3GPP TDL 通道模型的時間相干

### 🛠️ 實作
不是加 Sionna 輸入（已經有 velocity），是**怎麼用 CIR 的相位**：

```python
# 目前: 只取 magnitude
pg = np.sum(np.abs(coeffs) ** 2)

# 升級 A: 取 time-varying CIR（Sionna 支援 num_time_steps > 1）
a, tau = paths.cir(num_time_steps=100, time_step=1e-6, ...)  # 100 個時間點 × 1μs
# 輸出 per-OFDM-symbol 級的 phase 變化
```

### 🎯 觸發條件
- 高速移動 UE（車聯網、高鐵）場景
- HARQ 研究
- Link adaptation / MCS 切換行為分析

### 📏 工程量
Sionna 已支援 → 改 `compute_paths` 回傳結構 + 下游做 Doppler analysis → **~100 行，半天**。

---

## 9. Coverage Map / RadioMapSolver

### 🔍 現狀：**完全沒做**
我們用 Sionna `PathSolver()` → 只算**離散 UE 點**的 CIR。
Sionna 另有 `RadioMapSolver()` → 一次算**整個平面**每 1m×1m 一格的 RSRP，產 2D heatmap。

### 📊 差異對照
| 功能 | PathSolver（現狀） | RadioMapSolver（待加）|
|---|---|---|
| 輸出形態 | 每個 UE 一組 CIR | 2D tensor（W×H 的 RSRP）|
| 計算單位 | per UE-gNB pair | per grid cell-gNB pair |
| 速度 | 5 UE × 3 gNB ~70ms | 250×250 格 × 3 gNB **~2-5 秒** |
| 適合 | 即時 tick | 預算一次 + cache |

### 🎯 用途
- **Omniverse UI 熱圖可視化**（紅綠漸層畫在地圖上）
- 覆蓋率 % 統計（「RSRP > -95 dBm 覆蓋 87% 範圍」）
- **gNB 位置最佳化**（Sionna 可微分 → 自動搜尋最佳擺放點）
- Cell edge 自動偵測

### 🛠️ 實作
```python
# services/optional/ran_calculation/coverage_solver.py (新增)
from sionna.rt import RadioMapSolver

def compute_coverage_map(scene, cell_size=[1.0, 1.0], max_depth=5):
    rm_solver = RadioMapSolver()
    rm = rm_solver(scene=scene, max_depth=cell_size, cell_size=cell_size)
    return rm   # shape: (H, W, num_tx)

# 新端點:
POST /api/v0.1/RanpSim/RanSignal/ComputeRunner/coverage_map
```

回傳格式可以是：
```json
{
  "resolution_m": 1.0,
  "bounds": [-125, 125, -125, 125],   // x/z 範圍
  "grids": {
    "gNB_Macro_NW": [[-56, -58, ...], ...],   // 每格 RSRP
    "gNB_Macro_SE": [...]
  }
}
```

### ⚠️ 需要新增的 input（新端點）
```json
{
  "scene_id": "umi_3sector_v1",
  "cell_size_m": 1.0,
  "bounds": [-125, 125, -125, 125]   // 可選，預設整個 ground
}
```

### 🎯 觸發條件
- 前端要做覆蓋熱圖（🔥 常見 RAN digital twin 賣點）
- Demo 「拖 gNB 看覆蓋變化」互動式功能
- 研究 gNB 擺放最佳化

### 📏 工程量
- `coverage_solver.py` + 新 actor function + serializer + URL + INPUT_SPEC
- **~150 行，半天到一天**
- VRAM 壓力較大：250×250 = 62500 格 × 3 gNB 一次算，要 ~4 GB VRAM 暫緩區

---

## 10. 真 E2AP / ASN.1 over SCTP

### 🔍 現狀
`/ComputeRunner/compute` 回傳 JSON（有 success/message/data wrapper）。真 FlexRIC / OSC Near-RT RIC 的 E2 終端只認 **ASN.1 PER 編碼 + SCTP 傳輸**。

### 📊 影響
- 現在只能自己寫 adapter 吃 JSON。**無法直接連 OSC RIC / FlexRIC / srsRIC** 跑標準 xApp
- 論文寫「我實作 O-RAN E2 介面」站不住腳

### 🛠️ 實作
兩條路：

| 路線 | 做法 | 工期 |
|---|---|---|
| A. Adapter 程式 | 寫獨立 Python / Go 服務，輪詢 `/compute` JSON，轉 ASN.1 PER + SCTP 送 RIC | 1~2 週 |
| B. Django 內建 E2 agent | 用 `asn1tools` 或 FlexRIC 的 C lib，Django 啟一個 SCTP thread | 2~3 週 |

推薦 A：保持 ranp-sim 純 compute，轉碼責任獨立出去。

### ⚠️ 新增 input / 變更
無（外部 adapter 自己處理）。

### 🎯 觸發條件
**接真 RIC 的第一天必做**。是整個 O-RAN 合規的門票。

---

## 11. A3 TTT handover 邏輯

### 🔍 現狀
`rrc_event_tracker.py`：serving_gnb 跨 tick 變化立刻算 HO 一次。
```python
if prev != serving:
    counters['MM.HoExeIntraFreqReq'] += 1
```

### 📊 影響
- 真 3GPP TS 38.331 A3 事件：**`Mn + Ofn + Ocn - Hys > Ms + Ofs + Ocs + Off`** 持續 `timeToTrigger`（預設 160 ms）才觸發
- 沒這邏輯 → UE 在 cell 邊緣抖動會被**算成反覆 HO**（假警報）
- ConnMax / HoExe 計數器偏高

### 🛠️ 實作
加 TTT 狀態機：
```python
# rrc_event_tracker.py
class _A3State:
    def __init__(self):
        self.trigger_start_ms: int | None = None

A3_OFFSET_DB = 3.0
A3_HYSTERESIS_DB = 1.0
TIME_TO_TRIGGER_MS = 160

# 每 tick 比對 neighbor RSRP - serving RSRP:
condition_met = (neighbor_rsrp - A3_HYSTERESIS_DB > serving_rsrp + A3_OFFSET_DB)
if condition_met:
    if a3_state.trigger_start_ms is None:
        a3_state.trigger_start_ms = now_ms
    elif now_ms - a3_state.trigger_start_ms >= TIME_TO_TRIGGER_MS:
        # 真觸發 HO
else:
    a3_state.trigger_start_ms = None   # reset
```

### ⚠️ 新增 input
```json
"ran_params": {
  "a3_offset_db": 3.0,
  "a3_hysteresis_db": 1.0,
  "time_to_trigger_ms": 160
}
```
可選，預設 3GPP 標準值。

### 📏 工程量
~100 行 per UE state tracking + Serializer + INPUT_SPEC，**1 天**。

### 🎯 觸發條件
Demo 出現 HO ping-pong 時、或做 mobility 研究。

---

## 12. 真 HARQ + BLER 閉環 MCS

### 🔍 現狀
`pm_aggregator.py::accumulate_ue`：從 throughput 反推 MCS 一次查表。沒有 BLER 回授調整。`rounds[8]` HARQ 陣列有累積，但**只用 SINR 門檻分流**（>12 dB 算第 1 輪成，<0 dB 算失敗），不是真實 HARQ。

### 📊 影響
- 真 OAI MCS 選擇：**50 ms 滾動窗 BLER** → BLER>0.15 降 MCS、<0.05 升 MCS
- 沒這邏輯 → MCS 對 SINR 反應**過快**（查表一次定生死），無法反映真實 AMC 行為
- `du_DRB.AirIfDelayDlAvg.5QI9` 永遠是 0

### 🛠️ 實作
```python
# pm_aggregator.py 加 BLER 追蹤
class _MCSController:
    def __init__(self):
        self.current_mcs = 9       # 初始
        self.bler_window = []       # 50ms 累積
        self.last_update_ms = 0

    def update(self, sinr_db, timestamp_ms):
        # 從 SINR 估每次失敗機率
        ack_prob = sinr_to_success_prob(sinr_db, self.current_mcs)
        self.bler_window.append((timestamp_ms, 1 - ack_prob))
        # 滑動 50ms 窗
        self.bler_window = [(t,b) for t,b in self.bler_window if timestamp_ms - t <= 50]
        bler = sum(b for _,b in self.bler_window) / len(self.bler_window)
        # MCS 調整 (OAI 邏輯)
        if bler > 0.15: self.current_mcs = max(0, self.current_mcs - 1)
        elif bler < 0.05: self.current_mcs = min(27, self.current_mcs + 1)
```
每個 UE 一個 `_MCSController`。

### 📏 工程量
~150 行 + 對齊 OAI 的 `get_mcs_from_bler()`。**2 天**。

### 🎯 觸發條件
做 link adaptation / AMC 演算法研究。

---

## 13. 多 QoS（5QI）類型

### 🔍 現狀
UE 有 `qos_5qi` 欄位但**預設都 9（best-effort 資料）**。E2 欄位很多分 `_5QI1`（語音）/ `_5QI9`（資料）/ `_5QI4`（影片）展開。

### 📊 影響
- E2.md 的 pm 欄位：`cu_DRB.EstabAtt.5QI1/5QI9`、`PdcpSduVolumeUl_5QI1` 分別統計
- 多 QoS 區分 QoS flow 優先級、不同排程延遲
- demo 語音 + 資料混合流量時無法展示

### 🛠️ 實作
UE 每個 5QI 獨立算：
```python
# rrc_event_tracker.py
for qos in [1, 9, 4]:
    ue_count_per_qos[qos] = sum(1 for u in ues if u.qos_5qi == qos)
# pm_aggregator.py
record['cu_DRB.PdcpSduVolumeDL_5QI1'] = str(volume_per_qos[1])
record['cu_DRB.PdcpSduVolumeDL_5QI9'] = str(volume_per_qos[9])
```

### ⚠️ 新增 input
現有 `qos_5qi` 欄位即可，**不用加新欄位**。只是後端分 5QI 累積。

### 📏 工程量
~80 行，**半天**。

### 🎯 觸發條件
Demo 要展示「VoNR（5QI1）優先保證」、「eMBB（5QI9）吃頻寬」的差異。

---

## 14. PRB 排程爭用（multi-UE PF scheduler）

### 🔍 現狀
每個 UE 都**假設拿滿 PRB**（`rb_width=273`）。多 UE 時等於「每個 UE 都拿 100 MHz」→ 不現實。

### 📊 影響
- 真 gNB：N_PRB=273 要**除以活躍 UE 數**（或按 PF 權重分）
- 我們：5 個 UE 各拿 273 → **throughput 是 5x 真實值**
- 排程延遲（scheduling wait time）無法模擬

### 🛠️ 實作
簡化 PF (Proportional Fair) 排程器：
```python
# services/optional/ran_calculation/scheduler.py (新增)
def allocate_prb(ues_on_this_gnb, total_prb=273):
    # PF 權重 = instantaneous_rate / historical_avg_rate
    pf_weights = {ue.id: ue.sinr_based_rate / ue.avg_rate for ue in ues}
    total_w = sum(pf_weights.values())
    return {ue.id: int(total_prb * w / total_w) for ue, w in ...}
```
每 UE 的 `rb_width` 依 PF 權重配。

### 📏 工程量
~120 行 + historical rate 追蹤 state。**1 天**。

### 🎯 觸發條件
做**多 UE 容量研究**、PF scheduler 演算法對比、cell capacity planning。

---

## 15. 簡化 RRC 狀態機（ReEstab / Release reason）

### 🔍 現狀
目前 RRC 狀態只有「看到 UE 就是 Connected、消失就 Release」。真 RRC 有 INACTIVE / IDLE / CONNECTED / RECONFIGURED / HO_EXECUTION 五態。

### 📊 影響（E2 欄位）
- `cu_RRC.ConnReEstab.*` 永遠 0 ← 沒模擬連線掉了又接回來
- `cu_gnb.RRC.ConnRelease.Other` 永遠 0
- `cu_RRC.SigTimeSetup.*` 永遠 0
- `cu_gnb.RRC.ConnReEstab.ReEstab.sum` 永遠 0

### 🛠️ 實作
RRC 狀態機 per UE：
```python
# rrc_event_tracker.py
class _UEState:
    state: Literal["INACTIVE","IDLE","CONNECTED","HO","RECONFIG"] = "INACTIVE"
    last_transition_ms: int

# 判斷規則：
# RSRP < -110 dBm → drop to IDLE + Release
# 30s 後回來 → ReEstab
# SINR < 0 持續 > 2s → ReEstab
```

### 📏 工程量
~200 行 (狀態機 + 規則)，**2 天**。

### 🎯 觸發條件
連線穩定性分析、做 ReEstab 研究。

---

## 16. Slot-level 時間精度

### 🔍 現狀
每 tick 500 ms 一次。真 5G slot = **0.5 ms**（numerology 1），1000 倍差距。

### 📊 影響
- 無法模擬真 gNB 每 slot 排程
- HARQ timing（RTT = 4~8 slots）無法反映
- 瞬時 channel variation 看不出

### 🛠️ 實作
**不建議在 Django 做**——500ms → 0.5ms 表示 compute 要快 1000 倍，VRAM/GPU 根本不夠。
正確做法：把真時序交給 **OAI 或 Aerial CUDA RAN**（Plan 1 Option B/C）做，ranp-sim 只產 CIR feed 下去。

### 📏 工程量
**大**，需要接 OAI 外部系統。

### 🎯 觸發條件
做 HARQ RTT / scheduler timing 研究，且有 OAI 環境。

---

## 17. MCS table1 支援

### 🔍 現狀
`cqi_table.py` 只實作 table2（256QAM max）。E2.md 有 `PDSCHMCSDist.BinTable1.*` 欄位需要 table1（64QAM max）數據。

### 📊 影響
- 不支援舊 hardware（只到 64QAM 的 gNB）
- E2 欄位 BinTable1.* 永遠 0

### 🛠️ 實作
```python
# cqi_table.py 加第二組 table
_SINR_TO_CQI_TABLE1 = [...]  # 最高到 64QAM R=0.926
# pm_aggregator 依 gNB 設定的 mcs_table 選擇
```

### 📏 工程量
~30 行，**1 小時**。

### 🎯 觸發條件
極少需要（table2 更常見）。若外部要求 demo 舊 hardware 才做。

---

## 18. Coverage Summary 塞進 /compute

### 🔍 現狀
Coverage map 端點算完是 2D 2500-cell 陣列，**要有人畫才有意義**。如果不畫前端 / 沒 xApp 吃，就只是產生 JSON 放著。

### 📊 影響 / 價值
加入**摘要統計**讓 coverage 在「不畫」時也有決策價值：
```json
"coverage_summary": {
  "rsrp_gt_neg85_pct": 62.4,        // 62% 區域 RSRP > -85 dBm
  "rsrp_gt_neg95_pct": 78.9,
  "rsrp_gt_neg105_pct": 91.2,
  "weakest_point": {"position": [25, 1.5, 50], "rsrp_dbm": -118.2},
  "cell_edge_area_pct": 12.3,       // SINR 0~3 dB 區域占比
  "per_gnb_serving_pct": {
    "gNB_Macro_NW": 45.2,
    "gNB_Macro_SE": 32.1,
    "gNB_Small_Plaza": 22.7
  }
}
```

### 🛠️ 實作
每次 `/ComputeRunner/compute` tick 時**不重算** coverage，而是**快取最後一次 coverage map 結果** + 取 summary 數字塞到 response。

```python
# SionnaBusinessService 加 class var: _last_coverage_summary
# 每 N tick 背景重算 coverage 一次 → 更新 summary
# /compute response 加 "coverage_summary": cls._last_coverage_summary
```

### ⚠️ 新增 input
無（summary 自動產生）。可加 env `COVERAGE_REFRESH_EVERY_N_TICKS=60` 控制更新頻率。

### 📏 工程量
~80 行，**15~30 分鐘**。

### 🎯 觸發條件
**即刻**：做完之後即使前端不畫熱圖，後端 xApp 仍能讀覆蓋率 %。

---

## 19. Sionna 可微分 → gNB 位置最佳化

### 🔍 現狀
**完全沒用**。這是 Sionna 相對 WirelessInSite/Remcom 的**殺手鐧**，我們白拿沒用。

### 📊 影響 / 價值
Sionna RT 整條 pipeline 可對 gNB 位置 / 功率 / 天線參數求梯度：
- 自動找「整個場域 RSRP > -95 dBm 覆蓋率最大」的 gNB 擺放
- 梯度下降 50~200 次 iteration 達到最佳解
- 用現有工具做 = 人工試位置

### 🛠️ 實作
新端點：
```
POST /OptimizationRunner/find_best_gnb_positions
{
  "scene_id": "umi_3sector_v1",
  "n_gnb": 3,
  "freeze_n_first": 1,                    // 前 1 個位置固定（不優化）
  "initial_positions": [[...], [...], ...],
  "objective": "maximize_coverage_pct_95dbm",
  "max_iterations": 100,
  "learning_rate": 0.5
}
```

內部：
```python
import torch

gnb_positions = torch.tensor([...], requires_grad=True)
optimizer = torch.optim.Adam([gnb_positions], lr=0.5)

for step in range(max_iter):
    # 1. 更新 Sionna scene
    for i, tx in enumerate(scene.transmitters.values()):
        tx.position = gnb_positions[i]
    # 2. 跑 RadioMapSolver
    rm = solver(scene=scene, ...)
    # 3. 目標函數：最大化 RSRP > -95 dBm 面積
    coverage_pct = torch.mean((rm.rss > threshold).float())
    loss = -coverage_pct
    # 4. 反傳梯度
    loss.backward()
    optimizer.step()
```

### ⚠️ 風險
- Sionna 的 gradient 實作在 Dr.Jit + PyTorch 橋接；**首次跑會遇到 grad flow bug**（實測 v2.0.1 有 PR 在修）
- 每 iteration 跑 RadioMapSolver → **~200ms × 100 iter = 20 秒**
- VRAM 壓力：反傳需存 intermediate，比 forward 貴 3~5x

### 📏 工程量
~300 行 + 測試 + 可能要繞 Sionna bug，**2~3 天**。

### 🎯 觸發條件
- 寫論文「AI-Native RAN Optimization」
- Demo 「拖一個建築 → 系統自動重算最佳 gNB」的互動性
- 對標 AODT 的 `scene_editor` + optimization

**強烈建議**：這是 Sionna 最能秀肌肉的 feature。現在不用跟用 WirelessInSite 沒兩樣。

---

## 20. E2 RC（Radio Control）反向控制

### 🔍 現狀
目前只有**單向 upstream**：ranp-sim → RIC（透過 /compute JSON）。**沒實作 RIC → ranp-sim 的反向控制**。

### 📊 影響
真 O-RAN E2 協定有 **RC Service Model**：xApp 可以送控制指令改 gNB 參數
- `RAN Parameters Control`：即時改 TX power、beam weight、handover threshold
- **閉環 AI-RAN** 研究的關鍵：xApp 看數據 → 反手控制 gNB → 看效果

### 🛠️ 實作
新端點 RC 方向：
```
POST /ConfigManager/control_gnb
{
  "gnb_name": "gNB_Macro_NW",
  "parameter": "power_dbm",
  "new_value": 40,              // 原 43 → 降到 40
  "ttl_seconds": 300            // 5 分鐘後回復
}
```

效果：
- `SionnaBusinessService` 立刻更新該 gNB 配置
- 後續 `/compute` tick 就用新功率算
- TTL 到期自動回預設

### ⚠️ 新增 input
上面 request schema。響應格式沿用 `push_scene` 類似的回傳。

### 📏 工程量
~150 行。**1 天**。

### 🎯 觸發條件
接 FlexRIC 的 RC xApp / 做閉環 control loop demo。

---

## 21. Observability / Prometheus Metrics

### 🔍 現狀
`/metrics` 端點在原計畫但沒實作。只有 `/HealthChecker/read` 是 health check。

### 📊 影響
Production 部署時缺監控：
- 不知道 `/compute` p50 / p95 延遲
- 不知道 GPU 記憶體用多少
- 不知道 error rate

### 🛠️ 實作
```bash
pip install prometheus-client django-prometheus
```

新端點（非 POST，Prometheus 要 GET）：
```
GET /metrics
```
輸出：
```
ranp_sim_compute_duration_seconds{quantile="0.5"} 0.076
ranp_sim_compute_duration_seconds{quantile="0.95"} 0.109
ranp_sim_sionna_gpu_memory_bytes 1073741824
ranp_sim_active_ues 5
ranp_sim_coverage_requests_total 12
ranp_sim_errors_total{type="gpu_oom"} 0
```

⚠️ **違反鐵則 7-2**（「全 POST」）──GET `/metrics` 是 Prometheus 標準，不改。需跟使用者確認是否破例。

### 📏 工程量
~100 行 middleware + `/metrics` endpoint，**半天**。

### 🎯 觸發條件
deploy 到 production / 加 Grafana 儀表板。

---

## 22. Network Slicing（多 slice）

### 🔍 現狀
只有**單 slice**（SST=1 eMBB default）。真 5G 支援 3 種 slice：
- **eMBB**（Enhanced Mobile Broadband）：大頻寬，SST=1
- **URLLC**（Ultra-Reliable Low Latency）：低延遲，SST=2  
- **mMTC**（massive Machine Type Communication）：大量 IoT，SST=3

每個 slice 有獨立的：
- PRB 配額（例：eMBB 60% / URLLC 30% / mMTC 10%）
- SLA（URLLC 要 <1ms 延遲）
- 計數器分 slice 累積

### 📊 影響 / 價值
- 5G 獨有的殺手級 feature，RAN digital twin demo 必秀
- E2.md 的一堆 `5QI*` 欄位其實是 slice 分類（5QI1 語音 → URLLC；5QI9 資料 → eMBB）

### 🛠️ 實作
UE 新增 `slice_sst` 欄位（1/2/3），ranp-sim 內部：
- 按 slice 分 PRB 配額
- 按 slice 跑獨立 MCS / throughput 算
- 計數器 per slice 累積

```json
"ue_positions[].slice_sst": 2    // URLLC
```

### 📏 工程量
~250 行 + pm 欄位擴充。**2 天**。

### 🎯 觸發條件
Demo 「URLLC 和 eMBB 共存」、3GPP slice SLA 研究。

---

## 23. Integration Test Suite（E2E scenarios）

### 🔍 現狀
只有 `tests/services/test_mcs_table.py` 和 `tests/unit_test/test_compute_validation.py` 兩個單元測試。**沒有 E2E 場景測試**。

### 📊 影響
- 加新 feature 容易打破舊功能（regression）
- 手動跑 curl 測會漏細節
- CI/CD 時沒自動驗證

### 🛠️ 實作
用 `pytest-django` 寫 E2E test：
```python
# tests/e2e/test_ho_flow.py
def test_handover_ping_pong_prevented():
    # push 2 gNB + 1 UE 在 cell edge
    # 連續 10 ticks，UE 位置抖動 ±1m
    # 斷言：A3 TTT 生效，HoExeIntraFreqReq 累積 ≤ 2
```

### 📏 工程量
~500 行 (6~8 個情境 + fixtures + mock Sionna for 無 GPU CI)，**2~3 天**。

### 🎯 觸發條件
要開始穩定 deploy / 有團隊共同維護 / CI/CD pipeline。

---

## 🗓️ 建議實作時程

### Phase 1（近期，demo / quick win，總 ~3~4 天）
- [x] **P2** Coverage Map 端點（半天~一天）— ✅ **已完成**
- [ ] **P1** A3 TTT handover 邏輯（1 天）— 避免 HO ping-pong 假警報
- [ ] **P1** Coverage summary 塞進 /compute（15~30 分鐘）— 不畫也有用
- [ ] **P2** 大氣衰減 P.676 + P.838（半天）— 要展示天氣 / 切 mmWave 前
- [ ] **P2** 多 QoS（5QI）區分（半天）— Demo VoNR + eMBB 流量差異
- [ ] **P2** Observability / Prometheus（半天）— production 監控起手式

### Phase 2（中期，研究開始後，~2~3 週）
- [ ] **P1** 真 E2AP / ASN.1 over SCTP（1~2 週）— **接真 RIC 的必要門票**
- [ ] **P1** Sionna 可微分 → gNB 位置最佳化（2~3 天）— **Sionna 殺手鐧** ⭐
- [ ] **P1** 真 4×4 SU-MIMO 升級（需硬體升級到 ≥12 GB VRAM）
- [ ] **P2** E2 RC 反向控制（1 天）— 閉環 AI-RAN 必備
- [ ] **P2** 真 HARQ + BLER 閉環 MCS（2 天）— link adaptation 研究
- [ ] **P2** PRB 排程爭用（1 天）— 多 UE 容量研究
- [ ] **P2** Network Slicing（多 slice，2 天）— 5G 殺手級 feature
- [ ] **P3** Fast fading overlay（1 天）— link adaptation / HARQ 研究
- [ ] **P3** UL 真實模擬（~100 行）— UL 是研究主軸時
- [ ] **P3** Doppler 相位利用（半天）— 高移動 UE / HARQ 研究
- [ ] **P3** 簡化 RRC 狀態機（2 天）— ReEstab / Release.Other 欄位填值
- [ ] **P3** Integration test suite（2~3 天）— CI/CD 前置

### Phase 3（遠期 / 視硬體與外部系統）
- [ ] **P1** 真 64T64R MU-MIMO（需 RTX 6000 Ada 以上）
- [ ] **P3** 高階繞射（接 Remcom / 自寫或等 Sionna 升級）
- [ ] **P3** Slot-level 時間精度（需接 OAI 做真時序）
- [ ] **P4** MCS table1 支援（1 小時，極少需要）

---

## 💡 權衡原則

| 做了的代價 | 不做的代價 |
|---|---|
| 每加一層物理細節 → compute_ms 上升、VRAM 壓力大 | 數字跟真實差距明顯，論文被 reviewer 打 |
| 加 Serializer input 欄位 → 外部平台要配合改 | Demo 被問「雨天/高樓林立 worst case」答不出來 |
| 維運複雜度 | — |

**建議做法**：Demo 階段用 **Fake beam gain + ITU 大氣衰減** 兩個 quick win（總 <1 天工時，換來接近真實的 KPI 數字）；真 MIMO 等硬體升級後再談。

---

## 📎 相關文件

- `docs/BUGS.md` #008 — VRAM 競爭問題（限制 MIMO 升級）
- `docs/OAI_PM_SOURCES.md` — 真 OAI 對應計算如何做
- `LLM_learning/2026-04-18_sionna_research_note.md` — Sionna 能力與限制詳解
- `LLM_learning/2026-04-18_nvidia_aerial_note.md` — AODT（真 MU-MIMO + 大規模）對比
