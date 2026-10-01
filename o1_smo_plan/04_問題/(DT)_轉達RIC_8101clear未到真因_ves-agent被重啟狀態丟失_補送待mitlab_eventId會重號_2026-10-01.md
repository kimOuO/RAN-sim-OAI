# (DT) 轉達 RIC:8101 clear 未到的真因 —— ves-agent 在 clear 前被重啟、fault 狀態丟失;補送 clear 待 mitlab 執行;eventId 會重號請注意

- 日期:2026-10-01 06:28Z;回覆 `03_結果/(SMO)_回覆RIC_8101兩筆clear未到SMO_…_2026-10-01.md`

## 1. 逐項查證
1. alarmmanager 05:37:18Z 的 clear 有效,Alertmanager `/api/v2/alerts` 現為 0 筆。
2. Alertmanager 05:42:23Z(resolve_timeout 後)有推 resolved 給 vespamgr,但 ves-agent 回「clearFault: fault name not present in storage」→ 沒送 NORMAL。
3. 鍵一致,不是鍵的問題。**真因:05:37:07Z run 收場時 appmgr 發 xApp 通知 → vespamgr 收到即重產設定並重啟 ves-agent(原廠行為)→ ves-agent 的 fault 狀態只在記憶體 → 重啟後不認得這兩筆 fault。** 今天 appmgr 通知 11 次、ves-agent 重啟 10 次(每場 run 起 / 停都會)。02:50 那次 clear 能到是因為 02:52–02:56 之間剛好沒有 run 起停。

## 2. 對 SMO 的副作用(請注意)
ves-agent 每次重啟後 heartbeat 與 fault 的 `eventId` 序號從 1 重算(05:38 起 `heartbeat0000000001` 又出現;下一筆 fault 會再是 `fault0000000001`)。**SMO 若用 eventId 去重會撞**,請確認 SDNR / collector 的配對不依賴 eventId(先前 SMO 說用 alarmCondition + alarmInterfaceA 配對,應無影響)。

## 3. 補送 clear
RIC 已備好腳本(兩筆 NORMAL,sourceName ric-dt-71,eventId fault0000000001 / 0000000002,sequence 2,alarmCondition / alarmInterfaceA / specificProblem 與 raise 逐字相同),**等 mitlab 在 RIC 側執行**;送出後 RIC 通知,請 SMO 確認 SDNR 歸 0。

## 4. 根治(待 mitlab 決定)
vespamgr 補丁:xApp 通知後只在 ves-agent 設定內容有變才重啟(RIC 的量測已關閉 → 設定不變 → 不再重啟,fault 狀態與序號保住)。需重建 vespamgr 映像 + helm。
