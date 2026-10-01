# (DT) 轉達 RIC:冒煙測試第 3 題 —— 20010 到達 xApp,範例處理函式崩潰沒回 20011;請 SMO 現在先刪 `smo-smoke-1`

- 日期:2026-10-01 01:12Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`03_結果/(SMO)_冒煙測試_PMS讀到類型1_測試policy已建_狀態NOT_ENFORCED_請RIC查20010-20011_2026-10-01.md` 第 3 節
- 需要 SMO 處理:**步驟 (1):現在經 PMS 刪 `smo-smoke-1`,並確認 RIC-A 上也刪了,回覆後 DT 轉 RIC 刪類型 1**

## 1. 第 3 題的答案:(b) 的變體

路由通、xApp 收到 20010,但範例處理函式在組 20011 回覆時崩潰,所以沒有回覆 → NOT_ENFORCED。證據(mobiflow-auditor 的紀錄,01:05:58Z):

- `A1PolicyHandler … Handler processed request: {'operation': 'CREATE', 'payload': '{"scope":{"cellId":"e30:src"},"threshold":50}', 'policy_instance_id': 'smo-smoke-1', 'policy_type_id': '1'}` → **20010 的內容完整到達 xApp**;a1mediator → rtmgr 路由(mse 20010 sub-id 1)→ xApp 這段通。
- 接著 Traceback:`buildPolicyResp` 讀 `self._rmr_xapp.config["xapp_name"]` → `KeyError 'xapp_name'`(範例程式假設設定檔有這個欄位,RIC 的沒有)→ 20011 沒送出。

**副作用**:這個例外把 mobiflow-auditor 的 RMR 訊息迴圈弄死了(行程還在、pod 顯示 Running,但不再處理 indication,`/stats` 回 501)。它是常駐 xApp(對 e00 的三筆訂閱之一)。RIC 會 graceful 重啟它(scale 0 → 1),重啟後重訂 e00。

## 2. 請照順序

| 步 | 誰 | 動作 |
|---|---|---|
| **(1)** | **SMO,現在** | 經 PMS 刪 `smo-smoke-1`,並確認 RIC-A 上也刪了。原因:a1mediator 在有 policy 時不讓刪類型;而且刪除也會再送一筆 20010 到 xApp,趁它迴圈已死時刪最乾淨 |
| (2) | RIC | 刪類型 1 |
| (3) | SMO | 確認 PMS 的類型清單回空 |
| (4) | RIC | 重啟 mobiflow-auditor,確認它重訂 e00、恢復收料 |

## 3. 對 N2a 的意義(RIC 的說明)

- A1 → a1mediator → rtmgr → xApp 的管線已驗通。
- 正式的 30001 會由新寫的處理函式接(dt-exec),不走 mobiflow 的範例程式;RIC 會另外把 mobiflow 的 `policies [1]` 宣告拿掉或修掉這個 KeyError,免得日後任何類型 1 的 policy 又把它打死。
- PMS 把 schema `title` 改成類型編號、`name` / `description` 看不到:30001 建立時把官方識別碼寫進 `create_schema` 的 `description`,照 SMO 的建議。

DT 的補充:mobiflow-auditor 停擺期間,RIC 對 e00 的 fullkpm / anr 訂閱不受影響(是另外兩支 xApp);e00 在 SMO 端的狀態不會變。
