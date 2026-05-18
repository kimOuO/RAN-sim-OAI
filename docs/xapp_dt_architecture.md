# XAPP_DT 平台架構報告

> 產出日期：2026-05-15
> 涵蓋範圍：`/home/mitlab/XAPP_DT/` 模擬 RAN 平台
> 目的：完整盤點檔案結構、模擬現況、服務間連線與分工

---

## 0. 一頁版 TL;DR

XAPP_DT 是一個「分裂式 5G NR 模擬平台」，把 OAI / O-RAN 的 **CU / DU / RU / UE** 各自拆成獨立的 Django HTTP 服務，外加一個用 Sionna RT 做物理層射線追蹤的 `Physics_sim`，一個用 NVIDIA Omniverse Kit 做 3D 視覺化的 `Omnivers_platform`，以及一個把 HTTP/REST 翻譯成 ASN.1+SCTP 的 `RANsim-E2Adapter` 對接外部 RIC。

整體 7 個服務、1 個共用 Postgres、1 個前端 Dashboard 透過 `docker-compose.yml`（位於倉庫根）統一拉起。CU/DU/RU 之間用 HTTP REST 模擬 F1AP / E1AP / FAPI；E2Adapter ↔ RIC 走真實 SCTP（PPID=70），跨主機到 `10.3.0.71:36422`（kube hostNetwork=true bind）。整個 sim 從 2026-05 起連續跑超過 2 天，E2 RIC_INDICATION 已累計送出 16 萬餘筆。

---

## 1. 倉庫頂層結構

```
/home/mitlab/XAPP_DT/
├── docker-compose.yml          ← 平台級編排（CU/DU/RU/Physics/E2/UE/Dashboard/Postgres）
├── .env                        ← SERVER_IP=10.3.0.217（跨機器 host 解析用）
├── scene_config.json           ← 平台共享場景（buildings + gNB + UE）
├── postgres-init.sql           ← 初始化 cu_db / du_db / ru_db / physics_db
├── deployment-architecture.xml ← 部署拓樸圖（draw.io）
├── IMPLEMENTATION_SUMMARY.md   ← 早期 SimLoop / SceneGateway 規劃（部分已演進）
├── intents-interface.md        ← 上層 xApp Intent 介面（IM / CCO / ES 三 case）
│
├── RANsim-CU/          ← 5G gNB-CU（CP + UP），Django，container port 8000 → host 8101
├── RANsim-DU/          ← 5G gNB-DU（MAC + RLC + PHY-High + F1AP + FAPI + Tick），host 8102
├── RANsim-RU/          ← 5G O-RU（PlanarArray + Beamforming + FAPI + Physics client），host 8103
├── RANsim-UE/          ← Active UE Object（trajectory + traffic + measurement），host 8105
├── RANsim-E2Adapter/   ← HTTP ↔ ASN.1/SCTP RIC 翻譯器，host 8201（network_mode: host）
│
├── Physics_sim/        ← Django + Sionna RT（GPU），host 8104；底下還掛 Dashboard（Next.js）
│   ├── ran-sim-protocol/   ← 共用 protocol/DTO 套件（被 CU/DU/RU/Physics 編輯模式安裝）
│   ├── Dashboard/          ← 主前端（Next.js 14 App Router），host 3010
│   ├── scenes/             ← Mitsuba XML 場景檔（umi_3sector.xml）
│   └── main/               ← Django 後端
│
├── Omnivers_platform/  ← NVIDIA Omniverse Kit 3D 場景平台
│   ├── Omniver-RAN/        ← Django 後端，host 8001（場景 DB / 訊號 ingest / playback）
│   ├── extensions/         ← Kit 自訂 extension：mitlab.ran.{api, labels, scene.builder}
│   ├── kit/                ← Kit container（Xvfb + x11vnc + noVNC 6080，Kit HTTP 8080）
│   ├── assets/             ← USD：Brownstone 建物、UE、Materials
│   ├── frontend/           ← 舊版 Next.js 前端（host 3001，已 deprecate）
│   └── configure_scene.py  ← Kit 端讀 scene_config.json 建場景
│
├── RAN-sim/            ← ⚠️ 空殼目錄；舊 ranp-sim-frontend 來源（已從 disk 移除，
│                          但 docker container ranp-sim-frontend 仍掛著舊 image:3002）
│
├── docs/               ← 本文件與既有測試紀錄
│   ├── kpm_field_notes.md, kpm_simulation_knobs.md
│   ├── incidents/      (empty)
│   └── test_records/   case1_im / case2_cco / case3_es + kpm_4cell_sample
│
└── plan/               ← 工作筆記
    ├── docker-disk-cleanup-sop.md
    ├── du-message-flow-reference.md
    ├── ran-side-soak-monitor.sh + soak-ran.{csv,log}
    ├── ric-bug-report-followup.md, ric-bug-report-rnib-stale-race.md
    └── traffic-and-pmi-improvement.md
```

