# XAPP_DT 平台 RAN 初始化必設清單

> 產出日期:2026-05-15
> 依據:
> - `/home/mitlab/XAPP_DT/docs/xapp_dt_architecture.md` (平台架構)
> - `/home/mitlab/XAPP_DT/docs/oai_ran_config_report.md` (OAI RAN 設定盤點)
> - `docker-compose.yml`、`scene_config.json`、`ran-sim-protocol` DTO、CU/DU/RU 程式內預設值
> 目的:列出「在 sim 第一次啟動 / 換場景 / 切換實驗設定 前」必須先設定的 RAN 初始化參數,
> 並說明每一項是在設定什麼。

---

## 0. 為什麼這份清單必要

XAPP_DT 不是直接吃 OAI conf,而是把 RAN 設定拆散在 4 個地方:

| 地方 | 角色 | 影響 |
|---|---|---|
| `docker-compose.yml` env | 跨服務全域常數(PLMN、A3、power、cache TTL...) | 啟動時就鎖住 |
| `scene_config.json` | 場景內 gNB / cell / UE / building 的物理屬性 | 走 `SceneGateway/init` 進 Sionna |
| `ran-sim-protocol` DTO 預設值 | 跨服務 HTTP body 合約 | Dashboard / 各服務沒帶就用 fallback |
| Dashboard 端推送 | `update_cells / update_antenna / update_ues / Trajectory/set` | runtime 才生效,沒推就吃 env / scene default |

只要任何一格設錯或漏掉,Sionna RT 算出來的 RSRP/SINR 就會跟 CU 端 A3 判決的依據對不上 → xApp HO 驗證失準。

下面分 **必設 / 強烈建議 / 可後調** 三層列出。

---

## 1. ★★★ 必設(沒設好 sim 跑不起來 或 結果不可信)

### 1.1 場景幾何與 gNB 物理屬性 — `scene_config.json`

| 欄位 | 在設定什麼 | 目前值 / 建議 |
|---|---|---|
| `buildings[].position / size` | RT 場景內的建物幾何,Sionna 用它算遮蔽 / 繞射 | 必須與 Omniverse USD 場景一致,否則覆蓋圖跟 3D 視覺對不起來 |
| `gnbs[].position` | gNB 在世界座標的擺放(m, [x,y,z]) | 目前 3 站:NW(200,50,200)、SE(-200,45,-200)、Central(0,30,0) |
| `gnbs[].frequency_ghz` | 載波頻率 → Sionna RT 的 free-space loss / 材料反射係數 | Macro=3.5、Micro=2.6;對應 OAI `absoluteFrequencySSB` |
| `gnbs[].power_dbm` | 該 gNB 的 Tx EIRP 上界 | Macro=43 dBm、Macro_SE=40、Micro=20;對應 OAI `ssPBCH_BlockPower + antenna_gain` 總和 |
| `gnbs[].bandwidth_mhz` | 通道頻寬,影響 thermal noise floor 與資源量 | Macro=100、Micro=20;對應 OAI `dl_carrierBandwidth × SCS × 12` |
| `gnbs[].cells[].pci` | 每個 sector 的 Physical Cell ID | NW={100,101,102}、SE={200,201,202}、Central={300,301,302} — 不能重複 |
| `gnbs[].cells[].azimuth_deg` | 三扇區朝向(0/120/240) | RT 算 beam pattern 用,角度錯 → 覆蓋區轉向 |
| `gnbs[].cells[].cell_id` | 跨平台統一字串 ID,串到 RU / Physics / CU | `gnb1_cell0` 等;DU/RU map 直接 lookup |

> 對應 OAI 那邊的 `physCellId / absoluteFrequencySSB / dl_carrierBandwidth / ssPBCH_BlockPower / gNB 位置` 五件套。

### 1.2 PLMN / gNB-ID 全域識別 — `docker-compose.yml` (cu 與 du 兩 block)

