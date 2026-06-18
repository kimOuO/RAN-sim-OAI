# RC 指令拉取 API（RcObservationReader）

對外提供「拉取 RC（RAN Control）指令觀察」的查詢 API。供 user / xApp 監控端輪詢
RIC 對 CU 下達了哪些 E2-SM-RC 控制（PRB quota、Handover…）。

- **狀態**：已實作並驗證（quota / ho / unsupported 三型別）。
- **資料來源**：沿用 `ControlAction`（CU `e2_control_actor` 在每個 E2 RC 分支
  `push_control_action` 落地到 Omniverse DB）。**不另解析 CU log**。
- **實作位置**：`Omnivers_platform/Omniver-RAN/main/apps/ran/actors/control_action_actor.py`
  → `RcObservationReader`；路由 `main/apps/ran/api/urls.py`。

---

## Endpoint

```
POST http://<omniver_backend>:8001/api/v0.1/RAN/RC/RcObservationReader/read
Content-Type: application/json
```

> 註：本服務統一走 POST + JSON body（同 codebase 其它 reader）。

---

## Request 欄位（HTTP body，全部選填）

| 欄位 | 型別 | 必填 | 預設 | 說明 | 範例 |
| --- | --- | --- | --- | --- | --- |
| `action_type` | string | 否 | 全部 | RC 型別篩選；省略 = 不分型別全回 | `"rc_control_quota"` |
| `since` | string (ISO 8601) | 否 | 無下界 | 只回 `observed_at` **≥** since（含界） | `"2026-06-16T10:30:00Z"` |
| `until` | string (ISO 8601) | 否 | 無上界 | 只回 `observed_at` **≤** until（含界） | `"2026-06-16T10:30:15Z"` |
| `limit` | int | 否 | `50` | 單次最多回幾筆，**上限 200**（超過自動夾到 200，<1 夾到 1） | `100` |

- `action_type` 值域：`rc_control_quota` ｜ `rc_control_ho` ｜ `rc_control_unsupported`。
  其它值 → HTTP 400。
- 最簡呼叫：`{}` → 回最新 50 筆、全型別。

---

## Response

外層統一格式：

```json
{
  "status": "ok",
  "data": { /* 見下 */ },
  "message": null,
  "timestamp": "2026-06-16T10:30:16Z"
}
```

`data` 欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `items` | `RcCommandObservation[]` | 符合條件的 RC 指令觀察，依 `observed_at` **遞增**排序 |
| `count` | int | `items` 筆數 |
| `latest_observed_at` | string ｜ null | 本批最新 `observed_at`；**持續輪詢時下次帶為 `since`**；無資料為 `null` |
| `has_more` | bool | 是否因 `limit` 截斷、同條件下仍有更多記錄 |

### 事件物件 `RcCommandObservation`（在 `data.items[]`）

| 欄位 | 型別 | 說明 | 範例 |
| --- | --- | --- | --- |
| `uuid` | string | 該觀察唯一識別（**輪詢去重用**）。目前為 `ca{id}` | `"ca7"` |
| `observed_at` | string (ISO 8601, `Z`) | 控制器觀察到的時刻（= CU 落地該 control 的 `action_ts`） | `"2026-06-16T10:30:12Z"` |
| `action_type` | string | `rc_control_quota`｜`rc_control_ho`｜`rc_control_unsupported` | `"rc_control_quota"` |
| `e2_style` | string | E2AP Style | `"2"` |
| `e2_action` | string | E2AP Action | `"6"` |
| `target` | string | 作用對象 | `"cu"` |
| `params` | object | 指令參數（已 parse）。quota=`{min,max,dedicated}`；HO=`{rrc_ue_id}` | `{"min":0,"max":10,"dedicated":0}` |
| `evidence` | string | 證據來源 | `"cu_log"` |
| `raw` | string | 原始 CU log 行（目前由欄位重建，見「實作備註」） | `"[E2 AGENT][RC] Style 2/Action 6: min=0% max=10% dedicated=0%"` |