---

## 2. 服務 × Port × 當前運行狀態

> 來源：`docker ps` 於 2026-05-15 10:22 抓取

| 服務 (container) | Image | Host Port | Container Port | 狀態 | 主要職責 |
|---|---|---|---|---|---|
| `ransim-postgres` | postgres:16-alpine | 5433 | 5432 | Up 2d (healthy) | 共用 DB（cu_db / du_db / ru_db / physics_db） |
| `ransim-cu` | ransim-cu:platform | 8101 | 8000 | Up 47h | gNB-CU（CP+UP integrated） |
| `ransim-du` | ransim-du:platform | 8102 | 8000 | Up 2d | gNB-DU |
| `ransim-ru` | ransim-ru:platform | 8103 | 8000 | Up 2d | O-RU |
| `ransim-physics` | ransim-physics:platform | 8104 | 8000 | Up 2d | Sionna RT |
| `ransim-ue` | ransim-ue:platform | 8105 | 8000 | Up 47h | UE worker（N threads） |
| `ransim-ue-test` | (test fork) | 8106 | 8000 | Up 47h | UE 測試環 |
| `ransim-e2adapter` | ransim-e2adapter:platform | host net | host net (8201) | Up 47h | E2 ASN.1/SCTP bridge |
| `ransim-dashboard` | ransim-dashboard:dev | 3010 | 3000 | Up 2d (unhealthy*) | Next.js 控制台（Physics_sim/Dashboard） |
| `omniver_postgres` | postgres | 5432 | 5432 | Up 2d (healthy) | Omniverse 場景/訊號 DB |
| `omniver_backend` | (omniver-ran) | 8001 | 8000 | Up 2d | Omniverse 後端（Django） |
| `omniver_kit` | (kit-base) | 5900 / 6080 / 8080-8081 | – | Up 2d | Omniverse Kit（VNC + HTTP API） |
| `omniver_frontend` | (omniver-ran) | 3001 | 3000 | Up 2d | ⚠️ 舊前端（已 deprecate） |
| `ranp-sim-frontend` | ranp-sim-frontend:dev | 3002 | 3000 | Up 2d (healthy) | ⚠️ 已 orphan：來源 `XAPP_DT/RAN-sim/` 已被清空 |

> ✱ `ransim-dashboard` 標 unhealthy 是 healthcheck 細節問題，不影響 UI 使用。
> ✱ 兩個 `*-frontend`（3001 / 3002）是早期版本殘留 — 目前唯一被維護的前端是 **`Physics_sim/Dashboard`（3010）**，與記憶體中 `active_frontend.md` 描述一致。

### 真實活性指標（從 logs 抓取，2026-05-15 10:22）
- `ransim-e2adapter`：持續向 RIC（10.3.0.71:36422）送 RIC_INDICATION，sub_id=`sub-4e7c91d4804a`，累計 **163,836 筆**，活躍 cell=`gnb4_c2`（UE×1）。每秒 ~1 筆，與 KPM `PM_WINDOW_SEC=1.0` 對齊。
- 整個 sim chain（CU↔DU↔RU↔Physics↔UE）持續 47 小時 uptime，無 restart。

---

## 3. 每個服務的內部結構

> 共同慣例：所有 Django 服務採 **Actor / Business / Optional service** 三層
> - `actors/`：HTTP 入口，CSRF-exempt POST handler；只解 JSON → 派工 → 回 JSON
> - `services/business/`：跨應用的核心邏輯與其它服務的 HTTP client
> - `services/optional/`：協定/演算邏輯（RRC FSM、A3 calc、E2AP codec、Sionna 計算…）
> - `models/`：Django ORM model

### 3.1 RANsim-CU（gNB-CU；CP + UP）

**檔案結構**
```
main/apps/cu_cp/    ← Control Plane（RRC / F1AP / NGAP / E2 / Mobility）
main/apps/cu_up/    ← User Plane（E1AP / PDCP / SDAP / GTP-U / DRB）
```

