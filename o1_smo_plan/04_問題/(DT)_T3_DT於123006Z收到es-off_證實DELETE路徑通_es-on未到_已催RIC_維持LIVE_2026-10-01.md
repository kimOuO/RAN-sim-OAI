# (DT) T3:DT 於 12:30:06Z 收到 es-off(rApp DELETE 生效),證實 PUT→ENFORCED、DELETE→es-off 兩段都通;只有 xApp 的 es-on 沒送;已催 RIC;同意維持 LIVE 跑完

- 日期:2026-10-01 12:32Z;回覆 `03_結果/(SMO)_緊急回覆_T3_rApp已於121606Z_PUT_…`
- DT 側:12:14–12:30 三個 CU 都沒有收到 CCC es-on;**12:30:06Z cu-2(mid)收到 CCC enable:`ES: cell e32:mid → isNotEnergySaving (enabled)`**(mid 本來就開著,冪等)。這對應 rApp 在 B 期(12:28 起 4 Mbps)的 DELETE → PMS → RIC-A 刪除 → xApp es-off。請 SMO 補 DELETE 的時刻。
- 結論同 SMO:A1 / PMS / rApp 全部正確,問題在 dt-a1-xapp(0.2.5)沒對 e32 下 es-on。已請 RIC 查日誌並回覆是否能在 12:46 前修好。
- 後續:維持 LIVE;C 期(12:43 起 0.2 Mbps)預期 12:46–12:48 第二輪 PUT,若 RIC 已修即可驗完整;否則 DT 再起一場 T3(rApp 維持 LIVE)。
