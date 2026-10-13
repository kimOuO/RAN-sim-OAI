# RAN-SIM:場景網元清單 與 可調 RAN 參數表

> 建立 2026-09-12。為「重新構想 DT + 管理平台」而整理。
> 所有「現況」欄位皆由原始碼查證,非推測。
> 相關:[`ru_study_notes.md`](ru_study_notes.md)、[`phy_fidelity_sources.md`](phy_fidelity_sources.md)、
> [`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md)

---

## 表一:需要被部署在場景上的網路元件

「部署在場景上」= 這個元件有**空間位置**,而位置會改變無線傳播的結果。

### A. 目前已可放置

| 元件 | 空間屬性 | 定義在哪 | 現況 |
|---|---|---|---|
| **gNB** | `position [x,y,z]` | 劇本 `gnbs[].position`、`scene_config.json`、Omniverse `GnbConfig` | ✅ 可放,**但只是視覺物件** —— CU/DU/RU 只認得 cell 上的 `gnb_id` 字串,沒有 gNB 實體表 |
| **Cell / 扇區** | `position`(可獨立於 gNB)+ `azimuth_deg` | 劇本 `gnbs[].cells[]`、RU `Cell` | ✅ 最完整的網元。`sionna_engine` 已支援 cell 位置與 gNB 分離(= DAS/multi-TRP 的地基) |
| **建築物** | `position`、`size`、`scale`、`usd` | `scene_config.json` `buildings[]` | ⚠️ 只有幾何,**沒有電磁材質** |
| **UE** | 軌跡 `positions[[t,x,y,z],…]` | 劇本 `ues[]` | ✅ 含時間軸、離場、天線高度 |
| **地面** | `ground` | `scene_config.json` | ✅ |

### B. 建議新增(依對研究的價值排序)

| # | 元件 | 需要的空間屬性 | 為什麼要放在場景上 | 難度 |
|---|---|---|---|---|
| **1** | **RU / TRP**(獨立於 gNB) | `position`、`azimuth`、`tilt`、所屬 DU | O-RAN 的物理現實:CU/DU 在機房、RU 在天花板/燈桿。**是天線選擇與 DAS 研究的載體**。底層 Sionna 已支援 cell 位置分離,只差扶正成實體 | 🟢 低 |
| **2** | **建築材質** | 每個 building 面的材質(混凝土/玻璃/石膏板/木板) | Sionna 的反射**完全由材質決定**。室內場景的多徑結構幾乎由此決定 —— 你正在做室內掃描,這比室外重要得多 | 🟢 低(Sionna 原生支援 ITU 材質) |
| **3** | **外部干擾源** | `position`、`power`、`frequency`、`bandwidth`、時間模式 | 做 IM(干擾管理)卻只有 3GPP 自身干擾。WiFi AP / 微波 / 雷達是真實 RAN 的主要 SINR 殺手 | 🟡 中(要改 SINR 分母) |
| **4** | **動態遮蔽物** | 軌跡 + 尺寸 + 材質 | 車輛、人群、電梯門。現在 UE 就是人,但沒有「會擋訊號卻不是 UE」的物體。室內尤其需要 | 🟡 中 |
| **5** | **RIS**(可重構智慧表面) | `position`、`orientation`、相位配置 | 若天線/波束是研究主題,Sionna 原生支援,是很好的論文載體 | 🟡 中 |
| **6** | **室內結構細節** | 隔間牆、門、窗、家具 | 室內掃描場景的 ground truth。目前 `buildings` 是粗塊 | 🟡 中(掃描資料已有) |
| **7** | **傳輸節點** | 機房、光纖路由、midhaul 匯聚點 | 只有要做 fronthaul 延遲/容量研究時才需要 | 🔴 高(要先有鏈路模型) |
| **8** | **核心網 (AMF/UPF)** | 位置(對延遲有意義) | 目前只有 NGAP 訊息殼 | 🔴 高 |

### C. 不該放在場景上(無空間意義,但需要被管理)

`DU`、`CU-CP`、`CU-UP`、`Slice`、`NCRT 鄰區關係`、`E2 訂閱`、`DRB` ——
這些是**邏輯網元**,屬於管理平台的「網元版本管理」,不屬於「場景管理」。

> 但 **DU 與 CU 的「歸屬關係」有空間後果**(F1 走哪條傳輸、延遲多少),
> 所以若要做傳輸研究,它們需要「所在機房」這個間接位置屬性。

---

## 表二:可調的 RAN 參數

**分兩類 —— 這個區分是管理平台設計的關鍵:**

* **真 RAN 參數**:真實網路也有,管理平台應該暴露,對應 O1/A1/E2。
* **模擬器旋鈕**:現實不存在,是模擬實作的選項。**不該出現在管理平台的網元配置介面**,
  否則使用者會以為那是可以在真網路上調的東西。

---

### 2.1 真 RAN 參數 —— Cell / 載波層級

| 參數 | 範圍 / 單位 | 現在怎麼調 | 規範 | 現況備註 |
|---|---|---|---|---|
| `pci` | 0–1007 | 劇本 `gnbs[].cells[].pci`;RU `Cell.pci`;CU `CellConfig.pci` | TS 38.211 §7.4.2.1 | ✅ 三處都有,ANR 的 PCI confusion 題目靠它 |
| `nr_cellid` / NCGI | 36-bit | CU `CellConfig.nr_cellid` | TS 38.413 | ✅ |
| `served_plmn` (MCC/MNC) | — | CU `CellConfig.served_plmn`;env `PLMN_MCC`/`PLMN_MNC` | TS 23.003 | ✅ 預設 208/95 |
| **`ARFCN`** | 0–3279165 | ❌ **不存在** | TS 38.104 §5.4.2 | 🔴 只有 `NrCellRelation.target_arfcn` 有,`CellConfig` 沒有 → 鄰區關係與本地 cell 對不起來 |
| `frequency_ghz` | GHz | 劇本 `gnbs[].frequency_ghz`;RU `Cell.frequency_ghz` | — | ⚠️ 用頻率代替 ARFCN,非標準表示 |
| `bandwidth_mhz` | MHz | 劇本 `gnbs[].bandwidth_mhz` | TS 38.104 | ✅ |
| `power_dbm` (TX power) | dBm | 劇本 `gnbs[].power_dbm`;RU `Cell.power_dbm`;DU `set_runtime_phys{tx_power_dbm}`;env `RU_TX_POWER_DBM` | — | ⚠️ **四個地方可設,曾有不同步的歷史**(見 `rsrp_model.py` docstring) |
| `azimuth_deg` | 0–360° | 劇本 `cells[].azimuth_deg`;RU `Cell.azimuth_deg` | — | ✅ 每 cell 一個 Sionna Transmitter |
| **`tilt`(下傾角)** | ° | ❌ **不存在** | — | 🔴 CCO 研究的核心旋鈕之一,目前只能調 azimuth |
| `is_active`(Cell On/Off) | bool | RU `Cell.is_active`;DU `CellState.is_active`;E2SM-RC Style2/Action7 | O-RAN E2SM-RC | ✅ ES 節能用 |
| `is_barred` | bool | CU `CellConfig.is_barred`;`POST E2/Anr/set_barred` | TS 38.331 `cellBarred` | ✅ ANR 用 |
| `n_prb`(cell 頻寬對應 PRB) | 個 | env `SIM_DEFAULT_PRB_PER_CELL` = 106 | TS 38.104 Table 5.3.2-1 | ⚠️ 全域一個值,**不隨 cell 的 bandwidth_mhz 變** |
| numerology μ / SCS | μ=1 / 30 kHz | 固定;`phy_low` 有查表但沒接出來 | TS 38.211 §4.3.2 | 🔴 寫死 |
| TDD 上下行配置 | — | 硬編 `DDDDDDDSUU` | TS 38.213 §11.1 | 🔴 寫死(對齊 OAI band78 conf) |

### 2.2 真 RAN 參數 —— 天線

| 參數 | 範圍 | 現在怎麼調 | 現況備註 |
|---|---|---|---|
| `rows` × `cols` | 1–16 / 1–4 | RU `POST /Config/update_antenna`;Physics `scene_antenna_config` | 🔴 **全場景共用一組**,且 Physics 忽略 RU 送的值 → 實際恆 1×1 |
| `polarization` | V/H/VH/cross | 同上 | 同上 |
| `pattern` | `tr38901`/`dipole`/`iso`/… | 劇本 `antenna_pattern`;`scene_antenna_config.gnb_antenna_pattern` | ✅ **唯一真的會生效的天線參數** |
| `vertical/horizontal_spacing` | λ | RU `AntennaConfig` | 🔴 Physics 硬編 0.5λ,不讀傳入值 |
| UE 端陣列 | — | env `UE_ARRAY_ROWS/COLS`(2026-09-11 新增) | 🔴 Physics 仍忽略 |

### 2.3 真 RAN 參數 —— 移動性 / 換手

| 參數 | 範圍 | 現在怎麼調 | 規範 |
|---|---|---|---|
| A3 `enabled` | bool | 劇本 `a3_enabled`;env `HO_A3_ENABLED`;`set_a3_config()` | TS 38.331 |
| A3 `offset_db` | dB | 同上 | TS 38.331 §5.5.4.4 |
| A3 `hys_db`(遲滯) | dB | 同上 | 同上 |
| A3 `ttt_ms`(Time-to-Trigger) | ms | 同上 | 同上 |
| 鄰區關係 `ho_blocklist` / `no_remove` / `xn_blocklist` | bool | `POST E2/Anr/control`(SONTRIG FLAG) | TS 28.313 §6.4.1.3.5 |
| 鄰區關係增刪 | — | `POST E2/Anr/control`(ADD/REMOVE) | E2SM-ANR(自定) |

> A3 設定有 `/app/tmp/a3_override.json` 落盤機制 —— CU 重啟後仍保留劇本設定。

### 2.4 真 RAN 參數 —— 排程 / QoS

| 參數 | 範圍 | 現在怎麼調 | 規範 |
|---|---|---|---|
| PRB quota `max_prb` | % 或 PRB 數 | 劇本 `cell_quotas[]`;E2SM-RC Style2/Action6;DU `set_prb_quota` | O-RAN E2SM-RC |
| `qos_5qi` | 1–9 | UE 層;GBR(1–4)優先配置 | TS 23.501 Table 5.7.4-1 |
| GBR 最大佔比 | 0–1 | env `QOS_GBR_FIRST` / `_GBR_MAX_SHARE`=0.3 | — |
| 最小 PRB 分配 | PRB | 常數 `MIN_PRB` = 5 | OAI `gNB_scheduler_dlsch.c:753` |
| RLC `discardTimer` | ms | 劇本 `discard_timer_ms`;`set_runtime_phys` | 3GPP RLC discardTimer |
| RLC tx buffer 上限 | bytes | env `RLC_TX_MAXSIZE_BYTES` = 10 MB | OAI `nr_rlc_entity_am.c:1842` |
| 目標首傳 BLER | 0–1 | `SlotParams.target_bler` = 0.1 | TS 38.214 §5.2.2.1 CQI 定義(OAI 外迴路門檻 0.05/0.15 之間;OAI 無 `target_dl_bler` 參數) |

### 2.5 真 RAN 參數 —— UE / 情境

| 參數 | 現在怎麼調 |
|---|---|
| UE 軌跡 | 劇本 `ues[].positions[[t,x,y,z],…]` |
| UE 在場時段 | 劇本 `ues[].active` |
| UE 天線高度 | 劇本(waypoint y 為腳底高,另加天線高) |
| 流量模式 | 劇本 `traffic[].profile`:`idle`/`cbr`/`piecewise` |
| 流量突發性 | env `TRAFFIC_BURST_BYTES`(0=平滑 CBR) |
| 預設服務 cell | 劇本 `default_serving_cell` |

---

### 2.6 ⚠️ 模擬器旋鈕 —— 現實沒有,**不該放進管理平台的網元介面**

| 旋鈕 | 作用 | 為什麼不是 RAN 參數 |
|---|---|---|
| `sim_dt_ms` / `speed_x` | 時間軸倍速 | 真網路沒有「快轉」 |
| `rlc_delay_model`(`calib`/`subtick`) | delay 計算法 | 是實作選項。**且目前因 slot engine takeover 而失效** |
| `SLOT_ENGINE_TAKEOVER` / `SHADOW` | 哪個引擎產 delay KPM | 同上 |
| `inter_freq` | 強制同頻/異頻互擾 | 🔴 **現實中同頻與否是 ARFCN 的後果,不是獨立開關**。它存在正說明該補 ARFCN |
| `RU_CHANNEL_MODE`(`live`/`cached`) | 通道來源 | 模擬加速手段 |
| `RU_SCENE_CALIBRATION_LOSS_DB` | 補 Sionna 沒模到的損耗 | 校正常數。⚠️ 模組預設 36,compose 設 **0** |
| `noise_floor_dbm` | −98 dBm | 半真半假:現實是 noise figure + 頻寬的結果,不是可設值 |
| `NR_TBS_SPEC_MODE` | TBS 走規範式 | 2026-09-11 新增,預設 off |
| `NR_MIMO_LAYERS_ENABLED` | TBS 乘層數 | 同上 |
| `NR_EESM_ENABLED` | SINR 壓縮法 | 同上 |
| `PHY_PATH_GAIN_PER_PORT` | path_gain per-port 正規化 | 同上(Physics 側) |
| `fading_std_db` = 2.0 | slot 級快衰落 | 無出處的擬合值 |

---

## 三個我認為該優先補的參數

| 參數 | 為什麼 |
|---|---|
| **`ARFCN`** | 補了它,`inter_freq` 這個假開關就可以退休,同頻/異頻變成推導結果而非人工設定。也讓 `NrCellRelation.target_arfcn` 有本地對應 |
| **`tilt`(天線下傾角)** | CCO 研究的核心旋鈕。現在只能調 azimuth,等於少了一個維度 |
| **per-cell `n_prb`** | 目前全域 106,不隨 `bandwidth_mhz` 變 → 劇本裡設 100 MHz 和 40 MHz 的 cell,PRB 數卻一樣 |

---

## 對管理平台的一個建議

把目前劇本 JSON 拆成四份,對應你架構圖的四個管理框:

```
網元配置 (NE config)     ← gnbs[]、cells[](pci/arfcn/bw/power/azimuth/tilt)、antenna
場景 (Scene)             ← scene_id、buildings[](含材質)、ground、RU/TRP 位置
情境 (Scenario)          ← ues[] 軌跡、traffic[]、duration、干擾源時間模式
預演設定 (Run config)    ← cell_quotas、a3_*、speed_x、channel mode、模擬器旗標
```

現在這四層全部擠在同一個 JSON —— 而那正是管理平台要分開管的四件事。
**先拆這一刀,後面的版本管理、預演比較、O1 對接才有地方掛。**
