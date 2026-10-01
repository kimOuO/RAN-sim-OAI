# (DT) run N:**16:02:17Z es-on 到達,mid 關閉,O1 operationalState=DISABLED** —— T3 驗收點 2 達成

- 日期:2026-10-01 16:04Z;run N `00bba8b4-20261001T152921Z`
- 16:00:30Z RIC 重啟 dt-a1-xapp(0.2.6);16:01:00Z 新 pod 起;約 16:02:15Z xApp 向 a1mediator 查回 `smo-n3-corridor`(rApp 15:33:06Z 的那筆)。
- **16:02:17Z** DT e2adapter-2 收到 CCC `{e32:mid, disable, staged}` → CU:`Xn Handover [E2_RIC_CONTROL]: UE p17 e32:mid → e30:src` → `ES: cell e32:mid cleared (1 UE offloaded) → isEnergySaving (disabled)`。
- **16:02:19Z** O1 e32_du2 NRCellDU=0:administrativeState UNLOCKED、**operationalState DISABLED、cellState INACTIVE**(與 facade 設計一致:節能關閉 = UNLOCKED + DISABLED)。
- 請 SMO 核對:PMS 16:02 後轉 ENFORCED;SDNC 讀到 e32 DISABLED;PM 16:03 起 e32 歸零。
- 16:09:07Z run 停 → rApp 因 ME 斷線 DELETE → xApp es-off(對已停的 gNB,RIC 側記錄即可);之後 SMO 切回 dry-run。DT 之後出整場紀錄。
