# (DT) A6 / I2 後續:DT 端兩項已修;請 SMO 查「多 DU 的 F1 連結每 90 秒重建」,並準備複驗

- 日期:2026-10-10
- 回覆:`03_結果/(SMO)_A6_I2_C19結果_A6與I2通過_C19正常路徑三輪通過_補回路徑未重現_2026-10-10.md`
- mitlab 指示:A6 / I2 / C19 留下的問題全部查清並解決,DT 統籌;順序為 DT → SMO → RIC。

## 1. DT 端已處理(供 SMO 知悉)

| 項目 | 原因 | 修正 | 狀態 |
|---|---|---|---|
| e62 netopeer2-server 消失 | 上游 entrypoint 以背景常駐啟動 netopeer2,錯誤只寫 syslog(容器內沒有),且不等它就緒就啟動 gnb-adapter | netopeer2 改前景執行、輸出進 docker logs;結束就記錄結束碼並 2 秒內重啟;830 埠就緒後才啟動 gnb-adapter | 本機驗證:強制結束後 2 秒內恢復、NETCONF get 前後皆正常;18 顆同時啟動皆就緒。新映像待 mitlab 核准上線 |
| VES notifyFileReady `Timeout was reached` | 上游 adapter 寫死 curl 連線 1 秒、整體 1 秒,失敗不重送;17 顆同時在 PM 邊界送出時超過 1 秒 | patch 0013:連線 2 秒、整體 4 秒(上限 < 5 秒,避免拖到 PM 取樣使週期被標 suspect) | 已編譯,隨上述新映像上線 |
| 第二個 DU 的 FULLKPM 計數為 0 | CU 只向第一個 DU 讀 dump_pm | CU 改為向 F1 Setup 登記的每個 DU 讀,依 cell 對應 | 已修,CU 單元測試全過 |

- 「collector 無錯誤紀錄」與上述吻合:請求多半已送達,只是回應超過 1 秒被 adapter 判逾時。若 SMO 的 VES collector 有存取紀錄(回應時間),請提供 08:07Z、08:10Z 的數值,供確認 4 秒是否足夠。

## 2. 請 SMO 處理:多 DU 的 F1 連結每 90 秒被重建

DT 端提供的事實(S3 e60,一個 CU-CP + 兩個 DU):

| ME | 單元 | GNBDUFunction id(gNBDUId) | 備註 |
|---|---|---|---|
| gnb_208_095_000e60 | CU-CP | 無 GNBDUFunction | adapter 設定的 gnb-du-id 取第一個 DU 的值,但 CU-CP ME 不輸出 GNBDUFunction |
| gnb_208_095_000e60_du1 | DU | 1 | cell src |
| gnb_208_095_000e60_du2 | DU | 2 | cell spare |

- 兩個 DU ME 的 FDN 不同(ManagedElement 不同、gNBDUId 也不同),DT 端資料沒有重疊的識別。
- 請 SMO 檢查控制器產生 F1 連結時的 id / 比對鍵:若只以「CU」或「gNB」為鍵(未含 gNBDUId 或 DU ME 名稱),兩個 DU 會互相覆蓋,每次對帳週期(90 秒)就重建一次。
- 請在 `03_結果/` 回報:根因、修正內容、預計可複驗時間。若查出是 DT 送出的資料造成,請指明欄位,DT 立即修改。

## 3. 複驗(待 mitlab 定時間;DT 另行通知)

- 內容:S3 `mdu_corridor_test` 單場(含 e60 兩個 DU),必要時加一場讓 ME 數達 17。
- 驗收:(a) 所有 ME 的 NETCONF 全程可掛載,無 netopeer2 消失;(b) adapter 無 VES 逾時;(c) TEIV 中 e60_du2 → e60 的 F1 連結不再重建;(d) RIC / InfluxDB 的 e60:spare PRB 在有 UE 時不為 0。
- C19 補回路徑(helm 滾動換版)將與 RIC 另排,屆時請 SMO 依原 C19 手動腳本配合 PUT / DELETE。
