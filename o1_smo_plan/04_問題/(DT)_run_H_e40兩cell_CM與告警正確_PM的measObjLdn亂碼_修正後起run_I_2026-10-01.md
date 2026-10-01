# (DT) run H(`7fea27f8-20261001T084034Z`,08:40:21Z 起):e40 兩個 cell 的 CM、告警、註冊都正確;**PM 的 measObjLdn 有亂碼**(cellLocalId 指標失效),修正後起 run I

- 日期:2026-10-01 08:52Z
- run H 的 e40_du1:pnfRegistration / notifyFileReady 全 202;CM 有 `NRCellDU=0`(pci 0,ENABLED/ACTIVE)與 `NRCellDU=1`(spare,pci 3,DISABLED/INACTIVE —— spare cell 在 DU 未啟用,屬預期);AlarmList 有兩個 cell 各一筆負載告警。
- **問題**:PM 檔的 `measObjLdn="GNBDUFunction=1,NRCellDU=<亂碼>"`(每分鐘的檔都是)。原因:多 cell 版的 PM 累加器存了 cellLocalId 字串的指標,而該字串在每次取樣後被釋放。**請 SMO 忽略 run H 的 e40_du1 PM(InfluxDB 會出現亂碼名稱的 series,可刪)**;e41 / e42 不受影響。
- 已修(patch 0011c:每 cell 複製一份字串),重建後停 run H、起 run I,runId 另檔通知,屆時請驗四項。
