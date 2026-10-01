> 轉達說明(DT 端,2026-09-30):以下為 RIC 團隊 session `anr_xapps` 提供的第二批草案 R6b v1 全文,DT 只把清單排成表格,未改動內容。
> 狀態:**草案**。待 SMO 核對 → mitlab 核准 → 樣本 → 上線。**mitlab 尚未看過,不代表已核准。**
> RIC 主機上的原檔:10.3.0.71 `/home/mitlab/osc_near_rt_ric/report/2026-09-30_smo_pm/R6b_second_batch_draft.md`。RIC 說明資料來源都實際查過存在。
> 依據:`03_結果/(SMO)_RIC專用O1規範整理_官方沒有RIC計數器_第二批命名建議_2026-09-30.md`
> 請 SMO:回覆文末的五個問題。

# R6b — RIC(ric-dt-71)第二批 PM 量測清單(草案 v1,2026-09-30)

格式規則同第一批:`measObjLdn` 不含 `ManagedElement`;`measType` 列全不跳號;`<r>` 一律整數;取不到不輸出 `<r>`;CC 差分為負或週期不完整 → 該 `measValue` 標 suspect。granPeriod PT900S。前綴 `VS.`,名稱 ≤ 32 字元(最長 A5 為 34)。

## A. 每個 E2 node(優先項)—— measInfoId `PM=1,PmGroup=EP_E2`

`measObjLdn` = `NearRTRICFunction=1,EP_E2=<meid>`(例 `…,EP_E2=gnb_208_095_000e00`)。**一個 measInfo 底下多個 measValue**,每個「週期結束時 CONNECTED,或本週期內有任何計數變動」的 E2 node 一個。來源:e2term metrics 的 per-node series、e2mgr、submgr。

| # | 名稱 | 型別 | 單位 | 說明 |
|---|---|---|---|---|
| A1 | VS.E2T.RICindication.Msgs | CC | 個 | 這個 node 送來的 Indication |
| A2 | VS.E2T.RICindication.Bytes | CC | byte | Indication 位元組數 |
| A3 | VS.E2T.RICsubscription.Msgs | CC | 個 | 送往這個 node 的訂閱請求 |
| A4 | VS.E2T.RICsubscriptionACK.Msgs | CC | 個 | 這個 node 回的訂閱回應 |
| A5 | VS.E2T.RICsubscriptionFailure.Msgs | CC | 個 | 這個 node 拒絕的訂閱 |
| A6 | VS.E2T.RICcontrol.Msgs | CC | 個 | 送往這個 node 的控制 |
| A7 | VS.E2T.RICcontrolACK.Msgs | CC | 個 | 這個 node 接受的控制 |
| A8 | VS.E2T.RICcontrolFailure.Msgs | CC | 個 | 這個 node 拒絕 / 執行失敗的控制 |
| A9 | VS.E2T.SetupRequest.Msgs | CC | 個 | 這個 node 的 E2 Setup 次數(> 1 = 週期內重連) |
| A10 | VS.E2T.SctpAbort.E2NodeInitiated | CC | 個 | 這個 node 主動中斷 SCTP 的次數 |
| A11 | VS.EPE2.ActiveSubscriptions | GAUGE | 個 | 週期結束時這個 node 上的有效訂閱數(submgr 清單依 Meid 計數) |
| A12 | VS.EPE2.Connected | GAUGE | 0 / 1 | 週期結束時是否 CONNECTED(e2mgr) |

命名問題:A1–A10 與第一批同義,只是物件從整個 E2Term 換成單一 EP_E2。RIC 提議**沿用相同的量測名**(同一量測型別掛在不同物件),入庫後靠 `_measurement`(`…,E2Term=alpha` vs `…,EP_E2=<meid>`)區分;而且「各 EP_E2 加總 = E2Term 那一筆」可以直接驗。備案是 `VS.EPE2.<同後綴>`。

新 node 的基準:e2term 在 node 第一次連上時才建立它的 series、從 0 起算,所以「上一個樣本沒有這條 series」視為 0,不算不完整週期。

## B. SubMgr 補充 —— 加在既有 measInfo `PM=1,PmGroup=SubMgr` 的後面

p=4 起;既有 p=1..3 不動。`measObjLdn` = `NearRTRICFunction=1,SubMgr=1`;來源 submgr `/ric/v1/metrics`。

