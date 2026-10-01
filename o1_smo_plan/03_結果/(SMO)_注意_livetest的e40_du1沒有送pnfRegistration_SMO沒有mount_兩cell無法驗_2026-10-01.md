# (SMO) 注意:livetest 的 `gnb_208_095_000e40_du1` 沒有送 pnfRegistration,SMO 沒有它的 mount;e40 的兩個 cell 現在無法驗

- 日期:2026-10-01 08:36Z
- run:`7fea27f8-20261001T083136Z`(`livetest_corridor`;runId 取自 pnfRegistration 的 additionalFields)
- **請 DT 查 e40_du1 的 adapter**

## 1. SMO 看到的

| ME | pnfRegistration(VES collector) | oamPort | SDNC mount |
|---|---|---|---|
| gnb_208_095_000e40 | 08:31:40.875 | 1958 | connected |
| **gnb_208_095_000e40_du1** | **沒有收到** | (預期 1959) | **沒有** |
| gnb_208_095_000e41 | 08:31:41.579 | 1960 | connected |
| gnb_208_095_000e41_du1 | 08:31:41.813 | 1961 | connected |
| gnb_208_095_000e42 | 08:31:42.184 | 1962 | connected |
| gnb_208_095_000e42_du2 | 08:31:42.414 | 1963 | connected |

- collector 的 error.log 沒有任何 e40_du1 的紀錄,所以**不是被 collector 擋下,而是根本沒有送到 SMO**。
- MinIO `ropfiles/gnb_208_095_000e40_du1/` 目前也沒有檔案,看起來 notifyFileReady 同樣沒到。
- ME 生命週期控制器只能處理收到的 5 個 ME(08:32:35 已登錄 NCMP、PMS、E2 link)。

## 2. 影響

- 驗證項目 1(SDNC 兩個 NRCellDU)、2(e40 兩個 cell 的 PM)、3(TEIV 的兩個 cell)目前都**無法驗**。
- N3 rApp:範圍已經從 e40 CU 的 NRCellCU 讀到 `e40/0`、`e40/1`、`e41/0`、`e42/0` 四個 cell ✅。但 e40 的兩個 cell 沒有 PM,所以 rApp 不會做判斷;這是正確的保守行為。
- e41、e42 正常:例如 e41_du1 的 NRCellDU=0 讀到 pci 1、nRTAC 40960、UNLOCKED / ENABLED / ACTIVE。

## 3. 猜測(供 DT 查)

- 多 DU 的新功能:第 k 個 DU 的埠是第 0 個 + 1024·k。e40 只有一個 DU,但它有兩個 cell,可能是多 cell 的路徑讓 e40_du1 的 adapter 沒有啟動,或啟動時出錯。
- 請看 e40_du1 adapter 的日誌,以及 1959 埠有沒有在聽。

DT 修好後(重送 pnfRegistration 或重開 run)請通知,SMO 會立刻驗四項。

## 4. 原因(DT 08:45Z)

e40 第二個 cell 的 NRSectorCarrier 缺必要屬性 `sectorEquipmentFunctionRef`,sysrepo 拒絕寫入 → e40_du1 沒有 CM、沒有註冊、沒有 PM。已修(patch 0011b),跟 SMO 看到的現象一致。run H 開始後,SMO 會驗四項,並確認 run G 收場時 ME 生命週期控制器已把 5 個 ME 正確下線。
