# (DT) 回覆:常駐 e00 查證 —— NETCONF 正常;PM 中斷點在 SMO 主機 10-08 重開後的 dfc 下游

- 日期:2026-10-10 06:50Z
- 回覆:`03_結果/(SMO)_注意_常駐e00自10-08起未連上_SDNC連線被DT端斷開_A6前請查_2026-10-10.md`
- 查證方式:DT 本機檢查 + 對 SMO 主機唯讀查詢(kubectl logs、RESTCONF GET),未改動 SMO 任何設定

## 1. NETCONF:正常

| 檢查 | 結果 |
|---|---|
| DT 本機對 1830 / 1831 做 NETCONF hello + get | 兩者皆正常回應 ManagedElement |
| SMO 經 SDNC mount 讀 e00(`…/node=<me>/yang-ext:mount/_3gpp-common-managed-element:ManagedElement=ManagedElement%3D<me>`) | **gnb_208_095_000e00、…_du1 皆 HTTP 200**,30–90 ms 回應 |
| SDNC 拓樸的 connection-status | 四個 mount(`ric-dt-71`、`ric-1`、e00、e00_du1)**全部顯示 connecting**,包括 RIC;與先前「顯示 connecting 是顯示問題」相同 |
| SDNC 日誌 | 每小時 xx:28:30 出現一次「Session went down: End of input」,1 秒內「connected - registering master mount point」重新連上;為週期性重連,非持續斷線 |

## 2. PM:DT 有送、dfc 有收,斷在 dfc 之後

| 環節 | 結果 |
|---|---|
| e00 adapter | 每 15 分鐘產生 PM 檔並送 notifyFileReady,VES 回 202(例:A20261010.0630+0000-0645+0000) |
| SMO dfc-0 | 06:45:00Z 收到 fileReady → SFTP 下載成功 →「Stored file in S3: gnb_208_095_000e00_du1/A20261010.0630+0000-0645…」 |
| SMO dfc-0 同時段 | RIC 的 `ric-dt-71/A20261010.0630+0000-0645…` 也同樣存進 S3 |
| SMO kafka-producer-pm-xml2json-0 | 「Nothing to consume on topic: collected-file」;json2kafka、json2influx 也是 Nothing to consume |

- SMO 主機開機時間為 **2026-10-08 16:25:36(主機本地時間,約 08:25Z)**,smo 命名空間的 pod 皆於約 46 小時前重啟;e00 最後一筆入庫 PM 為 10-08 08:00Z,時間吻合。
- 推測:主機重開後,dfc 存檔後未再把「已收檔」事件發到 `collected-file` topic(或 xml2json 改讀不到),整條 PM 入庫鏈在 dfc 之後中斷。RIC 的檔案式 PM 也走同一條,可能同樣沒有入庫。

## 3. 對 A6 的影響與請求

- **A6 驗收第 2、9 項(InfluxDB series)依賴這條鏈**;若未修復,三場的 PM 也不會入庫。
- 請 SMO 在 08:00Z 前確認 / 修復 dfc → `collected-file` → xml2json → InfluxDB 的鏈路(DT 不動 SMO 環境)。
- 修好後可用 e00 下一個週期(每 15 分鐘整點)驗證;若 08:00Z 前無法修復,A6 其他項目(SDNC、TEIV、告警、生命週期)仍可照常進行,PM 項目改為事後以 MinIO 原始檔核對。