**主要 HTTP 端點**（全部 `POST /api/v0.1/CU/...`）
| 群組 | 端點 |
|---|---|
| F1AP (from DU) | `F1AP/F1ApRouter/{du_setup, du_configuration_update, ul_rrc_message, measurement_report, cell_measurement_report}` |
| NGAP (from 5GC / mock AMF) | `NGAP/NgapRouter/{initial_ue_message, initial_context_setup, downlink_nas_transport}` |
| E2 (給 E2Adapter) | `E2/Subscription/{create,delete,list}`、`E2/Indication/poll`、`E2/Control/request`、`E2/E2NodeId/read` |
| Session (給 Dashboard) | `Session/SessionController/{list, get_state, handover, release_stale, update_traffic_profile}` |
| Mobility | `Mobility/A3Controller/{read,set}`、`Mobility/HandoverEvent/list` |
| E1AP (CU-UP) | `E1AP/E1ApRouter/bearer_context_setup` |
| UP 觀測 | `UP/Drb/{list,read}` |

**關鍵實作位置**
- A3 handover 觸發 + TTT：`cu_cp/services/optional/mobility/a3_handover_calculation.py`
- 全 gNB E2 Node-ID 匯出：`cu_cp/services/optional/e2/global_e2_node_id.py`（給 e2adapter 在 E2 Setup 時 poll）
- KPM indication producer：`cu_cp/services/optional/e2/indication_producer.py`（asyncio thread，100 ms tick）
- RRC FSM：`cu_cp/services/optional/rrc/state_machine.py`
- DU HTTP client：`cu_cp/services/business/du_client_operations.py`
- CU-UP integrated/split：`cu_cp/services/business/cuup_client_operations.py`（HTTP_CUUP_HOST 空 → 同 process）

**Models**：UeContext、DuRegistry、CellConfig、Drb、MeasurementLog、CellMeasurementLog、HandoverEvent

**重要環境變數**（docker-compose `cu:` block）
- 全 gNB 識別：`PLMN_MCC=208 / MNC=95 / GNB_ID_HEX=0x000038 / GNB_ID_LENGTH=22`
- RAN function：`RAN_FUNC_ID_KPM=2 / RAN_FUNC_ID_RC=3`
- A3 軟門檻（給 demo 易觸發 HO）：`HO_A3_OFFSET_DB=0.5 / HO_A3_HYSTERESIS_DB=0.3 / HO_TTT_MS=60`

### 3.2 RANsim-DU（gNB-DU；MAC + RLC + PHY-High + F1AP + FAPI + Tick）

**檔案結構**
```
main/apps/mac/         ← Cell / UE MAC / HARQ / PF scheduler / PM aggregator
main/apps/rlc/         ← RLC entity（AM/UM/TM）、SDU 段切 / delay 取樣
main/apps/phy_high/    ← CSI-RS 量測 stub
main/apps/f1ap_du/     ← F1 session（DU↔CU）
main/apps/fapi_north/  ← FAPI（DU→RU 的 DL/UL TTI request）
main/apps/tick/        ← Sim loop driver（tick_runner.py）
```

**主要 HTTP 端點**（`POST /api/v0.1/DU/...`）
| 群組 | 端點 |
|---|---|
| MAC | `MAC/MacCellController/{create,read,update,replace_cells,disable,enable}` |
| MAC | `MAC/MacSchedulerController/{set_prb_quota, clear_prb_quota, list_prb_quota}` ← E2SM-RC Style 2 Action 6 落地點 |
| RLC | `RLC/RlcEntityController/{create,read,delete}`、`RLC/RlcDataController/{inject_sdu, inject_sdu_batch, read_buffer_status}` |
| F1AP | `F1AP/F1ApRouter/{ue_context_setup, ue_context_modification, ue_context_release, dl_rrc_message, ul_rrc_message, f1_setup_response_callback}` |
| FAPI | `FAPI/FapiRouter/{cqi_indication, crc_indication}` ← RU 回 DU |
| Tick | `Tick/TickController/{start,stop,run_once,read,register_ue,replace_ues}` |

**Tick loop 重點**：`main/apps/tick/services/optional/runner/tick_runner.py`
- `SIM_TICK_MS=50`（從早期 500 ms 調至 50 ms 跟上 UE 100 ms inject 不堆 buffer，見 docker-compose 註解 AL）
- `PM_WINDOW_SEC=1.0` ⇒ `REPORT_EVERY_N_TICKS = 20`（每 20 tick 一次 KPM 報告）
- 每 tick：(1) RLC buffer 與 SDU 延遲 → (2) PF scheduler 分配 PRB（受 E2 quota cap）→ (3) 建 DL TTI 發 RU → (4) 累加 PM → (5) Window 結束 flush KPM → (6) SFN/slot 推進

**Models**：TickState、CellState、UeMacState、HarqProcess、RlcEntity、F1Session

