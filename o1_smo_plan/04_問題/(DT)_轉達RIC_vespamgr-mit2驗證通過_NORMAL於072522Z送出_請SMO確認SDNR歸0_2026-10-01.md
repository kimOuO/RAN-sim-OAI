# (DT) 轉達 RIC:vespamgr mit2「跨 run 起停的 clear」驗證通過 —— 07:25:22Z ves-agent 送出 NORMAL;請 SMO 確認收到與 SDNR 歸 0

- 日期:2026-10-01 07:30Z
- 時序:07:03:45 起場通知 ×2「config unchanged」→ 07:07:17 RAISE 72004(fault0000000001 seq 1)→ 07:19:12 run D 停 → 07:20:01 收場通知 ×2「config unchanged」→ 07:20:47 CLEAR → **07:25:22 NORMAL 送出**(CLEAR 後 4 分 35 秒,≤ 6 分鐘內);ves-agent 全程同一行程。
- NORMAL 內容:eventId fault0000000001 sequence 2、sourceName ric-dt-71、alarmCondition / specificProblem 與 raise 相同。
- 對照 05:15 那次:ves-agent 被重啟 →「fault name not present in storage」→ 無 NORMAL。
- RIC 今天三個平台修正(rtmgr 0.9.7-mit5、dt-a1-xapp 0.2.5、vespamgr 0.7.5-mit2)皆已上線並驗證。
- 請 SMO 確認 collector 收到 NORMAL 的時間、SDNR 清單歸 0,結果放 `03_結果/`。
