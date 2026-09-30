# 結果:FM / PM 通知改 O-RAN O1 規範格式(VES stndDefined + 3GPP,Rel-18)

日期:2026-09-29 12:14–12:25Z。背景:SMO 端(mitlab 核准)要求改走官方格式。
- **FM 通過**:adapter 模板改 `domain stndDefined` / `3GPP-FaultSupervision`,schemaReference **`…/Rel-18/OpenAPI/TS28111_FaultNrm.yaml#components/schemas/NotifyNewAlarm|NotifyClearedAlarm`**。12:20:48Z raise、12:21:01Z clear,e00 與 e00_du1 皆 VES 202;alarmId 發生/清除相同(`ManagedElement=<ME>-internalConnectionLoss`)。
- 坑:SMO 給的 `TS28111_FaultNotifications.yaml` 只是入口檔,schema 在 `TS28111_FaultNrm.yaml`;用前者 VES 回 400「schemaReference value does not correspond to any external event schema file」。Rel-16 `faultMnS.yaml` 也可(備用);Rel-16 `PerDataFileReportMnS.yaml` 反而 400。
- **PM P1 通過**:合成 stndDefined `notifyFileReady`(Rel-18 TS28532_FileDataReportingMnS)對真實檔 → 202;adapter 仍送舊式。P2 待與 SMO 約時間(DT 換 `ves-file-ready.std.json`,SMO 改 dfc topic 與 message class)。
- 已生效:e00 兩顆 adapter(bind 模板)、`adapter-gnb:dt` 映像(下一 run)、orchestrator on_stop 的 CLEAR(stndDefined,alarmId 同 adapter)。舊 `fault` 網域模板保留為 `ves-*-alarm.fault.json`。
- TEIV:SMO 改走 NCMP → ncmp-to-teiv-adapter 自動產生;`make_run_teiv.sh` 保留備援。

## 12:40Z SMO 驗證
- FM 通過:Kafka 8 筆、SDNR Major→NonAlarmed、alarmId 一致。SMO 更正其文件(FaultNrm 才對)。
- 遺留:合成 `…-r18test` 的 raise/clear 同毫秒送出,SDNR 先處理 clear → 停在 Major;12:45Z 已補一筆 clear(202)。教訓:同一 alarm 的 raise/clear 不可同毫秒。
- PM P1 通過:結構、型別、檔名解析(`/ftp/<檔名>` 單層)皆符合 dfc `TS28532FileReadyMessage`。
- P2 暫定 13:16Z,待 mitlab 確認、SMO 放「P2 確認」後 DT 才切;P3 看 13:30Z 檔。
