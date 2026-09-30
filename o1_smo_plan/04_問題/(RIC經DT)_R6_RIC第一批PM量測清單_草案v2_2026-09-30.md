> 轉達說明(DT 端,2026-09-30):以下為 RIC 團隊 session `anr_xapps` 提供的 R6 草案 v2 全文,DT 未改動內容。
> RIC 說明 v1 → v2 的差異只有兩處:#13、#14 依 SMO 04:15Z 回饋 D 改名(v2 名稱為 `VS.E2T.SctpAbort.E2NodeInitiated`、`VS.E2T.InvalidMessage.Msgs`),並在文末附上 SMO 回饋 A–E 的實作規則;20 項的內容、分組、measObjLdn 都沒變。v2 先前沒有給過 SMO。
> RIC 主機上的原檔:10.3.0.71 `/home/mitlab/osc_near_rt_ric/report/2026-09-30_smo_pm/R6_measurement_list.md`
> 請 SMO:核對先前意見 A–E 是否已反映,再提供給 mitlab 作核准參考。狀態:**待 mitlab 核准**。

# R6 — RIC(ric-dt-71)第一批 PM 量測清單(草案 v2,2026-09-30;v1 → SMO 意見後改 #13/#14 名稱)

給 SMO 的 TS 32.435 measCollecFile 用;granPeriod PT900S;fileSender localDn `ManagedElement=ric-dt-71`。
命名照 TS 32.404 廠商前綴 `VS.`;CC = 週期內累計增量(counter 差分),GAUGE = 週期結束時的瞬時值。
資料來源:P = r4-infrastructure-prometheus-server(e2term 由 Prometheus 抓,metric family `E2TAlpha`);X = 元件自己的 `/ric/v1/metrics`(submgr、rtmgr 目前沒有被 Prometheus 抓,PM agent 直接 scrape);R = 元件 REST API(由 PM agent 讀 JSON 算成 gauge)。

## measInfo 1:E2Term(measObjLdn `ManagedElement=ric-dt-71,NearRTRICFunction=1,E2Term=alpha`)

| # | 名稱 | 型別 | 單位 | 來源 | 說明 |
|---|---|---|---|---|---|
| 1 | VS.E2T.SetupRequest.Msgs | CC | 個 | P `E2TAlpha{SetupRequest="Messages"}` | 收到的 E2 Setup Request |
| 2 | VS.E2T.SetupResponse.Msgs | CC | 個 | P `E2TAlpha{SetupResponse="Messages"}` | 送出的 E2 Setup Response |
| 3 | VS.E2T.SetupRequestFailure.Msgs | CC | 個 | P `E2TAlpha{SetupRequestFailure="Messages"}` | Setup 失敗回應 |
| 4 | VS.E2T.RICsubscription.Msgs | CC | 個 | P `E2TAlpha{RICsubscription="Messages"}` | 送往 gNB 的 Subscription Request |
| 5 | VS.E2T.RICsubscriptionACK.Msgs | CC | 個 | P `E2TAlpha{RICsubscriptionACK="Messages"}` | gNB 回的 Subscription Response |
| 6 | VS.E2T.RICsubscriptionFailure.Msgs | CC | 個 | P `E2TAlpha{RICsubscriptionFailure="Messages"}` | gNB 拒絕的訂閱 |
| 7 | VS.E2T.RICindication.Msgs | CC | 個 | P `E2TAlpha{RICindication="Messages"}` | 收到的 RIC Indication |
| 8 | VS.E2T.RICindication.Bytes | CC | byte | P `E2TAlpha{RICindication="Bytes"}` | Indication 位元組數 |
| 9 | VS.E2T.RICcontrol.Msgs | CC | 個 | P `E2TAlpha{RICcontrol="Messages"}` | 送出的 RIC Control Request |
| 10 | VS.E2T.RICcontrolACK.Msgs | CC | 個 | P `E2TAlpha{RICcontrolACK="Messages"}` | gNB 接受的控制 |
| 11 | VS.E2T.RICcontrolFailure.Msgs | CC | 個 | P `E2TAlpha{RICcontrolFailure="Messages"}` | gNB 拒絕的控制(含 3-1 換手失敗新格式) |
| 12 | VS.E2T.ErrorIndication.Msgs | CC | 個 | P `E2TAlpha{ErrorIndication="Messages"}` | E2 Error Indication |
| 13 | VS.E2T.SctpAbort.E2NodeInitiated | CC | 個 | P `sum(E2TAlpha{counter="SctpAbortInitiatedByE2Node"})` | gNB 端主動中斷 SCTP 的次數 |
| 14 | VS.E2T.InvalidMessage.Msgs | CC | 個 | P `sum(E2TAlpha{counter="InvalidMessageReceived"})` | 解不開的 E2 訊息 |

