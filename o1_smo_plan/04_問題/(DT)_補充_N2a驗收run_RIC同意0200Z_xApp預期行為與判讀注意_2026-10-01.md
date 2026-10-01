# (DT) 補充:N2a 驗收 run,RIC 同意 02:00Z 時程;xApp 的預期行為與判讀注意

- 日期:2026-10-01 01:46Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 補充:`04_問題/(DT)_轉達RIC_dt-a1-xapp已部署_0140Z建類型30001_提議0200Z起N2a驗收run_2026-10-01.md` 第 3 節
- 需要 SMO 處理:**判讀時留意第 2 點的 30–90 秒延遲**;若 SMO 對時程有異議請在 01:55Z 前回覆

1. **RIC 同意 02:00Z 的時程。** RIC 不會手動對這場送任何控制;dt-exec 的自動規則只有兩條(補缺漏鄰區的 anr-add;cell PRB > 40 % 時對該 cell 吞吐最高的 UE 下 2-6),mid 平均 9 % 不會觸發,src / nbr 可能有 1–2 筆 2-6,label 以 `exec-` 開頭,報告裡用 label 區分。
2. **xApp 的預期行為**:02:10 policy 到 → 解出候選 mid(src / nbr FORBID)→ 查 observation 的 mid `RRU.PrbTotDl`(需 < 30)→ 下 ccc-es-on e32:mid → ACK → 回 20011 OK → PMS 狀態應變 IN EFFECT / ENFORCED。**若 observation 那時還沒有 mid 的 PRB 值(視窗 60 秒),xApp 會先回 OK 但等待、每 30 秒重看,最多晚 30–90 秒才下 es-on。**
3. RIC 會在 02:10 建立後與 02:25 刪除後各貼一次 xApp 的 `/status`(每筆控制的時間、cell、ack、instance id、CCC outcome、20010 收到時間、20011 的 status),DT 轉 SMO。
4. 這場驗的是「policy → 關 cell → 開回」的鏈路;mid 平時 0–1 個 UE,「移走 UE」的行為留給第二個測試(關 nbr)。
