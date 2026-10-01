# (DT) 轉達 RIC 對 v0.2 第 (3) 項的回覆:接受 30001 / 30002 與不經 a1med-proxy;前提是 PMS 對 RIC-A 用 OSC adapter

- 日期:2026-09-30 18:05Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`01_計畫/(SMO)_下一階段計畫_討論稿v0.2_2026-09-30.md` 第 7 節第 (3) 項
- 需要 SMO 處理:**確認 PMS 對 `ric-dt-71` 的 adapter 類型**(第 2 點)
- 給 mitlab:六項決定裡的第 (3) 項,RIC 已接受,只剩 SMO 確認一個設定

## RIC 的回覆

1. **編號 30001(節能)/ 30002(負載平衡):接受。** a1mediator 的範圍是 1–2147483647,沒有衝突;RIC 的 xApp 會在 appmgr 宣告 policies [30001],rtmgr 就會把 20010 sub-id 30001 路由到它。20008 因 PMS 已有同號的舊自訂類型而不用,合理。

2. **不經 a1med-proxy、PMS 直接對 `http://10.3.0.71:30183`:接受,但有一個前提請 SMO 確認。** PMS 對這座 RIC 的設定必須用 **O-RAN SC A1 mediator 的 adapter(OSC_V1:直接講 `/A1-P/v2`、整數編號、類型欄位是 `create_schema`)**,不能用標準 A1 adapter(STD_V2:期待字串編號與 `policySchema` 欄位)。9/29 稽核時之所以擺 a1med-proxy,就是因為 PMS 當時用標準 adapter 讀不到 `create_schema`。如果 PMS 直接用 OSC adapter 讀得到,proxy 就不需要。請 SMO 在 PMS 設定裡確認 `ric-dt-71` 的 adapter 類型,或在類型 30001 建好後看 PMS 的 policytypes 能不能列出它的 schema。這一點 RIC 這邊測不到。

3. 第 (4) 冒煙測試:收到,mitlab 決定前不建任何類型。

4. 第 (2)、(5) 點沒有意見;N4 的排序照 RIC 估計的順序可以。

其餘等 mitlab 的六項決定。
