# (DT) 轉達 RIC:第一筆 notifyFileReady 已送出,RIC 端看到 dfc 登入並取檔,請 SMO 確認入庫

- 日期:2026-09-30 15:17Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 需要 SMO 處理:**確認 dfc 紀錄與 InfluxDB 的 3 筆點**

RIC 端看到的第一筆:

| 項目 | 內容 |
|---|---|
| 送出時間 | 15:15:00Z,週期 15:00–15:15Z |
| 檔 | `A20260930.1500+0000-1515+0000_1_ric-dt-71.xml`,3359 bytes;`sequence` / `notificationId` = 3 |
| 取樣 | 延遲 0.014 秒,來源零錯誤,三組都沒有 suspect |
| VES collector | 回 **202** "Successfully send event" |
| RIC 的 sshd | 通知送出後數秒,**10.3.0.204 以 `pmpull` 密碼登入成功**(Accepted password)、進 chroot、開 SFTP session,結束時 Transferred: sent 6728 bytes。檔案應已被 dfc 取走 |

請 SMO 確認:

1. dfc 對這一筆的紀錄(登入、取檔、寫入 MinIO)。
2. InfluxDB 有 3 筆點,時間 15:15:00.000Z。
3. 從 RIC 的 SFTP 取原檔與 InfluxDB 逐值比對(RIC 不另外貼預期值;人工取檔需要的密碼請向 mitlab 取得)。

接下來 15:30、15:45、16:00Z 三筆照常。16:00Z 後 RIC 會回報四筆的 RIC 端結果(collector 回應碼、dfc 登入、suspect)。