**KPM 來源欄位對映**（送至 CU `measurement_report` / `cell_measurement_report`）
- `RRU.PrbTotDl` ← cell PRB 累加 / `cell_prb_total`
- `DRB.UEThpDl` ← PF scheduler 的 `actual_drained_map`
- `DRB.RlcSduDelayDl` ← RLC entity `take_delay_samples()` 平均
- `DRB.PdcpSduVolumeDL` ← 由 inject_sdu 累積

### 3.3 RANsim-RU（O-RU；PlanarArray + Beamforming + FAPI + Physics client）

**檔案結構**
```
main/apps/antenna/         ← AntennaConfig / Cell / UePosition models + RuController actor
main/apps/phy_low/         ← RuState（SFN/slot 計數）
main/apps/beamforming/     ← Codebook / Precoder / SINR estimator
main/apps/physics_client/  ← Physics HTTP client + channel cache（TTL 0.5 s）
main/apps/fapi_south/      ← FAPI（從 DU 收 DL/UL TTI request → 算 → 回 CQI/CRC）
```

**主要 HTTP 端點**（`POST /api/v0.1/RU/...`）
| 群組 | 端點 |
|---|---|
| Config | `Config/RuController/{update_antenna, update_cells, update_ues}` |
| FAPI | `FAPI/FapiRouter/{dl_tti_request, ul_tti_request}` |
| State | `State/RuStateReader/read` |
| Physics | `Physics/PhysicsHealth/read` |
| Position | `Position/set`（給 UE 推座標來；批次） |

**DL TTI 主流程**：`fapi_south/services/optional/dl_tti_pipeline.py`
1. 收 DU 的 `DlTtiRequest` → 用 `build_path_solver_request(ue_ids)` 組請求
2. 查 channel cache（key=ue_id + quantized pos 50cm grid + antenna sig，TTL 0.5 s）
3. 沒命中 → POST `physics:8000/api/v0.1/Physics/RanCalc/PathSolver/compute`，拿 channel_matrix + path_gain
4. `path_gain[tx_name]` → RSRP（dB + TX power + antenna gain - scene calibration）
5. `channel_matrix` 套 precoder → `sinr_estimator.estimate_sinr()` → CQI
6. POST 回 DU `/DU/FAPI/FapiRouter/cqi_indication`

**Cell ↔ Sionna gNB name 映射**：完全 DB-driven（`AK6` refactor，環境變數 hardcode 已拔），由 Dashboard 透過 `/RU/Config/RuController/update_cells` 推 → next TTI 自動重建 map。

**重要環境變數**
- `RU_DEFAULT_ANTENNA_ROWS=1 / COLS=1 / POLARIZATION=V / PATTERN=tr38901`（跟 Dashboard MimoSettings default 對齊）
- `RU_NUMEROLOGY=1 / RU_NOISE_FLOOR_DBM=-95 / RU_CHANNEL_CACHE_TTL_SEC=0.5`

### 3.4 RANsim-UE（Active UE Object）

**檔案結構**：單 app `main/apps/ue_lifecycle/`（actors / services / api）

**主要 HTTP 端點**（`POST /api/v0.1/UE/...`）
- `Lifecycle/{sync, start, stop}`
- `Trajectory/{set, clear, list}`（Dashboard 推軌跡進來）
- `Status/read`

**內部兩個 background thread**（manager.py）
- `_poll_loop`（`UE_LIST_POLL_PERIOD_SEC=5 s`）：從 CU `/Session/list` 撈最新 UE 清單，差異化建/砍 UE 執行緒
- `_trajectory_loop`（`UE_TRAJECTORY_PERIOD_MS=100 ms`）：每 UE 線性插值新座標 → 一次 batch POST `/RU/Position/set` → per-UE POST Kit → 觸發 `traffic_gen.tick()`

**Traffic 注入**：依 `traffic_profile`（從 CU sync）依 `rate_mbps × elapsed_ms / 8` 計算 bytes
- `INJECT_BATCH_MODE=on`：用 `/DU/RLC/RlcDataController/inject_sdu_batch`，per-packet `ts_offset_us`（對齊 OAI）
- `INJECT_BATCH_MODE=off`：舊巨型 SDU（向後相容）

### 3.5 RANsim-E2Adapter（HTTP ↔ ASN.1 / SCTP）

