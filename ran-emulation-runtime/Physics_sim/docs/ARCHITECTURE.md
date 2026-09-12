# ranp-sim 架構總覽

**撰寫日期**：2026-04-18
**對應規範**：`../backend_rule.md` (Backend Architecture Specification 2.0)
**上游架構圖**：`../../newplan/artictecture.xml`

---

## 1. 在整體架構中的位置

```
┌───────────────────────┐                ┌─────────────────────┐
│  Omniverse server     │                │  FlexRIC / xApp     │
│  (Kit app + UI)       │                │  (KPM / RC)         │
└───────────┬───────────┘                └──────────▲──────────┘
            │  per-tick POST                        │ E2 JSON
            │  UE positions                         │
            ▼                                       │
   ┌─────────────────────────────────────────────────┐
   │  ranp-sim (本 repo)                              │
   │  ─ Django + DRF backend                          │
   │  ─ Sionna RT compute engine                      │
   │  ─ 對應架構圖上的「模擬RAN / DU(sionna)」方塊    │
   └─────────────────────────────────────────────────┘
```

**不負責**：Omniverse 場景建置、UE 位置預測、換手決策、E2AP 二進位協定（目前用 JSON mock）。

---

## 2. Request Chain（遵守鐵則 2-1）

```
Client (Omniverse / tester)
   │
   │ POST /api/v0.1/RanpSim/RanSignal/<Component>/<Element>
   ▼
main/urls.py                                      ← 只做 include
   │
   ▼
main/apps/ran_signal/api/urls.py                  ← 直接綁 Actor.function
   │
   ▼
Actor (compute_actor / config_actor / health_actor)
   │
   ├── Serializer 驗證輸入
   │
   ├── Business Service
   │     └─ SionnaBusinessService（狀態持有者：engine 實例 + loaded_config）
   │           │
   │           └── Optional Service（ran_calculation/）
   │                 ├─ scene_loader.py      (讀 scene_config.json)
   │                 ├─ sionna_engine.py     (PathSolver wrapper)
   │                 ├─ e2_formatter.py      (組 E2 JSON + ue_status)
   │                 └─ mcs_table.py         (SINR → MCS → throughput)
   │
   ├── Common Service（UUID / Timestamp / Validation）
   │
   └── 回傳（utils/response.success_response）
```

---

## 3. 分層職責

### 3.1 Actors（HTTP + 業務編排）

| Actor | action | 行為 |
|---|---|---|
| `ComputeActor.compute` | POST | per-tick 收 UE → 吐 E2 JSON |
| `ConfigActor.read` | POST | 查目前 loaded scene + gNB/UE list |
| `ConfigActor.reload` | POST | 重讀 `scene_config.json` |
| `HealthActor.read` | POST | Sionna ready? GPU ok? |

**職責**（鐵則 13-1）：解析 → Serializer 驗證 → 編排 Business Service → 錯誤處理 → 格式化回傳。

### 3.2 Serializers

- `compute_serializers.py` — Compute request/response 全欄位
- `config_serializers.py` — Config read/reload

**DRF 用法**：Write serializer 驗證 + validate_*；Read serializer 格式化輸出。符合鐵則 3-3。

### 3.3 Business Service（`services/business/`）

- `sionna_operations.py` — **SionnaBusinessService**
  - 單例狀態：持有 `SionnaEngine` instance、已載入的 `scene_config`
  - 方法：`reload_scene_config` / `compute_tick` / `get_loaded_config` / `health_status` / `is_scene_loaded`
  - 鐵則 14-2 通用性：方法接受參數（ue_positions, scene_id, timestamp_ms），不硬編碼具體 UE/gNB

> **為什麼沒有 `sqldb_operations.py`**：本服務 compute-only，`main.settings.base.DATABASES = {}`；經使用者核准免 DB（破例鐵則 11）。

### 3.4 Common Service（`services/common/`，鐵則 14-3 必備三件）

| 檔案 | 提供 |
|---|---|
| `uuid_service.py` | `generate_uuid(prefix, seed)`, `random_uuid()` |
| `timestamp_service.py` | `now_ms()`, `now_s()` |
| `validation_service.py` | `is_finite_vec3`, `in_range` |

### 3.5 Optional Service（`services/optional/ran_calculation/`）

RAN 計算邏輯集中在此，**不被放在 business**，因為：
1. 被多個 business 方法共用（`compute_tick` + 未來 `batch_simulate`）
2. 邏輯內聚且獨立可測（`mcs_table` 不需 GPU 就能單測）
3. 屬「特定領域邏輯」符合鐵則 14-4 條件

| 檔案 | 職責 |
|---|---|
| `scene_loader.py` | 讀 `scene_config.json`，驗欄位，自動補 PCI/cell_id |
| `sionna_engine.py` | 初始化 Sionna scene + Transmitters；per-tick 更新 Receivers 跑 PathSolver |
| `e2_formatter.py` | path gain → RSRP/RSRQ/SINR/MCS/neighbors → E2 JSON + ue_status |
| `mcs_table.py` | 3GPP TS 38.214 SINR → MCS → throughput 查表 |

### 3.6 Utils（`main/utils/`，鐵則 3-2-3 必備三件）

| 檔案 | 用途 |
|---|---|
| `env_loader.py` | **唯一** env 取得管道；get_str/get_int/get_float/get_bool/get_list |
| `logger.py` | 統一 logger（console + rotating file） |
| `response.py` | `success_response` / `error_response` DRF 回傳格式 |

---

## 4. 檔案依賴關係（import graph）

```
actors/compute_actor
  ├── serializers/compute_serializers
  ├── services/business/sionna_operations
  │     └── services/optional/ran_calculation/
  │            ├── scene_loader
  │            ├── sionna_engine  ← import sionna.rt (延遲 import)
  │            └── e2_formatter
  │                  └── mcs_table
  ├── services/common/timestamp_service
  ├── utils/logger
  └── utils/response
```

---

## 5. 啟動順序（生命週期）

1. **容器啟動** → `manage.py runserver 0.0.0.0:8000`（dev）或 `gunicorn`（prod）
2. **Django boot** → 載 INSTALLED_APPS，`RanSignalConfig.ready()` 不做事（避免 migrate 等 cmd 拖 GPU）
3. **第一次 `/compute` 或 `/config/reload`** → 延遲初始化 `SionnaEngine`
   - 讀 `scene_config.json`
   - 載入 Mitsuba XML 場景
   - 建所有 Transmitter (gNB)
   - 配天線陣列
4. **後續 tick** → 重用 engine，只更新 Receivers

---

## 6. 違反鐵則的地方（必須明示）

| 鐵則 | 違反 | 原因 | 使用者核准 |
|---|---|---|---|
| 11. 必須綁資料庫 | `DATABASES = {}` | 服務 compute-only，不需持久化 | ✅ 2026-04-18 |

其他鐵則（1/2/3/4/5/6/7/8/10/12/13/14）皆符合。

---

## 7. 跟專案其他部分的關係

| 專案 | 關係 |
|---|---|
| `scene_config.json` | **唯讀輸入**。ranp-sim 啟動時讀一次 gNB/UE/buildings 配置 |
| `kit-app-template/.../mitlab.ran.signal` | **外部 HTTP client**（由另一平台實作）將每 tick POST 到 ranp-sim |
| `RAN_knowledge/E2.md` | 輸出格式參考 |
| `LLM_learning/*.md` | 研究筆記，含 Sionna/Aerial/AODT 比較 |
