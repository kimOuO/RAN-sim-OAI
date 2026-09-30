# (DT) 轉達 RIC:notifyFileReady 已打開,第一筆在 15:15:00Z

- 日期:2026-09-30 15:13Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`03_結果/(SMO)_RIC樣本檢查通過_可以打開notifyFileReady_2026-09-30.md`
- 需要 SMO 處理:**看 dfc 對第一筆的紀錄,結果原文放到 `03_結果/`;驗連續 4 個週期**

| 項目 | 內容 |
|---|---|
| 名稱凍結 | RIC 回報 mitlab 已確認「上線」:R6 v2 的 20 項凍結,`measObjLdn` 與 `measInfoId` 照 SMO 14:35Z 的定案(mitlab 直接在 RIC 那邊回覆,DT 沒有經手) |
| 打開時間 | RIC 於 15:12Z 打開 `notifyFileReady` |
| **第一筆通知** | **15:15:00Z 送出,對應週期 15:00–15:15Z**,檔名 `A20260930.1500+0000-1515+0000_1_ric-dt-71.xml`,`sequence` / `notificationId` = 3 |
| 之後 | 每 15 分鐘一筆(15:30、15:45、16:00Z…) |
| 預期 | 第一筆是完整週期(15:00Z 的取樣在持久卷上),三組都沒有 suspect |
| 舊週期 | 14:30–14:45Z、14:45–15:00Z 不補送 |
| 驗收的 4 個週期 | 15:15、15:30、15:45、16:00Z 這四筆 |

RIC 會盯每一筆 collector 的回應碼與 sshd 的登入紀錄。RIC 另外請 SMO:之後若要改 pmproducer 的過濾設定,請先通知一聲(平台那組是單層 `measObjLdn`)。
