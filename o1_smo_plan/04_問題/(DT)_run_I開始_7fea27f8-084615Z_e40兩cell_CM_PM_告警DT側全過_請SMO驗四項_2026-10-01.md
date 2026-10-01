# (DT) run I 開始:`7fea27f8-20261001T084615Z`(`livetest_corridor`,08:46:01Z 起 1500 秒 → 約 09:11Z 停);e40 兩個 cell 的 CM / PM / 告警 DT 側全部正確,請 SMO 驗四項

- 日期:2026-10-01 08:55Z
- ME:e40 `gnb_208_095_000e40`、`gnb_208_095_000e40_du1`(**兩個 cell**:NRCellDU=0 src pci 0、NRCellDU=1 spare pci 3);e41 `…e41`/`_du1`;e42 `…e42`/`_du2`。PM 60 秒。

## DT 側(e40_du1)
| 項目 | 結果 |
|---|---|
| 註冊 / 心跳 / notifyFileReady | 全部 202 |
| CM | `NRCellDU=0`:nRPCI 0、UNLOCKED / ENABLED / ACTIVE;`NRCellDU=1`:nRPCI 3、UNLOCKED / **DISABLED / INACTIVE**(spare cell 在 DU 未啟用,屬預期);`NRSectorCarrier=0`、`=1` 各一個 |
| PM 檔 | 一個檔兩個 measValue:`GNBDUFunction=1,NRCellDU=0` → 3 UE / 5749 kbit/s / PRB 32 %;`NRCellDU=1` → 全 0 |
| AlarmList | `…NRCellDU=0-loadDownlinkExceededWarning`、`…NRCellDU=1-…` 各一筆 + internalConnectionLoss |
| 收工 | run H 收場時 6 個 ME 的 CLEAR(每 cell 一筆負載告警)與 notifyMOIDeletion 都送出,通知檔 / run 對照表正常 |

## 請 SMO 驗
1. SDNC / NCMP:e40_du1 下兩個 NRCellDU 與屬性;2. InfluxDB:`…000e40_du1,GNBDUFunction=1,NRCellDU=0` 與 `NRCellDU=1` 兩個 series(後者值為 0);3. TEIV 兩個 cell;4. N3 rApp 範圍 e40/0、e40/1、e41/0、e42/0 四個 cell 每期都有值(e40/1 為 0)。
- 提醒:N3 rApp 的逐 cell 版本仍待 mitlab 核准部署;目前叢集上的版本可能把 e40 兩個 cell 混在一起,驗第 4 項前請確認版本。
