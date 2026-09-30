# (DT) RIC 測試告警 round 3:raise 與 clear 都已到 SMO,請確認 SDNR 目前告警清單歸 0

日期:2026-09-30 03:35Z。來自 DT 端(唯讀查 SDNC log 與 Redpanda topic 大小)。

| UTC | 事件 | SDNR log |
|---|---|---|
| 03:25:58 | vespamgr 起回來(helm r4-vespamgr rev 4:metrics rules 0、pltCounterFile 不存在、Prometheus 位址無效 → 不再有 measurement;心跳/告警照送) | — |
| 03:26:42 | round 3 raise:`fault0000000001`、sourceName **RIC**、MINOR | 已處理 |
| 03:32:42 | round 3 clear:同 eventId、sourceName **RIC**、**NORMAL** | 已處理 |
- `SEC_FAULT_OUTPUT` 783 → 1566 → 2224 bytes(共 3 筆);`VES_MEASUREMENT_OUTPUT` 停在 520,800 不再增長;VES 新 pod(`f79fb9d47`)穩定。
- 請確認:(1) SDNR 目前告警清單歸 0(02:58 與 03:26 兩筆 sourceName=RIC 的都清掉);(2) VES log 不再暴增。
- 下一步:清單歸 0 後,mitlab 跑 alarmmanager 升級(alarm-go system_name 改讀 env → ric-dt-71),RIC 再 raise/clear 一輪,SMO 確認 node-id=ric-dt-71。
