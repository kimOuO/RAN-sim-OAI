# RANsim-DU

5G NR Distributed Unit 模擬器,RAN-sim 平台四大系統(CU / DU / RU / Physics)的 DU 角色。協議邏輯對齊 OpenAirInterface5G(`openair2/LAYER2/NR_MAC_gNB/`、`openair2/LAYER2/nr_rlc/`、`openair2/F1AP/f1ap_du_*.c`、`nfapi/`)。

## 角色

- **北向 (F1AP)** — 與 CU 互動:啟動時送 F1Setup;接收 DL RRC、UE Context Setup/Release;週期上報 measurement_report
- **南向 (FAPI)** — 與 RU 互動:每 tick 送 DL/UL TTI Request;接收 CQI/CRC indication
- **Tick driver** — 整個平台的時序驅動,500 ms 一輪

## 目錄結構

```
RANsim-DU/
├── manage.py
├── requirements/{base,local,production,test}.txt
├── Dockerfile / docker-compose.yml
├── shell/{init_project,run_migrations}.sh
├── conftest.py / pytest.ini
└── main/
    ├── settings/{base,local,production,test}.py
    ├── utils/{env_loader,logger,response}.py
    ├── urls.py     # 聚合 6 個 app
    └── apps/
        ├── mac/         # OAI: NR_MAC_gNB/   — Scheduler / HARQ / MCS / RA / LCP / PM
        ├── rlc/         # OAI: nr_rlc/        — AM / UM / TM
        ├── phy_high/    # OAI: NR_TRANSPORT/  — modulation / LDPC / layer / precoding
        ├── f1ap_du/     # OAI: F1AP/f1ap_du_* — F1Setup / UE context / DL RRC
        ├── fapi_north/  # OAI: nfapi/         — DL/UL TTI / CQI / CRC
        └── tick/        # tick driver(無對應 OAI)
```

每個 app 都遵守 `backend_rule.md` §1-2:`models / serializers / actors / api / services/{business,common,optional} / tests/{services,unit_test} / apps.py`。

## URL 規範

- 全部 POST(rule §7-2)
- 格式:`/api/v0.1/DU/{Module}/{Component}/{Element}`

### DU 對外 endpoint

| Endpoint | 說明 |
|---|---|
| `POST /api/v0.1/DU/MAC/MacCellController/{create,read,update}` | Cell 配置 |
| `POST /api/v0.1/DU/MAC/MacUeStateController/read` | 查 UE MAC 狀態 |
| `POST /api/v0.1/DU/MAC/MacHarqController/read` | 查 HARQ process |
| `POST /api/v0.1/DU/RLC/RlcEntityController/{create,read,delete}` | RLC entity |
| `POST /api/v0.1/DU/RLC/RlcDataController/inject_sdu` | 模擬注入 SDU |
| `POST /api/v0.1/DU/RLC/RlcDataController/read_buffer_status` | 查 BO |
| `POST /api/v0.1/DU/PHY/PhyHighController/compute_modulation_throughput` | MCS+PRB→Mbps |
| `POST /api/v0.1/DU/PHY/PhyHighController/estimate_bler` | SINR+MCS→BLER |
| `POST /api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup` | CU → DU |
| `POST /api/v0.1/DU/F1AP/F1ApRouter/ue_context_release` | CU → DU |
| `POST /api/v0.1/DU/F1AP/F1ApRouter/dl_rrc_message` | CU → DU → UE |
| `POST /api/v0.1/DU/F1AP/F1ApRouter/f1_setup_response` | CU → DU(callback) |
| `POST /api/v0.1/DU/F1AP/F1SessionController/read` | 查 F1 連線 DB row + in-memory bootstrap state |
| `POST /api/v0.1/DU/FAPI/FapiRouter/cqi_indication` | RU → DU |
| `POST /api/v0.1/DU/FAPI/FapiRouter/crc_indication` | RU → DU |
| `POST /api/v0.1/DU/Tick/TickController/{start,stop,run_once,read,register_ue}` | Tick driver |

### DU 對外主動呼叫

```
POST {RU}/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request
POST {RU}/api/v0.1/RU/FAPI/FapiRouter/ul_tti_request
POST {CU}/api/v0.1/CU/F1AP/F1ApRouter/du_setup                (啟動時)
POST {CU}/api/v0.1/CU/F1AP/F1ApRouter/measurement_report      (每 5 tick)
POST {CU}/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message          (UE 上行 RRC PDU)
POST {CU}/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update (cell add/modify/delete)
```

## 共用 Protocol Package

訊息格式由 `/home/mitlab/XAPP_DT/Physics_sim/ran-sim-protocol/` 統一定義(F1AP / FAPI / NGAP / E1AP / Physics)。本 repo 透過 editable install 引入:

```python
from ran_sim_protocol.f1ap import F1Setup, UeContextSetup, GnbDuMeasurementReport
from ran_sim_protocol.fapi import DlTtiRequest, CqiIndication, CrcIndication
from ran_sim_protocol import to_dict, from_dict
```

## 環境變數

複製 `.env.sample` 成 `.env` 後修改。關鍵 keys:

```env
DJANGO_SECRET_KEY=...
DB_HOST=postgres / DB_NAME=du_db
HTTP_CU_HOST / HTTP_CU_PORT
HTTP_RU_HOST / HTTP_RU_PORT
SIM_TICK_MS=500
SIM_SCHEDULER=PF | RR | MAXTHROUGHPUT
SIM_BLER_CURVE_PATH=/app/main/apps/phy_high/data/bler_curve.csv
SIM_GNB_DU_ID=1
SIM_DEFAULT_PRB_PER_CELL=273
```

