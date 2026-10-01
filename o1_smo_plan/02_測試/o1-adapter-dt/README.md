# o1-adapter-dt —— 我方對 OAI o1-adapter 的設定與改動

- `config/`:從 `../o1-adapter/docker/config/` 複製,只改 `config.json`;之後 fileReady 與 PM XML 模板換版也放這裡。
- `docker-compose.d0.yml`:D0 本機驗證(adapter + 官方假 gNB,VES 關)。`docker compose -f docker-compose.d0.yml up -d`。
- 驗證:`ssh -p 1830 netconf@10.3.0.217`(密碼 netconf!)出現 NETCONF hello;或 `docker exec o1-d0-adapter netopeer2-cli`。

## 已知修正(2026-09-29,D0)
- `Dockerfile.dt`:官方映像少開 YANG feature `MeasurementsUnderManagedElement`,adapter 寫 PerfMetricJob 會失敗;此薄層補開。compose 用 `adapter-gnb:dt`。
- `config/config.json`:必須有 `info.granularityPeriod` / `info.fileReportingPeriod`(>0,用 900),模板路徑用 `/adapter/config/...`;`unit-type` 要與 telnet 端 JSON 對應(官方假體是 CU-CP)。
- 結果紀錄:`../../03_結果/2026-09-29_D0_o1-adapter本機驗證.md`。

## D1(2026-09-29):telnet 假面 + 兩顆 adapter
- `facade/facade.py`:單一行程兩個埠。9091 = CU-CP 身分(`o1-config.NRCELLCU[]` 多小區 + device),9092 = DU 身分(BWP / NRCELLDU / O1-Operational)。資料來源 CU `E2/E2NodeId/read`、`E2/E2FullReporter/read`、DU `MacCellController/read`;0.8 s 快取。`stop/start_modem` 對 DU `MacCellController/disable|enable`;`bwconfig` 只記錄。
- `docker-compose.d1.yml`:facade host network;adapter-cucp 1830/1222、adapter-du 1831/1223(bridge + 映射,因 netopeer2 固定 830、sshd 固定 22)。
- ME:`gnb_208_095_000e00`(CU-CP)與 `gnb_208_095_000e00_du1`(DU)—— adapter 一顆只能建一種 Function,所以一個 gNB 兩個 ME。
- `patches/0001-cucp-plmn-and-celllocalid.patch`:上游 bug —— GNBCUCPFunction.pLMNId 寫死 001/01、NRCellCU.cellLocalId 永遠取第 0 筆。已套在 `../o1-adapter/src`,rebuild 後生效。
- 踩坑:DU 的 `nrcelldu3gpp:cellLocalId` 要字串;DU `device.gnbId` 會被填到 GNBDUFunction.gNBId,要給 gNB ID 不是 DU ID。

