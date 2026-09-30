# 結果:FM —— 斷線告警 MAJOR 與 CLEAR 送達 SMO

日期:2026-09-29 08:32–08:40Z。執行:DT 端。結論:**通過**(VES 202 ×4);SMO 端消費情況待其回報。

## 做法
不停 DT 平台的 DU(避免影響 E2 與 RIC),改停 `o1-d1-facade`:兩顆 adapter 的 telnet 斷線 → 內建告警 `internalConnectionLoss`;再啟動 facade → 清除。

## 時間線(UTC)
| 時間 | 事件 | 結果 |
|---|---|---|
| 08:32:36 | 第一次停 facade | 08:32:46 adapter `telnet disconnected` → 08:32:50 送告警 **VES 回 400** |
| 08:33–08:37 | 原因:內建 `ves-new-alarm.json` / `ves-clear-alarm.json` 是 **stndDefined 3GPP-FaultSupervision** 格式,這台 VES 對 stndDefined 做 externalSchema 檢查會拒(與 fileReady 同一類問題)。換成**標準 VES `fault` 網域**(faultFields 4.0:alarmCondition、eventSeverity、eventSourceType、specificProblem、vfStatus),clear 版 eventSeverity 固定 `NORMAL`;compose 補 mount 兩個模板;重建 adapter | |
| 08:37:49 | 啟動 facade(讓 adapter 先進入「已連線」狀態;adapter 在啟動時連不上不會發告警,只有「連線後斷線」才發) | `telnet connected` |
| 08:39:04 | 停 facade | 08:39:18 兩個 ME 各送 `internalConnectionLoss` **MAJOR** → VES **202** |
| 08:39:24 | 啟動 facade | 08:39:29 兩個 ME 各送 `internalConnectionLoss` **NORMAL**(清除)→ VES **202** |

## 更正
- 內建連線告警嚴重度是 **MAJOR**(`alarms.c` `ALARM_SEVERITY_MAJOR`),之前文件寫 MINOR 有誤(README 的表是舊版)。
- 通知檔寫「約 08:52Z 開始」有誤,實際 08:32Z(本機時鐘估算錯)。

## 待 SMO 端
- `unauthenticated.SEC_FAULT_OUTPUT` 應有 4 筆(sourceName `gnb_208_095_000e00`、`gnb_208_095_000e00_du1` 各 MAJOR + NORMAL);SDNR fault 處理與 ODLUX Fault 頁。

## SMO 端佐證(我方唯讀查到)
- `unauthenticated.SEC_FAULT_OUTPUT` 由 0 bytes → 4459 bytes。
- onap-sdnc-0 log 出現 4 行 `Fault VES Message is - …eventId ManagedElement=gnb_208_095_000e00_internalConnectionLoss_1 / _du1_internalConnectionLoss_1 / _2 / _2`,即 SDNR 已處理 MAJOR×2 + NORMAL×2。**FM 端到端通過**;ODLUX 呈現待 SMO 端回報。
