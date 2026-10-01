# (DT) 轉達 RIC:類型 30001 已於 01:40:00Z 建好;請 SMO 查 `$id`、送故意不合法的 policy;合法的 policy 等 run 起來再下

- 日期:2026-10-01 01:43Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 需要 SMO 處理:**第 2 節 (1)(2);(3) 是請 SMO 先不要做的事**

## 1. 類型 30001

`PUT /A1-P/v2/policytypes/30001` → 201;從 10.3.0.71:30183 看 `policytypes` = `[30001]`;`GET` 回 `name` "ORAN_EnergySaving_4.0.0"、`create_schema` 的 `$id` = `https://schemas.o-ran.org/jsonschemas/a1td/oran_energysaving_4.0.0`、`$schema` 2020-12、`$defs` 11 個,原文未改。

## 2. 請 SMO

| # | 事項 |
|---|---|
| (1) | 查 PMS 的 `policy-types/30001`,看 `$id` 有沒有保留 |
| (2) | 送那筆故意不合法的 policy(`cellId` 寫字串),確認 a1mediator 會拒(預期 400)。若 a1mediator 不認 2020-12 而放行,dt-a1-xapp 自己會解不到 cell、回 ERROR、不下任何控制,不會有副作用;但請把結果告知,RIC 再評估要不要在 xApp 加完整的 schema 驗證 |
| (3) | **先不要對 30001 下合法的 policy**,等 N2a 的 run 起來(02:00Z,見上一份通知)再下。現在沒有場景,候選 cell 解不到會回 ERROR |

dt-a1-xapp 的狀態頁(叢集內 `service-ricxapp-dt-a1-xapp-http:8080/status`)列出每筆 20010、下了什麼控制、ack、等門檻的原因;驗收時 RIC 會提供。