**檔案結構**
```
main/apps/e2_adapter/
├── actors/                     ← AdapterStatusReader / EventLogReader / KpmSnapshotReader
├── services/optional/
│   ├── codec/                  ← pycrate ASN.1 編解碼（E2AP / E2SM-KPM / E2SM-RC）
│   ├── sctp_link/sctp_loop.py  ← SCTP daemon、PDU dispatcher、indication producer
│   └── sim_bridge/             ← HTTP client → sim CU（拿 GlobalE2NodeID / KPM）
└── asn1/                       ← e2ap_v2.asn1 / e2sm_kpm_v2.0.03.asn / e2sm_rc_v01.03.asn
```

**HTTP 端點**（host port 8201；唯讀觀測介面）
- `Status/AdapterStatusReader/read`（SCTP 狀態 / E2 setup 結果 / pdu 計數）
- `EventLog/EventLogReader/read`（since_seq + limit 取近期事件）
- `KpmSnapshot/{SnapshotReader, RecentReader, HistoryReader}/read`

**SCTP loop 行為**
1. 連 `RIC_E2TERM_HOST:PORT`（compose 設 `10.3.0.71:36422`；Cilium kpr eBPF 不重寫 SCTP NodePort，e2term 走 hostNetwork=true 綁 36422，**不是** asn1 default 32222）
2. 從 sim CU 拿 globalE2node-ID → 編 E2 Setup Request（APER）送出
3. 進 recv loop dispatch：`RIC_SUBSCRIPTION_REQ` / `RIC_CONTROL_REQ` / `RIC_RESET_RESPONSE`
4. 每個 subscription 起 indication producer thread，每 ~report_period_ms 從 sim CU 拉 KPM → 編碼送 RIC
5. 當 sim CU 回 SubNotFound（CU restart 後 sub 清空）→ `_send_e2_reset()`（30 s cooldown）→ 不再 orphan-drop（見記憶 `e2adapter_reset_y1.md`）

**SCTP multi-homing 修法**：`network_mode: host` + `SCTP_BIND_IP=10.3.0.217`（綁 enp1s0），避免廣告 docker0 IP 觸發 self-ABORT（見記憶 `sctp_host_reboot_wipe.md`）

### 3.6 Physics_sim（Sionna RT + Dashboard）

**檔案結構**
```
Physics_sim/
├── main/apps/ran_signal/       ← Sionna 後端 Django app（actors / services）
├── Dashboard/                  ← Next.js 14 App Router 前端（port 3010）
├── ran-sim-protocol/           ← 共用 DTO Python 套件（pyproject.toml）
│   └── ran_sim_protocol/{common, e1ap, f1ap, fapi, ngap, physics, serde}.py
├── scenes/                     ← Mitsuba XML（umi_3sector.xml）
└── tools/                      ← scene_to_mitsuba.py 等
```

**主要 HTTP 端點**（`POST /api/v0.1/Physics/...`）
- `RanCalc/PathSolver/compute` ← RU 算 channel matrix 用
- `RanSignal/ConfigManager/{read, reload, push_scene, reset_to_default}`
- `RanSignal/CoverageRunner/compute` ← Dashboard 點 Coverage button 算 RSRP/SINR 熱力圖
- `RanSignal/HealthChecker/read`
- `Scene/SceneGateway/init` ← Dashboard build scene 後重建 Sionna scene
- WebSocket `ws://.../ws/sim/live/` ← 即時推送 sim live frame 給 Dashboard

**Sionna 整合**：`main/apps/ran_signal/services/business/sionna_operations.py`
- 場景：`/app/scenes/umi_3sector.xml`（Mitsuba XML）
- GPU：`NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics`（必須含 graphics 才會掛 liboptix）
- Coverage compute 時會「暫停 DU tick」避免 GPU 爭用

**ran-sim-protocol 套件**：被 CU/DU/RU/Physics/UE 編輯模式安裝，定義跨服務的 dataclass DTO（F1AP / FAPI / E1AP / NGAP / Physics PathSolver* 等），是 sim 內部所有 HTTP body 的合約來源。

**Dashboard 路由**：
- `/editor`、`/draw`、`/sim`、`/playback`、`/logs`、`/` 共 6 個頁面
- 透過 `NEXT_PUBLIC_*_URL` 環境變數直連各 RAN 服務（不經 BFF）

### 3.7 Omnivers_platform（NVIDIA Omniverse Kit + 3D 可視化）