## D2(2026-09-29):PM 模板換版
- `config/ves-file-ready.json`:舊式 notification 網域(dfc 預設格式);`config/pmData-measData.xml`:TS 32.435 measCollecFile。原版另存 `*.orig.*`。
- `patches/0002-pm-file-location-bare-filename.patch`:`pm_data.c` 的 `file_location` 改純檔名(dfc 用 `name` 當 S3 物件名,不能有斜線);模板 location 自己補 `/ftp/`。
- 模板是啟動時讀、且要 bind mount 進 `/adapter/config/`(compose 已含)。
- 重建順序:`docker build … Dockerfile.adapter`(套 `../o1-adapter/src` 內已打的 patch)→ `docker build -f Dockerfile.dt`(開 YANG feature)→ `docker compose -f docker-compose.d1.yml up -d --force-recreate adapter-cucp adapter-du`。
- 結果:`../../03_結果/2026-09-29_D2_PM鏈路_fileReady到InfluxDB.md`。
- `patches/0003-nrm-ids-case-and-sectorcarrier.patch`(2026-09-29,依 SMO 端 §3.4 意見):子物件 id 改 3GPP 大小寫 `NRCellCU=<n>` / `NRCellDU=0`;NRSectorCarrier id 去空白並補 `NRSectorCarrier=0`;NRSectorCarrier 的 arfcnDL/UL、bSChannelBwDL/UL 改用 NRCELLDU 的值(原本 0 / 寫死 60)。
- RESTCONF 讀樹的正確路徑(list key 是完整 DN):`.../node=<me>/yang-ext:mount/_3gpp-common-managed-element:ManagedElement=ManagedElement%3D<me>?content=nonconfig`。
- FM(2026-09-29):`config/ves-new-alarm.json` / `ves-clear-alarm.json` 改成標準 VES `fault` 網域(原 stndDefined 版另存 `*.orig.json`,會被這台 VES 400);連線告警實際嚴重度 MAJOR,clear 用 NORMAL。觸發方式:停/啟 `o1-d1-facade`(adapter 只在「連線後斷線」才發告警,啟動時連不上不發)。結果:`../../03_結果/2026-09-29_FM_斷線告警MAJOR與CLEAR.md`。
- `patches/0004-full-dn-cu-and-bwp.patch`(2026-09-29,依 SMO 端建議):NRCellCU / NRFreqRelation id 補齊 `GNBCUCPFunction=<cu>` 層;BWP id 由 `Downlink`/`Uplink` 改為完整 DN `ManagedElement=<me>,GNBDUFunction=<du>,BWP=Downlink|Uplink`。
- `patches/0005-default-10-metrics-and-unres-alias.patch`(2026-09-29):PerfMetricJob 預設 10 個量測(名稱同 SupportedPerfMetricGroups);`DRB.UeUnresVolDl/Ul` 別名(上游大小寫不一致致輸出 -1)。**注意:adapter 重啟會重建 running datastore,SMO 經 CM 改的量測清單會回到預設。**
- PM 週期已切 900 s(`config.*.json` 的 `pm-data-interval` / `granularityPeriod` / `fileReportingPeriod`)。聯調要看快一點就改 60 並 recreate。
- `patches/0006-gnbidlength-22.patch`(2026-09-29):GNBCUCPFunction / GNBDUFunction 的 gNBIdLength 32 → 22(與 E2 一致)。
- facade(2026-09-29):DU / CU 的 HTTP 不可達時,關閉對應身分的 telnet 埠與現有 session,讓 adapter 觸發 `internalConnectionLoss`;只停 ransim-du 時只有 `_du1` 告警。
- 接口文件:`/home/mitlab/XAPP_DT/docs/api/o1_interface.md`(D5)。
- facade watchdog(2026-09-29 09:45Z):後端不可達時**關閉 listener**(不是接受後關),否則 adapter 會把「接受即關」當成連線成功而清告警。`o1-telnet-facade:dt` 已重建;run 內 facade 需重建容器才會換新映像。
- 平台注意:per-run DU 停超過 120 s 會觸發 orchestrator 自動重啟整場 run(含 O1 容器)。
- 2026-09-29 12:25Z:FM 模板改 stndDefined Rel-18(`TS28111_FaultNrm.yaml`,**不是** FaultNotifications);舊 fault 版另存 `*.fault.json`。PM 的 `ves-file-ready.std.json`(Rel-18 TS28532_FileDataReportingMnS)備好,P2 切換時 `cp` 成 `ves-file-ready.json` 並重建映像/recreate;回退用 `ves-file-ready.legacy.json`。
- `patches/0007-pm-suspect-window-aligned.patch`(2026-09-29):上游以「首末取樣差 < 週期」判 suspect,1 s 輪詢相位會把完整週期誤標 true;改為視窗對齊(首筆距起點、末筆距終點 ≤5 s)。
- `patches/0012-cucp-pm-nrcellcu-counters.patch`(2026-10-01 G9):CU-CP ME 也送 PM(NRCellCU 的 RRC 重建 / 異常釋放計數器,每週期增量);PerfMetricJob 預設與 SupportedPerfMetricGroups 依節點型別。
- `patches/0011-multi-cell-per-du.patch` + `0011b`(2026-10-01):NRCELLDU 可為陣列(每 DU 最多 8 cell),`NRCellDU=<cellLocalId>`、每 cell 一個 NRSectorCarrier、PM 每 cell 一個 measValue、負載告警每 cell 一筆、狀態逐 cell;facade `DU_PORTS="<port>:<gnb_du_id>:<url>,..."` 多 DU 身分;編排服務每 DU 一個 adapter。
- 劇本分類(2026-10-01):`config/pmData-measData.xml` 的 `@dn-scn@` / `@run-label@`、`config/ves-new-alarm.json` 的 `@scn-id@` / `@run-id@` 由 `dt-entrypoint.sh` 依 `O1_SCENARIO_ID` / `O1_RUN_ID` 代入(無 `O1_LIFECYCLE` → 常駐,標 permanent);measObjLdn 改為相對 ME。
