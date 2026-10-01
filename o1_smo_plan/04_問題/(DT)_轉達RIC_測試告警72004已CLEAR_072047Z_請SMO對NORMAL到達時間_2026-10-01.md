# (DT) 轉達 RIC:測試告警 72004 已於 07:20:47Z CLEAR;請 SMO 對 NORMAL 到達時間(預期 07:25:47–07:26:50Z)

- 日期:2026-10-01 07:24Z
- vespamgr 0.7.5-mit2 行為:run D 起場通知 07:03:45Z ×2、收場通知 07:20:01Z ×2,日誌皆「ves-agent config unchanged, keeping ves-agent running」;ves-agent 自 07:03:41Z 起同一行程未重啟。
- **CLEAR 72004 `smo-ves-test-alarm-6`:07:20:47Z**(alarmmanager 200)。
- 預期 NORMAL 於 **07:25:47–07:26:50Z** 到 SMO(Alertmanager resolve_timeout 5 分鐘 + ves-agent 輪詢 ≤ 60 秒),eventId fault0000000001、sourceName ric-dt-71、alarmCondition / specificProblem 與 raise 相同。
- 請 SMO 確認:collector 收到 NORMAL 的時間、SDNR 歸 0。這就是「跨 run 起停的 clear 能送到」的驗收點;通過則今天 05:37 那類遺失不會再發生。
