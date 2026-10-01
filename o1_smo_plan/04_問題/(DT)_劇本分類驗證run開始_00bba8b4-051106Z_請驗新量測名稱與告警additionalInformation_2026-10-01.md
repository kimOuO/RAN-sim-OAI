# (DT) 劇本分類驗證 run 開始:`00bba8b4-20261001T051106Z`;請驗新量測名稱、告警 additionalInformation、轉換器對 userLabel

- 日期:2026-10-01 05:13Z
- run:`corridor24_16_24`,seed 12,`anr_auto_add=true`,PM **60 秒**,05:10:53Z 起 1500 秒 → 約 **05:36Z** 自動停(停止時 9 CLEAR + 6 notifyMOIDeletion)
- ME 同前:e30 `gnb_208_095_000e30`/`_du1`、e31 `gnb_208_095_000e31`/`_du1`、e32 `gnb_208_095_000e32`/`_du2`
- 已通知 RIC(對 RIC 只是普通 run,gen 13;RIC 會在這段換 dt-a1-xapp 0.2.5)

## adapter 內實際代入的模板(已核對)
- PM:`fileSender localDn="SubNetwork=corridor24_16_24,ManagedElement=<me>"`;`managedElement … userLabel="runId=00bba8b4-20261001T051106Z"`;`measObjLdn="GNBDUFunction=<N>,NRCellDU=0"`
- 告警:`additionalInformation: {"scenarioId": "corridor24_16_24", "runId": "00bba8b4-20261001T051106Z"}`

## 預期的 InfluxDB `_measurement`
- `SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e30_du1,GNBDUFunction=1,NRCellDU=0`
- `SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e31_du1,GNBDUFunction=1,NRCellDU=0`
- `SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e32_du2,GNBDUFunction=2,NRCellDU=0`

## 時程
| 時刻(UTC) | 事件 |
|---|---|
| 05:12 起 | 每分鐘 PM 檔(第一份約 05:13) |
| **05:20:00** | DT 停 e31 的 facade 30 秒 → `gnb_208_095_000e31`(CU)與 `_du1` 各一筆 `notifyNewAlarm`(internalConnectionLoss,MAJOR,**帶 additionalInformation**),約 05:21 自動 `notifyClearedAlarm` |
| ~05:36 | run 自動停 |

請驗 (a)(b)(c)(d) 四項,結果放 `03_結果/`。
