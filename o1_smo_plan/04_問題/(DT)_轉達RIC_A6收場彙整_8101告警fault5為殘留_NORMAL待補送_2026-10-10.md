# (DT) 轉達 RIC:A6 / I2 / C19 RIC 側彙整;8101 告警 fault0000000005 為殘留,NORMAL 待 RIC 補送

- 日期:2026-10-10 08:40Z(RIC 訊息轉達)

## 1. 請 SMO 注意:8101 MAJOR(fault0000000005,08:18:20Z)是殘留

- RIC 收場後查到 rtmgr 在 08:13:14–08:31:42 推不到 dt-a1-xapp(mit5 以同一 ClusterIP 重開、取回同一 whid,連線沒重建),看門狗 8101 舉報三次;SMO 收到一筆 MAJOR。
- 對應的 NORMAL 沒送成(ves-agent 存的告警 id 與最後一次清除的 id 不同)。
- **功能未受影響**:C19 期間 inst 188–193 全部送達並 ACK。RIC 會在其使用者核准後補送 NORMAL。

## 2. RIC 側彙整重點

- 場次:S1 run 29 08:00:12–08:31:54;S2 run 3 08:03:16–08:13:23;S3 run 1 08:06:17–08:28:54;三場真正同時 08:06–08:13。
- 資源:重疊期 pod CPU 最高 0.12 核、節點 load 0.7、可用記憶體 10G、磁碟 78%。
- I2:e60:spare 在 ran_func 5 pm_cell 1156 筆、ran_func 6 anr_kpm 1157 筆,與 e60:src 筆數相同、數值獨立;spare 整場 0 UE,PRB 0 為真值。
- C19:RIC 與 DT CU 時刻(inst 188–193)全部吻合;兩輪 scale 0→1 換 pod 第一筆 20010 都沒遺失;補回路徑需以 helm 滾動換版另排。
- RIC 待修(今天不改):dt-a1-xapp 0.2.8 改工作執行緒(解 inst 191 的 10 秒自卡 → ERROR);rtmgr 對同 ClusterIP 重開 xApp 的連線重建。
- 現況:閘道 scenarios 0、a1mediator 無 policy、劇本 xApp 0;dt-exec R2 仍停用(EXEC_PRB_HIGH_PCT=101),C20 定案後恢復。
