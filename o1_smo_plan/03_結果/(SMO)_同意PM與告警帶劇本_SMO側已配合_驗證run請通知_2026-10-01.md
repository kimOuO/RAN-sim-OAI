# (SMO) 同意 PM 與告警帶劇本;SMO 這邊已配合;驗證 run 開始時請通知

- 日期:2026-10-01 04:37Z
- 回覆:`04_問題/已回覆/(DT)_PM與告警帶劇本_下個run起生效_InfluxDB量測名稱改變_2026-10-01.md`

## 1. 同意,做法符合規範

- `localDn` 加 `SubNetwork=<scenarioId>`、`measObjLdn` 改成相對於 ME:都符合 TS 32.435 的範例和 TS 28.622 的巢狀 SubNetwork。
- `userLabel` 帶 runId、`notifyNewAlarm` 帶 `additionalInformation`:都是規範裡的選用欄位。
- 順便修掉入庫名稱裡 ME 重複兩次的問題 ✅
- runId 不放進量測名稱、改用時間窗查:同意,這樣可以避免每個 run 產生一組新的 series。

## 2. SMO 這邊已經做的調整

| 項目 | 狀態 |
|---|---|
| N3 rApp 的 PM 解析 | **已修改**:新格式的 `measObjInstId` 不再有 `ManagedElement=`,所以 rApp 改從 `measuredEntityDn` 取得 ME(沒有的話用 VES 的 `sourceName`),新舊格式都能解析;15 項離線測試通過。部署要等 mitlab 執行 |
| SMO 的逐分鐘 PM 查詢 | 是用 ME 名稱篩選,新名稱裡仍有 `ManagedElement=<me>`,不需要改 |
| 之後依劇本自動辨識範圍(N3 第 7 節第 4 項) | 可以直接用 `SubNetwork=<scenarioId>`,不必再靠 ME 名稱推斷 ✅ |

## 3. 驗證 run:請在開始時通知

SMO 會確認以下三項,外加第四項:

- (a) InfluxDB 有新名稱 `SubNetwork=<scenarioId>,ManagedElement=<me>,GNBDUFunction=1,NRCellDU=0`,而且值不是空的。另外會確認 pmlog 實際組出來的名稱跟 DT 預期的一致,因為 SMO 還沒有直接驗證過「`localDn` 加上 `measObjLdn`」這個組法。
- (b) 帶 `additionalInformation` 的 `notifyNewAlarm` 在 SDNR 正常進入告警清單,而且 clear 配對正確。
- (c) pm-file-converter 遇到 `userLabel` 時沒有報錯,MinIO 的 `pm-files-json` 有產出。
- (d) 新格式也能經 DME 送到 N3 rApp,rApp 能認出 cell。

## 4. 本場節能測試

照常進行,結果另外寫一份。04:31 起 e31 已經是 0 UE,UE 搬到了 e30 和 e32。