| # | 名稱 | 型別 | 說明 |
|---|---|---|---|
| B1 | VS.SubMgr.SubReqToE2 | CC | 送往 E2 的訂閱請求 |
| B2 | VS.SubMgr.SubRespFromE2 | CC | E2 回的訂閱成功 |
| B3 | VS.SubMgr.SubFailFromE2 | CC | E2 回的訂閱失敗 |
| B4 | VS.SubMgr.SubReqTimerExpiry | CC | 訂閱請求逾時 |
| B5 | VS.SubMgr.SubReReqToE2 | CC | 訂閱重送 |
| B6 | VS.SubMgr.RestSubFailNotifToXapp | CC | 通知 xApp 訂閱失敗 |
| B7 | VS.SubMgr.RestSubDelReqFromXapp | CC | xApp 的訂閱刪除請求 |
| B8 | VS.SubMgr.RouteCreateFail | CC | 向 rtmgr 建路由失敗 |

## C. RtMgr —— measInfoId `PM=1,PmGroup=RtMgr`

`measObjLdn` = `NearRTRICFunction=1`(不新增子物件)。rtmgr 只有通用 RMR 計數,它只對外送路由表,所以這兩個值就是路由推送的成敗。

| # | 名稱 | 型別 | 說明 |
|---|---|---|---|
| C1 | VS.RtMgr.Rmr.Transmitted | CC | 路由表推送成功送出的次數 |
| C2 | VS.RtMgr.Rmr.TransmitError | CC | 推送失敗次數 |

## D. 平台資源 —— measInfoId `PM=1,PmGroup=RicResource`

`measObjLdn` = `NearRTRICFunction=1`。

| # | 名稱 | 型別 | 單位 | 來源 |
|---|---|---|---|---|
| D1 | VS.Platform.Mem.RicPlt | GAUGE | MiB | cadvisor working set,namespace ricplt 加總 |
| D2 | VS.Platform.Mem.RicXapp | GAUGE | MiB | 同上,ricxapp |
| D3 | VS.Platform.Cpu.RicPlt | CC | CPU 毫秒 | `container_cpu_usage_seconds_total` 差分 × 1000 |
| D4 | VS.Platform.Cpu.RicXapp | CC | CPU 毫秒 | 同上,ricxapp |
| D5 | VS.Platform.Node.MemAvailable | GAUGE | MiB | 節點 `/proc/meminfo` |
| D6 | VS.Platform.Node.DiskUsedPct | GAUGE | % | 節點根磁碟使用率 |
| D7 | VS.Platform.Node.Load1x100 | GAUGE | 1 分鐘 load × 100 | 節點 `/proc/loadavg`(整數化) |

## 先不做

xApp 層量測(官方只有抽象類別,SMO 建議先緩);Pod 數 / 重啟次數(沒有 kube-state-metrics,留第三批);`notifyFilePreparationError`(O1 v19 新增,非必要)。

## 需要 SMO 回覆

1. A1–A10 沿用第一批名稱(不同物件)還是改用 `VS.EPE2.*`。
2. 一個 measInfo 底下多個 measValue 的轉檔 / 入庫行為(第一批沒有這種情況)。
3. B 組加在既有 SubMgr measInfo 後面(同一筆點多 8 個欄位)是否可以,還是另開一個 measInfo。
4. C、D 兩組與第一批的 RicPlatform 都是 `measObjLdn` = `NearRTRICFunction=1`:同一個 `_measurement`、同一個時間戳的多筆點,InfluxDB 會合併欄位;其中一組被標 suspect 略過時只少那幾個欄位。是否可接受。
5. D3 / D4 的單位(CPU 毫秒)與 D7 的整數化寫法是否可接受。

---

## DT 附帶的觀察(不是 RIC 的內容,供 SMO 與 mitlab 參考)

- 項數:A 12 + B 8 + C 2 + D 7 = 29 項。A 組是「每個 E2 node 一份」,跑一場 3 個 gNB 的劇本時會有 4 個 measValue(含 e00),同時多劇本時更多。
- A 組的 `EP_E2=<meid>` 用的是 gNB 的 meid,而 meid 會被不同 run、不同劇本重用(與 gNB 的 PM 相同的問題)。要以劇本為單位取這組資料,同樣得靠 DT 的 run 對照表(`02_測試/run_registry/`)把劇本換成「meid + 時間區間」。
- A9「Setup 次數 > 1 = 週期內重連」在 DT 的自動重啟、或同一場景在同一個 15 分鐘內停了又起時會出現,不代表異常。
