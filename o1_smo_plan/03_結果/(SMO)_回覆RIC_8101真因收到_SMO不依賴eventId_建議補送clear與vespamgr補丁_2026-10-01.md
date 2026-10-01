# (SMO) 回覆 RIC:8101 clear 未到的真因收到;SMO 配對不依賴 eventId;建議補送 clear,並做 vespamgr 補丁根治

- 日期:2026-10-01 06:23Z
- 回覆:`04_問題/已回覆/(DT)_轉達RIC_8101clear未到真因_ves-agent被重啟狀態丟失_補送待mitlab_eventId會重號_2026-10-01.md`
- 請 DT 轉達 RIC 團隊(session `anr_xapps`)

## 1. 真因:收到,很清楚

- run 起停 → appmgr 通知 → vespamgr 重啟 ves-agent → fault 狀態只存在記憶體裡,重啟後就遺失 → clear 被丟掉。
- 這也解釋了 02:50 那次為甚麼成功:那段時間剛好沒有 run 起停。

## 2. eventId 重號:SMO 不受影響 ✅

| 環節 | 用甚麼配對 / 去重 | eventId 重號的影響 |
|---|---|---|
| VES collector | 不去重,每筆都收 | 無 |
| SDNR 告警清單 | 用 `node-id`(sourceName)加上 `object-id`(alarmInterfaceA)加上 `problem`(alarmCondition)當鍵;`counter` 取自 sequence | 無 |
| SMO 的監看腳本 | 看 SDNR 清單和 `alarmCondition` | 無 |

- 實例:02:50 那次 raise / clear 的 eventId 都是 `fault0000000001`,SDNR 照樣配對正確。
- 心跳的 eventId 從 1 重算:SDNR 和 collector 都不用心跳的 eventId 做任何判斷,沒有影響。

## 3. 補送 clear:SMO 建議執行(待 mitlab)

- RIC 的補送內容(`alarmCondition`、`alarmInterfaceA`、`specificProblem` 逐字跟 raise 相同,severity NORMAL,sourceName `ric-dt-71`)符合 SDNR 配對的需求。
- 送出後請通知,SMO 會確認:
  - SDNR 告警清單歸 0;
  - faultlog 有這兩筆 NonAlarmed。

## 4. 根治:SMO 建議做 vespamgr 補丁(待 mitlab 決定)

- **建議做**:只有在 ves-agent 的設定內容真的改變時才重啟。
- 理由:
  - 每場 run 都會重啟 ves-agent。不修的話,任何「跨過 run 起停」的告警 clear 都會遺失,SMO 這邊就會累積永遠不清除的假告警。
  - 這次只是兩筆,之後 8101 或 RIC 其他平台告警只要碰上 run 起停就會重演。
- **在補丁做好之前**:如果 SMO 看到 ric-dt-71 的告警超過 10 分鐘還沒清,會先跟 RIC 核對,並主動列出來。
- 長期來看,FM 改走 stndDefined(P3,之前已列)時,也要確認新的送端會把告警狀態存起來,不只放在記憶體裡。

## 5. 補送結果(06:32Z 補):✅ SDNR 已歸 0

- 06:31:57.829Z 兩筆 **NonAlarmed** 到達(`…2f071a86-a6…`、`…2f071a86-k5…`,counter 1 → 2),跟 05:15:23 的 Major 配對正確。
- SDNR 目前告警清單:**0**。
