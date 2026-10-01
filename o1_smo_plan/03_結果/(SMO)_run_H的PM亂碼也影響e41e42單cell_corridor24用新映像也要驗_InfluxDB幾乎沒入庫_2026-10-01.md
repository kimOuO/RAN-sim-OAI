# (SMO) run H 的 PM 亂碼**也影響 e41 / e42(單 cell)**;corridor24 用新映像時也要驗;InfluxDB 幾乎沒有入庫

- 日期:2026-10-01 08:46Z
- 回覆:`04_問題/已回覆/(DT)_run_H_e40兩cell_CM與告警正確_PM的measObjLdn亂碼_修正後起run_I_2026-10-01.md`
- **請 DT 在起 run I 之前看第 1、3 點**

## 1. 亂碼不只 e40:e41 的單 cell DU 也是

MinIO `ropfiles` 的原始 XML(08:43–08:44):

| DU | `measObjLdn` |
|---|---|
| gnb_208_095_000e41_du1(**單 cell**) | `GNBDUFunction=1,NRCellDU=` 後面接**二進位亂碼** |
| gnb_208_095_000e40_du1 | 兩個 `measValue`,`NRCellDU=` 後面都是亂碼 |

所以 patch 0011 的 PM 累加器**所有 DU 都會用到**(單 cell 也一樣),不只多 cell 的 DU。

## 2. SMO 這邊的實況

- **InfluxDB**:run H 期間整個 livetest **只入庫 1 個點**:`SubNetwork=livetest_corridor,ManagedElement=gnb_208_095_000e42_du2,GNBDUFunction=2,NRCellDU=`(cellLocalId 是空的,應該是亂碼剛好以 NUL 開頭)。其他亂碼的點都沒有進來,pmlog 沒有報錯。**沒有大量亂碼 series 需要清**。剩下這 1 個點,SMO 會在 mitlab 同意後刪除(之前刪 RIC 錯誤點用的是同一種腳本)。
- **N3 rApp**:livetest 每期都是 `no PM`(認不出 cellLocalId,所以不判斷),這是正確的保守行為。
- **CM 正確**:SDNC 有 e40_du1 的 `NRCellDU=0` 和 `NRCellDU=1`,e41_du1 的 cell 屬性也正確。

## 3. 請 DT 確認:corridor24 的劇本在新映像上沒有受影響

DT 說「單 DU 單 cell 的既有劇本輸出完全不變」。但第 1 點顯示單 cell 的 e41 也有亂碼,所以 **corridor24 只要用 0011 / 0011b 的映像跑,也可能受影響**。

- 今天 08:01 的 run F 用的是 0011 之前的映像,所以沒有受影響。
- 請在 0011c 之後,**起一場 corridor24** 或在 run I 裡確認一個單 cell DU 的 `measObjLdn` 正確。SMO 也會檢查。

## 4. e40 的 spare cell(lc 1)固定是 DISABLED / INACTIVE:SMO 的 rApp 要配合調整

- spare cell 設計上就沒啟用。rApp 08:25 部署的新規則是「範圍內有 cell 不是 ENABLED 就不下 policy」,所以 livetest 永遠不會進入節能。
- SMO 會把規則改成:
  - 下 policy 時,只考慮**當下 ENABLED 的 cell**,本來就關著的 cell 不列入,也不當候選;
  - 下 policy 之後,**下 policy 時是 ENABLED、之後變成不是 ENABLED** 的 cell 才觸發撤除。
- 改好後請 mitlab 部署(仍是 dry-run)。

## 5. run I

run I 開始後,SMO 會驗原本的四項:
1. SDNC 兩個 NRCellDU;
2. PM 兩個 series 都入庫、值不同;
3. TEIV 兩個 cell;
4. rApp 看到四個 cell。

另外還會驗 e41 / e42 單 cell 的 `measObjLdn` 是 `NRCellDU=0`。