```yaml
PLMN_MCC: "208"
PLMN_MNC: "95"
GNB_ID_HEX: "0x000e00"      # 2026-05-16 改:對齊 OAI gNB_ID=0xe00
GNB_ID_LENGTH: "12"          # 2026-05-16 改:0xe00 是 12-bit
# 核網對接 env 空殼(2026-05-16 P3.2/P3.3 新增,接口存在但邏輯未實作)
SERVED_TAC: "0xa000"         # 對齊 OAI tracking_area_code,值會編進 NGAP 但不做 TAU 流程
SST: "1"                     # eMBB,值會編進 NGAP S-NSSAI 但不做 slice-aware 分流
```
**在設定什麼**:E2 Setup 時對外 RIC 表明自己是誰。**CU 與 DU 必須一致**,否則 cell.served_plmn 與 globalE2node-ID 對不上,E2 Adapter 開不起來 subscription。

> 對應 OAI `plmn_list` + `gNB_ID` + `tracking_area_code` + `snssaiList`。
> ⚠ TAC / SST 目前是 **env 接口空殼** — NGAP PDU 會帶上正確值,但 CU 內部:
> - 不做 Tracking Area Update 流程
> - 所有 traffic 都默認走 SST=1,沒有 slice-aware 分流
> 要做這兩塊邏輯時參考 `alignment_action_plan.md` Phase 3。

### 1.3 RAN Function ID — `docker-compose.yml` (cu)

```yaml
RAN_FUNC_ID_KPM: 2
RAN_FUNC_ID_RC:  3
```
**在設定什麼**:E2AP RAN Function 註冊用的 function ID。xApp 訂閱時是用這個 ID 指定要哪個 service model(KPM=量測、RC=控制)。必須與 RIC / xApp 端期望的 ID 一致。

### 1.4 A3 量測事件三件套 — `docker-compose.yml` (cu)

```yaml
HO_A3_OFFSET_DB:     0.5
HO_A3_HYSTERESIS_DB: 0.3
HO_TTT_MS:           60
```
**在設定什麼**:CU 端 `a3_handover_calculation.py` 的 A3 觸發條件
- `offset`:鄰區 RSRP 比 serving 高多少才算候選(spec 0–3 dB)
- `hysteresis`:防 ping-pong(spec 0–15 dB)
- `TTT`:條件需持續多久才真的觸發(spec 40–5120 ms)

> 對應 OAI `nr_measurement_configuration.A3` 的 `offset / hysteresis / timeToTrigger`。
> ⚠ 目前預設 (0.5 / 0.3 / 60 ms) 是 demo 易觸發值,做正式 xApp 驗證必須換成實驗 sweep matrix(IM/CCO/ES case 各自的目標值)。

### 1.5 RU 發射端 link budget — `docker-compose.yml` (ru) 或 RU env

```yaml
RU_TX_POWER_DBM:            43.0    # 對應 scene_config.gnbs[].power_dbm
RU_ANTENNA_GAIN_DBI:        14.0    # TR 38.901 antenna 預設
RU_SCENE_CALIBRATION_LOSS_DB: 50.0  # scene 校準偏移
RU_NOISE_FLOOR_DBM:         -95
```
**在設定什麼**:RU 端 `dl_tti_pipeline.py` 算 RSRP 的公式:
```
RSRP = TX_POWER + ANTENNA_GAIN + path_gain_db - SCENE_CALIBRATION_LOSS
```
缺一不可。三者加總後的「實際 EIRP」就是 OAI 的 `ssPBCH_BlockPower + antenna gain`,
若不對齊 scene_config 的 `power_dbm` 會出現 RSRP 雙重計算。

### 1.6 RU 天線陣列預設 — `docker-compose.yml` (ru)

```yaml
RU_DEFAULT_ANTENNA_ROWS: 1
RU_DEFAULT_ANTENNA_COLS: 1
RU_DEFAULT_POLARIZATION: V         # base.py 預設 "cross"(4×2)
RU_DEFAULT_PATTERN:      tr38901
```
**在設定什麼**:RU 上每個 cell 的天線陣列(rows × cols × polarization)。
- 影響 Sionna 算 channel 時要不要展開 MIMO
- 對應 OAI `nb_tx / nb_rx`
- 目前 compose 強制 1×1(SISO),`base.py` 預設是 4×2 cross,**兩處互相覆蓋**,實驗前要先確認生效的是哪一組(env 勝 base.py)。

### 1.7 Numerology / Tick 節拍 — `docker-compose.yml` (du / ru)

