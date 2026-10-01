# DT RAN 的 O1 介面說明(給 SMO 端)

日期:2026-09-29 建立,2026-09-30 更新。狀態:多 gNB(每場 3 個)已與 smo-master(10.3.0.204)聯調通過:註冊、CM 讀寫、PM(數值已對過)、FM、心跳、上線 / 下線 / 自動重啟的自動化。驗證紀錄在 `o1_smo_plan/03_結果/`,未完成項目在 `o1_smo_plan/01_計畫/待辦清單_O1_SMO_RIC_2026-09-30.md`。
實作:OAI o1-adapter(netopeer2 + sysrepo + 3GPP Rel-18 NRM YANG)+ DT 自製 telnet 假面;原始碼與 patch 在 `o1_smo_plan/02_測試/o1-adapter-dt/`。

## 1. Managed Element(ME)

| ME(VES `sourceName` = SDNC node-id) | 身分 | NETCONF | SFTP | 內容 |
|---|---|---|---|---|
| `<meid>` 例 `gnb_208_095_000e00` | CU-CP | `10.3.0.217:1830+2·slot` SSH | `1222+2·slot` | `GNBCUCPFunction=<cu>` → `NRCellCU=<n>`(多小區)→ `NRFreqRelation=<n>` |
| `<meid>_du<N>` 例 `gnb_208_095_000e00_du1` | DU | `1831+2·slot` | `1223+2·slot` | `GNBDUFunction=<N>` → `BWP=Downlink|Uplink`、`NRCellDU=0`、`NRSectorCarrier=0` |

- `meid` = `gnb_<mcc>_<mnc3>_<gnbid 6 hex>`,與 E2 node 名、PMS managedElementIds 相同;gNB ID = `0xe00 | slot`,22 bit(`gNBIdLength=22`)。
- 一個 gNB 兩個 ME 是 adapter 一顆只能建一種 Function 所致;A1 的 managedElementIds 只放 `<meid>`。
- 每個 ME 另有 `PerfMetricJob`(id = `ManagedElement=<me>`)與 `AlarmList=1`。
- NETCONF 帳號 `netconf`,密碼隨 pnfRegistration `additionalFields` 帶給 SDNR。
- 埠位規則(D3/D4 上線後):slot 由 `e2_identity` 決定,`slot = 16·block + index`;單機 D1 測試固定 1830/1831、1222/1223。

## 2. 註冊 / 心跳(VES → `http://10.3.0.204:30417/eventListener/v7`,HTTP,noAuth)
- 啟動即送 `pnfRegistration`(VES 7.2.1;`oamV4IpAddress=10.3.0.217`、`oamPort`、`protocol=SSH`、帳密),SDNR 自動建 mount(實測 1.2 s)。
- 每場 run 起的 ME,`pnfRegistration` 的 `additionalFields` 另帶四個欄位(2026-09-30,SMO 的 `o1-me-lifecycle-controller` 使用):

| 欄位 | 值 | 說明 |
|---|---|---|
| `scenarioId` | 例 `corridor24_16_24` | 劇本名稱 |
| `runId` | `<rid>-<啟動時間>`,例 `00bba8b4-20260930T091215Z` | 每次啟動唯一。`rid` 跟著場景,同場景重啟會相同,所以加啟動時間;自動重啟後會換新值 |
| `role` | `CU-CP` / `DU` | 節點角色 |
| `lifecycle` | `ephemeral` | 可由 SMO 自動清理。**常駐節點(e00)不帶這四個欄位**,SMO 永不自動清理 |

- pnfRegistration 其他欄位(2026-10-01 H5 起):`softwareVersion=dt-0.1`(與 PM swVersion 一致)、`lastServiceDate`=啟動日、`manufactureDate=2026-09-29`、`serialNumber=<vendor>-<unitType>-<me>`;此前為上游範本寫死值。
- `heartbeat` 每 30 s,`heartbeatInterval=30`。
- adapter 重建/重啟 → 送新 pnfRegistration,SDNC 自動重連;**running datastore 重建,SMO 經 CM 改的值回到預設**。

## 3. CM
### 3.1 讀(RESTCONF 經 SDNC mount)
list key 是完整 DN,`=` 要編碼:
```
GET http://10.3.0.204:30267/rests/data/network-topology:network-topology/topology=topology-netconf/node=<me>/yang-ext:mount/_3gpp-common-managed-element:ManagedElement=ManagedElement%3D<me>?content=nonconfig
```
主要屬性:

| 物件 | 屬性 | 來源(DT) |
|---|---|---|
| GNBCUCPFunction | gNBId、gNBIdLength=22、gNBCUName=meid、pLMNId | CU `E2/E2NodeId/read` |
| NRCellCU | cellLocalId、pLMNInfoList{mcc,mnc,sst,sd=ff:ff:ff} | CU components.cells(順位 = local cell id) |
| GNBDUFunction | gNBId、gNBIdLength=22、gNBDUId、gNBDUName | 同上 + config `gnb-du-id` |
| BWP Downlink/Uplink | numberOfRBs(=DU total_prb)、startRB 0、subCarrierSpacing 30、isInitialBwp | DU `MacCellController/read` |
| NRCellDU | nRPCI、arfcnDL/UL、bSChannelBwDL/UL(MHz)、cellLocalId、pLMNInfoList、ssb* | CU cells(pci、arfcn、bandwidth_mhz、tac、plmn) |
| NRSectorCarrier | arfcnDL/UL、bSChannelBwDL/UL(同 NRCellDU) | 同上 |
| PerfMetricJob | performanceMetrics[]、granularityPeriod、fileReportingPeriod | 預設 7 個 / 900 / 900(2026-09-30 起,見 §4) |
| AlarmList | alarmRecords[] | adapter 內建告警狀態 |

未映射(需要再加):nRTAC、administrativeState、operationalState、tx power。

### 3.2 寫(NETCONF edit-config 經 SDNC PATCH)
| 可寫 | 效果 | 驗證 |
|---|---|---|
| `PerfMetricJob/attributes/performanceMetrics` | 下一個 PM 檔即反映 | 2026-09-29 08:38:49Z SMO PATCH 1→10,15 s 內生效 |
| `NRCellDU/attributes/bSChannelBwDL` + `bSChannelBwUL`(需相等) | adapter 對 DT 下 `o1 bwconfig`;**DT 目前只記錄不改頻寬**(n_prb 全域) | 未驗 |
其餘屬性寫入會被 adapter 忽略。

## 4. PM
- **CU-CP ME 的 PM(2026-10-01 G9 起)**:每個 CU-CP ME 每週期一個檔,`measInfoId="PM=1,PmGroup=NRCellCU"`,每 cell 一個 `measObjLdn="GNBCUCPFunction=0,NRCellCU=<cellLocalId>"`;計數器(每週期增量,TS 28.552):`RRC.ReEstabAtt`、`RRC.ReEstabSuccWithUeContext`、`RRC.ReEstabSuccWithoutUeContext`、`DRB.RelActNbr.5QI9`;來源 CU 的 RlfEvent / DRB 釋放(自 run 起累計,adapter 取與前一週期末的差)。SMO 入庫名稱 `SubNetwork=<scn>,ManagedElement=<cu me>,GNBCUCPFunction=0,NRCellCU=<lc>`。
- **檔名(2026-10-01 H2 起)**:`A<YYYYMMDD>.<HHMM>+0000-<HHMM>+0000_-1_<me>.xml`(TS 32.432 5.1.2:`_-<jobId>` + `_<UniqueId>`,jobId=1);此前為 `…_1_<me>.xml`。
- **`DRB.UEThpDl` / `DRB.UEThpUl`**:內部以實數計算、輸出四捨五入整數 kbit/s(2026-10-01 H6:SMO 決定 (b),因 InfluxDB 同 shard 已為 integer,送小數會整筆被拒;整數為合法 real 值;N5 pmlog 改 float 後再協調改送小數)。
- 檔案:TS 32.435 `measCollecFile` XML,900 s 一份,對齊 :00/:15/:30/:45;檔名 `A<yyyymmdd>.<hhmm>+0000-<hhmm>+0000_1_<me>.xml`;放在 ME 的 SFTP `/ftp/`(剛好一層目錄),保留 24 h。
- 通知:VES `stndDefined`,`stndDefinedNamespace=3GPP-PerformanceAssurance`,`schemaReference=https://forge.3gpp.org/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28532_FileDataReportingMnS.yaml#components/schemas/NotifyFileReady`;`fileInfoList[0].fileLocation=sftp://netconf:<pw>@10.3.0.217:<sftp port>/ftp/<檔名>`。SMO 的 dfc 從這個 URL 取得帳密並來拉檔(認證方式選項 a,2026-09-30 mitlab 決定;通知通道加密列為後續工作)。
- **劇本分類(2026-10-01 起,下個 run 生效)**:`fileSender localDn` 與 `managedElement localDn` = `SubNetwork=<scenarioId>,ManagedElement=<me>`(`dnPrefix` 仍為 `SubNetwork=DT`;TS 32.435 DN = dnPrefix + localDn,SubNetwork 可巢狀);`managedElement userLabel` = `runId=<runId>`;常駐節點不加 SubNetwork 層、userLabel = `permanent`。
- `measObjLdn` = `GNBDUFunction=<N>,NRCellDU=0`(相對 ME,照 32.435 範例)。SMO 入庫 `_measurement` = `<fileSender localDn>,<measObjLdn>` → `SubNetwork=<scenarioId>,ManagedElement=<me>,GNBDUFunction=<N>,NRCellDU=0`;按劇本查用此前綴,按 run 查用 run 對照表。2026-10-01 以前的資料名稱為 `ManagedElement=<me>,ManagedElement=<me>,GNBDUFunction=<N>,NRCellDU=0`(ME 重複一次)。
- 量測(DU ME,預設 7 個):

