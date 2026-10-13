# (DT) 轉達 RIC:dt-a1-xapp 0.2.7(每 60 秒向 a1mediator 對帳)16:29:02Z 上線;對 SMO / PMS 無影響

- 日期:2026-10-01 16:36Z
- 0.2.7:每 60 秒送 20012 查詢,漏掉的 20010 一分鐘內由 a1mediator 重送補回;同一份 policy 重送不重下控制、仍回 20011 現況。16:30:18Z 起 a1mediator 每分鐘收到一次 A1_POLICY_QUERY(SMO 會在 a1mediator 日誌看到,PMS 不受影響)。
- 「換 pod 後第一筆 20010 遺失 → 一分鐘內補回」尚未活體驗證,下次有 policy 時順帶驗(RIC 不自建測試 policy,免得 PMS 看到不認得的 instance)。
- 現役 RIC 版本:rtmgr 0.9.7-mit5、vespamgr 0.7.5-mit2、dt-preproc 0.1.8、dt-a1-xapp 0.2.7。
- C19 在 DT 待辦改為「已上線,待活體驗證」。
