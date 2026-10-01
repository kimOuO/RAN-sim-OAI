# (DT) O1 多 DU、多 cell 支援完成,即將以 `livetest_corridor` 劇本測試:gNB e40 一個 DU 兩個 cell

- 日期:2026-10-01 08:40Z;依 mitlab 08:20Z 指示
- 改動(DT 側,adapter patch 0011 + facade + 編排服務):
  - **CM**:一個 DU ME 下有多個 `NRCellDU[id='ManagedElement=<me>,GNBDUFunction=<N>,NRCellDU=<cellLocalId>']`(以前寫死 `NRCellDU=0`,單 cell 時 cellLocalId=0,DN 不變),每個 cell 一個 `NRSectorCarrier=<i>`;每個 cell 各自的 nRPCI / arfcn / 頻寬 / nRTAC / 三個狀態。
  - **PM**:一個檔案裡每個 cell 一個 `<measValue measObjLdn="GNBDUFunction=<N>,NRCellDU=<cellLocalId>">`(TS 32.435 單 NE 多量測物件)。SMO 的 pmlog 會自動變成每 cell 一個 `_measurement`:`SubNetwork=<scn>,ManagedElement=<me>,GNBDUFunction=<N>,NRCellDU=<lc>`。
  - **FM**:`loadDownlinkExceededWarning` 每個 cell 一筆(alarmId 帶該 cell 的 DN);收工 CLEAR 也逐 cell 送。
  - **多 DU**:一個 gNB 有多個 DU 時,每個 DU 一個 ME(`<meid>_du<gNB-DU ID>`),各自 NETCONF / SFTP 埠(第 k 個 DU = 第 0 個 + 1024·k);pnfRegistration、notifyMOIDeletion、run 對照表、通知檔都逐 DU。
  - 單 DU 單 cell 的既有劇本(corridor24_*)輸出完全不變。
- **測試劇本 `livetest_corridor`**(第一次上 O1):3 個 gNB —— e40 `gnb_208_095_000e40`(**cell src lc=0 pci 0、cell spare lc=1 pci 3,同一個 DU**)、e41 nbr、e42 mid。NCI:src 59768832、spare 59768833、nbr 59785216、mid 59801600。
- 請 SMO 在 run 開始後驗:
  1. NCMP / SDNC:`gnb_208_095_000e40_du1` 下有 **兩個 NRCellDU**(0 與 1),各自屬性正確;
  2. PM:`…000e40_du1,GNBDUFunction=1,NRCellDU=0` 與 `…NRCellDU=1` 兩個量測都入庫、值不同;
  3. TEIV:兩個 cell 都出現在拓樸;
  4. N3 rApp(dry-run)能把 e40 的兩個 cell 當兩個候選。
- runId 另檔通知。
