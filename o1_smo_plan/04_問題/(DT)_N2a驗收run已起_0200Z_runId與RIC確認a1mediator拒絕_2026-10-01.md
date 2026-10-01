# (DT) N2a 驗收 run 已起(02:00:01Z);RIC 確認不合法 policy 是 a1mediator 依 schema 拒絕的

- 日期:2026-10-01 02:02Z
- 來自:DT 端(10.3.0.217)
- 需要 SMO 處理:**照時程 02:05 算 NCI、02:10 建 policy**

| 項目 | 內容 |
|---|---|
| run | 02:00:01Z 開始,預計 02:45:01Z 結束;`runId` **`00bba8b4-20261001T020019Z`**;21 個容器正常;`anr_auto_add=true`、PM 60 秒已確認生效 |
| ME | e30 / e31 / e32(NETCONF 1926–1931) |

RIC 確認(a1mediator 紀錄 01:41:47Z):「schema validation error : jsonschema: /scope does not validate with …oran_energysaving_4.0.0#/properties/scope/anyOf: anyOf failed」→「Invalid Json」→ 400。**是 a1mediator 依 schema 拒絕的**,它認得 2020-12 的 `$id` / anyOf / `$defs` 參照,驗證有效;xApp 不另外加 schema 驗證(自己的解析仍把解不到的 cell 回 ERROR 當第二道)。
