# (DT) 轉達 RIC(04:30Z):clear 事件根因、修補、殘留 3 筆處理、R6 改名

- **根因**(ONAP-VESPA v0.3.0 `converter.go` resolved 分支):alarmCondition 只讀 annotation `clearAlertName`、specificProblem 只讀 `clearDescription`,alarm-go 不提供 → clear 兩欄為空;時戳沿用 raise 的 start;object-id 未填;所有告警共用同一內部 fault 名(label id / annotation service 皆空)。
- **修補**(自建 vespamgr 0.7.5-mit1,patch `/home/mitlab/ric-lab/platform/patches/vespamgr/0002-*`,建置中,需 mitlab 跑 helm 換版):clear 沿用 raise 的 alertname 與 description;fault 名改 alarm_id + service;`alarmInterfaceA = "<managedObjectId>/<applicationId>"`(供 SDNR object-id);clear 的 start/last = 清除當下。
- **殘留 3 筆**:RIC session 不對 SMO collector 直接寫入(權限),已把 3 筆 clear(node-id / alarmCondition「E2 CONNECTION PROBLEM」/ specificProblem 與原 raise 一字不差 / NORMAL)寫成腳本交 **mitlab 執行**,送出後會給時間;請屆時確認清單歸 0。之後以新版 vespamgr 做 round 5 raise/clear。
- **R6**:意見 A–E 全收;#13/#14 改名 `VS.E2T.SctpAbort.E2NodeInitiated` / `VS.E2T.InvalidMessage.Msgs`;等 mitlab 核准後進 SFTP 與樣本。
