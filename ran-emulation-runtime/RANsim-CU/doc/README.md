# RANsim-CU — gNB-CU

## 系統用途
5G NR **gNB 中央單元(CU)**,埠 `:8101`。負責控制面 RRC / F1AP / NGAP / E2 訊令、A3 換手決策、UE session 管理,以及使用者面 PDCP/SDAP/GTP-U(E1AP bearer)。是 xApp(經 E2Adapter → RIC)下控制的落地點。
↔ OAI:`RRC/NR/rrc_gNB.c`、`F1AP/f1ap_cu_*`、`NGAP/ngap_gNB.c`、`LAYER2/PDCP`、`SDAP`。

## 模組(Django apps,`main/apps/`)
| 模組 | 路徑 | 功能 | 對應 OAI |
|---|---|---|---|
| `cu_cp` | `main/apps/cu_cp` | 控制面:RRC 狀態機、F1AP/NGAP/E2 router、A3 HO 評估、UE context、KPM 匯集/E2 訂閱 | rrc_gNB / f1ap_cu / ngap_gNB |
| `cu_up` | `main/apps/cu_up` | 使用者面:E1AP bearer context、DRB(PDCP/SDAP/GTP-U) | PDCP_v10.1.0 / SDAP |

## API(全部 POST,前綴 `/api/v0.1/CU/`)

### F1AP/F1ApRouter
| 端點 | 說明 |
|---|---|
| `F1AP/F1ApRouter/du_setup` | DU 向 CU 註冊(F1 Setup) |
| `F1AP/F1ApRouter/du_configuration_update` | 更新 DU cell 設定 |
| `F1AP/F1ApRouter/ul_rrc_message` | 轉送上行 RRC |
| `F1AP/F1ApRouter/measurement_report` | 處理 UE 量測回報 |
| `F1AP/F1ApRouter/cell_measurement_report` | 處理 cell 量測回報 |

### NGAP/NgapRouter
| 端點 | 說明 |
|---|---|
| `NGAP/NgapRouter/initial_ue_message` | UE 初始 attach |
| `NGAP/NgapRouter/initial_context_setup` | 建 PDU session |
| `NGAP/NgapRouter/downlink_nas_transport` | 下行 NAS |

### Session/SessionController
| 端點 | 說明 |
|---|---|
| `Session/SessionController/list` | 列出所有 UE session |
| `Session/SessionController/get_state` | 取單一 UE 狀態 |
| `Session/SessionController/handover` | 觸發 UE 換手 |
| `Session/SessionController/release_stale` | 釋放 stale session |
| `Session/SessionController/release_all` | 釋放所有 session |
| `Session/SessionController/update_traffic_profile` | 設 UE 流量樣式 |

### E2(xApp/RIC 介面)
| 端點 | 說明 |
|---|---|
| `E2/E2KpmReporter/read` | 讀 KPM 快照 |
| `E2/Subscription/create`·`delete`·`list` | xApp KPM 訂閱管理 |
| `E2/Indication/poll` | 拉 KPM indication(E2Adapter 用) |
| `E2/Control/request` | 落地 xApp 控制(RC) |
| `E2/E2NodeId/read` | 讀 gNB node id |
| `E2/KpmSpeed/set`·`read` | 設/讀 KPM 模擬速度 |

### Mobility / Logs / UP
| 端點 | 說明 |
|---|---|
| `Mobility/A3Controller/read`·`set` | 讀/設 A3 換手門檻 |
| `Mobility/HandoverEvent/list` | 列 HO 事件 |
| `Logs/Ring/read` | 讀 CU debug log |
| `E1AP/E1ApRouter/bearer_context_setup` | 建 DRB(cu_up) |
| `UP/Drb/list`·`read` | 列/讀 DRB 狀態 |

> 完整平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md);運作流程見 [`docs/workflow.md`](../../docs/workflow.md)。
