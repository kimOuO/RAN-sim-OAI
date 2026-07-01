# RANsim-E2Adapter — gNB E2 termination

## 系統用途
**E2 介面翻譯器**,埠 `:8201`(host network)。把 sim 的 HTTP 世界橋接到 O-RAN RIC 的 **SCTP + ASN.1/APER**:維持 SCTP 連線與 E2 Setup 握手、從 CU 拉 KPM 編成 E2SM-KPM 送 RIC、收 RIC 的 E2SM-RC 控制落地回 CU。
↔ O-RAN:E2AP v2.0.3、E2SM-KPM v2.0.03、E2SM-RC v01.03;SCTP PPID=70。

## 模組(Django app `e2_adapter`,子模組)
| 子模組 | 路徑 | 功能 |
|---|---|---|
| `codec` | `.../services/optional/codec` | E2AP / E2SM-KPM Format3 / E2SM-RC / Subscription 的 APER 編解碼(pycrate) |
| `sctp_link` | `.../services/optional/sctp_link` | SCTP 常駐 daemon、E2 Setup 握手、per-sub indication 執行緒、Reset debounce |
| `event_log` | `.../services/optional/event_log` | KPM ring(per UE×metric)、事件 ring |
| `sim_bridge` | `.../services/optional/sim_bridge` | HTTP 打 sim CU:拉 E2 node id / indication、落地 control |

## API(全部 POST,前綴 `/api/v0.1/E2Adapter/`)
| 端點 | 說明 |
|---|---|
| `Status/AdapterStatusReader/read` | 讀 adapter 狀態(SCTP link / E2 Setup / codec self-test) |
| `EventLog/EventLogReader/read` | 讀事件 log |
| `KpmSnapshot/SnapshotReader/read`·`reset` | 讀/重置 KPM 快照 |
| `KpmSnapshot/RecentReader/read` | 讀最近 KPM |
| `KpmSnapshot/HistoryReader/read` | 讀 KPM 歷史 |
| `KpmSpeed/SpeedController/set`·`read` | 設/讀 E2 indication 速率 |

> RC 控制的觀察查詢見 [`docs/api/rc_observation_api.md`](../../docs/api/rc_observation_api.md)。平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md)。