**全 repo 嚴禁 `os.getenv()`**,只能透過 `from main.utils.env_loader import get_str/int/float/bool/list`。

## 啟動

### 本機 (venv)

```bash
./shell/init_project.sh        # 建 venv, 裝 deps, 跑 migrate
python manage.py runserver 0.0.0.0:8002
```

### Docker Compose

```bash
docker compose up --build -d
docker compose logs -f du
```

## 一些 curl 範例

啟動 tick driver:
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/Tick/TickController/start -d '{}'
```

同步跑一個 tick(不啟 thread,測試用):
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/Tick/TickController/run_once -d '{}'
```

註冊 UE 進 tick registry:
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/Tick/TickController/register_ue \
  -H 'Content-Type: application/json' \
  -d '{"ue_id": "ue-1", "serving_cell": "cell-0", "sinr_db": 15.0}'
```

CU 模擬送 UE Context Setup:
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup \
  -H 'Content-Type: application/json' \
  -d '{"ue_id":"ue-1","drbs":[{"drb_id":1,"qos_5qi":9,"rlc_mode":"AM"}]}'
```

RU 模擬上報 CQI:
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/FAPI/FapiRouter/cqi_indication \
  -H 'Content-Type: application/json' \
  -d '{"ue_id":"ue-1","sinr_db":18.5,"cqi":11,"rank":1,"pmi":0}'
```

UE 模擬送 UL RRC(例如 RA Msg3,初始 attach):
```bash
curl -X POST http://localhost:8002/api/v0.1/DU/F1AP/F1ApRouter/ul_rrc_message \
  -H 'Content-Type: application/json' \
  -d '{"ue_id":"ue-1","rrc_msg_b64":"UlJDU2V0dXBSZXF1ZXN0","is_initial":true}'
```

## 測試

```bash
pytest                          # 全部 (54 cases)
pytest main/apps                # 各 app 自己的 service / unit_test
pytest tests/integration        # CU/RU 對接整合測試 (mock HTTP server)
pytest -k pf_scheduler -v       # 指定函式
```

`tests/integration/` 在測試 process 內起 mock CU + mock RU(stdlib `ThreadingHTTPServer`),
透過 `monkeypatch` 改 `HTTP_CU_HOST/PORT` / `HTTP_RU_HOST/PORT` 把 client 導向 mock。
覆蓋:
- F1Setup payload schema 對 CU
- DL/UL TTI Request schema 對 RU
- measurement_report schema 對 CU
- 完整 loop:CU→DU `ue_context_setup` + `register_ue` + `cqi_indication` + `inject_sdu` → 跑 5 tick → mock RU 收到 5 筆 `dl_tti_request`、mock CU 收到 1 筆 `measurement_report`
- UE release 後不再被排程
- CU/RU 不可達時 client 不拋例外,優雅回 None / False

## Tick 流程(每 500 ms)

1. `rlc.entities.scan_buffer_status()` — 收集每個 entity 的 BO
2. `mac.scheduler.allocate(per_cell, ues_with_bo)` — PRB+MCS map(PF / RR / MaxThroughput)
3. `mac.mcs_controller.update()` — 閉環 AMC
4. `fapi_north.tti_builder.build()` → `RuClient.post_dl_tti_request()`
5. RU 主動 POST `cqi_indication` / `crc_indication` 進來(非同步)
6. `mac.pm_aggregator.accumulate_tick()`
7. 每 5 tick:`f1ap_du.cu_client.post_measurement_report()`

`sfn`/`slot` 推進(slot 0..19,sfn 0..1023)。

## 不在範圍

- 真 IQ samples(由 RU 處理 PHY-Low)
- 真 LDPC 編解碼(用 BLER curve)
- 真 ASN.1 / nFAPI wire format
- 真 SCTP / GTP-U(用 HTTP 取代)

## OAI 對應路徑

| 本 repo | OAI |
|---|---|
| `apps/mac/services/optional/scheduler/` | `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler*.c` |
| `apps/mac/services/optional/harq/` | `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c` (HARQ pool) |
| `apps/mac/services/optional/random_access/` | `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_RA.c` |
| `apps/mac/services/optional/link_adaptation/mcs_controller.py` | `get_mcs_from_bler()` in scheduler_primitives.c |
| `apps/rlc/services/optional/entities/{am,um,tm}_entity.py` | `nr_rlc_entity_{am,um,tm}.c` |
| `apps/phy_high/services/optional/coding/ldpc_abstract.py` | `openair1/PHY/CODING/` (LDPC,我們抽象成 BLER) |
| `apps/phy_high/services/optional/precoding/mimo_processor.py` | `openair1/PHY/MODULATION/` (precoding 抽象) |
| `apps/f1ap_du/actors/f1ap_router_actor.py` | `openair2/F1AP/f1ap_du_{ue_context_management,rrc_message_transfer}.c` |
| `apps/f1ap_du/services/optional/lifecycle/du_bootstrap.py` | `openair2/F1AP/f1ap_du_task.c:F1AP_DU_REGISTER_REQ` |
| `apps/fapi_north/services/optional/tti_builder/` | `nfapi/oai_integration/` (FAPI MAC→PHY) |
| `apps/tick/services/optional/runner/tick_runner.py` | `executables/nr-softmodem.c::main()` 的 slot loop(高度抽象) |