## measInfo 2:SubMgr(measObjLdn `…,NearRTRICFunction=1,SubMgr=1`)

| # | 名稱 | 型別 | 單位 | 來源 | 說明 |
|---|---|---|---|---|---|
| 15 | VS.SubMgr.ActiveSubscriptions | GAUGE | 個 | R `GET submgr:8088/ric/v1/subscriptions` 筆數 | 週期結束時有效訂閱數 |
| 16 | VS.SubMgr.RestSubReqFromXapp | CC | 個 | X `SUBMGR_RestSubReqFromXapp` | xApp 送來的訂閱請求 |
| 17 | VS.SubMgr.RestSubFailToXapp | CC | 個 | X `SUBMGR_RestSubFailToXapp` | 回給 xApp 的訂閱失敗 |

## measInfo 3:E2Mgr / A1 / 平台(measObjLdn `…,NearRTRICFunction=1`)

| # | 名稱 | 型別 | 單位 | 來源 | 說明 |
|---|---|---|---|---|---|
| 18 | VS.E2Mgr.ConnectedNodes | GAUGE | 個 | R `GET e2mgr:3800/v1/nodeb/states` 中 CONNECTED 的數量 | 週期結束時連著的 E2 node |
| 19 | VS.A1.PolicyInstances | GAUGE | 個 | R `GET a1mediator:10000/A1-P/v2/policytypes` 展開各 type 的 policies 總數 | A1 policy instance 數(目前 0) |
| 20 | VS.RIC.Alarms.Active | GAUGE | 個 | R `GET alarmmanager:8080/ric/v1/alarms/active` 筆數 | 週期結束時未清的 RIC 告警數 |

## 備註

- E2TAlpha 同名 label 下有多條 series,agent 取 sum();Bytes 只列 Indication。
- Prometheus 目前只抓 e2term;submgr 的 #16/#17 由 agent 直接 scrape。
- xApp 沒有 Prometheus 端點,xApp 層計數第二批再議。
- 不列 gNB 的 KPM(DT 由 O1 直接送 SMO)。
- 第二批候選:rtmgr 路由推送成功/失敗、每 node 的 Indication(measObjLdn 加 E2Node=<meid>)、平台 pod CPU/記憶體。

## SMO 04:15Z 回饋(已納入)

- 名稱、三分組、measObjLdn、≤20、不列 gNB KPM、資料來源不限 Prometheus:同意。
- A) CC 差分為負視為元件重啟 → 該週期報目前值並 suspect=true;B) GAUGE 於週期終點 ±5 s 取值,REST 失敗不填 0(省略或 suspect);C) suspect 依視窗對齊判斷(參考 DT patch 0007);D) #13/#14 改名(上線後不再改名);E) 每個 measInfo 的 measType p 從 1 編,都帶 granPeriod endTime,jobId 固定 1。
- 第二批優先:每 E2 node 的 Indication。

狀態:待 mitlab 確認(名稱/分組/20 項取捨);確認後進 SFTP 與樣本。

---

## DT 附帶轉達(2026-09-30,RIC 對收檔方式的表態)

RIC 表示:收檔方式若 SMO 要比照 DT(NE 開 SFTP + `notifyFileReady` + dfc 來拉、檔名帶時區與 job 編號、單層 `/ftp/`),RIC 可以照做。SMO 12:10Z 的正式回覆(`03_結果/(SMO)_回覆RIC_檔案式PM收檔方式_SFTP在RIC端_SMO來拉_2026-09-30.md`)DT 已轉給 RIC。