---

## 範例

**只拉換手**
```bash
curl -X POST http://localhost:8001/api/v0.1/RAN/RC/RcObservationReader/read \
  -H 'Content-Type: application/json' \
  -d '{"action_type":"rc_control_ho","limit":20}'
```

**時間窗 + 全型別**
```bash
curl -X POST http://localhost:8001/api/v0.1/RAN/RC/RcObservationReader/read \
  -H 'Content-Type: application/json' \
  -d '{"since":"2026-06-18T00:00:00Z","until":"2026-06-18T06:00:00Z"}'
```

**回應(quota 範例)**
```json
{
  "status": "ok",
  "data": {
    "items": [
      {
        "uuid": "ca7",
        "observed_at": "2026-05-27T09:06:19.175749Z",
        "action_type": "rc_control_quota",
        "e2_style": "2",
        "e2_action": "6",
        "target": "cu",
        "params": { "min": 0, "max": 3, "dedicated": 0 },
        "evidence": "cu_log",
        "raw": "[E2 AGENT][RC] Style 2/Action 6: min=0% max=3% dedicated=0%"
      }
    ],
    "count": 1,
    "latest_observed_at": "2026-05-27T09:06:19.175749Z",
    "has_more": false
  },
  "message": null,
  "timestamp": "2026-06-18T05:23:42Z"
}
```

**回應(HO 範例)**
```json
{
  "uuid": "ca881184",
  "observed_at": "2026-06-18T05:30:00Z",
  "action_type": "rc_control_ho",
  "e2_style": "3",
  "e2_action": "1",
  "target": "cu",
  "params": { "rrc_ue_id": 12345 },
  "evidence": "cu_log",
  "raw": "[E2 AGENT][RC] Style 3/Action 1: handover rrc_ue_id=12345"
}
```

---

## 持續輪詢（去重 + 不漏）

```
1. 第一次：{"limit":100}
2. 記下回應的 data.latest_observed_at
3. 下次：{"since": <上次 latest_observed_at>, "limit":100}
4. 用每筆 uuid 去重（邊界同秒可能重抓到上批最後一筆，因 since 為含界）
5. has_more=true → 立刻再拉一輪（別等下個週期），直到 has_more=false
```

---

## 錯誤

| 情況 | HTTP | body |
| --- | --- | --- |
| `action_type` 不在值域 | 400 | `{"status":"error","data":null,"message":"invalid action_type: <值>","timestamp":"..."}` |

---

## 型別對應（內部）

| `action_type` | `action_label` | (e2_style, e2_action) |
| --- | --- | --- |
| `rc_control_quota` | `PRB_QUOTA` | (2, 6) |
| `rc_control_ho` | `HANDOVER` | (3, 1) |
| `rc_control_unsupported` | 其它（非上述兩者） | — |

---

## 實作備註 / 已知限制

1. **資料源是「真 xApp/RIC 的 E2 RC」**（經 CU `e2_control_actor` → `push_control_action`）。
   劇本自帶的 `cell_quotas` 是 `du_client` 直打 DU、**不經 E2 control**，**不會**出現在此 API。
2. **`observed_at` = CU 落地時刻（`action_ts`）**，非「從 log 觀察（晚 1–11s）」語意。
3. **`raw` 目前由結構化欄位重建**；若 payload_json 帶 `raw` 則優先用它。
   要「字面 CU log 行」需在 CU `push_control_action` 帶 `raw`（小改 + 重啟 CU）。
4. **`params.rrc_ue_id`**：優先 `payload_json.rrc_ue_id`，否則退用 `ue_name`。
5. **`uuid`**：目前 `ca{id}`（穩定可去重）；若 payload_json 帶 `obs_uuid` 則優先用它。
6. 服務以 `daphne`/單進程跑、原始碼 bind-mount；改後需 `docker restart omniver_backend` 生效。
