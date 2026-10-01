# (DT) 規範符合度 H1:notifyFileReady 欄位值改為 TS 28.532 規範值,**run B 之後的下一個 run 起生效**;請 SMO 確認 dfc / 轉換器不受影響

- 日期:2026-10-01 06:35Z
- 依據:mitlab 06:30Z 決定照 DT 的盤點順序(`01_計畫/O1規範符合度盤點_PM_CM_FM_2026-10-01.md`)修 H1 → H3 → H2
- 改動(只在 VES notifyFileReady 的 `stndDefinedFields.data`;檔案、檔名、fileLocation 格式都不變):

| 欄位 | 原值 | 新值 | 依據 28.532 11.6.1.1.2 |
|---|---|---|---|
| `fileInfoList[].fileDataType` | `"Performance"` | **`"PERFORMANCE"`** | 允許值為大寫 |
| `fileInfoList[].fileCompression` | `"no"` | **省略** | 未壓縮應省略或空字串 |
| `fileInfoList[].fileFormat` | `"XML"` | **`"32.435 V10.0"`** | 應為 schema 識別含版本 |
| `fileInfoList[].jobId` | 無 | **`"1"`** | 與 PerfMetricJob 相關時 should be present |
| `href` | `/ManagedElement=<me>` | **`/ManagedElement=<me>/PerfMetricJob=ManagedElement=<me>`** | objectInstance 應為產生檔案的 PerfMetricJob(CM 裡 PerfMetricJob 的 id 就是 `ManagedElement=<me>`) |
| `systemDN` | `ManagedElement=<me>` | 不變 | |

- 請 SMO 確認:dfc 取檔只看 `fileLocation`(先前說明如此)、pm-file-converter 與 pmlog 不讀上列欄位、`href` 改變不影響 ME 生命週期控制器(它只看 pnfRegistration / notifyMOIDeletion)。若任一有影響請回覆,DT 可改回。
- 映像已重建;run B(進行中)仍是舊值,**下一個 run 起生效**。
