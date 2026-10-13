# (DT) 回覆:S3 e62 的 NETCONF 未開 —— 兩顆 adapter 的 netopeer2-server 行程已消失

- 日期:2026-10-10 08:13Z
- 回覆:`03_結果/(SMO)_緊急_S3的e62_NETCONF埠2026未開_SMO無法掛載_約0816Z控制器會將其下線_2026-10-10.md`

| ME | 容器 | 埠 | netopeer2-server | 結果 |
|---|---|---|---|---|
| gnb_208_095_000e62(CU-CP) | o1adapter-cucp-89a45a6e-2 | 2026 | **不在** | SSH 連線被 reset |
| gnb_208_095_000e62_du2 | o1adapter-du-89a45a6e-2 | 2027 | **不在** | SSH banner 讀不到 |
| 其餘 15 個 ME(含 e60_du2:3047) | — | — | 正常 | e61 等抽測 NETCONF get 正常 |

- 兩顆容器 08:06:20Z 啟動時都印出「Starting netopeer2-server」,adapter 本體仍在跑(VES 心跳 202),但 netopeer2 行程已不存在,日誌沒有錯誤訊息。e62 是 S3 最後啟動的 gNB,推測與 17 顆 adapter 短時間內同時初始化 sysrepo 有關(待查)。
- 另:08:07、08:10Z 有數顆 adapter 的 notifyFileReady 對 VES collector 逾時(`Timeout was reached`),請 SMO 看 collector 當時負載。
- DT 端修復(在容器內重新啟動 netopeer2,或重啟這兩顆容器)需 mitlab 核准,尚未執行。**SMO 控制器 08:16Z 將 e62 下線可照常進行**,這本身是 A6 的有效觀察;若 DT 之後修好,e62 會再送 pnfRegistration / 可被重新掛載,請 SMO 記錄控制器能否把它重新上線。
