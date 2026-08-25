# ANR 觀測類 xApp 命令 — 規劃

承 `docs/plan/anr_xapp_commands_plan.md`(控制 3 件已端到端驗證)。本文規劃**觀測類**。

## 現況盤點(2026-08-11)

觀測資料 + CU 查詢端點**已實作大半**(P0-2/3/4/5),都在 CU HTTP:

| 文件命令 | CU 端點 | 資料源 | 狀態 |
|---|---|---|---|
| `RC_E2NODEINFO_QUERY` | `POST /CU/E2/NodeInfo/read` | NrCellRelation + freq + NrRelationChangeEvent | ✅ §9.3.38 全欄 |
| `RC_MEASCONFIG_REPORTCGI` | `POST /CU/E2/Anr/cgi_resolve` | CellConfig（PCI→NCGI + confusion） | ✅ |
| perNeighbourRelation KPM | `POST /CU/E2/Anr/kpm` | HandoverEvent（HO 速率/成功比/failureCause） | ⚠️ 見缺口① |
| `RC_MSGCOPY_SUBSCRIBE_MEAS`（RSRP 分位數） | `POST /CU/E2/Anr/meas_aggregate` | MeasurementLog.neighbor_cells_json | ✅（MEAS 部分） |
| `KPM_REPORT_SUBSCRIBE` | 既有 KPM | — | ✅ |
| `RC_MOBILITY_HO_CONTROL` | 既有 RC Style3/Action1 | — | ✅ |

## 兩類缺口

### 缺口 A — 正規 E2 路徑（delivery）
以上都是 **CU HTTP 端點,還沒上 E2 wire**。xApp 要能經 RIC/rc-probe 拿到,需決定 E2 遞送方式:

- **方案 A1（建議）：ANR Indication(ran_func=6 訂閱 → 週期推 JSON)**
  比照 FULLKPM producer:xApp 對 ran_func=6 下 RIC Subscription → sim 每 period 推一包 JSON,內含
  `{e2NodeInformation, neighbourCellRelations, relationChangeEvents, kpmIndication(perNeighbourRelation), e2MessageCopyAggregate}`。
  一條 subscribe 就覆蓋 `RC_E2NODEINFO_SUBSCRIBE` + KPM/meas 觀測。改動集中在 adapter(SUB_REQ 分流 + producer)。
- 方案 A2:實作 E2SM-RC QUERY(Style1)+ Report(Style3)—— 最貼規範但工程重(RC codec 要加 query/report)。
- 方案 A3:維持 CU HTTP,xApp 走 sidecar 拉 —— 不上 E2,最省但非「正規下發」。

> confirm 慣用式:A1 的 relationChangeEvents/version 週期推 = `RC_E2NODEINFO_SUBSCRIBE`,把 confirm 從輪詢升級為事件。

### 缺口 B — 資料忠實度(平台缺參數)
| 缺口 | 現況 | 補法(A/B/C 方法論) |
|---|---|---|
| ① HO failureCause 分類 | HandoverEvent **無 cause 欄位** → `handoverFailureCause*`(TXnRELOCprepExpiry/CellNotAvailable/RandomAccessProblem/HandoverToWrongCell)無真值 | B:HandoverEvent 加 `fail_cause` 欄位 + HO 執行時依情境標(如 target 不可用/RA 失敗) |
| ② RRC Reestablishment | 未模擬 → `reestablishmentInboundByPreviousPci`、`RRC.ConnReEstabInboundRatePerMin` 無源 | B/C:HO 失敗後補一條 reestab 事件模型,或標卷面假設留白 |
| ③ MRO 分類(HO.IntraSys.TooEarly/Late/ToWrongCell) | 無 | C:由 failureCause + 時序衍生(需 ① 先做) |

## 里程碑

- **O0**（已完成）：CU 查詢層(NodeInfo/kpm/meas/cgi_resolve/change events)。
- **O1（建議下一步）**：ANR Indication(方案 A1)—— adapter SUB_REQ(ran_func=6)分流 + producer 週期推 JSON;沿用 CU 現有查詢函式當資料源。→ xApp 正規訂閱一次拿到全部觀測。
- **O2**：資料忠實度缺口 ①(HO failureCause)—— HandoverEvent 加 cause + 落地標記。
- **O3**：缺口 ②③(reestab + MRO 分類)。

每步同步更新 `docs/api/e2_supported_commands.md`。

## 待拍板
1. E2 遞送:A1(ANR Indication,建議)/ A2(RC QUERY 正规)/ A3(維持 HTTP)?
2. 資料缺口 ①②③:這輪一起補,還是先把 O1 遞送打通、缺口之後補(先讓 xApp 拿得到現有觀測)?
