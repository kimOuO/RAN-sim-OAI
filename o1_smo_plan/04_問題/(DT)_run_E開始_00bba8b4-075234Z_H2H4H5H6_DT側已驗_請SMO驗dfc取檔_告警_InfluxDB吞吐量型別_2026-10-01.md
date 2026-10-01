# (DT) run E 開始:`00bba8b4-20261001T075234Z`;H2 / H4 / H5 / H6 DT 側已驗;請 SMO 驗 dfc 取新檔名、告警新欄位、InfluxDB 吞吐量型別

- 日期:2026-10-01 08:00Z;run E:corridor24_16_24,seed 17,07:52:16Z 起 900 秒 → 約 08:07Z 停

## DT 側結果
| # | 項目 | 實測 |
|---|---|---|
| H2 | 檔名 | `A20261001.0753+0000-0754+0000_-1_gnb_208_095_000e31_du1.xml` ✅;notifyFileReady 全部 202(07:53 起每分鐘) |
| H6 | `DRB.UEThpDl` / `Ul` | `8871.2` / `1152.8`(實數一位小數)✅ |
| H5 | pnfRegistration | `softwareVersion=dt-0.1`、`lastServiceDate=2026-10-01`、`manufactureDate=2026-09-29`、`serialNumber=MITLAB RANsim-DT-DU-gnb_208_095_000e31_du1` ✅ |
| H4 | 07:55:21Z 停 e31 facade 30 秒 → notifyNewAlarm | `alarmType=COMMUNICATIONS_ALARM`、`probableCause=COMMUNICATIONS_SUBSYSTEM_FAILURE`、`specificProblem=internalConnectionLoss`、MAJOR;約 07:56 清除;VES 202 ✅ |

## 請 SMO 驗
1. **H2**:dfc 以新檔名取檔、MinIO `ropfiles` / `pm-files-json` 有 07:53 起的檔、InfluxDB 入庫(確認 dfc / 轉換器沒有依賴 `_1_` 的檔名解析)。
2. **H4**:SDNR 07:55:21 的兩筆 internalConnectionLoss(e31 CU / DU)raise 與 clear 配對正確;probableCause 顯示新值。
3. **H5**:SDNR / NCMP 顯示的設備資訊更新(mount 不變)。
4. **H6**:InfluxDB `DRB.UEThpDl` / `Ul` 欄位型別 —— 依前一檔的 (a)(b)(c) 回覆決定。若已變 string 且 SMO 選 (b),DT 下個 run 改回整數。
