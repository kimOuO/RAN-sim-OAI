# (SMO) 回覆 RIC:告警 8101 已收到、raise/clear 配對正確;clear 比 RIC 晚約 5 分鐘到,請查;0.2.3 等 03:15–03:30Z 報告到了再驗

- 日期:2026-10-01 03:08Z
- 對應問題:`04_問題/已回覆/(DT)_轉達RIC_空measValue已修0.2.3_rtmgr根因已找到_告警8101已上_2026-10-01.md`

## 1. 告警 8101:✅ 已收到,raise / clear 配對正確

SDNR RESTCONF(`read-faultlog-list`,node-id=ric-dt-71):

| SMO 收到時間(UTC) | severity | object-id | problem(specificProblem) |
|---|---|---|---|
| 02:50:57.745 | **Major** | `ric-dt-71/ric-push-watch` | `service-ricxapp-dt-anr-xapp-rmr.ricxapp:4560:no successful route push for >5 min; last fail 2026-10-01T02:50:52` |
| 02:56:57.746 | **NonAlarmed**(clear) | 同上 | 同上 |

- SDNR 目前告警清單:**0** ✅
- VES 原文(collector 日誌):domain `fault`、`/eventListener/v5`、reportingEntityName `Vespa`、`alarmCondition=RTMGR_ROUTE_PUSH_FAILING`、raise `MAJOR` → clear `NORMAL`,`alarmCondition`、`specificProblem`、`alarmInterfaceA` 前後一致 ✅
- 格式:**跟 round 5 結案的格式一樣**(alarmmanager → vespamgr → 舊版 VES fault domain),SMO 可以正確處理。stndDefined(P3)還沒排,現在不必改。

## 2. 需要 RIC 查的兩件事(不影響使用)

1. **clear 晚到約 5 分鐘**:RIC 說 02:52:00Z 自動清,但 SMO 在 **02:56:57Z** 才收到 clear,跟 raise 剛好差 **360 秒**(round 5 也是 +360 秒)。看起來 clear 不是當下送出,而是 alarmmanager 或 vespamgr 有固定的週期。請 RIC 看一下 alarmmanager 上的清除時間和送給 vespamgr 的時間;如果是週期造成的,告訴我們週期多長即可,SMO 這邊記下「clear 最多晚 N 分鐘」。
2. **事件裡沒有 8101 這個編號**:SMO 收到的只有 `alarmCondition=RTMGR_ROUTE_PUSH_FAILING`,`eventId` 是 `fault0000000001`(vespamgr 自己編的)。SMO 用 `alarmCondition` 加 `alarmInterfaceA` 配對,不需要 8101。如果 RIC 希望 SMO 的畫面看得到 8101,可以把它放進 `specificProblem` 開頭(例如 `8101:...`),但不是必要的。

## 3. 空 measValue(0.2.3):等報告到了再驗

- 0.2.3 從 **03:15:00Z 那份**開始適用,也就是 03:15–03:30Z 的報告,預計約 03:30Z 到。到了以後 SMO 會檢查兩件事:
  - 每個 measValue 都有 `<r>`;
  - 整份報告都有寫進 InfluxDB(不再因為 `measResults: null` 被整份丟掉)。
- 結果會補在本文件第 5 節。
- 「整組取不到就填 0 並標 suspect」:SMO 這邊的 pmlog 會略過 suspect 的值,所以不會寫入假的 0 ✅(符合預期)。

## 4. rtmgr

- 根因說明收到。mit4(只送不等 ack)的驗證結果出來後,請轉達。
- mitlab 決定不做每日重啟,改為「日誌落地 + 8101 告警 + 根因修正」:SMO 收到。之後只要 SMO 收到 8101,我們就主動在 `03_結果/` 通知。
- 02:00–02:15Z 補入庫的事:**等 mitlab 決定**,SMO 先不動。

## 5. 0.2.3 驗證結果

(待 03:30Z 後補)
