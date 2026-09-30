# (DT) 轉達 RIC:修補版 vespamgr 上線,round 5 開始,請用 RESTCONF 看告警出現與消失

- 04:29:58Z vespamgr 0.7.5-mit1(ves-agent clear 修正)上線,helm rev 5;量測仍關、collector 30417、vnfName ric-dt-71。
- round 5:約 04:31Z raise `smo-ves-test-alarm-5`(72004 MINOR、sourceName ric-dt-71、新增 `alarmInterfaceA="ric-dt-71/smo-ves-test"`),30 s 後 clear;Alertmanager 約 5 分鐘後 resolved → clear 事件應帶與 raise 相同的 alarmCondition「E2 CONNECTION PROBLEM」與 specificProblem「smo-ves-test-alarm-5:round 5 clear-fix verification」,時戳為清除當下。
- 請用 RESTCONF 看:raise 後 ric-dt-71 底下出現、clear 後消失。我會在 Kafka/SDNR log 看到 clear 時補時間。
- 殘留 3 筆的 clear 腳本已交 mitlab 執行,送出後 RIC 會回時間,再請你們確認清單歸 0。

## 04:35Z 補:殘留 3 筆的 clear 已由 mitlab 於 04:30:40Z 送出(VES 202 ×3)
| sourceName | eventId | specificProblem(與原 raise 一字不差) |
|---|---|---|
| RIC | fault0000000001 | smo-ves-test-alarm-2:RIC to SMO VES verification 2026-09-30 round 2, will be cleared |
| RIC | fault0000000001 | smo-ves-test-alarm-2:…round 3 (clear residual) |
| ric-dt-71 | fault0000000002 | smo-ves-test-alarm-4:…round 4 (sourceName ric-dt-71), will be cleared |
alarmCondition 皆「E2 CONNECTION PROBLEM」、NORMAL、object-id 未填(同原 raise)。請用 RESTCONF 確認這 3 筆消失;若 SDNR 仍留著,請回是哪一筆與差在哪個欄位。
