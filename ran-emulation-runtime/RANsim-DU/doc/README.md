# RANsim-DU — gNB-DU

## 系統用途
5G NR **gNB 分散單元(DU)**,埠 `:8102`。**整個模擬的真實來源與心跳**:每 tick 跑 MAC PF 排程、RLC、HARQ、link adaptation、PM 聚合,並以 0.5ms slot engine 建模 delay。DU tick 驅動 UE/CU/E2Adapter 同步。
↔ OAI:`NR_MAC_gNB/gNB_scheduler_*`、`nr_rlc`、`F1AP/f1ap_du_task.c`、nFAPI。

## 模組(Django apps,`main/apps/`)
| 模組 | 路徑 | 功能 | 對應 OAI |
|---|---|---|---|
| `tick` | `main/apps/tick` | slot 時鐘、sim/wall 解耦、PM window、RLC delay 模型、measurement_report 觸發 | gNB_scheduler 迴圈 |
| `mac` | `main/apps/mac` | PF 排程(2-pass/retx-aware)、HARQ、CQI→MCS、PRB quota、PM 聚合 | NR_MAC_gNB scheduler |
| `rlc` | `main/apps/rlc` | AM/UM/TM entity、SDU→PDU 分段、retx、BO、SDU delay、discardTimer | nr_rlc_entity.c |
| `phy_high` | `main/apps/phy_high` | MCS→調變階數、layer mapping、BLER 查表、TBS/吞吐 | LAYER1/NR_TRANSPORT |
| `f1ap_du` | `main/apps/f1ap_du` | F1Setup、UE context CRUD、DL/UL RRC 轉送、measurement_report 匯集 | f1ap_du_task.c |
| `fapi_north` | `main/apps/fapi_north` | DL/UL TTI 組裝、CQI→MCS/CRC→HARQ 回饋、in-process SINR(讀 cache) | nFAPI DL/UL TTI |

## API(全部 POST,前綴 `/api/v0.1/DU/`)

### Tick/TickController
| 端點 | 說明 |
|---|---|
| `Tick/TickController/start`·`stop`·`run_once` | 起/停/單步 tick 引擎 |
| `Tick/TickController/read` | tick 狀態 |
| `Tick/TickController/set_speed` | 設模擬速度(wall_tick) |
| `Tick/TickController/dump_pm`·`reset_pm` | 匯出/重置 PM(KPM) |
| `Tick/TickController/register_ue`·`replace_ues` | 註冊/替換 UE registry |

### MAC/MacScheduler
| 端點 | 說明 |
|---|---|
| `MAC/MacScheduler/set_runtime_phys`·`get_runtime_phys` | 設/讀 runtime 物理旋鈕(tx/inter_freq/discard/rlc_delay) |
| `MAC/MacScheduler/set_prb_quota`·`clear_prb_quota`·`list_prb_quota` | PRB quota 設/清/列 |

### MAC(cell / UE / HARQ)
| 端點 | 說明 |
|---|---|
| `MAC/MacCellController/create`·`read`·`update`·`replace_cells`·`disable`·`enable` | cell 管理 |
| `MAC/MacUeStateController/read` | 讀 UE MAC 狀態 |
| `MAC/MacHarqController/read` | 讀 HARQ 狀態 |

### RLC
| 端點 | 說明 |
|---|---|
| `RLC/RlcEntityController/create`·`read`·`delete` | RLC entity |
| `RLC/RlcDataController/inject_sdu`·`inject_sdu_batch` | 注入 SDU |
| `RLC/RlcDataController/read_buffer_status` | 讀 RLC buffer(BO) |
| `RLC/RlcDataController/report_ul_traffic` | 回報上行流量 |

### PHY / F1AP / FAPI
| 端點 | 說明 |
|---|---|
| `PHY/PhyHighController/compute_modulation_throughput`·`estimate_bler` | 吞吐/BLER 估計 |
| `F1AP/F1ApRouter/ue_context_setup`·`ue_context_modification`·`ue_context_release` | UE context |
| `F1AP/F1ApRouter/dl_rrc_message`·`ul_rrc_message`·`f1_setup_response` | RRC 轉送 / F1 setup |
| `F1AP/F1SessionController/read` | F1 session 狀態 |
| `FAPI/FapiRouter/cqi_indication`·`crc_indication` | CQI/CRC 回饋(RU→DU) |

> 平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md);運作流程見 [`docs/workflow.md`](../../docs/workflow.md)。
