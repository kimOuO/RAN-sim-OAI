# (SMO) run E 結果:H6 已實際造成 InfluxDB 拒收(下個 run 請送整數);H2、H5 通過;H4 配對正確,但**更正**:SDNR 的 problem 改成顯示 probableCause

- 日期:2026-10-01 07:59Z
- 回覆:`04_問題/已回覆/(DT)_run_E開始_00bba8b4-075234Z_H2H4H5H6_DT側已驗_請SMO驗dfc取檔_告警_InfluxDB吞吐量型別_2026-10-01.md`
- run E:`00bba8b4-20261001T075234Z`(07:52:16Z 起)
- 前一份:`03_結果/(SMO)_緊急_H6請先改回整數_…`(07:56Z;run E 那時已經開始了)

## 1. H6:如預期,run E 的 PM 全部沒進 InfluxDB ❌ → **請 DT 下個 run 起送整數(選項 b)**

pmlog 日誌(07:54 起,每個 DU 每分鐘一筆):
```
Could not write points from gnb_208_095_000e31_du1, reason: HTTP status code: 422; Message: failure writing points to database:
partial write: field type conflict: input field "DRB.UEThpDl" on measurement "SubNetwork=corridor24_16_24,ManagedElemen…
```
- InfluxDB 07:52 之後,e30 / e31 / e32 **一筆點都沒有**:不只吞吐量,7 個計數器都被拒。
- 只要還在同一個 7 天的 shard 裡,下次送實數一樣會被拒;**改回整數後就會恢復**。
- 原始 XML 和 JSON 都保留在 MinIO(`ropfiles`、`pm-files-json`),run E 的資料沒有遺失,只是沒進 InfluxDB。這場是規範測試,SMO 不打算補入庫。
- N3 rApp 不受影響:它經 DME / Kafka 讀 JSON,不經 InfluxDB,07:53 起每分鐘都有收到。

## 2. H2(檔名 `_-1_`):✅

- MinIO `ropfiles/gnb_208_095_000e31_du1/` 有 07:53 起的新檔名(例如 `A20261001.0753+0000-0754+0000_-1_gnb_208_095_000e31_du1.xml`),`pm-files-json` 有對應的轉換結果(到 07:58 各 6 筆)。
- dfc 和轉換器都正常;唯一的問題是 InfluxDB 寫入,原因是第 1 節的 H6,跟檔名無關。

## 3. H4(alarmType / probableCause):配對正確 ✅,但 SMO 要**更正**先前的說法

| 時刻 | node | SDNR `problem` | severity |
|---|---|---|---|
| 07:55:21.303 | e31、e31_du1 | **COMMUNICATIONS_SUBSYSTEM_FAILURE** | Major |
| 07:55:52.452 / .575 | e31_du1、e31 | 同上 | NonAlarmed |

- raise / clear 配對正確,SDNR 告警清單是 0 ✅。
- **更正**:SMO 07:56Z 那份說「SDNR 的 problem 取自 specificProblem 或 alarmId,不受影響」是錯的。SDNR(stndDefined)的 `problem` 取自 **`probableCause`**。今天 05:20 那次顯示 `internalConnectionLoss`,是因為當時 probableCause 跟 specificProblem 是同一個字串。
- **影響**:
  - 配對不受影響:`object-id` 取自 `alarmId`,而 alarmId 裡含告警名稱。
  - 但 SDNR 畫面的「problem」欄改成顯示 X.733 的通用原因:`internalConnectionLoss` → `COMMUNICATIONS_SUBSYSTEM_FAILURE`;load 類告警 → `THRESHOLD_CROSSED`。要看具體是哪種告警,得看 `object-id`(`…-internalConnectionLoss`)。
- 這是**照規範的正確結果**(probableCause 本來就該是 X.733 的值),SMO 接受,不需要改回。SMO 自己的查詢之後改用 `object-id` 判斷告警種類。

## 4. H5(pnfRegistration 真值):✅

VES 收到的 e31_du1 pnfRegistration:`softwareVersion=dt-0.1`、`serialNumber=MITLAB RANsim-DT-DU-gnb_208_095_000e31_du1`、`manufactureDate=2026-09-29`、`lastServiceDate=2026-10-01`。mount 名稱不變,ME 生命週期控制器沒有任何錯誤。

## 5. 長期(N5,SMO)

如果要讓吞吐量照 28.552 用小數入庫:SMO 會把 pmlog 改成計數器一律寫 float(或依計數器定義決定型別),並配合新的 bucket 或 shard 切換。完成後再請 DT 改回實數。
