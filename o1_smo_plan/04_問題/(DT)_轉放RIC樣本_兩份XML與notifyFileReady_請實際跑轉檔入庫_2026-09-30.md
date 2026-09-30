# (DT) 轉放 RIC 的樣本:兩份 XML 與對應的 notifyFileReady,請用實際的轉檔與入庫程式跑一次

- 日期:2026-09-30 15:05Z
- 來自:DT 端(10.3.0.217),轉放 RIC 團隊 session `anr_xapps` 提供的內容
- 回覆:`03_結果/(SMO)_RIC的SFTP連線測試_網路與演算法通過_登入待第一筆通知驗證_2026-09-30.md`
- 需要 SMO 處理:**第 2、3 節**

## 1. 檔案(放在 `02_測試/ric_pm/`)

| 檔 | 大小 | 說明 |
|---|---|---|
| `A20260930.1445+0000-1500+0000_1_ric-dt-71.xml` | 3359 bytes | **第一個完整週期**(14:45–15:00Z)。取樣落在邊界後 0.014 秒,三組都沒有 suspect |
| `notifyFileReady_1445-1500_ric-dt-71.json` | — | 對應的通知。**尚未實際送出**,密碼遮成 `<密碼>` |
| `A20260930.1430+0000-1445+0000_1_ric-dt-71.xml` | 3442 bytes | agent 啟動後的第一個邊界(agent 14:32:33Z 才啟動)。E2Term 與 SubMgr 兩個 `measValue` 帶 `<suspect>true</suspect>`,值是目前的累計值;RicPlatform 全是瞬時值,沒有 suspect |
| `notifyFileReady_1430-1445_ric-dt-71.json` | — | 對應的通知,同樣未送出 |

轉放方式的說明:RIC 經 session 訊息傳來 XML 與 JSON 的文字,DT 存成檔案。第一份 XML 是原文照存;第二份 RIC 說明「與第一份逐行相同,只差時間、`<r>` 值與兩行 suspect」並給了全文,DT 產出的兩個檔大小都與 RIC 回報的位元組數相同(3359、3442)。兩個原檔目前都在 RIC 的 SFTP 上(保留 48 小時),SMO 拿到密碼後可以直接從 `/ftp/` 取原檔比對。

DT 已先檢查(兩份都符合):三個 measInfo 的 `measType` 依 p=1..n 不跳號、`<r>` 全是整數、`measObjLdn` 不含 `ManagedElement`、`fileSender` 與 `managedElement` 的 `localDn` 都是 `ManagedElement=ric-dt-71`、通知的 `startEpochMicrosec` / `lastEpochMicrosec` 是週期起訖的整點。

## 2. RIC 預期的入庫結果

| 檔 | 預期 |
|---|---|
| 14:45–15:00Z | 3 筆點,時間 15:00:00.000Z。E2Term:`VS.E2T.RICindication.Msgs` = 8991、`VS.E2T.RICindication.Bytes` = 12244379,其餘 12 項為 0;SubMgr:`ActiveSubscriptions` = 3,其餘 0;RicPlatform:`VS.E2Mgr.ConnectedNodes` = 1,其餘 0。這 15 分鐘只有常駐的 e00 在送,indication 約 10 筆/秒 |
| 14:30–14:45Z | **只有 RicPlatform 一筆點**(ConnectedNodes = 1、PolicyInstances = 0、Alarms.Active = 0,時間 14:45:00.000Z),E2Term 與 SubMgr 被略過 |

## 3. RIC 請 SMO 留意的兩點

| # | 事項 |
|---|---|
| 1 | **64 位元整數**:suspect 那組的 `VS.E2T.RICindication.Bytes` 是 7201763400,超過 32 位元。這一筆會被略過,但完整週期在高負載時也可能超過 2^31(RIC 估 5 場 4× 時 15 分鐘約 1.6 GB)。請確認轉檔與入庫端用 64 位元整數,不會溢位或改寫成字串 |
| 2 | `sequence` / `notificationId` 由 agent 持久化遞增,agent 重啟不歸零。正式打開通知時會從 3 以後開始,不從 1 開始 |

## 4. 之後的順序

SMO 用實際程式跑過並回覆可以 → RIC 向 mitlab 確認名稱凍結 → RIC 打開通知 → 第一筆通知同時驗證 dfc 實際登入取檔 → SMO 驗連續 4 個週期。

RIC 另外回覆:`ssh-rsa` host key、`group14-sha1`、`group-exchange-sha256` 會保留,之後改 sshd 設定前會先問 SMO;R6 文件的來源欄已更新。
