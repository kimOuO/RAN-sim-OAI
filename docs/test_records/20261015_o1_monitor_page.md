# O1 監控頁 PM / CM / FM 資訊整合（2026-10-15）

依現有 Run 監控頁的 Panel、StatTile、TimeSeriesChart 與表格版型擴充 O1 頁面。

- PM：DT 歸檔的每 cell PRB、吞吐與附著 UE 趨勢，可篩選 cell 與時間範圍；另外呈現真正 O1 PM XML、suspect、量測內容與 VES HTTP 回覆。兩種資料來源分別標示，DT 趨勢不當成 SMO 入庫資料。
- CM：以唯讀 sysrepo export 取得 O1 管理資料，呈現 ME、cell、PCI、TAC、ARFCN、頻寬、PRB、PLMN、管理／運作狀態及 PerfMetricJob。無快照時明確標示為目前劇本設定，不推定歷史運作狀態。
- FM：目前告警與歷史 raise/clear 紀錄。只在全部預期網元都讀取成功時提供目前告警數，缺資料顯示未查證。Run 停止時由 orchestrator 送出的 clear 也保留傳送結果。
- 每 10 秒更新與手動重新整理；停止前保存經過欄位篩選的 CM/FM 與 PM 資料。以每次執行的 O1 runId 分開保存，並依開始時間過濾舊紀錄。未改變 PM 週期、模擬參數或 SMO 設定。
- 不回傳原始 VES、SFTP fileLocation、帳密或 token；VES HTTP 202 與 SMO 取檔／入庫保持區別。

## 驗證

- 13 項 unittest 通過，涵蓋 XML 解析、suspect、不同執行的隔離、容器移除後快照、告警 clear、缺少網元與帳密過濾。
- TypeScript typecheck、修改檔案 ESLint、Django system check 通過。
- 直接唯讀驗證常駐 D1 的 CU-CP／DU adapter：CM/FM 與各 96 份 PM XML 均成功解析，沒有對 D1 發送控制或 VES 通知。
- `test` O1 API 回 HTTP 200；本次執行讀到 202 個趨勢點、5 個 cell、4 份 PM 傳送紀錄與 88 筆通知，沒有查詢警告。該次執行早於此功能，沒有保留 XML 內容或 O1 CM 快照，頁面據實標示。
- Chromium 實測 cell／時間篩選、PM 紀錄選擇、心跳顯示、VES 回覆篩選、手動更新、自動輪詢及桌面／390px 手機版面；沒有頁面 JavaScript exception。手機頁寬 390px，表格在區塊內橫向捲動。另有既有 favicon.ico 404，與 O1 API 無關。
- 瀏覽器紀錄及截圖：`/tmp/xapp-dt-audit/o1-dashboard-check.json`、`o1-dashboard-desktop.png`、`o1-dashboard-mobile.png`；API 樣本：`o1-monitor-api.json`。

本次沒有重跑劇本、觸發告警、改變 RAN 組態或查證 SMO 接收端的取檔與入庫。後端以 Gunicorn HUP 載入更新，載入前確認沒有執行中的劇本。
