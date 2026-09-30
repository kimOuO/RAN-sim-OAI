# (DT) 轉達 RIC:mitlab 選 (a),RIC 已開工;請 SMO 確認多 measInfo 檔的入庫規則

- 日期:2026-09-30 14:30Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`03_結果/(SMO)_規範查證_R6與檔案式PM認證_SMO查證結果與兩處修正_2026-09-30.md`
- 需要 SMO 處理:**第 3 節的問題**

## 1. RIC 回報的 mitlab 決定

以下是 RIC 團隊 session 回報的內容(mitlab 直接在 RIC 那邊回覆的,DT 沒有經手):

| 事項 | 決定 |
|---|---|
| 檔案式 PM 的認證方式 | **(a) 維持現狀**:SFTP 帳密在 `fileLocation` 的 URL、通知走現有 VES collector;帳號專用、唯讀、chroot |
| R6 量測清單 | mitlab 沒有提出修改,RIC 以草案 v2(20 項)開工。**名稱在正式上線時才凍結**,上線前 RIC 會再向 mitlab 確認一次;在那之前請 SMO 把名稱當成「預定」 |

RIC 現在開始做:PM agent(每 15 分鐘產 TS 32.435 XML)、RIC 端 SFTP(專用唯讀帳號、單層 `/ftp/`、保留 ≥ 24 小時)、`notifyFileReady`。SFTP 開好後 RIC 會告知 IP 與埠(預計 10.3.0.71 的 NodePort),XML 與 `notifyFileReady` 樣本由 DT 轉放 `02_測試/`。

## 2. RIC 對其他事項的回覆

- O-RAN.WG3.O1-Interface-for-NearRT-RIC:RIC 主機上沒有,RIC 也沒有 O-RAN 帳號,只能由 mitlab 下載。RIC 的看法是現在用 `VS.` 安全,日後若有官方 `OR.` 名稱可以並存,不必改既有欄位名;第二批量測會先查那份文件再定名。
- 選項 (b) 在 RIC 端約半天(需要 SMO 提供 collector 的 CA 憑證與新的埠),(c) 約 1–2 天。

## 3. 請 SMO 確認(RIC 的第 5 個問題,DT 只能回答一部分)

RIC 問:SMO 入庫時用哪些欄位當 InfluxDB 的 measurement / tag,`measObjLdn` 怎麼拆,`sourceName` 或 `ManagedElement` 是否要等於 `ric-dt-71`,`measInfoId` 有沒有要求。

DT 已把參考文件 §6 的內容轉給 RIC(pmlog 寫進 InfluxDB:`_measurement` = `ManagedElement=<sourceName>,<measObjInstId>`,`_field` = 量測名稱,時間 = `lastEpochMicrosec`)。以下幾點 DT 不確定,請 SMO 回覆:

| # | 問題 |
|---|---|
| 1 | R6 的 XML 一個檔有 **3 個 measInfo**(E2Term、SubMgr、平台),各有不同的 `measObjLdn`。xml2json 與 pmlog 是否正確處理多個 measInfo?DT 的 gNB 檔只有一個,沒有驗過 |
| 2 | `measInfoId` 有沒有格式要求?DT 用的是 `PM=1,PmGroup=NRCellDU`。RIC 的三組建議怎麼命名 |
| 3 | `_measurement` 是 `ManagedElement=<sourceName>,<measObjInstId>`。RIC 的 `measObjLdn` 本身已含 `ManagedElement=ric-dt-71,…`,組出來會不會重複一段?`measObjLdn` 該寫完整 DN 還是省略 `ManagedElement` |
| 4 | `sourceName`、`fileSender localDn`、`managedElement localDn` 是否都必須是 `ric-dt-71`(與 SDNC 的 mount 名稱一致) |
| 5 | GAUGE 型量測取不到值時,RIC 打算省略該 `<r>` 或標 suspect。省略個別 `<r>`(p 不連續)xml2json 能不能處理 |
