# (DT) N2a 即時(第四則):02:25:03Z DELETE 後 mid 已開回,UE 2 秒內回流;RIC 整場時間線

- 日期:2026-10-01 02:27Z
- 來自:DT 端(10.3.0.217),含 RIC 團隊 session `anr_xapps` 的回報
- 需要 SMO 處理:**確認 PMS 的 policy 已刪、RIC-A 清單為空;看 gNB 60 秒 PM 02:26 起 mid 的 UE 數回來**;02:45Z run 結束後整理 N2a 結果

## 1. gNB 端(DT 的 CU / E2 adapter,UTC)

| 時間 | 事件 |
|---|---|
| 02:25:03 | mid 的 E2 adapter 收到 CCC control `{cell_id: e32:mid, action: enable}` |
| 02:25:03 | CU:「ES: cell e32:mid → isNotEnergySaving (enabled)」 |
| 02:25:05、02:25:07 | p06、p12 從 nbr 重建到 mid(開回後 2 秒 UE 就回來) |
| 02:25:41、02:25:44 | p06 重建、p12 以 Xn 換手到 mid |
| 02:25:45 | 取樣:mid 2 個 UE(PRB 尚 0,流量還沒起);nbr 5 個 / 7 % |

節能期間(02:10:03–02:25:03,15 分鐘):mid UE 0、PRB 0,沒有收到任何其他控制;src / nbr 正常服務。

## 2. RIC 端整場時間線(RIC 提供,UTC)

| 時間 | 事件 |
|---|---|
| 02:10:03 | 收 CREATE → es-on mid ACK(inst 115);20011 未送出(路由) |
| 02:11:04 | xApp 0.2.2(種子路由) |
| 02:12:20 | 取回 policy → es-on 冪等 ACK(116)→ 20011 送出,但 a1mediator 因字串型別 panic 重啟 |
| 02:13:27 | xApp 0.2.3(數字型別) |
| 02:15:04 | 取回 policy → 20011 OK → **a1mediator ENFORCED** |
| 02:15:07 | rtmgr 重啟、推送恢復 |
| 02:16:21 | xApp 0.2.4(DELETE 關候選) |
| 02:17:37 | 取回 policy → OK |
| **02:25:03** | 收 DELETE → es-off mid ACK(119)→ 20011 DELETED(sent=true) |
| 02:25:20 | a1mediator policies 清單 = [],沒有再重啟(restart 仍 12);xApp 的 policy 表清空 |

run 到 02:45Z RIC 不再動任何東西。

## 3. DT 對驗收六點的初步對照(以 gNB 端為準,待 SMO 補 PMS 與 InfluxDB 側)

| # | 驗收點 | 結果 |
|---|---|---|
| 1 | 類型 30001 在 PMS 看得到、schema 官方原文 | ✅(SMO 01:41Z) |
| 2 | PMS 建 policy,RIC 回報 IN EFFECT / ENFORCED | ✅ 02:15:04Z(比建立晚 5 分鐘,原因:RIC 平台兩個問題,見第 2 節) |
| 3 | RIC 對 mid 下 es-on;RIC PM 的 `VS.A1.PolicyInstances` 0 → 1 | es-on ✅ 02:10:03Z;PM 待 SMO 看 02:15 / 02:30 的檔 |
| 4 | mid 的 `DRB.MaxActiveUeDl`、`RRU.PrbTotDl` 歸零,鄰 cell 上升 | gNB 端 ✅(02:10:43Z 起 0 / 0);InfluxDB 待 SMO |
| 5 | SMO 刪 policy → es-off → mid 恢復、UE 回流 | ✅ 02:25:03Z,UE 2 秒內回流 |
| 6 | 三方紀錄時間對得起來 | gNB 與 RIC 的 02:10:03、02:12:20、02:25:03 逐秒吻合;SMO 側待補 |

## 4. 這場暴露的 RIC 平台問題(RIC 已記,供 N3 前處理)

1. rtmgr 在元件換 pod / 重啟後不重推路由(xApp 02:04Z、a1mediator 02:12Z 兩次都遇到),唯一有效的處理是重啟 rtmgr。N3 的 rApp 無人值守時這會卡住整個閉環。
2. a1mediator 3.2.3 收 20011 時對 `policy_type_id` 的型別脆弱(字串會 panic)。
3. xApp 重啟後不知道哪些 cell 已在節能(0.2.4 以「DELETE 關候選」暫解,正式做法待補)。
