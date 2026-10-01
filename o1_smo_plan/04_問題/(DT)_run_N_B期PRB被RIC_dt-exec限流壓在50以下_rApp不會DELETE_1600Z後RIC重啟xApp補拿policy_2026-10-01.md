# (DT) run N:B 期 PRB 被 RIC 的 dt-exec 限流(2-6,max 50 %)壓在 50 % 以下 → rApp 不會 DELETE(正確);16:00Z 後 RIC 重啟 xApp 補拿 policy 以驗 es-on

- 日期:2026-10-01 15:58Z
1. **rApp 沒 DELETE 是正確的**:15:47:27Z RIC 的 dt-exec 對 e30 / e31 下 PRB 配額(min 10 / max 50),之後 src / nbr PRB 被壓在 45–55 %(DT 與 RIC 觀測一致),沒有達到 rApp 的 > 70 % 退出門檻。T2 校正那場 dt-exec 因觀測缺失沒下 2-6,所以 PRB 到 70–100 %。這是 rApp「> 70 % 退出」與 dt-exec「> 40 % 限流到 50 %」互相牴觸,run 後三方要定(建議:T3 期間 dt-exec 對 corridor 停用 2-6,或 rApp 退出門檻改 50 %)。
2. 第一輪 policy(15:33:06)仍在 PMS / RIC-A(NOT_ENFORCED,因 20010 遺失),rApp 在 16:00 回低負載後不會重 PUT 同一 id。**DT 已請 RIC 於 16:00:30Z 左右重啟 dt-a1-xapp**,它啟動 75 秒後會向 a1mediator 查回現存 policy → 判 e32 eligible → es-on 關 mid。請 SMO 留意約 16:02–16:03:PMS 應轉 ENFORCED、O1 e32 operationalState=DISABLED、PM e32 歸零。
3. 16:09 run 停 → rApp 因 ME 斷線 DELETE → es-off(run M 已驗);之後 SMO 切回 dry-run。
