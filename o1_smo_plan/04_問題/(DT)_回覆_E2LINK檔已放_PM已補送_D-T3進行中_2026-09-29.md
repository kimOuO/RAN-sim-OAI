# (DT) 回覆:e00 與 run 的 E2LINK/F1CLINK 檔已放、PM 5 檔已補送、D-T3 已於 14:46:54Z 開始

日期:2026-09-29 15:15Z。來自 DT 端。C1 = 方案 A(以官方 adapter 為準)收到,產生器改為只產連線關係。

## 1. TEIV 連線關係檔(`02_測試/teiv/links/`)
- 新腳本 `gen_teiv_links.py`:只產 `OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION`、`ODUFUNCTION_E2LINK_NEARRTRICFUNCTION`、`ODUFUNCTION_F1CLINK_OCUCPFUNCTION`,aSide 用 adapter id(`urn:oran:smo:teiv:ManagedElement=<meid>,GNBCUCPFunction=0` / `…_du<N>,GNBDUFunction=<N>`),bSide RIC `urn:3gpp:dn:ManagedElement=ric-dt-71,NearRTRICFunction=1`;`ce_source ransim-dt:run-orchestrator`。
- **常駐 e00**:`teiv_links_e00.create.json`(3 條)+ `teiv_links_e00.delete.01–03.json`(單筆)。請發佈 create。
- **D-T3 這場 run(c9ad0776:e10_du1、e11_du1、e12_du2)**:`teiv_links_run_c9ad0776.create.json`(9 條)+ `…delete.01–09.json`(單筆)。請在把 6 個 ME 註冊進 NCMP、adapter 產出 Function 之後再發佈 create;run 結束後逐筆發佈 delete。
- 舊的 `teiv_corridor24_00_08*.json`、`teiv_platform_e00_and_ric*.json` 不再使用(RIC 那兩個物件已在 TEIV 內,保留)。

## 2. PM 補送(檔案都還在 SFTP)
15:13:25–15:13:46Z 每 5 s 一筆,對 `gnb_208_095_000e00_du1` 送 stndDefined notifyFileReady,VES 皆 202:`1316-1330`、`1330-1345`、`1345-1400`、`1400-1415`、`1415-1430`(註:13:16 重建後第一個檔是 1316-1330,沒有 1315-1330)。請確認 5 個時間點入 InfluxDB。

## 3. D-T3(背景程式在看到你們 14:46 的 P3 結果檔後自動啟動)
- **14:46:54Z** 起 run `c9ad0776`(corridor24_00_08),6 ME:`gnb_208_095_000e10/_du1`、`000e11/_du1`、`000e12/_du2`,埠同前(1862–1867 / 1254–1259);「新增 ME」通知已於 14:47:54Z 放在 04_問題(`(DT)_D-T3開始_新增ME_1446Z_…`)。PM 已是 stndDefined、FM 已是 stndDefined。
- **15:22:54Z** 停 e12 的 facade 30 s → 只 `gnb_208_095_000e12_du2` notifyNewAlarm / notifyClearedAlarm。
- **約 15:24Z** 停 run:先 6 筆 notifyClearedAlarm → teardown → 「移除 ME」通知(自動放 04_問題)。
- 這場的 15:00、15:15 整點檔應已進 InfluxDB(4 個 DU)。請依 §2.1 流程做 NCMP 註冊/移除與 TEIV 驗證;連線關係檔見 §1。
