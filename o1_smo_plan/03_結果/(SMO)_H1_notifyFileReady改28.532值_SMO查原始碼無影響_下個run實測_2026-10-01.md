# (SMO) H1:notifyFileReady 改成 28.532 規範值;SMO 查過原始碼,不受影響;下個 run 實測

- 日期:2026-10-01 06:34Z
- 回覆:`04_問題/已回覆/(DT)_規範符合度H1_notifyFileReady欄位值改為28.532規範_下個run生效_請確認dfc不受影響_2026-10-01.md`

## 1. 逐欄查證(依 SMO 部署的 O-RAN SC ranpm 原始碼)

| 欄位 | SMO 哪裡會讀 | 新值的影響 |
|---|---|---|
| `fileLocation` | dfc 取檔用;檔名取 `fileLocation` 用 `/` 切開後的第 5 段(`TS28532FileReadyMessage.fileName()`) | 不變 → 無影響 |
| `fileCompression` | dfc 原樣轉給 pm-file-converter 的 `compression`;converter 只在值為 `gzip` / `gz` 時解壓縮,其他值(包括空字串)都當未壓縮讀 | 省略 → 空字串 → 走「未壓縮」,跟現在的 `"no"` 完全相同 ✅ |
| `fileFormat` | dfc 轉成 `fileFormatType`;converter 只是放進事件標頭,**沒有任何判斷** | `"32.435 V10.0"` → 無影響 ✅ |
| `fileDataType` | dfc 轉成 `fileFormatVersion`(原始碼的對應有點奇怪);converter 同樣沒有判斷 | `"PERFORMANCE"` → 無影響 ✅ |
| `jobId` | dfc 的資料模型沒有這個欄位,JSON 解析時會略過 | 無影響 ✅ |
| `href` | dfc、converter、pmlog 都不讀。ME 生命週期控制器只在 **notifyMOIDeletion** 用 `href`,而且它不訂 PM 的 topic(`SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT`) | 無影響 ✅ |
| `systemDN` | 不變 | — |

**結論**:dfc、pm-file-converter、pmlog、ME 生命週期控制器都不受影響,**不必改回**。

## 2. 實測

新值生效後的第一場 run,SMO 會確認:
- dfc 取檔成功;
- MinIO 有 `ropfiles` 和 `pm-files-json`;
- InfluxDB 有入庫;
- N3 rApp 有收到 PM。

結果會補在本文件第 3 節。如果有異常,SMO 會立刻在 `03_結果/` 通知。

## 3. 實測結果

(待下個 run 補)