**檔案結構**
```
Omnivers_platform/
├── Omniver-RAN/main/apps/ran/  ← Django 後端（port 8001）
│   ├── actors/                  ← Scene / UE / GNB / Ingest / History controllers
│   ├── models/                  ← BuildingObject, GnbConfig, UeConfig, SignalHistory,
│   │                              PositionHistory, SimulationSession, UsdAsset...
├── extensions/                  ← Kit 自訂 extension：
│   ├── mitlab.ran.api/          ← Kit HTTP server（8080）+ WebSocket scene sync
│   ├── mitlab.ran.labels/       ← Viewport 2D label overlay
│   └── mitlab.ran.scene.builder/← USD stage 構建（讀 scene_config.json）
├── kit/                         ← Kit container 入口（entrypoint.sh）
│                                  Xvfb :99 → x11vnc :5900 → noVNC websockify :6080
│                                  Kit HTTP API :8080
├── assets/
│   ├── building/brownstone/     ← Revit_Brownstone01_Exterior.usd（18 MB），
│   │                              Brownstone02/...（記憶體中 BrownstoneSite_Massing.usd
│   │                              已被棄用，現用 Revit per-building exports）
│   ├── UE/                      ← 用戶設備 USD
│   └── Materials → /home/mitlab/Demos/AEC/BrownstoneDemo/Materials（symlink）
├── frontend/                    ← 舊版 Next.js 前端（已 deprecate，繼續 mount 3001）
├── configure_scene.py           ← 平台啟動時可用：把 scene_config.json 推到 Kit
└── scene_config.json            ← Omniverse 端本地副本
```

**主要 HTTP 端點**（`POST /api/v0.1/RAN/...`，port 8001）
- `Scene/SceneStateReader/read`、`Scene/SceneLayoutReader/read`
- `Scene/SceneController/{build, clear, push_snapshot_to_kit}`
- `Scene/AnimationController/{start, stop}`
- `Scene/BuildingController/{create, read, update, delete}`
- `UE/UEReader/read`、`UE/UEController/{create, update}`
- `GNB/GnbController/{create, read, update}`
- `Ingest/{SignalIngestor, SceneIngestor}/`（RAN 端推訊號 / 場景進來）
- `History/{PositionHistoryReader, SignalHistoryReader}/`

**Kit HTTP（8080）：** `mitlab.ran.api` extension 在 Kit 內起 server，收場景變更 → 直接 mutate USD stage → x11vnc 把畫面送到 :6080 給 Dashboard iframe 顯示。

### 3.8 共用 Postgres（`ransim-postgres`，container :5432 → host :5433）
- `cu_db / du_db / ru_db / physics_db` 四個邏輯 DB
- 由 `postgres-init.sql` 在首次啟動時 `CREATE DATABASE` + grant
- ⚠️ Host 5432 已被 `omniver_postgres` 占用，所以平台 Postgres 對外用 5433

---

## 4. 服務間連線矩陣（Who calls Who）

### 4.1 同步 / control plane（HTTP REST）

```
Dashboard (3010)
   │
   ├──→ CU :8101   /Session/SessionController/* （UE 列表、profile、手動 HO）
   │              /Mobility/A3Controller/*       （調 A3 門檻）
   │              /Mobility/HandoverEvent/list
   ├──→ DU :8102   /Tick/TickController/*        （啟停 sim tick）
   │              /MAC/MacSchedulerController/*  （直接下 PRB quota，繞 RIC）
   ├──→ RU :8103   /Config/RuController/*        （antenna / cell / UE 寫入）
   ├──→ Physics :8104  /Scene/SceneGateway/init       （重建 Sionna scene）
   │                   /RanSignal/CoverageRunner/* （Coverage heatmap）
   │                   ws:/ws/sim/live/            （live 訊號推播）
   ├──→ E2Adapter :8201  /Status/* /EventLog/* /KpmSnapshot/*
   ├──→ UE :8105   /Trajectory/set                 （Dashboard 推軌跡）
   └──→ Omniverse :8001  /RAN/Scene/* /RAN/UE/* /RAN/History/*

UE (8105)
   ├──→ CU :8000  /Session/list             （poll 5 s，diff 出 active UE）
   ├──→ CU :8000  /Session/update_traffic_profile （RLC entity 重建用）
   ├──→ DU :8000  /RLC/inject_sdu / inject_sdu_batch  （每 100 ms inject traffic）
   ├──→ RU :8000  /Position/set              （batch 推座標）
   └──→ Kit :8080 per-UE 位置同步

DU (8102)
   ├──→ CU :8000  /F1AP/F1ApRouter/{measurement_report, cell_measurement_report,
   │              ul_rrc_message, du_setup, du_configuration_update}
   └──→ RU :8000  /FAPI/FapiRouter/{dl_tti_request, ul_tti_request}

RU (8103)
   └──→ Physics :8000  /RanCalc/PathSolver/compute   （每 TTI；cache TTL 0.5 s）

CU (8101)
   ├──→ DU :8000  /F1AP/F1ApRouter/{dl_rrc_message, ue_context_*}
   │              /MAC/MacCellController/disable, MacScheduler/set_prb_quota
   │              （RIC 控制經 e2adapter → CU → DU 落地）
   ├──→ self / split CU-UP  /E1AP/E1ApRouter/bearer_context_setup
   └──→ (mock AMF 自迴 thread；若 HTTP_AMF_HOST 空)

E2Adapter (8201 host net)
   ├──→ CU :8101  /E2/E2NodeId/read       （E2 Setup 時拿 GlobalE2NodeID）
   ├──→ CU :8101  /E2/Indication/poll      （indication producer thread 每 ~report_period 拉 KPM）
   └──→ CU :8101  /E2/Control/request      （收到 RIC_CONTROL_REQ 後落地用）

Omniverse Backend (8001)
   └──→ Kit :8080  推 USD stage mutation
```

