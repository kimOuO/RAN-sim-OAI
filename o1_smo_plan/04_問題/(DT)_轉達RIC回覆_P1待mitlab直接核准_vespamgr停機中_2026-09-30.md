# (DT) 轉達 RIC 團隊回覆(03:40Z)

- P1(R1–R6)需求已收到並記下;RIC 團隊會**直接向 mitlab 確認核准與順序**後才開工(跨 session 轉達不視為核准),確認後先交 R6 量測清單。
- 現況:vespamgr 自 03:06:54Z 停機,等 mitlab 跑 helm upgrade 套用「量測關閉」設定;**期間 ric-dt-71 的心跳與告警暫停**,`SEC_HEARTBEAT_OUTPUT` 沒有 ric-dt-71 是預期。
- 起回來後順序:先用舊 alarmmanager(sourceName=RIC)raise + clear 一輪清掉 SDNR 上那筆殘留 → 再換 alarm-go 新版對 ric-dt-71 raise/clear。完成會通知,我再轉。
