# (SMO) G9 收到;corridor24 新映像確認;N3 rApp 加上「RRC 重建」退出條件(待 mitlab 部署);run K 開始後驗四項

- 日期:2026-10-01 09:25Z
- 回覆:`04_問題/已回覆/(DT)_G9_CU-CP_ME開始送PM_NRCellCU重建與異常釋放計數器_run_K驗證_corridor24新映像已驗_2026-10-01.md`

## 1. corridor24 新映像(run J):收到 ✅

DT 已驗 `NRCellDU=0`、`_-1_`、202。SMO 抽查:run J 期間 `SubNetwork=corridor24_16_24,…,NRCellDU=0` 照常入庫。

## 2. G9 對 SMO 各元件的影響

| 元件 | 影響 |
|---|---|
| dfc / 轉換器 / pmlog | 不用改:CU-CP ME 的檔案跟 DU 一樣走 notifyFileReady → dfc,入庫成 `…,ManagedElement=gnb_…e3x,GNBCUCPFunction=0,NRCellCU=<lc>` |
| ME 生命週期控制器 | 不受影響 |
| **N3 rApp** | **已修改**(見第 3 節) |

## 3. N3 rApp:加上「RRC 重建」退出條件

- **DME 工作**:measTypeSpecs 加上 `{measuredObjClass: NRCellCU, measTypes: [RRC.ReEstabAtt]}`。
- **解析**:CU-CP 的 `NRCellCU=<lc>` 跟 DU 的 `NRCellDU=<lc>` 用同一個鍵 `<cu>/<lc>` 合併。DU、CU 是不同的報告,會分開到達,所以同一期會等兩邊都到(或等 50 秒)才判斷。
- **新退出條件**(保護性的,不受冷卻限制):範圍內 `RRC.ReEstabAtt` 每期合計 **≥ 20**,**連續 2 期** → 撤 policy,原因記為「RLF,可能覆蓋洞」。
  - 依據:節能第二測試 DT CU 的紀錄,覆蓋洞時 RLF 每分鐘 40–50 次,正常時 ≤ 6 次。
- 沒有 CU-CP PM 的舊映像不受影響,這條不會觸發。
- 26 項離線測試通過。**部署要等 mitlab 核准**(仍是 dry-run)。
- 其他三個計數器(`ReEstabSuccWith/WithoutUeContext`、`DRB.RelActNbr.5QI9`)SMO 先不用,但會照常入庫,之後可以用來分析。

## 4. run K 開始後,SMO 會驗

1. MinIO `ropfiles` 有 `…_-1_gnb_208_095_000e3x.xml`(CU-CP),`pm-files-json` 有轉換結果。
2. InfluxDB 出現 `…000e3x,GNBCUCPFunction=0,NRCellCU=0` 四個欄位。
3. DT 對 nbr 硬鎖 30 秒之後那一分鐘,src / mid 的 `RRC.ReEstabAtt` > 0。SMO 也會記下實際數值,看「20 / 期」這個門檻是否合適。
4. 如果 rApp 已部署,日誌每期會帶 `/re<n>`(重建次數)。
