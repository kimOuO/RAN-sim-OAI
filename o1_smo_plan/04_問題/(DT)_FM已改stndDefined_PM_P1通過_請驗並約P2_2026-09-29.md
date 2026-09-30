# (DT) FM 已切 stndDefined(Rel-18)且 VES 全 202;PM P1 並行驗證通過;請驗 FM 並約 P2 時間

日期:2026-09-29 12:25Z。來自 DT 端。更正:先前通知寫 11:20Z,實際動作時間如下(UTC)。

## 選用 Release:**18**,但 FM 的 schemaReference 要用 `TS28111_FaultNrm.yaml`,不是 `TS28111_FaultNotifications.yaml`
- 你們 §1.2 給的 `…/Rel-18/OpenAPI/TS28111_FaultNotifications.yaml#components/schemas/NotifyNewAlarm` 會被 VES **400**(`schemaReference value does not correspond to any external event schema file`)。原因:VES pod 內的 `TS28111_FaultNotifications.yaml`(2.6 KB)只是入口,`NotifyNewAlarm` 等 schema 定義在 **`TS28111_FaultNrm.yaml`**(也在 schema map 內)。
- 實測(對 `gnb_208_095_000e00_du1` 送合成事件):
  | schemaReference | 結果 |
  |---|---|
  | `…/Rel-18/OpenAPI/TS28111_FaultNotifications.yaml#components/schemas/NotifyNewAlarm` | 400 |
  | **`…/Rel-18/OpenAPI/TS28111_FaultNrm.yaml#components/schemas/NotifyNewAlarm` / `NotifyClearedAlarm`** | **202 / 202** ✅(採用) |
  | `…/SA88-Rel16/OpenAPI/faultMnS.yaml#components/schemas/NotifyNewAlarm` | 202(備用) |
  | `…/Rel-18/OpenAPI/TS28532_FileDataReportingMnS.yaml#components/schemas/NotifyFileReady` | **202** ✅(PM 採用) |
  | `…/SA88-Rel16/OpenAPI/PerDataFileReportMnS.yaml#components/schemas/NotifyFileReady` | 400 |
  → FM、PM 都用 Rel-18,同一 Release。

## FM 驗證(§2.2)—— 請你們對照
| UTC | ME | 事件 | VES |
|---|---|---|---|
| 12:15:42 / 12:15:55 | e00、e00_du1 | 第一次(FaultNotifications URL)raise / clear | 400 / 400(未進 Kafka,可忽略) |
| 12:17:xx | e00_du1 | 合成 `…-schematest`(Rel-16)raise → 已清除(Rel-16 clear) | 202 / 202 |
| 12:18:xx | e00_du1 | 合成 `…-r18test`(Rel-18 FaultNrm)raise → 清除 | 202 / 202 |
| **12:20:48** | **e00 與 e00_du1** | adapter 正式模板 **notifyNewAlarm**,alarmId `ManagedElement=<ME>-internalConnectionLoss`,perceivedSeverity MAJOR,alarmType COMMUNICATIONS_ALARM | **202** |
| **12:21:01–02** | **e00 與 e00_du1** | **notifyClearedAlarm**,同 alarmId,perceivedSeverity CLEARED | **202** |
請確認 `SEC_3GPP_FAULTSUPERVISION_OUTPUT` 有這些筆、SDNR 發生→清除、目前告警清單為空(含兩筆合成測試的 alarmId 也應已清)。
- 現況:e00 兩顆 adapter 已只送 stndDefined(舊 `fault` 網域停用);run 用的 `adapter-gnb:dt` 映像已內建 stndDefined FM(下一個 run 生效);orchestrator 收工 CLEAR 也改為 `notifyClearedAlarm`(Rel-18 FaultNrm,alarmId 與 adapter 相同)。**不會兩種並存。**

## PM P1(並行驗證)—— 已做
- 12:16Z 對 `e00_du1` 的真實檔 `A20260929.1214+0000-1215+0000_1_gnb_208_095_000e00_du1.xml` 補送 stndDefined `notifyFileReady`(Rel-18 TS28532_FileDataReportingMnS)→ **VES 202**;adapter 同時照常送舊式。請確認 `SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT` 收到且能被 dfc 的 TS28532 類別解析(`fileInfoList[0].fileLocation` 為 sftp URL、`fileFormat XML`、`fileCompression no`)。樣本:`02_測試/o1-adapter-dt/config/sample_stndDefined_notifyFileReady.json`。
- 注意 dfc 的 `TS28532FileReadyMessage` 是否需要 `fileInfoList[].fileLocation` 以外的欄位(例如 `fileSize`),我方都有帶。

## P2 提案
- 時間:**你們選一個 15 分整點後 1 分鐘**(例如 13:01Z 或 13:16Z)。屆時 DT 把所有 DU adapter(e00 + 之後的 run)換成 stndDefined fileReady 模板(`ves-file-ready.std.json` 已備好),你們同時改 dfc(`FILE_READY_EVENT_TOPIC=unauthenticated.SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT`、`FILE_READY_MESSAGE_CLASS=TS28532`)。
- P3:下一個整點檔 → dfc 取檔 → pmlog → InfluxDB,`e00_du1` 有 10 指標即通過(現在沒有 run 在跑,只有 e00;要驗 4 個 DU 可再起一場)。
- 回退:你們改回 dfc;DT 換回 `ves-file-ready.legacy.json`(保留)。

## TEIV 走 NCMP:收到,`make_run_teiv.sh` 保留為備援。
