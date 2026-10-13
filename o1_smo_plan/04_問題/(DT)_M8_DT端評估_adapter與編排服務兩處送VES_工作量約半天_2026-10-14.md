# (DT) M8 VES 改 HTTPS:DT 端評估(回覆草案第 2.3 節「DT 自己評估」)

- 日期:2026-10-14
- 回覆:`01_計畫/(SMO)_M8_VES改HTTPS_三方計畫草案_2026-10-13.md`
- 狀態:僅評估,DT 尚未修改任何東西;整體計畫仍待 mitlab 核准。

## 1. DT 有兩處會送 VES

| 送出端 | 送什麼 | 目前 |
|---|---|---|
| O1 adapter(每 ME 一顆,含常駐 e00) | pnfRegistration、heartbeat、fault、fileReady | URL 由 env `O1_VES_URL` 產生;Basic 帳密**寫死** `sample1/sample1`(dt-entrypoint) |
| run-orchestrator(DT 編排服務) | 收場時的 notifyMOIDeletion、補送 fault CLEARED | Python urllib 直接 POST 到同一個 `O1_VES_URL`,**沒有帶 Basic** |

## 2. 要改的地方

| # | 位置 | 改法 |
|---|---|---|
| 1 | adapter `src/ves/ves_internal.c`(patch 0016) | 上游把 `CURLOPT_SSL_VERIFYPEER/VERIFYHOST` 寫死為 0(**不驗 server 憑證**)。改成:有提供 CA 檔就設 `CURLOPT_CAINFO` 並開啟驗證;沒提供則維持現狀(HTTP 不受影響) |
| 2 | `dt-entrypoint.sh` | 新增 env `O1_VES_USER` / `O1_VES_PASS` / `O1_VES_CA`(CA 檔路徑),取代寫死的 sample1 |
| 3 | adapter 映像 / 掛載 | `ca.crt` 以唯讀掛載進容器(不打進映像,換 CA 不必重建) |
| 4 | run-orchestrator `o1_spawner.py` | 自己送的 VES 加 Basic 與 CA 驗證;新帳密與 CA 路徑由環境變數提供,同時傳給每顆 adapter |
| 5 | 常駐 e00 `docker-compose.d1.yml` | URL、帳密、CA 掛載;重建 e00 兩顆 adapter(各斷約 10 秒) |

- 帳密不寫進 git:由 mitlab 帶外提供後放在 DT 主機的 env 檔(權限 600)。
- 工作量:程式與單元驗證約半天;W2b 當場切換約 15 分鐘(先 e00,再開一場短劇本驗劇本 ME 與收場的 notifyMOIDeletion)。

## 3. 對草案的意見

1. 同意第一期 server TLS + Basic。DT 端會**實際驗證 server 憑證**(上述第 1 項),否則只是加密、無法防假冒。
2. 30418、CA 3 年 / server 1 年:DT 無意見。
3. W2b 驗收請加一項:**劇本收場時編排服務送的 notifyMOIDeletion 走 30418 成功**(控制器據此下線;這一路與 adapter 不同程式)。
4. 一個提醒:fileReady 的 `fileLocation` 帶 SFTP 帳密明文(模擬器預設值)。改 HTTPS 後傳輸已加密,但帳密仍會出現在 SMO 的事件內容與日誌;是否另外處理(例如改金鑰登入),請 mitlab 另行決定,不併入 M8。
