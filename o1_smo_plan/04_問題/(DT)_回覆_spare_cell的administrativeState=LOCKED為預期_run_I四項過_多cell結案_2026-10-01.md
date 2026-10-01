# (DT) 回覆:spare cell 的 administrativeState = **LOCKED 是預期**(DT 通知寫錯);run I 四項通過,多 DU / 多 cell 結案

- 日期:2026-10-01 09:02Z;回覆 `03_結果/(SMO)_run_I多cell四項全過_…_2026-10-01.md`
1. **spare cell(e40 NRCellDU=1)**:facade 的映射規則是「DU 未啟用且不是節能流程 → administrativeState=LOCKED、operationalState=DISABLED、cellState=INACTIVE」;spare cell 設計上就沒啟用,等同營運者鎖定,所以 **LOCKED 才是預期**,SDNC 讀到的正確。DT 09:55Z 通知寫 UNLOCKED 是筆誤,抱歉。只有 RIC 經 A1 / CCC es-on 關掉的 cell 才會是 UNLOCKED + DISABLED。
2. run H 單 cell 也亂碼:收到,0011c 已修,run I 的 e41 / e42 SMO 已驗 `NRCellDU=0` 正確;corridor24 下一場 run 也會用同一映像,DT 會再看一次 measObjLdn。
3. run H 留下的 1 個壞點(`…e42_du2,…,NRCellDU=`):**待 mitlab 同意**後請 SMO 刪除(DT 已呈報)。
4. N3 rApp(逐 cell + spare cell 只看在服務中的 cell):**待 mitlab 核准部署**(DT 已呈報)。
5. 多 DU / 多 cell 在 DT 待辦 I1 結案;下一場多 DU(一個 gNB 兩個 DU)的劇本目前沒有,等有需求再驗。
