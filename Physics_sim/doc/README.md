# Physics_sim — Sionna RT 物理層 + 劇本/場景倉庫

## 系統用途
埠 `:8104`(需 GPU)。兩個角色:
1. **物理層(`ran_signal`,compute-only)**:用 NVIDIA Sionna RT 光追算通道 —— RU 即時查 PathSolver(path_gain / channel matrix)、Dashboard 算 coverage 熱圖、離線 precompute 把 (tick,ue,cell) 存成 `.npz` 供 cached 模式查表。取代真實 RF/channel。
2. **劇本/場景倉庫(`scenario_store`,用 physics_db)**:鏡像 Omniverse 的劇本/場景端點,讓 RAN sim 可**脫離 Omniverse** 運作(見 [`docs/plan` 已刪 → memory `omniverse_decouple_goal`])。

↔ OAI:`RADIO/RF/` channel model 取代;Sionna 為外部高保真引擎。

## 模組(`main/apps/`)
| 模組 | 路徑 | 功能 |
|---|---|---|
| `ran_signal` | `main/apps/ran_signal` | PathSolver(光追)、Coverage、Precompute、ConfigManager、SceneGateway、Health;**compute-only 不碰 DB** |
| `scenario_store` | `main/apps/scenario_store` | physics_db 上的 Scenario/GnbConfig/UeConfig/BuildingObject;鏡像 Omniverse 劇本/場景端點 |

## API(全部 POST)

### 物理計算(`/api/v0.1/Physics/`)
| 端點 | 說明 |
|---|---|
| `Physics/RanCalc/PathSolver/compute` | 光追算 path_gain / channel matrix |
| `Physics/Precompute/run`·`status` | 離線通道 precompute → npz |
| `Physics/RanSignal/ConfigManager/read`·`reload`·`push_scene`·`reset_to_default` | 場景設定 |
| `Physics/RanSignal/CoverageRunner/compute` | 算 coverage 熱圖(RSRP/SINR) |
| `Physics/RanSignal/HealthChecker/read` | 健康 + GPU 狀態 |
| `Physics/Scene/SceneGateway/init` | 初始化 Sionna 場景 |

### 劇本/場景倉庫(`/api/v0.1/RAN/`,鏡像 Omniverse,可作脫離來源)
| 端點 | 說明 |
|---|---|
| `RAN/Scenario/ScenarioController/upload`·`list`·`read`·`delete` | 劇本 CRUD(raw_json) |
| `RAN/Scenario/ScenarioController/apply_to_scene` | 劇本拓樸寫進 scene 表 |
| `RAN/Scenario/ScenarioController/precompute`·`update_status` | precompute 狀態 |
| `RAN/GNB/GNBReader/read` · `RAN/UE/UEReader/read` | 讀 gNB / UE 場景 |
| `RAN/Scene/BuildingController/read` · `RAN/Scene/SceneLayoutReader/read` | 讀建築 / 場景 layout |

> 消費端用 `SCENARIO_STORE_URL`(預設 Omniverse)切到此 store。平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md)。