```yaml
RU_NUMEROLOGY:    1            # μ=1 → 30 kHz SCS
SIM_TICK_MS:      50           # sim loop 50 ms 一拍
PM_WINDOW_SEC:    1.0          # 1 s 一次 KPM flush
UE_MEASUREMENT_PERIOD_MS: 80
```
**在設定什麼**:
- `RU_NUMEROLOGY=1` ↔ OAI `subcarrierSpacing=1`(30 kHz),改 0/2/3 要連 carrier BW 一起改
- `SIM_TICK_MS / PM_WINDOW_SEC` 決定 KPM report rate,直接影響 xApp 量測解析度
- 兩者比值 (`PM_WINDOW_SEC × 1000 / SIM_TICK_MS = 20`) 是每 window tick 數,改任一個都要重算

---

## 2. ★★ 強烈建議(影響實驗一致性)

### 2.1 鄰區關係 — Dashboard `/RU/Config/RuController/update_cells` 或 scene reload

XAPP_DT 沒有像 OAI 那樣的 `neighbour-config.conf`,而是用「同 scene 內所有 active cell 互為鄰區」的隱式策略。
**初始化必須確認**:
- `scene_config.gnbs[].active=true` 的所有 gNB 都會被當鄰區
- 想做「定向」鄰區(只有 A→B 不有 B→A)目前要在 CU 端硬編,沒 GUI 入口
- PCI 集合必須與場景 BS 物件一致(對應記憶 [[brownstone_asset_resolution]] 的教訓:asset/設定不一致會悄悄失敗)

> 對應 OAI `neighbour_list`。

### 2.2 UE 軌跡與量測週期

| 來源 | 欄位 | 在設定什麼 |
|---|---|---|
| `scene_config.json` | `ues[].waypoints / speed_mps` | UE 移動軌跡;Sionna 跑 coverage 時 UE 座標 |
| compose (ue) | `UE_TRAJECTORY_PERIOD_MS=100` | UE worker 每 100 ms 插值新位置 → RU `/Position/set` |
| compose (ue) | `UE_LIST_POLL_PERIOD_SEC=5` | UE worker 多久從 CU `/Session/list` 同步一次 |
| compose (ue) | `UE_MEASUREMENT_PERIOD_MS=80` | UE 多久產生一次 measurement report |

**為什麼重要**:HO 觸發是「TTT (60 ms) 內條件持續滿足」,如果 measurement period 大於 TTT 就根本量不到。
目前 80 ms > 60 ms 已經太邊緣,正式跑 case 前最好調 30–50 ms。

### 2.3 RU channel cache TTL

```yaml
RU_CHANNEL_CACHE_TTL_SEC: 0.5
```
**在設定什麼**:RU 對同一 UE(50 cm grid 量化)在 0.5 s 內不重跑 Sionna,直接用 cache。
- 太大 → UE 邊走邊穿牆 RSRP 不會更新,HO 永遠不觸發
- 太小 → Sionna GPU 每 TTI 都被打,sim 跑不動
- 經驗值與 `UE_TRAJECTORY_PERIOD_MS × UE 平均速度` 的位移要對應(<50 cm 內可重用)

### 2.4 Postgres / 服務間 host 解析

```yaml
SERVER_IP=10.3.0.217   # .env
```
**在設定什麼**:跨主機 SCTP bind 與 service 間 hostname 解析。
- 必須與真實網卡 IP 一致(目前綁 `enp1s0`)
- 對應記憶 [[sctp_host_reboot_wipe]]:host 重開機後必須先跑 `host_setup_sctp.sh` 再起 e2adapter

---

## 3. ★ 可後調(初始化不需動,但要知道在哪)

| 設定 | 位置 | 在做什麼 |
|---|---|---|
| `HTTP_AMF_HOST` | compose (cu) | 空字串 → 用內建 mock AMF;接真實 5GC 時才需設 |
| `HTTP_CUUP_HOST` | compose (cu) | 空字串 → CU integrated 模式;split 才需設 |
| `ASN1_VERBOSITY`, `RIC_E2TERM_HOST/PORT` | compose (e2adapter) | RIC 連線目標,接到 `10.3.0.71:36422` 走 host net |
| `RU_CHANNEL_*`、`pf_scheduler_*` | DU/RU env | scheduler / channel 微調 |
| `log_level` | 各服務 settings | 純 debug |
| `INJECT_BATCH_MODE=on` | compose (ue) | traffic 注入模式,新預設 |

---

## 4. 不同實驗 case 對應的「必動」表

