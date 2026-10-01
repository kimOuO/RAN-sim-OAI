# (DT) G9:CU-CP 的 ME 開始送 PM —— NRCellCU 的 RRC 重建 / 異常釋放計數器(TS 28.552);run K 驗證;另 corridor24 用新映像(run J)PM 名稱已驗正確

- 日期:2026-10-01 09:28Z
- corridor24 新映像驗證(run J `00bba8b4-20261001T091759Z`,09:18–09:25Z):三個 DU 的 measObjLdn 都是 `GNBDUFunction=<N>,NRCellDU=0`、檔名 `_-1_`、202 ✅。

## G9 內容(adapter patch 0012 + facade)
- **誰送**:每個 gNB 的 **CU-CP ME**(`gnb_208_095_000e3x`)現在也每週期產一個 PM 檔並送 notifyFileReady(以前只有 DU ME 送)。
- **檔案**:`A<date>.<start>-<end>_-1_gnb_208_095_000e3x.xml`,`measInfoId="PM=1,PmGroup=NRCellCU"`,每個 cell 一個 `<measValue measObjLdn="GNBCUCPFunction=0,NRCellCU=<cellLocalId>">`。
- **SMO 入庫後的 `_measurement`**:`SubNetwork=<scn>,ManagedElement=gnb_208_095_000e3x,GNBCUCPFunction=0,NRCellCU=0`(注意是 CU 的 ME,沒有 `_du1`)。
- **計數器(每週期的增量,CC 型)**:

| 名稱 | 28.552 | 意義 | DT 來源 |
|---|---|---|---|
| `RRC.ReEstabAtt` | 5.1.1.17.1 | RRC 重建嘗試次數(RLF 後) | CU RlfEvent(REESTAB_*) |
| `RRC.ReEstabSuccWithUeContext` | 5.1.1.17.2 | 重建成功(有 UE context) | REESTAB_WITH_CTX |
| `RRC.ReEstabSuccWithoutUeContext` | 5.1.1.17.3 | 重建成功(無 context,回 setup) | REESTAB_WITHOUT_CTX |
| `DRB.RelActNbr.5QI9` | 5.1.1.10.x | 異常釋放的 DRB 數(5QI 9) | CU DRB.RelActNbr |

- 未納入:`RLF 掉話數`(28.552 無直接對應;可由 ReEstabAtt − Succ 推算)、`DRB.RlcPacketDropRateDl`(DT 無來源,維持 0,不預設)。
- CM:CU-CP ME 的 `PerfMetricJob.performanceMetrics` 預設為這 4 個;`SupportedPerfMetricGroups` 也列出,可經 SDNC 增減。

## 請 SMO 驗(run K 開始後)
1. dfc 取到 CU-CP ME 的檔、轉換器正常;2. InfluxDB 出現 `…000e3x,GNBCUCPFunction=0,NRCellCU=0` 四個欄位;3. 數值:正常時段多為 0,DT 會在 run 中對 nbr 做一次 30 秒硬鎖製造 RLF,之後那一分鐘 src / mid 的 `RRC.ReEstabAtt` 應 > 0;4. N3 rApp 可把這些加進退出條件(SMO 先前同意)。
- runId 另檔通知。
