# (DT) N2a 即時(第三則):02:15:04Z a1mediator 狀態已 ENFORCED,請 SMO 查 PMS;02:25 的 DELETE 會對 mid 下 es-off

- 日期:2026-10-01 02:18Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 需要 SMO 處理:**查 PMS 的 `smo-n2a-es-1` 狀態(應為 ENFORCED / IN EFFECT);02:25Z 刪除照原訂**

| 時間(UTC) | 事件(RIC 回報) |
|---|---|
| 02:15:07 | rtmgr 重啟完成,立刻推成功到 a1mediator、dt-a1-xapp 及其他端點 |
| 02:15:04 | xApp 用 20012 取回 policy、回 20011 OK(`policy_type_id` 數字)→ **a1mediator 狀態 = ENFORCED**(`GET …/policies/smo-n2a-es-1/status` 回 `{"enforceStatus":"ENFORCED"}`),a1mediator 沒有再崩 |
| 02:16:21 | xApp 0.2.4 上(見下) |

補充(RIC):

- 這次取回後 xApp 沒再下 es-on:mid 已在節能、observation 裡沒有 mid 的 PRB(cell 關了沒有 PM),xApp 依「有門檻而量不到 → 等」每 30 秒重看,不影響 gNB 狀態。
- 這暴露一個問題:重啟後 xApp 不知道 mid 已經在節能,DELETE 若只關「它自己開過的」會漏掉 mid。**0.2.4 把 DELETE 改成關「開過的 ∪ 候選」**(es-off 對沒在節能的 cell 冪等無害),所以 02:25 的 DELETE 會對 e32:mid 下 ccc-es-off。這正是 SMO 先前說的「從 CCC 的 `energySavingState` 重建」要解的問題;RIC 之後補正式做法(讀 CCC indication 或閘道露出 `energySavingState`)。

gNB 端(DT):mid 自 02:10:03Z 起持續節能,02:12:20Z 之後沒有再收到控制;src / nbr 正常。
