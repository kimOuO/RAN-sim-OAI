# (DT) FM 改 stndDefined:驗證通知(Release 18)

- 時間:2026-09-29 約 11:20Z 起。ME:`gnb_208_095_000e00` 與 `gnb_208_095_000e00_du1`(觸發方式是停 facade 10 s,兩個 ME 會同時發;若你們只要 du1,忽略 CU-CP 那筆即可)。
- 選用 **Rel-18**:FM `…/Rel-18/OpenAPI/TS28111_FaultNotifications.yaml#components/schemas/NotifyNewAlarm` / `NotifyClearedAlarm`;PM 之後用 `…/Rel-18/OpenAPI/TS28532_FileDataReportingMnS.yaml#components/schemas/NotifyFileReady`。
- 事件:`domain stndDefined`、`stndDefinedNamespace 3GPP-FaultSupervision`、`eventName stndDefined_3GPP-FaultSupervision_NotifyNewAlarm|NotifyClearedAlarm`;data:notifyNewAlarm / notifyClearedAlarm、`alarmId = ManagedElement=<ME>-internalConnectionLoss`(發生與清除相同)、alarmType COMMUNICATIONS_ALARM、perceivedSeverity MAJOR / CLEARED、systemDN `ManagedElement=<ME>`。
- 目前只有 e00 兩顆 adapter 換新模板(舊 `fault` 網域已停);run 用的映像與 orchestrator 收工 CLEAR 等你們驗過再切,避免兩種並存。
- PM P1(並行驗證)緊接著做:對 `e00_du1` 已存在的 PM 檔補送一筆 stndDefined `notifyFileReady`(adapter 仍照常送舊式),請看 `SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT`。
