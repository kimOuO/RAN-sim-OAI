# 結果:D2 —— PM 檔案鏈路 DT → VES → dfc(SFTP 取檔)→ MinIO → xml2json → InfluxDB

日期:2026-09-29 07:37–07:43Z。執行:DT 端。結論:**DT 端到 SMO 的 InfluxDB 寫入前一步全部打通**;InfluxDB 內容待 SMO 端以 token 確認;pmlog 分支因 SMO 端 ICS job DISABLED 未走通(SMO 側問題)。

## 模板換版(`02_測試/o1-adapter-dt/config/`)
- `ves-file-ready.json`:stndDefined → **舊式 `notification` 網域**(`changeType: FileReady`、`changeIdentifier: PM_MEAS_FILES`、`arrayOfNamedHashMap[{name, hashMap{location, compression, fileFormatType: org.3GPP.32.435#measCollec, fileFormatVersion: V10}}]`),VES 7.2.1。
- `pmData-measData.xml`:28.532 `measDataFile` → **TS 32.435 `measCollecFile`**(fileHeader/fileSender/measCollec、measData/managedElement/measInfo、granPeriod/repPeriod、measType/measValue/r/suspect、fileFooter),measObjLdn = `ManagedElement=<me>,GNBDUFunction=<du>,NRCellDU=<cell>`。
- adapter 讀模板是在啟動時,而且**只有 config.json 原本有掛進容器**,模板要另外 bind mount(compose 已補)。
- `pm-data-interval`/`granularityPeriod`/`fileReportingPeriod` 聯調期間 60 s。

## 時間線(UTC)
| 時間 | 事件 | 證據 |
|---|---|---|
| 07:39:00 | 第一筆舊式 fileReady → VES 202;dfc 收到 | dfc log `Received ... DefaultFileReadyMessage` |
| 07:39:00 | dfc **S3 存檔失敗**:`Object name contains unsupported characters`,物件名 `gnb_…_du1//ftp/A….xml.lck` | dfc log ERROR |
| 07:40 | 原因:adapter 把 `@fileLocation@` 填成 `/ftp/<檔名>`,dfc 用 `name` 當 S3 物件名,不能有斜線 → 修 C(`patches/0002`:file_location 改純檔名),模板 location 改 `…:@port@/ftp/@fileLocation@`;重建映像 | |
| 07:41:00 | 重建後第一筆:`name=A20260929.0740+0000-0741+0000_1_gnb_208_095_000e00_du1.xml`,VES 202 | adapter log |
| 07:41:01.3 | dfc **SFTP 取檔成功**(`Download successful from xNF`),`Stored file in S3: gnb_208_095_000e00_du1/A….xml` | dfc log |
| 07:41:01 | dfc → topic `collected-file`(503 bytes) | Redpanda |
| 07:42:01 | xml2json 轉檔 → `json-file-ready-kp` / `json-file-ready-kpadp` 各一筆(`msg sent ok`) | xml2json log |
| 07:42:01 | json2influx 消費 `json-file-ready-kp[2]@1`(ICS job `job-kp-influx-json-0`:InfluxDB2 `http://influxdb2:8086`,org `est`,**bucket `pm-bucket`**) | json2influx log |

## 另一路(pmlog → `pm-logg-bucket`)沒走通,屬 SMO 側
- ICS job `PmData_5b3f4db6-…` 狀態 `DISABLED`、`producers: []`;pm-producer 6 分鐘內只有 supervision 心跳;topic `pmreports` 0 bytes。→ pm-producer 沒接到 PmData 型別的 job,請 SMO 端查(ICS 產生者註冊 / job 啟用)。
- xml2json、json2kafka、json2influx log 裡每 5 分鐘一次 `2/2 brokers are down`,是 librdkafka 對 9095 閒置斷線的雜訊,實際訊息 `sent ok`,不影響。

## DT 端可驗與待 SMO 驗
- DT 端:`ftp-du/` 每分鐘一個 `A<start>-<end>_1_<me>.xml`;SFTP 1223 以 netconf 帳號可列出。
- **待 SMO 端(有 token)**:InfluxDB2 `pm-bucket`(org est)查 `sourceName`/`managedElement` = `gnb_208_095_000e00_du1`,measType `DRB.MeanActiveUeDl`。
- 目前 PerfMetricJob 只有預設 1 個量測 `DRB.MeanActiveUeDl`(值 0,現在沒 UE);SMO 可透過 NETCONF 改 `PerfMetricJob/attributes/performanceMetrics` 加 `RRU.PrbTotDl`、`DRB.UEThpDl/Ul`、`DRB.MeanActiveUeUl`、`DRB.MaxActiveUeDl/Ul`(adapter 支援清單)。SMO 想要的 `RRU.PrbUsedDl` 命名需在 facade/adapter 改名輸出,列入 D2b。

## 踩到的問題
| # | 現象 | 原因 | 處置 |
|---|---|---|---|
| 1 | 換了模板沒生效 | 只有 config.json bind mount,模板仍用映像內建 | compose 加兩個 mount |
| 2 | `<suspect><suspect>true</suspect></suspect>` | `@suspect@` 由 adapter 替換成整個元素 | 模板只留 `@suspect@` |
| 3 | dfc S3 物件名含 `//ftp/` 被拒 | adapter `file_location` 是完整路徑 | `patches/0002` + 模板 location 補 `/ftp/` |
| 4 | dfc pod 內 `</dev/tcp` 測 1222/1223 FAIL | dfc 映像用 sh,不支援 `/dev/tcp`(假陰性) | 改從 onap-sdnc-0(bash)測:OK;dfc 實際取檔成功 |
