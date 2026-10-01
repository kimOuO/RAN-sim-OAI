> 轉達說明(DT 端,2026-09-30):RIC 團隊 session `anr_xapps` 的第二批草案 **R6b v2**。RIC 只傳來 v2 相對 v1 的改動,DT 把它併進 v1 全文而成;A1–A10、B1–B8、C1–C2 的名稱 / 型別 / 來源與 v1 完全相同。
> 狀態:SMO 已核對(五題皆可、三處修改已納入)。**待 mitlab 核准(名稱凍結)→ 樣本 → 上線。mitlab 尚未核准。**
> RIC 主機上的原檔:10.3.0.71 `/home/mitlab/osc_near_rt_ric/report/2026-09-30_smo_pm/R6b_second_batch_draft.md`(v1 另存為 `R6b_second_batch_draft_v1.md`)。若與本檔有出入,以 RIC 的原檔為準。
> v1 → v2 的改動:A11、A12 改名;D 組補單位與算法;命名說明改寫;文末補 SMO 回覆摘要。

# R6b — RIC(ric-dt-71)第二批 PM 量測清單(草案 v2,2026-09-30;v1 → SMO 17:00Z 核對後改 A11 / A12 名稱、D 組補單位與算法)

格式規則同第一批:`measObjLdn` 不含 `ManagedElement`;`measType` 列全不跳號;`<r>` 一律整數;取不到不輸出 `<r>`;CC 差分為負或週期不完整 → 該 `measValue` 標 suspect。granPeriod PT900S。前綴 `VS.`,名稱 ≤ 64 字元、盡量 ≤ 32(最長 A5 為 34)。

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
| A11 | VS.SubMgr.ActiveSubscriptions | GAUGE | 個 | 週期結束時這個 node 上的有效訂閱數(submgr 訂閱清單依 Meid 計數)。與第一批 #15 同名,物件不同;各 node 加總 = #15 |
| A12 | VS.E2Mgr.Connected | GAUGE | 0 / 1 | 週期結束時這個 node 是否 CONNECTED(e2mgr connectionStatus;1 = 是)。與第一批的 `VS.E2Mgr.ConnectedNodes` 是不同的量 |

命名說明:A1–A11 沿用第一批相同的量測名,只是物件換成 `NearRTRICFunction=1,EP_E2=<meid>`;前綴 = 資料來源的元件(E2T / SubMgr / E2Mgr)。**查詢時一定要指定 `_measurement`**,只用欄位名加總會把 E2Term 那筆與各 EP_E2 重複算。可驗:各 EP_E2 的 A1–A10 加總 = 第一批 E2Term 那一筆、A11 加總 = 第一批 #15。

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

`measObjLdn` = `NearRTRICFunction=1`。T = 週期終點;所有值都是整數。

| # | 名稱 | 型別 | 單位 | 算法 |
|---|---|---|---|---|
| D1 | VS.Platform.Mem.RicPlt | GAUGE | MiB(2^20 bytes) | Prometheus `sum(container_memory_working_set_bytes{namespace="ricplt",container!=""})` 在 T 的值 ÷ 1048576,四捨五入 |
| D2 | VS.Platform.Mem.RicXapp | GAUGE | MiB | 同 D1,`namespace="ricxapp"` |
| D3 | VS.Platform.Cpu.RicPlt | CC | CPU 毫秒 | `sum(container_cpu_usage_seconds_total{namespace="ricplt",container!=""})` 在 T 的值 − 在 T−900 的值,× 1000 四捨五入;900000 = 平均用滿 1 顆核心;差分為負(容器重建)→ 該 measValue 標 suspect |
| D4 | VS.Platform.Cpu.RicXapp | CC | CPU 毫秒 | 同 D3,`namespace="ricxapp"` |
| D5 | VS.Platform.Node.MemAvailable | GAUGE | MiB | 節點 `/proc/meminfo` 的 MemAvailable(kB)÷ 1024,取整 |
| D6 | VS.Platform.Node.DiskUsedPct | GAUGE | %(0–100) | 節點根檔案系統(總量 − 可用)÷ 總量 × 100,四捨五入 |
| D7 | VS.Platform.Node.Load1x100 | GAUGE | 無單位 | 節點 `/proc/loadavg` 第一欄(1 分鐘平均負載)× 100 取整;例 0.27 → 27;節點 12 核,1200 = 滿載 |

備註:D1–D4 經 Prometheus(cadvisor,scrape 間隔 1 分鐘),取「T 當下最近一次 scrape」的值,與邊界最多差 60 秒;D3 / D4 兩端用同樣的取法,差分視窗仍是 900 秒。D5–D7 是主機的量,RIC 目前單節點;之後若多節點改成每節點一筆,屆時再議。C、D 與第一批 RicPlatform 同一個 `measObjLdn`,三組之間量測名稱不可重複,本清單已檢查沒有重複。

## 先不做

xApp 層量測(官方只有抽象類別,SMO 建議先緩);Pod 數 / 重啟次數(沒有 kube-state-metrics,留第三批);`notifyFilePreparationError`(O1 v19 新增,非必要)。

## SMO 17:00Z 的核對(已納入)

- 五題皆可:A1–A10 沿用第一批名稱;一個 measInfo 多個 measValue 支援(每個 measValue 一筆點,suspect 以 measValue 為單位);B 組加在既有 SubMgr measInfo 後面可以;C、D 與第一批平台組共用 `measObjLdn` 可以(三組名稱不可重複);D3 / D4 / D7 的單位與整數化可以。
- 三處修改:A11 → `VS.SubMgr.ActiveSubscriptions`;A12 → `VS.E2Mgr.Connected`;D 組明列單位與算法。
- 補充:O1 NRM v05 有 RIC 物件的正式 YANG(`o-ran-o1-NearRTRIC`、`o-ran-o1-EPE2`);Near-RT RIC Architecture v08 要求 RIC 平台能經 O1 上報個別 xApp 的 PM → xApp 層量測列入之後的批次。

## 下一步(RIC)

SMO 整理給 mitlab 核准 → RIC 實作(agent 新增:一個 measInfo 多個 measValue、per-node 取樣、Prometheus 與 /proc 來源)→ 提供一個有 run 在跑的完整週期樣本 → 上線後驗各 EP_E2 加總 = E2Term 那一筆。mitlab 核准前 RIC 只做不影響線上的準備,不改正在跑的 agent 輸出。
