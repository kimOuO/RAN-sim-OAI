# (DT) 轉達 RIC:run N 收場 —— 16:10:36Z xApp 收到 DELETE(rApp 因 ME 斷線撤)→ 節點已拆 → 回 DELETED;RIC 將上 dt-a1-xapp 0.2.7(每 60 秒對帳);C20 待 SMO / mitlab 定

- 日期:2026-10-01 16:20Z
1. 收場:run 16:09:07Z 停 → rApp 撤除 → **16:10:36Z xApp 收到 DELETE smo-n3-corridor**,節點已不在閘道 → ack=GONE、回 20011 **DELETED**(run M 同情境回 ERROR,0.2.6 已改);a1mediator 清單空。請 SMO 補 PMS 側 DELETE 時刻與切回 dry-run 時刻。
2. 這場驗到:dt-preproc 0.1.8(撞號 run 24 起點正確、observation 有 PRB);帶 dlPrbUsage 的 policy → es-on(16:02:16 CREATE → 16:02:17 ACK → ENFORCED,PRB 來源 observation);收場 DELETE → DELETED。沒驗到:高負載 DELETE → es-off(C20)、PRB fallback(observation 正常未走到)。
3. UE:16:02 後 mid 0 UE;src / nbr 各 9–12 UE、PRB 6–13 %,無覆蓋洞(與第二測試關 nbr 不同)。
4. RIC 接下來:部署 dt-a1-xapp **0.2.7**(每 60 秒向 a1mediator 送 20012 對帳,漏掉的 20010 一分鐘內補回;同一份重送不重下控制),換好後通知。之後 PUT 與 xApp 換版至少隔 2 分鐘。
5. **C20 待定**(RIC 側可做:T3 期間以 env 開關停用 dt-exec 的 R2;或 rApp 退出門檻降 50 %)。DT 建議選「停用 R2」;請 SMO 給意見,mitlab 定。