| Case | 必動的初始化設定 | 為什麼 |
|---|---|---|
| **IM(干擾管理)** | DU `MacScheduler PRB quota` 透過 RIC_CONTROL_REQ 控制;A3 不動 | 驗證 PRB 分配對 throughput / delay 的影響 |
| **CCO(覆蓋/容量)** | `scene_config.gnbs[].power_dbm`、`HO_A3_*`、PCI 鄰區設定 | 變更覆蓋區與 HO 邊界 |
| **ES(節能)** | `gnbs[].active=false` 的能力(關 cell)、`HO_A3_OFFSET_DB` 調寬、PRB quota max=5 | 邊關 cell 邊強迫 UE HO 到鄰區 |
| **新 scene 上線** | scene_config(buildings + gNB position)+ Omniverse USD 對齊 + Physics `SceneGateway/init` reload | 三層必須同步,參考記憶 [[coverage_data_flow]] |

---

## 5. 初始化檢查清單(實作 SOP)

新 scene / 新實驗開跑前,**依序**確認:

```
[ ] scene_config.json:buildings / gnbs / ues 都填齊;PCI 全域不重複
[ ] docker-compose.yml(cu):PLMN_MCC/MNC、GNB_ID_HEX、RAN_FUNC_ID_KPM/RC
[ ] docker-compose.yml(cu):HO_A3_OFFSET_DB / HO_A3_HYSTERESIS_DB / HO_TTT_MS
[ ] docker-compose.yml(ru):RU_TX_POWER_DBM / RU_ANTENNA_GAIN_DBI /
                            RU_SCENE_CALIBRATION_LOSS_DB / RU_NOISE_FLOOR_DBM
[ ] docker-compose.yml(ru):RU_DEFAULT_ANTENNA_ROWS/COLS/POLARIZATION/PATTERN
                            ← 與 scene_config 的 gnbs[].cells 數量一致
[ ] docker-compose.yml(du/ru):RU_NUMEROLOGY、SIM_TICK_MS、PM_WINDOW_SEC
                            ← 比值 = 20
[ ] docker-compose.yml(ue):UE_MEASUREMENT_PERIOD_MS ≤ HO_TTT_MS
[ ] .env:SERVER_IP 與 enp1s0 IP 一致
[ ] host 重開機後:sudo bash host_setup_sctp.sh
[ ] sim 啟動後:Dashboard → SceneGateway/init reload(Layer 2,把 scene 推進 Sionna)
[ ] sim 啟動後:E2Adapter `/Status/read` 確認 sub 已建立、累計 indication > 0
```

---

## 6. 與 OAI 那 7 大類的對照速查

| OAI 設定類別(出自 `oai_ran_config_report.md`) | XAPP_DT 對應位置 | 必設層級 |
|---|---|---|
| 1. 頻率 (`absoluteFrequencySSB`) | `scene_config.gnbs[].frequency_ghz` | ★★★ |
| 2. 頻寬 (`dl_carrierBandwidth`) | `scene_config.gnbs[].bandwidth_mhz` | ★★★ |
| 3. SSB / PDSCH 功率 (`ssPBCH_BlockPower`) | `scene_config.gnbs[].power_dbm` + RU env(`RU_TX_POWER_DBM` 等) | ★★★ |
| 4. 天線數 (`nb_tx/nb_rx`) | `RU_DEFAULT_ANTENNA_ROWS/COLS` env | ★★★ |
| 5. PCI (`physCellId`) | `scene_config.gnbs[].cells[].pci` | ★★★ |
| 6. 鄰區表 (`neighbour_list`) | scene 內所有 `active=true` 的 cell;隱式 | ★★(無 GUI,要小心) |
| 7. 量測事件 (`A2/A3`) | `HO_A3_*` env + `UE_MEASUREMENT_PERIOD_MS` | ★★★ |
| PLMN / gNB_ID | `PLMN_MCC/MNC` + `GNB_ID_HEX` env | ★★★ |
| PRACH / TDD / pucch hopping | XAPP_DT 不模這層,**不需設** | — |
| SCTP / F1 / E1 / NGAP IP | compose service hostname + `.env SERVER_IP` | ★★ |
| Security ciphering / integrity | XAPP_DT 不做,**不需設** | — |

---

*本份是 `oai_ran_config_report.md` 的 XAPP_DT 落地版。先讀那份了解 OAI 是怎麼設,再用這份對應到本平台要動哪幾個檔案。*
