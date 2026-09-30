# R6 — RIC(ric-dt-71)第一批 PM 量測清單(草案 v1,2026-09-30)—— RIC 團隊原文,DT 端原樣轉載

granPeriod PT900S;fileSender localDn `ManagedElement=ric-dt-71`;命名 TS 32.404 廠商前綴 `VS.`;CC = 週期內累計增量(counter 差分),GAUGE = 週期結束時瞬時值。
來源代號:P = Prometheus(r4-infrastructure-prometheus-server,e2term metric family E2TAlpha);X = 元件自己的 /ric/v1/metrics(submgr/rtmgr 目前沒被 Prometheus 抓,agent 直接 scrape,或選配加 prometheus.io 註解);R = 元件 REST API(agent 讀 JSON 算 gauge)。

## measInfo 1 E2Term(measObjLdn `ManagedElement=ric-dt-71,NearRTRICFunction=1,E2Term=alpha`)
| # | measType | 型別 | 單位 | 來源 | 意義 |
|---|---|---|---|---|---|
| 1 | VS.E2T.SetupRequest.Msgs | CC | 個 | P E2TAlpha{POD_NAME="e2term",SetupRequest="Messages"} | 收到的 E2 Setup Request(gNB 連線/重連次數) |
| 2 | VS.E2T.SetupResponse.Msgs | CC | 個 | P E2TAlpha{SetupResponse="Messages"} | 送出的 Setup Response(成功接受連線) |
| 3 | VS.E2T.SetupRequestFailure.Msgs | CC | 個 | P E2TAlpha{SetupRequestFailure="Messages"} | Setup 失敗回應 |
| 4 | VS.E2T.RICsubscription.Msgs | CC | 個 | P E2TAlpha{RICsubscription="Messages"} | 送往 gNB 的 RIC Subscription Request |
| 5 | VS.E2T.RICsubscriptionACK.Msgs | CC | 個 | P E2TAlpha{RICsubscriptionACK="Messages"} | gNB 回的 Subscription Response |
| 6 | VS.E2T.RICsubscriptionFailure.Msgs | CC | 個 | P E2TAlpha{RICsubscriptionFailure="Messages"} | gNB 拒絕的訂閱 |
| 7 | VS.E2T.RICindication.Msgs | CC | 個 | P E2TAlpha{RICindication="Messages"} | 收到的 RIC Indication(KPM/ANR 資料流量) |
| 8 | VS.E2T.RICindication.Bytes | CC | byte | P E2TAlpha{RICindication="Bytes"} | Indication 位元組數(E2 資料量) |
| 9 | VS.E2T.RICcontrol.Msgs | CC | 個 | P E2TAlpha{RICcontrol="Messages"} | 送出的 RIC Control Request(閉環動作次數) |
| 10 | VS.E2T.RICcontrolACK.Msgs | CC | 個 | P E2TAlpha{RICcontrolACK="Messages"} | gNB 接受的控制 |
| 11 | VS.E2T.RICcontrolFailure.Msgs | CC | 個 | P E2TAlpha{RICcontrolFailure="Messages"} | gNB 拒絕的控制(含 3-1 換手失敗新格式) |
| 12 | VS.E2T.ErrorIndication.Msgs | CC | 個 | P E2TAlpha{ErrorIndication="Messages"} | E2 Error Indication |
| 13 | VS.E2T.SctpAbortByE2Node | CC | 個 | P sum(E2TAlpha{counter="SctpAbortInitiatedByE2Node"})(NODEB 維度加總) | gNB 端主動中斷 SCTP 次數(RAN adapter 抖動指標) |
| 14 | VS.E2T.InvalidMessageReceived | CC | 個 | P sum(E2TAlpha{counter="InvalidMessageReceived"}) | 解不開的 E2 訊息 |

## measInfo 2 SubMgr(measObjLdn `…,NearRTRICFunction=1,SubMgr=1`)
| # | measType | 型別 | 單位 | 來源 | 意義 |
|---|---|---|---|---|---|
| 15 | VS.SubMgr.ActiveSubscriptions | GAUGE | 個 | R GET submgr:8088/ric/v1/subscriptions 筆數 | 週期末有效訂閱數(常駐 3 + 每場景 node×3) |
| 16 | VS.SubMgr.RestSubReqFromXapp | CC | 個 | X SUBMGR_RestSubReqFromXapp | xApp 送來的訂閱請求 |
| 17 | VS.SubMgr.RestSubFailToXapp | CC | 個 | X SUBMGR_RestSubFailToXapp | 回給 xApp 的訂閱失敗(含路由/E2 逾時) |

## measInfo 3 E2Mgr / A1 / 平台(measObjLdn `…,NearRTRICFunction=1`)
| # | measType | 型別 | 單位 | 來源 | 意義 |
|---|---|---|---|---|---|
| 18 | VS.E2Mgr.ConnectedNodes | GAUGE | 個 | R GET e2mgr:3800/v1/nodeb/states 中 CONNECTED 數 | 週期末連著的 E2 node(常駐 e00 + 場景 node) |
| 19 | VS.A1.PolicyInstances | GAUGE | 個 | R GET a1mediator:10000/A1-P/v2/policytypes 展開各 type 的 policies 總數 | A1 policy instance 數(目前 0;A1 閉環上線後有意義) |
| 20 | VS.RIC.Alarms.Active | GAUGE | 個 | R GET alarmmanager:8080/ric/v1/alarms/active 筆數 | 週期末未清的 RIC 告警數 |

備註:E2TAlpha 每訊息型有 Messages/Bytes,同 label 下多條 series,agent 取 sum();Bytes 只列 Indication。Prometheus 目前只抓 e2term;submgr/rtmgr/alarmmanager/o1mediator 的 /ric/v1/metrics 活著但沒被抓,第一批 agent 直接 scrape,SMO 要全走 Prometheus 可加 Service 註解(不重啟元件)。xApp(python ricxappframe)無 Prometheus 端點,xApp 層計數第二批再議。不列 gNB KPM(DT 由 O1 直送 SMO)。第二批候選:rtmgr 路由推送成功/失敗、每 node Indication(measObjLdn 加 E2Node=<meid>)、平台 pod CPU/記憶體。待 mitlab 確認名稱/分組/取捨。
