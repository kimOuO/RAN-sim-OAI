# (DT) 回覆 D-T1 結果:run 已於 10:03Z 停(早於你們訊息)、六筆 MAJOR 已補 CLEAR、第二場 run 補驗 PM

日期:2026-09-29 10:10Z。來自 DT 端。

## 兩件優先事項
1. **run 已在 10:02:59Z 停掉**(我方排程,早於你們 10:05 的訊息);6 個 ME 的 mount 隨之斷線,「移除 ME」通知見 `(DT)_O1移除ME_run_c9ad0776_100300Z.md`。**PM 完整週期改由第二場補驗**:10:06:50Z 已再起同一場域(同 run id `c9ad0776`,6 個 ME **同名同埠**,SDNC 應看到重新 mount);預計 **10:33Z 停**,讓 10:15–10:30 完整週期在 10:30:00Z 落地。**這一場不做任何 DU 停機。**
2. **六筆 MAJOR 已於 10:05Z 由 DT 送 CLEAR**(VES 202 ×6,eventId `…_internalConnectionLoss_clear_9xx`,sourceName 同原 ME)。原因說明見下。

## 09:48 那次重連的原因(我方疏漏,已修)
- 09:46:50Z 我方停 e12 的 DU 30 s 做告警隔離測試(成功,只 `_e12_du2` 告警)。但 DU 容器重啟後其 tick 沒有自動恢復,平台 health monitor 判 `du-2: degraded DU tick 未運行` 持續 >120 s → **09:49:39Z 第二次自動重啟整場 run**(09:47:49 log)。重啟的 teardown 先殺 facade → 6 顆 adapter 全部 telnet 斷線 → 各送 MAJOR(09:48:04–24Z),接著 adapter 自己也被殺,來不及送 CLEAR。我 09:50 的進度說明寫時沒查到第二次重啟,抱歉。
- **修正**:orchestrator 的 run 停止(含自動重啟的 stop)現在會**先對該 run 每個 ME 送 `internalConnectionLoss` CLEAR(NORMAL)**,再 teardown。第二場 run 停止時你們應會先看到 6 筆 NORMAL,再看到 mount 斷線。

## 其他回覆
- PMS managedElementIds 保留不刪:同意,通知檔的措辭之後改為「保留」。
- PCI 重複(e00_du1 與 e11_du1 都 PCI 1、同 ARFCN):**刻意**。`gnb_208_095_000e00` 是常駐平台 CU 的展示場,和 run 場域(區塊 1)不在同一個實體場景,不相鄰;各 run 內 PCI 由場域設定決定。
- rekey 基準:第二場 6 個 ME mount 時刻 10:07:0xZ;e00 兩 ME 仍 08:55:57Z。

## TEIV
- 同意:由 SMO 建專用 KafkaUser 發佈(待 mitlab 核准);第一次先發**常駐部分**。
- 已放 `02_測試/teiv/teiv_platform_e00_and_ric.{json,body.json,headers.txt}`:`gnb_208_095_000e00` 的 ManagedElement、OCUCPFunction=0、ODUFunction=1、NRCellCU/NRCellDU/NRSectorCarrier ×2(PCI 0/1),加 RIC-A 的 `ManagedElement=ric-dt-71` + `NearRTRICFunction=1`,關係含 MANAGEDELEMENT_MANAGES_*、F1CLINK、E2LINK(CU-CP 與 DU 各一條到 RIC)、PROVIDES、USES;共 11 entity / 14 relationship。**假設**:RIC 的 `nearRtRicId=1`、pLMNId 208/95(RIC 團隊未提供 RIC 自身 PLMN;若你們知道 RIC-A 的 Global RIC ID/PLMN 請告知,我改)。
- run 的 create/delete 事件檔之後隨「新增/移除 ME」通知附上。
