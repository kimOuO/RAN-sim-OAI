# SMO 端回覆(第八到十輪)—— FM/PM stndDefined、P2/P3、TEIV 改官方路徑

- FM stndDefined 通過(SMO 更正 schema 為 TS28111_FaultNrm);同毫秒 raise/clear 教訓;PM P1 通過;P2 13:16Z 雙方切換。
- P3 一度阻塞:dfc 對新 topic 無 Kafka Read ACL(DT 唯讀查到並通知);SMO 修 ACL(13:16–14:41 缺口 5 檔),DT 15:13Z 補送 5 筆 notifyFileReady 皆 202。
- SMO 修好官方 ncmp-to-teiv-adapter(YANG 打包、relationship module 前綴、多筆 delete 卡死 → 拆單筆);mitlab 定案 C1 = 方案 A:TEIV 以 adapter 為準,DT 只產 E2LINK/F1CLINK(aSide 用 adapter id,delete 單筆一檔)。DT 舊發佈的 urn:3gpp:dn 物件已被刪,RIC 物件保留。
- D-T3 由背景程式於 14:46:54Z 自動開始(看到 P3 結果檔);SMO 15:05 才說可開始,時間吻合。
- 待決:C2 DT 對 smo-master SSH 是否繼續。
