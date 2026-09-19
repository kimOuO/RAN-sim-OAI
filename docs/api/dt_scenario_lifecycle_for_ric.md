# DT 端場景生命週期 —— 給 RIC 端的對照表

目的:RIC 端看到場景被宣告或消失時,能直接對照是哪一種情況、要不要處理。
對應版本:orchestrator 2026-09-19。

**ID 對應:閘道的 `scenarioId` = 我們的 `scene_run_uuid`**,不需要額外對照表。
`nodes.cu.meid` 由我們配的 gNB ID 推導(`gnb_208_095_000eXX`)。

---

## 1. 我們什麼時候會動閘道

| 情況 | 對閘道做什麼 | 之後會不會自己回來 |
|---|---|---|
| 啟動 run | `POST /v1/scenarios`(帶 `cleanStale: true`)→ 部署場景 xApp → E2 Setup 完成後 `POST /activate` | — |
| 手動停止 run | `DELETE /v1/scenarios/{id}` + `POST /v1/rnib/clear` | 不會 |
| **劇本跑完自動停止** | 同上 | 不會 |
| **健康檢查判定不健康 → 自動重啟** | 先 DELETE,約 20–30 s 後重新 `POST /v1/scenarios` | **會**,同一個 scenarioId 重新宣告(你們的 `run` 會 +1) |
| **RIC 端異常(SCTP 未連線)** | **什麼都不做** | — |

### 1.1 自動停止(2026-09-18 起)
UE 劇本的模擬時間跑完 `duration_sec` 就自動走正常停止流程。
run 的 `notes` 會留 `auto-stop <時間>: 劇本跑完 <實際> / <設定> s`。

### 1.2 自動重啟(2026-09-15 起)
我們這邊的容器持續不健康超過門檻(預設 120 s)就重啟整個 run:先停(含 DELETE 場景)再起(重新宣告)。
- 觸發原因只看**我們自己的容器**:CU / DU / RU / UE / adapter 的容器掛掉、HTTP 不通、記憶體逼近上限、依賴鏈斷掉。
- **上限:同一個 run 一小時最多 3 次**,超過就停手只告警,不會無限重建。
- run 的 `notes` 會留 `auto-restart <時間>: <原因>`。

### 1.3 RIC 異常時我們不動場景(2026-09-16 改)
當時 RIC 的 SCTP 斷線,我們的健康檢查把 run 判成不健康,每 10 分鐘重啟一次,模擬一直被打斷、對 RIC 也沒幫助。
現在「SCTP 未連線」被明確歸類為**外部問題**:狀態標成 degraded 讓我們的監控頁看得到,但**不觸發自動重啟、不拆場景**。

所以:**RIC 當機或重啟時,我們這邊不會自動拆場景。** 你們看到場景消失,一定是上表其他幾種情況之一。

---

## 2. gNB ID(meid)是動態配的

每次啟動 run 從 `0x000e01`–`0x000e1ff` 挑一個當下沒人用的槽位,**編號不固定、不對應特定實體節點**。
停止時釋放,之後可能被別的場景重用 —— 這也是你們加 `scenario` / `run` 標籤要解決的問題。

配槽位與寫回狀態在同一把鎖內完成,`starting` 狀態也算佔用(2026-09-16 修:兩個 run 同時自動復原曾拿到同一槽位)。

需要我們避開某些編號的話告訴我們範圍,可以把分配起點調開。

---

## 3. 我們如何對照兩邊的資料

- 我們自己的遙測存在 orchestrator 的資料庫,每筆帶 `scene_run_uuid`(全域唯一、不重用),所以不受 meid 重用影響。
- 要和 RIC 端數據對照時,我們會用閘道的 `/v1/scenarios/{id}/series` 與 `/latest`,`{id}` 直接放 `scene_run_uuid`。

---

## 4. 查一筆場景消失的原因(我們這邊可提供)

給我們 `scenarioId` 與時間,我們可以從這三處查：

| 來源 | 內容 |
|---|---|
| orchestrator 日誌 | `RIC gateway register/DELETE`、`auto-stop`、`auto-restart`、健康檢查判定 |
| registry `scene_run` | `status`、`started_at`、`stopped_at`、`notes`(auto-stop / auto-restart 原因) |
| registry `launch_request` | 每次 start / stop 的請求與結果 |

**範例(2026-09-19 上午 e01–e04 被刪)**:我們的編排器在 9/18 17:20 UTC 到 9/19 13:15 UTC 之間沒有任何日誌,
期間沒有 run 在執行,也沒有任何 DELETE 紀錄 → 該次刪除不是我們發出的。
