# (DT) T3 LIVE run M 開始:`00bba8b4-20261001T121214Z`(corridor24_16_24,12:12:01Z 起 2400 秒 → 12:52:01Z 自動停)

- 日期:2026-10-01 12:14Z;rApp LIVE(SMO 12:10:39Z)
- 流量腳本 12:13:03Z 啟動:

| 階段 | 時間(UTC) | 每 UE | 預期 rApp |
|---|---|---|---|
| A | 12:13–12:28 | 0.2 Mbps | 約 12:16–12:18 PUT `smo-n3-corridor`(候選多半 e32 mid)→ RIC es-on → mid 關;O1 e32 operationalState=DISABLED |
| B | 12:28–12:43 | 4.0 Mbps | 約 12:30–12:31 DELETE(src/nbr > 70 % 連 2 期)→ es-off → mid 開回 |
| C | 12:43–12:52 | 0.2 Mbps | 冷卻後約 12:48–12:50 可能第二輪 PUT;12:52 run 停 → rApp 因 ME 斷線撤除 |

- DT 記:三 cell 每 10 秒 PRB / UE、CU 的 ES 狀態機與 CCC 事件時刻、facade 的 operationalState。
- 止損:DT 看到異常會停 run 並通知;SMO 可 `deploy.sh dry-run`。
