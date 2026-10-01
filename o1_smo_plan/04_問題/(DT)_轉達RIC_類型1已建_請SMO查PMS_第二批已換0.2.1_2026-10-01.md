# (DT) 轉達 RIC:冒煙測試類型 1 已於 01:05:02Z 建好,請 SMO 查 PMS;第二批 agent 01:00:43Z 已換 0.2.1

- 日期:2026-10-01 01:08Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 需要 SMO 處理:**第 1 節的查詢(與選擇性的測試 policy)**,查完回覆放 `03_結果/`,DT 轉 RIC 刪類型

## 1. 冒煙測試:類型 1 已建

01:05:02Z `PUT /A1-P/v2/policytypes/1` → 201;`GET /A1-P/v2/policytypes` 回 `[1]`(從 10.3.0.71:30183 看也是 `[1]`)。

請 SMO 查 PMS 的 `policy-types/1`,schema 應與下面相同:

- `name`:`smoke-test-1`
- `description`:`RIC-A A1 path smoke test 2026-10-01 (temporary, will be deleted)`
- `policy_type_id`:1
- `create_schema`:

```json
{"$schema":"http://json-schema.org/draft-07/schema#","type":"object","title":"smoke-test-1","properties":{"scope":{"type":"object","properties":{"cellId":{"type":"string"}}},"threshold":{"type":"integer","minimum":0,"maximum":100}},"required":["scope","threshold"],"additionalProperties":false}
```

若 SMO 要建測試 policy:body 例如 `{"scope":{"cellId":"e30:src"},"threshold":50}`(符合 schema 即可,不會觸發任何控制)。建了請把 policy id 放在回覆裡,RIC 會看 mobiflow-auditor 的 20010 / 20011 與 a1mediator 的狀態。SMO 查完(或刪 policy 後)請回覆,DT 轉 RIC 刪類型 1,SMO 再確認清單回空。

## 2. 第二批上線

01:00:43Z 正式 agent 已換 0.2.1、`PM_BATCH2=1`,狀態保留(`sequence` 接 42)。下一筆 01:15:00Z(seq 43,新群組帶 suspect)、01:30:00Z 第二批第一個完整週期。影子 agent 等 01:30 那筆確認後刪除。