| 名稱 | 意義 | 計算 |
|---|---|---|
| `DRB.MeanActiveUeDl` / `Ul` | 平均 UE 數 | 週期內每秒取樣的平均,**整數、無條件捨去**(上游 o1-adapter 的整數除法);Ul 與 Dl 同值 |
| `DRB.MaxActiveUeDl` / `Ul` | 最大 UE 數 | 週期內取樣的最大值;Ul 與 Dl 同值 |
| `DRB.UEThpDl` / `Ul` | 該 cell 所有 UE 吞吐合計(kbit/s) | 每秒取樣的週期平均 |
| `RRU.PrbTotDl` | 已配置 PRB 佔該 cell 總 PRB 的百分比 | 每秒取樣的週期平均,0–100 |

- 資料來源:CU 的 `E2/E2FullReporter/read`(與送給 RIC 的 FullKPM 同一份)的 `e2[].cells[].ues[]`,以 PCI 對應 cell;UE 數 = 清單長度,吞吐 = `dl_throughput` / `ul_throughput`(Mbps × 1000),PRB = `rb_width` 合計 ÷ 該 cell 總 PRB。telnet 假面轉成 OAI `o1 stats` 格式,o1-adapter 每秒取樣。
- `DRB.UeUnresVolDl/Ul`、`DRB.RlcPacketDropRateDl` 沒有資料來源(恆為 0),2026-09-30 起預設不上報;仍列在 SupportedPerfMetricGroups,經 CM 寫入可選回(值為 0)。
- 不完整週期(run 起始、結尾)的 `measValue` 帶 `<suspect>true</suspect>`,SMO 的入庫程式會略過,不進 InfluxDB。
- CU-CP ME 不產 PM 檔(上游 o1-adapter 的 CU-CP 型態沒有 PM)。
- SMO 端落地:dfc → MinIO `ropfiles` → xml2json → pmlog → InfluxDB2 `pm-logg-bucket`(org est);`_field` = 量測名稱,時間 = 通知的 `lastEpochMicrosec`。
- 對值方法與結果:`o1_smo_plan/02_測試/pm_v1/pm_v1_compare.py`;2026-09-30 三個完整週期 XML 與 InfluxDB 逐值相同。

## 5. FM(VES `stndDefined`,`3GPP-FaultSupervision`)
`schemaReference` = `…/Rel-18/OpenAPI/TS28111_FaultNrm.yaml#components/schemas/NotifyNewAlarm` / `NotifyClearedAlarm`。`sourceName` = ME。

| 告警 | alarmId | 觸發 | 嚴重度 | 清除 |
|---|---|---|---|---|
| `internalConnectionLoss` | `ManagedElement=<me>-internalConnectionLoss` | adapter 與 DT 假面 telnet 斷線 3 s(DU / CU 的 HTTP 不可達時假面會主動關閉對應身分的 telnet) | MAJOR | 恢復連線,或 run 收工時由編排服務清 |
| `loadDownlinkExceededWarning` | `ManagedElement=<me>,GNBDUFunction=<N>,NRCellDU=0-loadDownlinkExceededWarning` | DL 負載 > 50 % 持續 15 s | WARNING | 低於門檻,或 run 收工時由編排服務清 |

`alarmType`:internalConnectionLoss = COMMUNICATIONS_ALARM、loadDownlinkExceededWarning = QUALITY_OF_SERVICE_ALARM(2026-10-01 H4 前為 EQUIPMENT_ALARM)。`probableCause`(2026-10-01 H4 起,28.111 Annex B):COMMUNICATIONS_SUBSYSTEM_FAILURE / THRESHOLD_CROSSED;`specificProblem` 仍為告警名稱。`notifyNewAlarm.additionalInformation` = {scenarioId, runId}。

同一告警的 raise 與 clear 不可同毫秒。DT 的 RLF / 換手失敗 / PCI 混淆尚未映射為告警。

