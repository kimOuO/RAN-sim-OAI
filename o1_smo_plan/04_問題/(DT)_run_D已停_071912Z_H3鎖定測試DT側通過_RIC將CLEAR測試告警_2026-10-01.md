# (DT) run D 已停(07:19:12Z);H3 鎖定測試 DT 側通過;RIC 即將 CLEAR 測試告警 72004,請 SMO 記 NORMAL 到達時間

- 日期:2026-10-01 07:22Z
- run D `00bba8b4-20261001T070358Z`:07:03:43–07:19:12Z,正常收場(9 CLEAR + 6 notifyMOIDeletion)。

## H3 鎖定測試(DT adapter 日誌)
| 時間 | 動作 | adapter 寫入 e31 NRCellDU |
|---|---|---|
| 07:12:03Z | DU cell disable(硬鎖) | 07:12:04.5 administrativeState=LOCKED、operationalState=DISABLED、cellState=INACTIVE |
| 07:15:03Z | DU cell enable | 07:15:04.8 UNLOCKED / ENABLED / ACTIVE |
nRTAC 全程 40960;e30 / e32 不變。請 SMO 以 SDNC 讀到的值(含 operational datastore)對照;若 SMO 在 07:12–07:15 之間沒讀到,可從 SDNC 的 netconf 通知或下一場 run 再驗。

## H1
run D 三個 DU 的 notifyFileReady 全部 202(07:05 起每分鐘);請 SMO 補 H1 實測結果(dfc / MinIO / InfluxDB / rApp)。

## RIC clear 驗證
run D 停後 RIC CLEAR 72004;預期 ≤ 6 分鐘 SMO 收到 NORMAL、SDNR 歸 0。RIC 給時刻後 DT 轉達。接下來 30 分鐘 DT 不起 run。
