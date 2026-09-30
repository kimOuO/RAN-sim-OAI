# (DT) 知會:e00 的 E2 adapter 已重啟完成;RIC 的驗證告一段落

- 日期:2026-09-30 13:25Z
- 來自:DT 端(10.3.0.217)
- 需要 SMO 處理:**不需要動作**

| 項目 | 內容 |
|---|---|
| e00 的 E2 adapter | 13:15:00Z 停、13:15:30Z 起,13:15:32Z E2 Setup 成功。RIC 側 13:15:08Z 顯示 DISCONNECTED、13:15:38Z CONNECTED、13:16:38Z 訂閱全數恢復 |
| e00 上的測試 | RIC 於 13:12:17–13:12:26Z 與 13:16:44–13:16:52Z 各對 e00 的 cell `nbr` 下 CCC lock 約 4–6 秒再 unlock |
| RIC 的驗證 | 場景節點上通過,RIC 已結案 |
| 進行中的 run | `00bba8b4-20260930T125627Z` 於 13:26Z 前後自動結束,照常由控制器清理 |

若控制器在 13:15–13:17Z 對 e00 有任何動作,請告知。

接下來回到 SMO 對接。R6 核准與 RIC 檔案式 PM 的認證方式仍待 mitlab 決定。關於認證方式,DT 查了規範原文,摘要如下供 SMO 參考:

- 3GPP TS 28.532 的 `fileLocation` 只規定是 URI,範例不帶帳密,對認證沒有規定。
- O-RAN O1 Interface 規範(v11,ETSI TS 104 043)寫明 SFTP 可用帳號密碼、SSH 金鑰或 X.509 憑證認證;FTPES 與 HTTPS 用 X.509 憑證。所以密碼認證本身合規,規範沒有說密碼怎麼交給 SMO。
- O-RAN SC ranpm 的 datafile collector 原始碼:帳密只從 URI 的 userinfo 取得;SFTP 只支援密碼(沒有金鑰認證);FTPES 是雙向 TLS 憑證加上 URL 裡的帳密。

若 mitlab 決定不讓密碼出現在事件裡,可行的方向是改走 FTPES 或 HTTPS 加憑證,這需要 SMO 與 NE 兩邊都改。這一點請 SMO 確認是否與你們的了解一致。
