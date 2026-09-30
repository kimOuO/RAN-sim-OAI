# (DT) D2:PM 檔鏈路已從 DT 打到你們的 json2influx,請用 token 驗 InfluxDB;另有兩件 SMO 側事項

日期:2026-09-29 07:43Z。來自 DT 端。

## 已通(你們 log 可對)
- 07:41:00Z 起 `gnb_208_095_000e00_du1` 每 60 s 送一筆舊式 `notification` fileReady(`changeIdentifier PM_MEAS_FILES`,`fileFormatType org.3GPP.32.435#measCollec`),location `sftp://netconf:…@10.3.0.217:1223/ftp/A<start>-<end>_1_gnb_208_095_000e00_du1.xml`。
- dfc-0:`Download successful from xNF` → `Stored file in S3: gnb_208_095_000e00_du1/A….xml` → topic `collected-file`。
- xml2json:`msg sent ok` 到 `json-file-ready-kp` / `json-file-ready-kpadp`。
- json2influx:消費 `json-file-ready-kp[2]@1`;其 ICS job `job-kp-influx-json-0` 指向 InfluxDB2 org `est`、**bucket `pm-bucket`**(不是 pm-logg-bucket)。
- 07:39–07:40Z 那兩筆 dfc 報 `Object name contains unsupported characters` 是我方檔名帶路徑的 bug,已修,之後不會再有。

## 請你們驗
1. InfluxDB2(31781 / token)查 `pm-bucket`,measurement 應含 managedElement/sourceName `gnb_208_095_000e00_du1`、measType `DRB.MeanActiveUeDl`(現在沒 UE 所以值 0)。請回報有無資料與 schema(measurement 名、tag 名),我方好對量測名。
2. **pmlog 分支沒通(SMO 側)**:ICS job `PmData_5b3f4db6-3d9e-11ed-b878-0242ac120002` 狀態 `DISABLED`、`producers: []`,pm-producer 只有 supervision 心跳,`pmreports` topic 0 bytes → `pm-logg-bucket` 不會有資料。請查 pm-producer 對 ICS 的 PmData 型別註冊 / job 啟用。
3. 資訊:xml2json / json2kafka / json2influx 每 5 分鐘一次 `2/2 brokers are down`,是 librdkafka 對 9095 閒置斷線的雜訊,實際 `sent ok`;不影響。

## 目前狀態
- 兩個 ME 持續 mount 中;心跳 30 s;PM 60 s(正式再改 900)。
- PerfMetricJob 預設只有 `DRB.MeanActiveUeDl`;你們可經 NETCONF 改 `ManagedElement=gnb_208_095_000e00_du1/PerfMetricJob/attributes/performanceMetrics` 加 `RRU.PrbTotDl`、`DRB.UEThpDl`、`DRB.UEThpUl`、`DRB.MeanActiveUeUl`、`DRB.MaxActiveUeDl`、`DRB.MaxActiveUeUl`(adapter 支援清單;改了會即時進下一個檔)。`RRU.PrbUsedDl/Ul`、`RRU.PrbAvailDl`、`RRC.ConnMean`、`PEE.Energy` 這幾個名稱 adapter 原生沒有,DT 端列入 D2b 加。
