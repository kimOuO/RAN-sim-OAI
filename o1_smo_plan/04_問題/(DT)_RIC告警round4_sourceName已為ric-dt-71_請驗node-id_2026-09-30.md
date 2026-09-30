# (DT) RIC 測試告警 round 4:sourceName 已是 ric-dt-71,請驗 SDNR node-id 與清單

日期:2026-09-30 03:48Z。來自 DT 端。
- 03:42:20Z RIC 上線 alarmmanager 0.5.17-mit1(`ALARM_SYSTEM_NAME=ric-dt-71`,mitlab 核准);03:42:39Z raise `smo-ves-test-alarm-4`(72004 MINOR)。
- **03:42:44Z SDNR 收到 `fault0000000002`,sourceName `ric-dt-71`、MINOR**;`SEC_FAULT_OUTPUT` 2224 → 3036。
- 請確認:(1) 這筆掛在 **node-id=ric-dt-71** 下;(2) round 3 之後清單曾歸 0(02:58、03:26 兩筆 RIC 的都已清);(3) RIC clear 後(約 5 分鐘內)清單再歸 0。我會在 clear 落地時補上時間。
- R6 量測清單全文已原樣放在 `(RIC經DT)_R6_RIC第一批PM量測清單_草案v1_2026-09-30.md`,請給意見(名稱/分組/取捨、是否要求全走 Prometheus)。

## 03:52Z 更新:round 4 clear 已到
- 03:51:44Z SDNR 收到 `fault0000000002`、sourceName `ric-dt-71`、**NORMAL**。請確認 ric-dt-71 底下告警清單歸 0,並回一句;RIC 端等這個回覆就把 §2(心跳/告警 sourceName=ric-dt-71、量測關閉)結案。
