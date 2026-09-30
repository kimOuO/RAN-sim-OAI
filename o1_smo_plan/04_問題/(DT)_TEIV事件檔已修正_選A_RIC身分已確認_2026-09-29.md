# (DT) TEIV 事件檔已依 §2.2 修正(方案 A),RIC 身分已由 RIC 團隊確認;D-T1 結案收到

日期:2026-09-29 10:50Z。來自 DT 端。

## 修正內容(兩個檔都已覆蓋,在 `02_測試/teiv/`)
- **方案 A**:DU 側掛在自己的 ManagedElement `<meid>_du<N>` 下,id 與 O1 / PM 的 DN 一致:
  - `urn:3gpp:dn:ManagedElement=gnb_208_095_000e00_du1,ODUFunction=1,NRCellDU=0`(O1 是 `GNBDUFunction=1`,TEIV 模型名為 `ODUFunction`,其餘完全相同)
  - 新增 `MANAGEDELEMENT_MANAGES_ODUFUNCTION` 從 `<meid>_du<N>` 指向 ODUFunction;`ODUFUNCTION_F1CLINK_OCUCPFUNCTION` 跨兩個 ME 連回 CU-CP。
  - run 檔的 DU id 取自 orchestrator 的實際值(e10_du1、e11_du1、**e12_du2**),之後 orchestrator 會在通知旁產 `me_map.json` 供產生器讀。
- **e00 的 NRCellDU 改為 1 個**(`NRCellDU=0`,PCI 1),與 O1 目前呈現一致;NRCellCU 仍 2 個(O1 CU 也是 2 個)。真實拓樸是 2 cell 同 DU,O1 只顯示第一個是 adapter 單 NRCellDU 的限制,已列 DT 待辦(讓 O1 DU ME 呈現多 NRCellDU);屆時 TEIV 同步補第二個。
- **RIC-A 身分(RIC 團隊 10:45Z 確認為 ric-dep 預設,未改)**:`nearRtRicId` = 0xAACCE = **699598**,`pLMNId` **310/411**。已寫入 `teiv_platform_e00_and_ric.json`。
- 檔案統計:常駐檔 10 entity / 11 relationship;run 檔 21 entity / 21 relationship。id 字元集與 relationship sourceIds≥2 已再檢查。

## 請 SMO 端(mitlab 核准後)
1. 建專用 KafkaUser,先發佈 `teiv_platform_e00_and_ric.json`。
2. 查 `topology-exposure` RAN domain:ManagedElement ×3(e00、e00_du1、ric-dt-71)、OCUCPFunction、ODUFunction、NearRTRICFunction、NRCellCU ×2、NRCellDU ×1、NRSectorCarrier ×1;relationship 11 條;回報 ingestion validation log。
3. run 檔留到下一個 run 再發(create 隨「新增 ME」通知、delete 隨「移除 ME」通知)。

## D-T1 結案:收到,謝謝。同名 slot 重啟不需清理 mount 也記下了。
