# (DT) TEIV 產生器已補 E2LINK;下一個 run 的處理順序確認

日期:2026-09-29 11:10Z。來自 DT 端。
- 產生器預設 `--ric-meid ric-dt-71`,每顆 gNB 加 `OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION` 與 `ODUFUNCTION_E2LINK_NEARRTRICFUNCTION`(bSide `urn:3gpp:dn:ManagedElement=ric-dt-71,NearRTRICFunction=1`),delete 事件同步帶這些 id。`teiv_corridor24_00_08.json` / `.delete.json` 已重產(21 entity / 27 relationship)。
- 下一個 run 的處理順序(run 開始:通知 + create 檔 → SMO 確認 mount、加 PMS、發佈 create、驗證;run 結束:CLEAR → teardown → 通知 + delete 檔 → SMO 刪 mount、發佈 delete;同名 slot 立即重啟:不刪 mount,TEIV 若已 delete 就重新 create):**確認照辦**。
