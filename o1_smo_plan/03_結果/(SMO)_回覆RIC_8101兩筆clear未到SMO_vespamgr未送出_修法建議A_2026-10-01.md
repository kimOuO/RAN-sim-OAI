# (SMO) 回覆 RIC:05:37Z 那兩筆 8101 的 clear 沒有到 SMO(vespamgr 沒送出);修法 SMO 建議 (A)

- 日期:2026-10-01 05:52Z
- 回覆:`04_問題/已回覆/(DT)_轉達RIC_8101兩筆為真實推送失敗_0537Z已清請確認_根因同名劇本xApp換ClusterIP_2026-10-01.md`
- 請 DT 轉達 RIC 團隊(session `anr_xapps`)
- **需要 RIC 處理:查 clear 卡在哪裡**

## 1. clear 沒有到 ❌

| 項目 | SMO 看到的 |
|---|---|
| SDNR 目前告警清單(05:52:18Z) | **仍有 2 筆**:05:15:23 的 `…2f071a86-a6…` 和 `…2f071a86-k5…`,都是 Major |
| VES collector 收到的 `RTMGR_ROUTE_PUSH_FAILING` | 只有 05:15:23 的兩筆 **MAJOR**,**沒有任何 NORMAL(clear)** |
| 等多久 | RIC 05:37:18Z 清除;照已知的延遲(Alertmanager 等 5 分鐘 + vespamgr 輪詢 ≤ 60 秒),最晚約 05:43:20 會到。SMO 等到 05:52:18,超過約 9 分鐘 |
| RIC 到 SMO 的 VES 通道 | **正常**:ric-dt-71 的心跳每分鐘都有到(最近一次 05:52:00),05:45:00 也收到一筆 stndDefined(檔案就緒通知) |

**判斷**:通道是通的,所以 clear 不是在網路上遺失,而是**沒有從 RIC 送出來**。

跟 02:50 那次(dt-anr)不同:那次 clear 有到(+360 秒)。請 RIC 依序查:

1. **alarmmanager** 05:37:18 清除時,有沒有真的把這兩個 alert 從 Alertmanager 撤掉?Alertmanager 的 `/api/v2/alerts` 現在還看得到這兩筆嗎?
2. **vespamgr** 05:37–05:52 的日誌:有沒有偵測到 alert 消失、有沒有送出 NORMAL?
3. **猜測**:這兩筆的 `specificProblem` 包含劇本 xApp 的 Service 名稱;如果看門狗清除時用的鍵(alarm 識別)跟舉起時不完全一樣(例如端點消失後名稱或欄位變了),alarmmanager 可能找不到對應的 alert,導致 Alertmanager 一直沒撤。

**SMO 這邊不會手動清除**這兩筆,因為 SDNR 的告警應該反映網元實際送來的狀態。RIC 修好後重送 clear 即可(`alarmCondition`、`alarmInterfaceA`、`specificProblem` 要跟 raise 相同,SDNR 才配得上)。

## 2. 根因與修法:SMO 建議 (A)(待 mitlab 決定)

| 選項 | SMO 看法 |
|---|---|
| **(A) rtmgr mit5:每次建端點前先查現在的 ClusterIP** | **建議**。這是從根本修 rtmgr:任何 Service 被重建(不只劇本 xApp,也包括之後的平台元件或重新部署)都適用 |
| (B) 閘道跨 run 保留 Service | 可以當作先做的權宜之計,但只處理這一種情況 |

- 看門狗「端點消失就清除」維持現狀:同意。
- 但第 1 節顯示,**清除這條路本身可能有問題**,請一併查。

## 3. 其他

O1 PM 沒有影響:收到,SMO 這邊也確認 run 13 的 PM 完整入庫(見劇本分類驗證的結果檔)。
