# (DT) PM 與告警開始帶劇本資訊(治本):下一個 run 起生效;InfluxDB 的 `_measurement` 名稱會改變,請 SMO 配合

- 日期:2026-10-01 04:45Z
- 依據:mitlab 決定「資料本身帶劇本,治本」(對應待辦 A1 / A3);作法比照 DT ↔ RIC(閘道以 scenarioId + labels.scene_name 分類)
- **生效時間:這場節能測試的 run 不受影響;下一個 run 起生效**。常駐節點 e00 不加劇本層(標 `permanent`)。

## 1. PM 檔(TS 32.435)改動

| 欄位 | 現在 | 改後 | 依據 |
|---|---|---|---|
| `fileHeader dnPrefix` | `SubNetwork=DT` | 不變 | 32.435:DN = dnPrefix + localDn |
| `fileSender localDn` | `ManagedElement=<me>` | **`SubNetwork=<scenarioId>,ManagedElement=<me>`** | 32.435 範例 `localDn="SubNetwork=CountryNN,MeContext=…,ManagedElement=…"`;28.622 SubNetwork 可巢狀 |
| `managedElement localDn` | 同上 | 同上;並加 **`userLabel="runId=<runId>"`** | 32.435 `userLabel` 為選用自由文字 |
| `measValue measObjLdn` | `ManagedElement=<me>,GNBDUFunction=1,NRCellDU=0` | **`GNBDUFunction=1,NRCellDU=0`**(相對 ME,照 32.435 範例) | 一併修掉入庫名稱裡 ME 重複兩次的問題 |

**SMO 入庫後的 `_measurement`**(pmlog:`fileSender.localDn + "," + measObjLdn`)會從
`ManagedElement=gnb_208_095_000e31_du1,ManagedElement=gnb_208_095_000e31_du1,GNBDUFunction=1,NRCellDU=0`
變成
**`SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e31_du1,GNBDUFunction=1,NRCellDU=0`**。
→ 按劇本查:`r._measurement =~ /^SubNetwork=corridor24_16_24,/`;按 run 查:仍用 A2 的 run 對照表時間窗(runId 刻意不放進名稱,避免每 run 一組新 series、儀表板要用 regex)。

檔名、`notifyFileReady` 的 `sourceName`、NCMP 的 CM handle 名稱、TEIV 都不變。`dnPrefix`、`userLabel`、`measInfoId` SMO 的轉換器會解析但不入庫,所以 run 只在原始 XML 與 MinIO 檔裡看得到。

## 2. 告警(TS 28.111 notifyNewAlarm)改動
- `data.additionalInformation = {"scenarioId": "<scenarioId>", "runId": "<runId>"}`(28.111 的選用欄位,型別 AttributeNameValuePairSet)。`sourceName`、`systemDN`、`alarmId` 不變,SDNR 配對不受影響。
- `notifyClearedAlarm` 的 schema 沒有 additionalInformation,不加,靠 `alarmId` 對應。

## 3. 請 SMO 配合
1. pmlog 不用改;InfluxDB 既有查詢(n2a 的逐分鐘紀錄腳本、N3 rApp 的 PM 讀取)請改成以 `SubNetwork=<scenarioId>,` 前綴篩選。N3 rApp 若從 DME/Kafka 讀,JSON 的 `measuredEntityDn` 也會帶這個前綴。
2. 歷史資料(09-29 至今)名稱不變;要跨新舊比對請用 run 對照表。
3. 這場節能測試結束後,DT 會起一場約 20 分鐘的驗證 run,請 SMO 確認:(a) pmlog 新名稱入庫、值不為空;(b) `notifyNewAlarm` 帶 additionalInformation 時 SDNR 仍正常收;(c) 轉換器對 `userLabel` 沒有報錯。
