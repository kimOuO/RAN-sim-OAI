# (DT) 多 cell 第一場(run G,08:31–08:40Z)已停:e40 的 CM 在 sysrepo 驗證失敗,已修;run H 重測,runId 另檔通知

- 日期:2026-10-01 08:45Z
- run G(`livetest_corridor`,rid 7fea27f8)e41 / e42(單 cell)正常,e40(兩 cell)的 running datastore 第一次寫入被 sysrepo 拒絕:`Mandatory node "sectorEquipmentFunctionRef" instance does not exist`(第二個 cell 的 NRSectorCarrier 缺必要屬性)→ e40_du1 沒有 CM、沒有 PM。SMO 若看到 e40/e41/e42 註冊後又下線,就是這場。
- 已修(adapter patch 0011b),重建後起 run H(1200 秒)。請以 run H 驗前一檔的四項。
