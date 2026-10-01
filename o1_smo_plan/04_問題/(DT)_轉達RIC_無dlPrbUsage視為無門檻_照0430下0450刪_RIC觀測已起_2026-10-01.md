# (DT) 轉達 RIC:esResources 沒有 dlPrbUsage 時 xApp 視為「無門檻」,收到 policy 立刻下 ccc-es-on;04:30 PUT / 04:50 DELETE 照做

- 日期:2026-10-01 04:17Z;回覆 `03_結果/(SMO)_節能第二測試_SMO已排程_…_2026-10-01.md`
- xApp 判定(policy.py eligible):`dlPrbUsage` 為 None → 不看 PRB、直接 eligible;候選 = scope − FORBID = e31:nbr。a1mediator 驗證會過,不必填 100。
- 預期時序:04:30:00 PUT → a1mediator 20010 → xApp 對閘道下 ccc-es-on e31:nbr(gen 12)→ ACK → 20011 → **ENFORCED**;04:50:00 DELETE → ccc-es-off → 20011 **DELETED**。
- RIC 側觀測 04:14Z 起每 10 秒記錄(各 cell UE 數、PRB、policy 清單、xApp 事件)。開場 04:14Z:src 9 UE / 28.5 %,nbr 7–8 UE / 30.8 %,mid 2 UE / 0.2 %。
- 三方結束後互對時間;SMO 的結果檔請附 PUT / DELETE 的精確時刻與 PMS 狀態轉為 ENFORCED 的時刻。
