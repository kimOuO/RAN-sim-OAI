# (DT) 轉達 RIC:SFTP 已開(10.3.0.71:30922),請 SMO 從 dfc 的 Pod 測連線

- 日期:2026-09-30 14:50Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`03_結果/(SMO)_回覆RIC_多measInfo檔的入庫規則_依原始碼確認_2026-09-30.md`
- 需要 SMO 處理:**第 1 節測連線**;樣本 15:00Z 後另行轉放

## 1. SFTP 連線資訊

| 項目 | 內容 |
|---|---|
| 位址 | **10.3.0.71,埠 30922**(NodePort),SFTP |
| 帳號 | `pmpull` |
| 密碼 | 24 位英數,不含 `@` `:` `/`。**由 mitlab 提供,不經 session 或共用資料夾** |
| 路徑 | `/ftp/<檔名>`,剛好一層 |
| 權限 | 唯讀、chroot(登入後根目錄只看得到 `ftp/`),寫入會被拒 |
| 保留 | 48 小時 |

host key 指紋(做 known_hosts 或嚴格檢查時核對;金鑰在持久卷上,Pod 重啟不會變):

```
ECDSA    SHA256:qsInVFkRQatwvm5VIhdrX8zg393W7KOSvdq5rjhopvA
ED25519  SHA256:UbTQuwiRdSn3y/dvoK5uXd2rJXFF0a3rCYWFzk7o9wc
RSA 3072 SHA256:2Vedr0vrzqVtFXbPcRcWMB6mg/GXtwsV0IkCeNZg85M
```

伺服器是 OpenSSH 10.3。除預設演算法外,另開了 `ssh-rsa` host key 與 `diffie-hellman-group14-sha256`、`group-exchange-sha256`、`group14-sha1` 的 kex 當相容選項。**若 dfc 連不上,請把錯誤訊息(no matching kex / host key / cipher)原文放到 `03_結果/`**,RIC 會照 dfc 支援的清單調整。

RIC 已自行從 RIC 主機經 NodePort 測過:列目錄、取檔成功,上傳被拒。

## 2. RIC 的實作狀態

- PM agent 已在跑,**目前只產檔,`notifyFileReady` 先關著**。SMO 確認樣本後 RIC 才打開通知。
- 已照 SMO 14:35Z 的入庫規則:`measObjLdn` 不含 `ManagedElement`;`measInfoId` = `PM=1,PmGroup=E2Term` / `SubMgr` / `RicPlatform`;`measType` 列全不跳號;`<r>` 一律整數,取不到就不輸出該 `<r>`;整組取不到或週期不完整才在該 `measValue` 標 suspect;`fileSender` 與 `managedElement` 的 `localDn` 都是 `ManagedElement=ric-dt-71`;`lastEpochMicrosec` = 週期結束整點。
- 與 R6 文件不同的一處:e2term 的 14 項改成 agent 在週期邊界當下直接讀 e2term 的 metrics 端點(Prometheus 抓的是同一個端點,但 1 分鐘才抓一次,對不齊邊界)。數值定義不變。

## 3. 樣本時程

| 檔 | 產生時間 | 說明 |
|---|---|---|
| 第一個檔 | 14:45Z | agent 剛啟動,兩組計數器會帶 suspect |
| **第一個完整週期** | **15:00Z** | RIC 會把 XML 原文與對應的 `notifyFileReady` JSON(密碼遮掉、不實際送出)交給 DT,DT 轉放 `02_測試/` |
