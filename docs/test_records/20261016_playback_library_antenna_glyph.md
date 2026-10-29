# 回放清單 / 播放器重做、gNB 天線外觀分類（2026-10-16）

## 回放
- 新增 orchestrator `Run_telemetry_archive/RunExecutionReader/read`：依 (scene_run, run_seq) 彙總每次執行的起訖時間、模擬時長、量測視窗數、結束時 UE / cell 數、換手 / RLF / 控制命令數。測試 `RunExecutionReaderTest`（archive 測試 14 項通過）。以 Gunicorn HUP 載入，當時無執行中劇本。
- 監控前端新增 `/playback` 回放清單（頂部導覽「回放」）：卡片顯示劇本名稱、組別（scene.category）、通道模式、第幾次執行、執行時間、模擬 / 實際時長與倍速、規模、事件數，以及場景俯視縮圖（建築、UE 路徑、gNB）。可依組別、時間、名稱篩選。
- `/runs/<id>/playback`：未帶 `?seq=` 時列出該劇本保留的執行；帶 `?seq=` 進播放器。播放器一條時間軸（含換手 / RLF / RIC / SON 事件標記）同步驅動 3D、UE 卡片、四張每 cell 圖表（PRB、吞吐、附著 UE、SINR，皆有目前時間游標、點圖跳轉）與事件清單（點事件跳轉）。播放速度 1–60×。
- 限制：每個劇本只保留最近 3 次執行（既有歸檔保留政策）；縮圖只用場景樹，掃描 / OSM 網格不畫。

## 天線外觀
- 編輯器 CellMarker 與監控 3D 依 cell 生效的天線範本（RU 範本，否則場景預設）分三類：全向（iso / dipole：直立偶極 + 水平環，無方向）、扇區（TR 38.901：朝方位角的直立面板 + 方向棒）、mMIMO（TR 38.901 且元件數 ≥ 32：大面板 + 元件格點）。cell 標籤加註類型。
- 以暫時預覽頁實際算繪三類外觀確認可分辨，預覽頁已刪除。

## 其他
- 監控頂部導覽不再換行：劇本分頁區橫向捲動。
- TimeSeriesChart 新增 `cursor`、`onPick`（回放用，其他頁不受影響）。
- 兩套前端 TypeScript、ESLint 通過。
