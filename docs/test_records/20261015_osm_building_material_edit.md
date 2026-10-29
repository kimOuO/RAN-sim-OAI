# 地圖建築逐棟選取與材質編輯（2026-10-15）

原先產生後的 OSM 建築由 SceneMeshes 當背景顯示，沒有選取事件；右側材質欄位只處理資料庫中的 Building，地圖產生的 test 則沒有 Building 列。模型又依材質合併，直接替換網格材質會一次改到多棟建築。

## 修改

- 依既有 OSM extrude 的頂點／屋頂排列還原各棟建築，保留相鄰建築的分界。無法辨識的掃描網格保持原網格，不假定為逐棟建築。
- 3D 點選與高亮、左側建築搜尋清單、右側材質選單及儲存後讀回。放置模式仍使用原表面落點流程；裁切掉的表面不接收選取。
- 新增 `Field_scene/SceneGeometryController/set_material`：只處理選定場景的網格及材質目錄項目，執行中／預算中的場景拒絕修改。
- 第一次儲存會建立該場景自己的 XML／PLY 修訂，更新 geometry_source.path；不覆寫原始或其他場景共用的資產。幾何不變，只有選定物件的 ITU 材質參照改變。
- 清除該場景 Run 的 cache_path；geometry_source.path 的改變也會改變現有通道快取指紋。後續快取模擬需要重新預算。
- 網格中繼資料有快取；編輯器並行載入，材質更新重用既有幾何，避免每次重抓全部建築。

## 驗證

- 5 項 Django 測試通過：相鄰建築分離、單棟修改與幾何不變、共用場景隔離、快取標記清除、執行狀態與輸入／路徑驗證。
- TypeScript typecheck、修改檔案 ESLint、Django system check 通過。
- 用 test 的暫時副本進行 Chromium 實測：354 棟建築與 1 個地面；直接點 3D 建築成功，只修改 1 棟為 itu_wood；全部 geometry_key 保持一致。重新開頁與從左側清單選取後，材質仍為木材。沒有頁面 JavaScript exception。
- Physics 容器唯讀載入修改後的 XML，Sionna 成功辨識 itu_wood。預設 merge_shapes=True，最後依材質合併成 3 個物件（glass、concrete、wood），沒有執行通道預算或模擬。
- 原始 test XML 的 SHA-256 前後一致：`5cf7c71c70599d4895cd7e723d19af7b05991ffdae2d5796d08f9795759cf39d`。
- 驗證資料與截圖：`/tmp/xapp-dt-audit/material-editor-browser.json`、`material-editor-before.png`、`material-editor-saved.png`。驗證副本與其專用資產測完後移除，未改動使用者的 test 場景材質。

本次未重啟 physics、未重跑 test，也未改變模擬時鐘或移動／換手邏輯。場景管理後端以 Gunicorn HUP 載入更新。
