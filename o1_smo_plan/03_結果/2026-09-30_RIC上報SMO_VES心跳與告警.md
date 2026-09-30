# 結果:RIC-A 上報 SMO(VES 心跳 / 告警)—— DT 端協調紀錄

日期:2026-09-30 02:51–03:33Z。執行:RIC 團隊(mitlab 核准);DT 端負責轉達與 SMO 側唯讀驗證。
- 02:51Z vespamgr 指向 SMO VES(sourceName ric-dt-71)。發現:vespamgr 0.7.x 讀 `/cfg/config-file.json` 而非 env;alarmmanager 原廠指向不存在的 `cpro-alertmanager`;alarm-go 把告警 system_name 寫死 "RIC"(fault 的 sourceName 因此為 RIC,需改 alarm-go 重建映像)。
- 事故:vespamgr 每 30 s 的 measurement 讓 SMO VES collector log 每 30 s 漲 130 MB,pod 反覆被 evict(02:54、03:02)。03:06:54Z RIC 縮到 0;SMO 03:21Z 做 P0 防護(log INFO、16 MB×3);03:25:58Z vespamgr 帶「量測關閉」起回。
- 驗證:心跳 sourceName=ric-dt-71 到達(SMO 確認);measurement 曾到達(topic +50 KB/90 s)後停止;告警 round 2(02:58Z)與 round 3(03:26 raise / 03:32 clear)皆到 SDNR,但 node-id 為 "RIC";清單歸 0 待 SMO 確認。
- 後續:alarmmanager 升級(ric-dt-71)再驗一輪;P1 檔案式 PM(R1–R6)待 mitlab 直接對 RIC 核准。

## 03:52Z 補:round 3 / round 4 完成
- round 3(sourceName RIC):03:26:42 raise、03:32:42 clear,皆到 SDNR。
- 03:42:20Z alarmmanager 0.5.17-mit1(`ALARM_SYSTEM_NAME=ric-dt-71`,mitlab 核准)上線;round 4:03:42:44 raise、03:51:44 clear,**sourceName ric-dt-71**,皆到 SDNR。
- 待 SMO 回 RESTCONF 清單歸 0 → §2 RIC 端結案。R6 量測清單 v1(20 項)已交 SMO 徵詢。

## 04:15Z SMO 驗證:node-id 正確,但 clear 未生效(清單 3 筆殘留)
- SDNR 以 node-id + object-id + problem(alarmCondition)識別;RIC 的 clear 事件 alarmCondition 為空、時間戳沿用 raise、object-id null → 三筆 raise 仍在清單。RIC 需修 vespamgr AlertToFault 的 resolved 分支,補送 3 筆同字串 clear,再測一輪。已轉達。
- R6:SMO 建議核准(來源不限 Prometheus),附實作注意 A–E;第二批優先每 E2 node Indication。待 mitlab 核准。

## 04:40Z:round 5(vespamgr 0.7.5-mit1 修補版)通過
- 根因(ONAP-VESPA converter.go resolved 分支 alarmCondition/specificProblem 取不到、時戳沿用 raise、無 object-id)由 RIC 修補;04:29:58Z 上線。
- round 5:04:31:45 raise / 04:37:45 clear,欄位一致(alarmCondition、specificProblem、alarmInterfaceA ric-dt-71/smo-ves-test),clear 時戳為清除當下。04:30:40Z mitlab 送的 3 筆殘留 clear 亦被 SDNR 處理。
- 待 SMO RESTCONF 確認清單 0 → §2 結案。

## 04:40Z SMO 結案:§2 RIC 上報 SMO 通過
- RESTCONF:3 筆殘留 NonAlarmed;round 5 raise Minor(object-id ric-dt-71/smo-ves-test)→ NonAlarmed;**清單 0**。心跳、告警、量測關閉、VES 防護皆 ✅。
- 後續:P1 等 mitlab 核准 R6;P3 FM 改 stndDefined 之後排。
