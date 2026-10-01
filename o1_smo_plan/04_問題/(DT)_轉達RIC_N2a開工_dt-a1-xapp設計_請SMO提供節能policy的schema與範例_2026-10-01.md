# (DT) 轉達 RIC:N2a 開工 —— dt-a1-xapp 的設計;請 SMO 提供節能 policy 的 schema 原文與實際範例(四題)

- 日期:2026-10-01 01:30Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`(RIC 回報 mitlab 已指示 N2a 開工)
- 需要 SMO 處理:**第 2 節四題**

## 1. RIC 端的做法

新的 xApp **dt-a1-xapp**:RMR 收 20010 / 回 20011;向 appmgr 宣告 policies [30001];把 policy 翻成閘道的 ccc-es-on / ccc-es-off;例外一律接住回 ERROR;`/status` 列出 policy 與動作;啟動時送 20012 向 a1mediator 要回現有 policy,重啟不丟狀態。類型 30001 由 RIC 建(`create_schema` 放官方原文、`description` 寫 `ORAN_EnergySaving_4.0.0`),建之前照舊告知時間。

## 2. 請 SMO 提供 / 回覆

| # | 問題 |
|---|---|
| 1 | **`ORAN_EnergySaving_4.0.0` 的 JSON Schema 原文**(A1TD v12 的那份;規範有授權條款,請放 `01_計畫/參考/` 或直接寫在回覆裡) |
| 2 | **SMO 實際會送的一筆 policy 範例**,對 e32:mid(NCI 59539456)下 policy。尤其 `cellId` 的寫法:是 `{"plmnId":{"mcc":"208","mnc":"95"},"cId":{"ncI":59539456}}` 這種物件,還是 NR CGI 字串?有沒有 sliceId / qosId / 其他必填欄位?scope 可以同時列多顆 cell 嗎? |
| 3 | DELETE policy 時 a1mediator 只送 operation=DELETE 與 instance id、不帶 payload,所以 xApp 會記住 CREATE 時的 cell 清單,DELETE 時對同一批 cell 下 es-off。這與 SMO 的預期一致嗎? |
| 4 | 類型 30001 的 `description` 要寫 `"ORAN_EnergySaving_4.0.0"`,還是帶更多字(例如 `"O-RAN A1TD v12 ORAN_EnergySaving_4.0.0"`)? |

## 3. DT 對 RIC 的確認(已直接回 RIC,供 SMO 知悉)

- ccc-es-on / es-off 的 `cell_id` 用 cell 名(例 `e32:mid`),與今天 lock / unlock 相同;RIC 從 E2 資料的 nci 反查 cell 名。
- run 的 controlPolicy 已允許 ccc-es-on / ccc-es-off(與 ccc-lock / unlock 同一份清單)。
- gNB 收到 es-on 的行為(CU 程式):先擋新 UE 接入、把現有 UE 以 Xn 移到鄰 cell(`_es_offload_round`);一輪沒清空會在背景持續趕人,狀態 `toBeEnergySaving`;清空後關 cell,狀態 `isEnergySaving`。es-off:開回 cell,狀態 `isNotEnergySaving`。CCC indication 會帶 `energySavingState`。這是 9/27 RIC 驗過的,DT 這次只重讀程式確認。
