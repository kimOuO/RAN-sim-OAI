# (DT) 注意:run `00bba8b4-20261001T064643Z`(06:46:25Z 起)的 notifyFileReady 被 VES collector 回 **400**,PM 檔沒有被 dfc 取走;H1 新值有欄位不過 collector 的 stndDefined 驗證,DT 修正中

- 日期:2026-10-01 06:52Z
- 現象:三個 DU adapter 自 06:47:00Z 起每分鐘的 notifyFileReady 都收到 HTTP 400(pnfRegistration、heartbeat 正常 202)。PM 檔在 adapter 的 SFTP 目錄裡都在,只是通知沒進去。
- 懷疑:H1 新加的 `jobId`、或 `href` 指向 PerfMetricJob 的寫法,不在 collector 載入的 28.532 OpenAPI schema 允許範圍。DT 正核對 schema;修正後會先在這場 run 內熱替換模板,並補送這段期間的檔案通知。
- 請 SMO 若方便,從 collector 日誌抓一筆 400 的回應原文(通常會寫哪個欄位不合 schema),放 `03_結果/`。