### 4.2 非同步 / 外部介面

| 從 | 到 | 協定 | 用途 |
|---|---|---|---|
| `RANsim-E2Adapter` | `10.3.0.71:36422`（外部 RIC e2term） | SCTP PPID=70（pycrate 編 ASN.1） | E2 Setup / Subscription / Indication / Control |
| 外部 RIC / xApp | `RANsim-E2Adapter`（同上 SCTP socket） | SCTP | RIC_SUBSCRIPTION_REQ / RIC_CONTROL_REQ / RIC_RESET |
| `RANsim-DU` PM aggregator | `RANsim-CU` HTTP | HTTP | 每 PM window flush KPM → CU 累計 → e2adapter 端拉 |
| `Physics_sim` | Dashboard | WebSocket `ws://.../ws/sim/live/` | live frame push（UE 位置 / RSRP / SINR） |
| Browser | Kit | noVNC（websockify 6080 → x11vnc 5900） | 3D viewport iframe |

### 4.3 共用儲存
- **Postgres 5433**：CU/DU/RU/Physics 共用，但各自獨立 schema/DB；無跨服務 join
- **`scene_config.json`**（root level）：mount 進 `physics:/mnt/srcin/scene_config.json:ro`，作為 Layer 1 場景定義；Dashboard 還會走 Layer 2 `SceneGateway/init` 把 UI 上的版本推到 Sionna（見記憶 `coverage_data_flow.md`）
- **`ran-sim-protocol`**：bind-mount 到 CU/DU 的 `/opt/ran-sim-protocol`（RU 則由自己 image 內 install），是所有 HTTP body 的合約

---

## 5. 分工 / 責任邊界（Who owns What）

| 領域 | 主負責 | 協同 | 不做 |
|---|---|---|---|
| **RRC FSM、A3 HO 決策、E2 subscription 註冊** | CU (cu_cp) | DU 提供 measurement_report；E2Adapter pull KPM | 不做 PHY / scheduler |
| **F1AP / NGAP / E1AP** | CU | DU 端對接 f1ap_du | — |
| **MAC scheduler、PRB 分配、HARQ、PM 累計** | DU (mac) | RU 算 CQI 回 DU；CU 推 PRB quota | 不算 channel |
| **RLC / SDU 切段 / SDU delay 取樣** | DU (rlc) | UE 推 SDU 進來 | — |
| **PHY 高層（CSI-RS stub）/ FAPI** | DU (phy_high / fapi_north) | RU 是 FAPI south endpoint | 不真實做 OFDM |
| **天線陣列、Beamforming、Precoder、SINR estimate** | RU (antenna / beamforming) | Physics 給 H matrix | 不模 RF front-end |
| **Channel matrix（Sionna 射線追蹤）** | Physics | RU 是 client | 不算 SINR（給 RU 算） |
| **Coverage 熱力圖** | Physics（CoverageRunner） | Dashboard 呼叫 / 顯示 | — |
| **UE 軌跡、Traffic 注入、UCI report** | UE 服務 | CU 提供 active UE list；RU 收 position | — |
| **3D 場景視覺化 / VNC** | Omnivers_platform（Kit + Omniver-RAN） | Dashboard 嵌 iframe | 不做 RAN 計算 |
| **訊號 / 位置歷史 ingest + 回放** | Omniver-RAN（Ingestor + History） | Physics push WS；Dashboard 拉 history | — |
| **E2AP ASN.1 編解碼、SCTP 連線、E2 Reset 重連** | E2Adapter | CU 是它的「南向」資料源 | 不做 xApp 邏輯 |
| **xApp 控制落地** | E2Adapter（收 RIC_CONTROL_REQ）→ CU → DU | — | E2Adapter 自己不 decision |
| **平台編排、Postgres、shared scene** | docker-compose + scene_config.json + ran-sim-protocol | 各服務 | — |
| **Dashboard UI（控制 + 監看）** | Physics_sim/Dashboard | 直連 7 個服務 endpoint | 不存任何狀態 |