## 6. 生命週期(2026-09-30 定案,SMO 端由 `o1-me-lifecycle-controller` 自動處理)
- **上線**:編排服務每個 gNB 起 1 個 telnet 假面 + 2 個 o1-adapter(CU-CP / DU)→ `pnfRegistration`(帶 §2 的四個欄位)→ SDNR 自動 mount → SMO 的控制器自動註冊 NCMP、登記 PMS 歸屬、建 TEIV 的 E2 / F1 連線關係。DT 不需要通知 SMO。
- **正常收工**(順序固定):
  1. 停該 run 的全部 o1-adapter(NETCONF 隨之關閉)。
  2. 每個 gNB 送 3 筆 `notifyClearedAlarm`:CU ME 與 DU ME 的 `internalConnectionLoss`、DU ME 的 `loadDownlinkExceededWarning`(不論當下是否發生中;對不存在的告警送 CLEAR 在 SMO 端無副作用)。
  3. 隔 1 秒,每個 ME 送 1 筆 `notifyMOIDeletion`:`stndDefinedNamespace=3GPP-Provisioning`,`schemaReference=…/Rel-18/OpenAPI/TS28532_ProvMnS.yaml#components/schemas/NotifyMoiDeletion`,`data.href` / `systemDN` = `ManagedElement=<me>`,`data.attributeList.runId`(必帶,與註冊時相同)、`scenarioId`。**必須是該 ME 在這個 run 的最後一筆事件。**
  4. 停其餘容器。
  SMO 的控制器收到 `notifyMOIDeletion` 後自動刪連線關係、NCMP 登記、mount、PMS 歸屬(實測 6–42 秒)。
- **自動重啟**(run 連續 120 s 不健康):走同一個停止流程但**不送 `notifyMOIDeletion`**(停止請求帶 `reason=auto_restart`);ME 以相同名稱、新的 `runId` 重新註冊,SMO 只更新屬性不清理。實測 o1-adapter 離線約 62 秒。
- **備援**:沒有 `notifyMOIDeletion` 也沒有重新註冊時,SMO 在 mount 斷線 10 分鐘後清理(尚未實測)。
- 編排服務中途重啟:收工時的 topo、`runId`、`scenarioId` 從容器資訊重建(`runId` 讀 o1-adapter 容器的 `O1_RUN_ID`)。
- 實作:`run_lifecycle/services/optional/o1_spawner.py`;掛點在 `launch_request_actor.py`(啟動後 spawn、teardown 前 on_stop)與 `health_monitor.py`(`reason=auto_restart`)。
- 通知檔(`run_logs/<rid>/o1/notify_*.md`)仍會產生,只供對照時間,SMO 不依賴。連線關係檔(`gen_teiv_links.py`)SMO 已能從 O1 推導,是否停產待決定。

## 7. 已知限制
- adapter 重啟重設 CM 改動(見 §2)。
- NRCellCU 不帶 PCI/ARFCN(3GPP 放在 NRCellDU)。
- `bwconfig` 只記錄;TAC、admin/operational state 未映射。
- 心跳 SMO 端目前無 consumer。
- 多 DU、多 cell(2026-10-01 起支援):每個 DU 一個 ME `<meid>_du<gNB-DU ID>`(第 k 個 DU 的 NETCONF / SFTP / telnet 埠 = 第 0 個 + 1024·k);每個 cell 一個 `NRCellDU=<cellLocalId>` 與 `NRSectorCarrier=<i>`;PM 檔每個 cell 一個 measValue;負載告警每個 cell 一筆。上限每 DU 8 個 cell。
- SMO 端的資料沒有劇本層:PM、告警只帶 ME 名稱,而 ME 名稱會被不同 run 重用;按劇本收資料目前只能用「ME 名稱 + 時間區間」對應。
- 通知通道是明文 HTTP、不認證(O1 規範要求 HTTP/TLS 雙向憑證);帶帳密的 `fileLocation` 以明文傳送。
- 同時多個劇本未實測。

## 8. 補充:送端規則(2026-09-30)
- FM / PM 通知都走 VES `stndDefined`(見 §4、§5);舊的 `fault` / `notification` 網域停用。
- `fileLocation` 維持單層 `/ftp/<檔名>`;dfc 以 MinIO 同名檔去重(7 天),補送前需請 SMO 刪檔;補送時 header 的 start/lastEpochMicrosec 填週期起訖。
- suspect 旗標改為視窗對齊判斷(patch 0007)。
- TEIV:拓樸本體由 SMO 的 ncmp-to-teiv-adapter 從 O1 產生;DT 只提供 E2LINK / F1CLINK(`o1_smo_plan/02_測試/teiv/gen_teiv_links.py`,delete 每條一檔)。
