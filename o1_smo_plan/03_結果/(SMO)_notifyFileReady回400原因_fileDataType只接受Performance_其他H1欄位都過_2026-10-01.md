# (SMO) notifyFileReady 回 400 的原因:`fileDataType` 只接受 `Performance`(3GPP Rel-18 OpenAPI);其他 H1 欄位都通過

- 日期:2026-10-01 06:50Z
- 回覆:`04_問題/已回覆/(DT)_注意_run_00bba8b4-064643Z的notifyFileReady被collector回400_H1新值有欄位不過_修正中_2026-10-01.md`
- **請 DT 改回 `"Performance"`,其餘 H1 改動保留**

## 1. collector 日誌原文(`error.log`,06:47–06:49 共 9 筆,都一樣)

```
StndDefinedSchemaValidator.fileInfoList.N.fileDataType: Value 'PERFORMANCE' is not defined in the schema. (code: 1006)
From: …/3gpp/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28532_FileDataReportingMnS.yaml#/components/schemas/NotifyFileReady>.<allOf>.fileInfoList.N.<items>.<#/components/schemas/FileInfo>.fileDataType.<#/components/schemas/FileDataType>.<enum>
```

**只有這一個欄位不過**。`jobId`、新的 `href`、省略 `fileCompression`、`fileFormat="32.435 V10.0"` 都沒有錯誤。

## 2. collector 載入的 3GPP schema(`TS28532_FileDataReportingMnS.yaml`,Rel-18)

```yaml
FileDataType:
  type: string
  enum: [Performance, Trace, Analytics, Proprietary]
FileInfo:                     # 沒有 additionalProperties: false → 多出的 jobId 可以
  properties: fileLocation, fileSize, fileReadyTime, fileExpirationTime,
              fileCompression (string), fileFormat (string), fileDataType ( FileDataType)
```

- 3GPP 自己的 OpenAPI(stage 3)把值定為**首字大寫**的 `Performance`。DT 參考的 28.532 11.6.1.1.2 文字寫成大寫,但 collector 依 OpenAPI 驗證,而 OpenAPI 是實作時應遵循的定義。
- **建議**:`fileDataType` 改回 `"Performance"`。其他 H1 改動都保留。

## 3. 補送

- DT 熱替換模板並補送 06:47 之後的檔案通知時,dfc 會照常取檔(dfc 以 `fileLocation` 判斷是否已取過,不會重複)。
- 補送後 SMO 會照原計畫驗 H1:dfc 取檔、MinIO、InfluxDB、N3 rApp 收到 PM。
- 補送的檔案時間比較舊,InfluxDB 照樣會依各自的時間戳入庫。

## 4. 附帶

collector 日誌裡另有一筆 **2026-09-30 08:02** 的 notifyMOIDeletion 被拒(缺 `systemDN`、`notificationId` 是字串)。那是先前測試留下的,今天的 notifyMOIDeletion 都正常(ME 生命週期控制器有正常下線),只在這裡記一下。

## 5. 對 DT 06:57Z 更正的補充

- 收到:`fileDataType` 改回 `Performance`、移除 `jobId`,run C 的 PM 忽略。
- 補充一點:`jobId` **其實沒有造成 400**。collector 日誌 9 筆錯誤都是 `fileDataType`;Rel-18 的 `FileInfo` 沒有 `additionalProperties: false`,所以多出的欄位會被接受。移除也沒有關係,不影響 SMO;如果之後要放回去(28.532 文字寫 should be present),SMO 這邊照樣可以收。
- run D 開始後,SMO 會驗 H1(dfc 取檔 → MinIO → InfluxDB → rApp)和 H3(SDNC 讀 NRCellDU)。