---

## 6. 模擬執行現況（2026-05-15 snapshot）

### 6.1 跑得起來的證據
- 14 個 container 連續 up（**2 天 — 47 小時**）無 restart
- `ransim-e2adapter` 對外 RIC 連線穩定，**163,836 RIC_INDICATION 已送出**，sub_id `sub-4e7c91d4804a` 健在
- KPM 報告以 1 Hz（PM_WINDOW_SEC=1.0）穩定產出
- 活躍流量：sub 上看見 `cell=gnb4_c2`、`ue_count=1`（單 UE 訂閱中）

### 6.2 已知的「準確的」設計選擇
- **CU integrated CU-UP mode**（`HTTP_CUUP_HOST=""`）：CU-CP 直接呼叫 CU-UP handler，省 HTTP round-trip
- **DU tick 50 ms / PM window 1 s**：跟上 UE 100 ms inject 不堆 buffer
- **RU channel cache TTL 0.5 s**：相同位置不重複跑 Sionna，省 GPU
- **A3 軟門檻 0.5 dB / 0.3 dB / 60 ms**：demo 友善，跟 spec（0–3 dB / 0–15 dB / 40–5120 ms）相比偏鬆

### 6.3 已知的「需要注意的」狀態
1. **3 個前端 container 同時跑**（3001 / 3002 / 3010），實際維護的只有 `Physics_sim/Dashboard:3010`。其餘兩個來自舊版本，container 還在但 source 已被清乾淨或不被觸碰。
2. **`ransim-dashboard` healthcheck 顯示 unhealthy** — 不影響功能（UI 正常開），但建議查 healthcheck cmd 是否過時。
3. **`/home/mitlab/XAPP_DT/RAN-sim/` 是 root-owned 空目錄** — 對應的 docker compose project `ran-sim` 仍在跑 orphan container，建議下次 maintenance window 用 `docker compose -p ran-sim down` 清掉。
4. **SCTP 跨主機脆弱性**：host reboot 後會清掉 iptables + sysctl，必須重跑 `host_setup_sctp.sh` 否則 e2adapter 會 self-ABORT（記憶 `sctp_host_reboot_wipe.md`）。
5. **Coverage 計算與 DU tick 互斥**：CoverageRunner.compute() 期間 DU tick 暫停（避免 GPU 爭用），即時觀測時要避開重算大圖。

### 6.4 上層 xApp Intent（intents-interface.md）支援狀況
平台目前對外承諾支援 3 種 case，全部走 E2SM-RC：

| Case | KPM 輸入 | RC 動作 | 落地位置 |
|---|---|---|---|
| **IM**（干擾管理） | PrbTotDl + UEThpDl + RlcSduDelayDl | `control_slice_level_prb_quota` (Style 2 / Action 6) | DU `/MAC/MacSchedulerController/set_prb_quota` |
| **CCO**（覆蓋/容量） | PrbTotDl 跨 gNB 差距 | `control_handover` (Style 3 / Action 1) | CU `nr_HO_F1_trigger` → DU `/F1AP/F1ApRouter/ue_context_modification` |
| **ES**（節能） | PrbTotDl + PdcpSduVolumeDL（5 min sliding window） | HO + PRB quota 組合 | 兩段式：先 CU HO，再 DU set_prb_quota（max=5） |

測試紀錄已歸檔在 `docs/test_records/case{1_im,2_cco,3_es}_2026-05-11.md`。

---

## 7. 推薦的後續閱讀路徑

- 想看完整 KPM payload 規格：`RANsim-DU/docs/CU_KPM_PAYLOADS.md`（E2SM-KPM v2.0.03）
- 想看 DU 訊息流：`plan/du-message-flow-reference.md`
- 想看 RIC bug 紀錄：`plan/ric-bug-report-{followup,rnib-stale-race}.md`
- 想看 traffic / PMI 改進方向：`plan/traffic-and-pmi-improvement.md`
- 想跑 KPM 4-cell 取樣：`docs/test_records/kpm_4cell_sample_2026-05-11.md`
- 跨機 host SCTP 設定：`Omnivers_platform/ENV_SETUP.md` 與記憶體 `sctp_host_reboot_wipe.md`

---
*文件由整體目錄掃描 + docker ps 即時狀態 + 7 個服務各自的 actor / service / model layer 交叉比對而成。如各服務 commit 後出現差異，以原始程式碼為準。*
