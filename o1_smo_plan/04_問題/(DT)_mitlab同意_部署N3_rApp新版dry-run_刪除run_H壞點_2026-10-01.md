# (DT) mitlab 同意:1. 部署 N3 rApp 新版(逐 cell、spare cell 只看在服務中的 cell,仍 dry-run);2. 刪除 run H 留在 InfluxDB 的 1 個壞點

- 日期:2026-10-01 09:05Z(mitlab 09:04Z 決定)
1. 請 SMO 執行 `deploy.sh dry-run` 部署目前最新版 rApp(含 O1 狀態退出條件、逐 cell、spare cell 處理),部署後把版本與時間寫在 `03_結果/`。切 LIVE 前仍另請核准。
2. 請 SMO 刪除 `SubNetwork=livetest_corridor,ManagedElement=gnb_208_095_000e42_du2,GNBDUFunction=2,NRCellDU=` 這 1 個點,刪後回報。
