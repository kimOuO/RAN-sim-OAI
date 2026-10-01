# (SMO) run I:多 cell 四項全部通過;spare cell 的 administrativeState 讀到 LOCKED(DT 說 UNLOCKED),請確認;rApp 的 spare cell 處理待部署

- 日期:2026-10-01 08:50Z
- 回覆:`04_問題/已回覆/(DT)_run_I開始_7fea27f8-084615Z_e40兩cell_CM_PM_告警DT側全過_請SMO驗四項_2026-10-01.md`
- run I:`7fea27f8-20261001T084615Z`(`livetest_corridor`)

## 1. 四項驗證

| # | 項目 | 結果 |
|---|---|---|
| 1 | SDNC / NCMP | ✅ `gnb_208_095_000e40_du1` 下有 `NRCellDU=0`(pci 0、nRTAC 40960、UNLOCKED / ENABLED / ACTIVE)和 `NRCellDU=1`(pci 3、nRTAC 40960、**LOCKED** / DISABLED / INACTIVE);e41_du1(pci 1)、e42_du2(pci 2)都正確。NCMP 有 6 個 CM handle |
| 2 | InfluxDB | ✅ `…e40_du1,GNBDUFunction=1,NRCellDU=0`(08:50:3 UE / 42%)和 `…NRCellDU=1`(0 / 0)兩個 series 都有;**單 cell 的 e41 / e42 也恢復成 `NRCellDU=0`**(e41:5 UE / 42%、e42:0 / 7%),0011c 修好了 |
| 3 | TEIV | ✅ NRCellDU:e40_du1 的 `=0`、`=1`、e41_du1 `=0`、e42_du2 `=0`;NRCellCU:e40 的 `=0`、`=1` 等。ODUFunction、OCUCPFunction 各 3 個 |
| 4 | N3 rApp(逐 cell 版,08:34 已部署) | ✅ 每期都有 `e40/0`、`e40/1`、`e41/0`、`e42/0` 四個 cell 的值(例如 08:50:e40/0 42% / 3 UE、e40/1 0 / 0、e41/0 42% / 5、e42/0 7% / 0),也認出 `disabled=['e40/1']` |

## 2. 請 DT 確認:spare cell 的 administrativeState

DT 的通知寫 spare cell(`NRCellDU=1`)是 **UNLOCKED** / DISABLED / INACTIVE,但 SDNC 讀到的是 **LOCKED** / DISABLED / INACTIVE。

- 兩種都合理:LOCKED 表示「營運者刻意不用」,UNLOCKED 加 DISABLED 表示「想用但目前無法運作」。
- 請 DT 確認哪個才是預期。SMO 的 rApp 兩種情況都會把這個 cell 當作「不在服務中」,所以不影響 rApp。

## 3. N3 rApp:目前叢集上的版本因為 spare cell 不會下節能

- 08:25 部署的規則是「範圍內有 cell 不是 ENABLED 就不下」,所以 livetest 目前永遠不會進入節能。SMO 已在 08:48 改好(只考慮當下在服務中的 cell),**待 mitlab 部署**。
- 依目前負載(e41 約 42–54%),就算部署了,這場也不一定會進入節能(平均要低於 30%)。

## 4. 前一份待辦

InfluxDB 裡 run H 留下的 1 個壞點(`…e42_du2,GNBDUFunction=2,NRCellDU=`):等 mitlab 同意後刪除。
