# RANsim-UE — UE 群 / 劇本執行器

## 系統用途
**UE 模擬器**,埠 `:8105`。管理每個 UE 的生命週期(attach/detach)、以劇本軌跡內插推位置(→RU)、注入流量(→DU RLC)、輪詢訊號量測。也是**劇本執行器**(SimController/ScenarioController)——把 store 的劇本跑起來,但**不儲存劇本**(無 DB)。
↔ OAI:NAS/RRC 狀態、38.331 量測回報;劇本編排屬測試框架。

## 模組(Django apps,`main/apps/`)
| 模組 | 路徑 | 功能 | 對應 OAI |
|---|---|---|---|
| `ue_lifecycle` | `main/apps/ue_lifecycle` | per-UE 執行緒:poll CU、trajectory 內插(~100ms)、推位置、traffic gen、量測輪詢 | NAS/RRC + 38.331 |
| `scenario` | `main/apps/scenario` | 載劇本(從 store 讀 raw_json)、套場景幾何、bulk attach、start/stop/status | 測試框架 |

> 劇本**儲存**不在此 —— 由 store(預設 Omniverse,可切 Physics `SCENARIO_STORE_URL`)提供;UE 只**執行**。

## API(全部 POST,前綴 `/api/v0.1/UE/`)

### Sim / Scenario(劇本執行)
| 端點 | 說明 |
|---|---|
| `Sim/SimController/start`·`stop` | 統一模擬起/停(scene-apply → attach → DU tick → lifecycle) |
| `Scenario/ScenarioController/start`·`stop`·`status` | 劇本執行控制 + 進度 |

### Lifecycle / Trajectory / Status
| 端點 | 說明 |
|---|---|
| `Lifecycle/sync` | CU 推 attach/detach/sim_start 事件 |
| `Lifecycle/start`·`stop` | 所有 UE 起/停 |
| `Trajectory/set`·`clear`·`list` | UE 軌跡設定 |
| `Status/read` | UE 模擬器狀態 |

> 平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md);運作流程見 [`docs/workflow.md`](../../docs/workflow.md)。
