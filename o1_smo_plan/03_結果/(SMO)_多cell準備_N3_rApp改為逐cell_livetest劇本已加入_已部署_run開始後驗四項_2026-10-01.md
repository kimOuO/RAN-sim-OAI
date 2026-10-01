# (SMO) 多 cell 準備:N3 rApp 改成以 cell 為單位,`livetest_corridor` 劇本已加入(待 mitlab 部署);run 開始後驗四項

- 日期:2026-10-01 08:33Z
- 回覆:`04_問題/已回覆/(DT)_多DU多cell支援_即將以livetest_corridor測試_gNB_e40有兩個cell_2026-10-01.md`

## 1. SMO 端檢查

| 元件 | 多 DU / 多 cell 是否能處理 | 說明 |
|---|---|---|
| pmlog / InfluxDB | ✅ 不用改 | 每個 `measValue` 一個 `_measurement`,`NRCellDU=0`、`NRCellDU=1` 會是兩個不同的 series |
| dfc / 轉換器 | ✅ 不用改 | 一個檔案裡有多個 `measValue` 是 32.435 的標準格式 |
| ME 生命週期控制器 | ✅ 不用改 | ME 的比對規則 `^gnb_\d{3}_\d{3}_[0-9a-f]{6}(_du\d+)?$`,`base_meid` 會去掉 `_du<k>`,所以多個 DU 的 ME 名稱都能處理 |
| **N3 rApp** | ❌ → **已修改** | 原本假設「一個 gNB 一個 cell」:PM 以 CU 名稱為鍵(e40 的兩個 cell 會互相覆蓋)、NCI 查詢在 CU 有超過一個 cell 時直接報錯、O1 cell 狀態以 CU 為單位 |

## 2. N3 rApp 的修改(以 cell 為單位)

- cell 的鍵改成 `<cu>/<cellLocalId>`,例如 `gnb_208_095_000e40/1`:
  - PM 從 `measObjLdn` 的 `NRCellDU=<lc>` 取;
  - CM 從 NRCellDU / NRCellCU 的 `cellLocalId` 屬性取。
- **劇本的範圍改從 O1 讀**:ME 上線時,讀各 CU 的 NRCellCU 清單,不再寫死。NCI = gNBId × 2^(36 − gNBIdLength) + cellLocalId,每個 cell 各算一次。
- O1 的 `operationalState` 改成逐 cell 判斷,節能候選也逐 cell 選。
- 設定新增劇本 `livetest`(e40 / e41 / e42,dry-run)。
- **測試**:
  - 22 項離線測試通過,其中兩項專測多 cell。e40 的 src(lc 0)和 spare(lc 1)會被當成兩個候選;spare 沒有 UE 時會被選中,policy 的 NCI 是 59768833。
  - 對現在的 SDNC 實際讀過 e00:它有兩個 NRCellCU,讀到兩個 cell,NCI 58720256 / 58720257。
- **部署要等 mitlab 執行**(仍是 dry-run):`SMO_OSC/dep/n3-es-rapp/deploy.sh dry-run`

## 3. run 開始後,SMO 會驗

1. **SDNC / NCMP**:`gnb_208_095_000e40_du1` 下有 NRCellDU 0 和 1,各自的 nRPCI(0 / 3)、nRTAC、三個狀態都正確;NCMP 有 CM handle。
2. **PM**:`…000e40_du1,GNBDUFunction=1,NRCellDU=0` 和 `…NRCellDU=1` 兩個 series 都入庫,值不同。
3. **TEIV**:兩個 cell 都出現在拓樸(NRCellDU 的實體)。
4. **N3 rApp**:日誌的 scope 會列出 `e40/0、e40/1、e41/0、e42/0` 四個 cell,每期都有四個 cell 的值。

runId 請另檔通知。
