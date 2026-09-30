# (DT) C3 已生效:gNBIdLength = 22

日期:2026-09-29 ~09:35Z。兩 ME 已重建(patch 0006),SDNC 會看到一次重連;rekey 基準請改為這次 mount 時刻。
- GNBCUCPFunction / GNBDUFunction `gNBIdLength` 22;NRFreqRelation.cellReselectionPriority 仍 32;PerfMetricJob 10 個 / 900 s;下一個 PM 檔 09:45:00Z。
- 之後不會再為 patch 重建,rekey 觀察應可安穩跑滿一小時。
- D-T1 / D-T2 等 mitlab 放行後執行,動手前會寫通知。
