# RANsim-RU

5G NR Radio Unit 模擬器（Django）。RAN-sim 平台的四個系統之一（RU / DU / CU / Physics 之一）。

協議邏輯參照 [OpenAirInterface5G](https://gitlab.eurecom.fr/oai/openairinterface5g)：
- `executables/nr-ru.c`（RU thread / FH）
- `openair1/PHY/MODULATION/nr_modulation.c`（5G NR Type I codebook，本專案 codebook 直接對拍）
- `nfapi/`（FAPI south side）

跨系統訊息統一用 [`ran-sim-protocol`](../Physics_sim/ran-sim-protocol/)：
- `fapi.py` 定義 `DlTtiRequest` / `UlTtiRequest` / `CqiIndication` / `CrcIndication`
- `physics.py` 定義 `PathSolverRequest` / `PathSolverResponse`

## 角色與責任

RU 是 **reactive** 元件，被 DU 觸發後流程：
1. 收 `dl_tti_request`（每個 PDU 帶 `ue_id, prb_*, mcs, layers, pmi, harq_pid`）
2. 從本地 DB 拉 UE 位置 → 構 `PathSolverRequest` → 打 `Physics`
3. 對每個 PDU：用 PMI 查 codebook 套到 channel matrix → 算 SINR / rank / CQI
4. POST `CqiIndication` 回 DU + 寫 `LastTti` 紀錄

**不在範圍**：真 IFFT/FFT、真 IQ samples、真 LDPC、真 eCPRI / O-RAN 7.2 wire format。
（這些由 OAI 真的做；本專案只做 control-plane 模擬。）

## 啟動（Docker）

```bash
cp .env.sample .env
shell/init_project.sh                              # 把 sibling 的 ran-sim-protocol 同步進 _vendored/
docker compose up -d --build                       # 起 postgres + ru
docker compose exec ru python manage.py migrate    # 跑 migration
```

## 跑測試

```bash
docker compose exec ru pip install -r requirements/test.txt
docker compose exec ru pytest                       # 全部測試
docker compose exec ru pytest main/apps/beamforming # 只跑 codebook / precoder / sinr
```

## Endpoints

URL 格式（backend_rule §7-1）：`/api/v0.1/RU/{Module}/{Component}/{Element}`，**全 POST**。

| Method+Path | 來源 | 用途 |
|-------------|------|------|
| `POST /api/v0.1/RU/Config/RuController/update_antenna` | DU/Dashboard | 設陣列 |
| `POST /api/v0.1/RU/Config/RuController/update_cells`   | DU           | 設多 cell |
| `POST /api/v0.1/RU/Config/RuController/update_ues`     | DU/Dashboard | UE 位置 |
| `POST /api/v0.1/RU/FAPI/FapiRouter/dl_tti_request`     | DU           | DL slot 配置（**主入口**） |
| `POST /api/v0.1/RU/FAPI/FapiRouter/ul_tti_request`     | DU           | UL slot 配置 |
| `POST /api/v0.1/RU/State/RuStateReader/read`           | Dashboard    | 查 RU 狀態 |
| `POST /api/v0.1/RU/Physics/PhysicsHealth/read`         | Dashboard    | 查 Physics 鏈路 |

RU 主動呼叫：
- `POST {PHYSICS}/api/v0.1/Physics/RanCalc/PathSolver/compute`
- `POST {DU}/api/v0.1/DU/FAPI/FapiRouter/cqi_indication`
- `POST {DU}/api/v0.1/DU/FAPI/FapiRouter/crc_indication`

## curl 範例

### 1. 設定天線陣列
```bash
curl -X POST http://localhost:8002/api/v0.1/RU/Config/RuController/update_antenna \
  -H 'Content-Type: application/json' \
  -d '{"rows":4,"cols":2,"polarization":"cross","pattern":"tr38901"}'
```

### 2. 設定 cells（每個 cell 一個方位）
```bash
curl -X POST http://localhost:8002/api/v0.1/RU/Config/RuController/update_cells \
  -H 'Content-Type: application/json' \
  -d '{
    "cells": [
      {"name":"gnb1#1","pci":1,"azimuth_deg":  0,"position":[0,30,0],"frequency_ghz":3.5,"bandwidth_mhz":100},
      {"name":"gnb1#2","pci":2,"azimuth_deg":120,"position":[0,30,0],"frequency_ghz":3.5,"bandwidth_mhz":100},
      {"name":"gnb1#3","pci":3,"azimuth_deg":240,"position":[0,30,0],"frequency_ghz":3.5,"bandwidth_mhz":100}
    ]
  }'
```

### 3. 更新 UE 位置
```bash
curl -X POST http://localhost:8002/api/v0.1/RU/Config/RuController/update_ues \
  -H 'Content-Type: application/json' \
  -d '{
    "ues": [
      {"id":"ue-1","position":[10,1.5, 5],"velocity":[1.0,0,0]},
      {"id":"ue-2","position":[-8,1.5,12]}
    ]
  }'
```

### 4. 觸發 DL TTI（主流程）
```bash
curl -X POST http://localhost:8002/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request \
  -H 'Content-Type: application/json' \
  -d '{
    "sfn":10, "slot":5,
    "pdus":[
      {"ue_id":"ue-1","prb_start":0, "prb_count":24,"mcs":15,"layers":2,"pmi":3, "harq_pid":0,"payload_size_bytes":1500},
      {"ue_id":"ue-2","prb_start":24,"prb_count":24,"mcs":10,"layers":1,"pmi":12,"harq_pid":1,"payload_size_bytes": 800}
    ]
  }'
```

### 5. 查 RU 狀態
```bash
curl -X POST http://localhost:8002/api/v0.1/RU/State/RuStateReader/read -d '{}'
```

## 目錄速查

```
RANsim-RU/
├── main/
│   ├── settings/{base,local,production,test}.py
│   ├── utils/{env_loader,logger,response}.py        ← rule §3-2-3 必備
│   ├── urls.py                                      ← 只做 include
│   └── apps/
│       ├── antenna/         （AntennaConfig / Cell / UePosition + RuController）
│       ├── beamforming/     （codebook 直接對拍 OAI）
│       ├── phy_low/         （RuState + ofdm_descriptor + grid_builder）
│       ├── physics_client/  （HTTP client 打 Physics + LRU/TTL cache）
│       └── fapi_south/      （FapiRouter — 主入口；dl/ul_tti_pipeline 編排器）
├── requirements/{base,local,production,test}.txt
├── shell/{init_project,run_migrations}.sh
├── Dockerfile / docker-compose.yml
├── pytest.ini / conftest.py
└── _vendored/ran-sim-protocol/                      ← init_project.sh 同步進來
```

## 對 OAI 的對應

| 本專案 | OAI 對應 |
|---|---|
| `main/apps/beamforming/services/optional/codebook.py` | `openair1/PHY/MODULATION/nr_modulation.c:33-118`（六張 Type I 表）|
| `main/apps/beamforming/services/optional/precoder.py` | `nr_feptx_prec()` (`nr_ru_procedures.c`) |
| `main/apps/phy_low/services/optional/ofdm_descriptor.py` | `openair1/PHY/MODULATION/ofdm_mod.c` 的參數面 |
| `main/apps/phy_low/services/optional/grid_builder.py` | `nr_feptx_tp()` 的 input grid 概念 |
| `main/apps/fapi_south/actors/fapi_router.py` | `nr-ru.c::ru_thread()` 收到 nFAPI DL/UL request 後的處理鏈（control plane only）|
| `main/apps/physics_client/services/optional/physics_http.py` | 取代 OAI `radio/COMMON/common_lib.h` 的 `openair0_device.trx_read_func`：訊號模型由 Physics service 提供 |

## 環境變數

詳見 `.env.sample`。關鍵：
- `HTTP_PHYSICS_HOST` / `HTTP_PHYSICS_PORT` — Physics service 位置
- `HTTP_DU_HOST` / `HTTP_DU_PORT` — DU 位置（用於回 CqiIndication / CrcIndication）
- `RU_CHANNEL_CACHE_TTL_SEC` — UE 同位置不重打 Physics 的 TTL（預設 0.5s）
- `RU_NOISE_FLOOR_DBM` — SINR 估算用的 noise floor（預設 -95 dBm）
