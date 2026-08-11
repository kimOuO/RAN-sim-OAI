# E2 Full KPM 完整欄位報告

> 端點:`POST /api/v0.1/CU/E2/E2FullReporter/read`(CU,port 8101)
> 欄位架構 1:1 對齊 `docs/E2_data_example.md`(legacy ranp-sim E2 輸出格式)
> 實作:`RANsim-CU/main/apps/cu_cp/services/optional/e2/full_kpm_reporter.py`
> 驗證:2026-08-07,2 gNB × 2 cell × 3 UE live sim,8 項結構檢查全過
> (top-level / e2 UE 欄位 / neighbors 內層 / ue_status / pm 190 欄 / pm 字串型別 / bbu_status / timestamp)

## 資料真實性分級

每個欄位標注三種等級之一:

- **真** — 模擬器內實際發生的事件/計算的量測(Sionna 光追、DU 排程器、CU 狀態機)
- **代理** — 數據是真量測,但語意是近似(如 host CPU 溫度代表 BBU 溫度)
- **0** — 模擬器沒有對應事件源,依規格填 0(值恆為 `"0"`)

## 資料流總覽

```
Sionna RT(RSRP/SINR/neighbor)→ RU → DU(排程/RLC/PM 聚合)
  → F1AP measurement_report → CU DB(MeasurementLog / UeContext / HandoverEvent)
                                        │
DU dump_pm(MCS/CQI bins、PRB、PDCP bytes)──┤
UE Status/read(即時位置)────────────────────┼──→ FullKpmReporter.collect()
BbuTelemetry(host psutil/pynvml)───────────┘        → 本報告所述 JSON
```

---

## 1. Top-level 欄位

| 欄位 | 等級 | 來源與說明 |
|---|---|---|
| `timestamp_ms` | 真 | snapshot 產生時刻(epoch ms) |
| `compute_ms` | 真 | 本次 collect() 實際耗時(ms),實測 ~25ms |
| `tick_ms` | 真 | DU `dump_pm` 的 `wall_tick_ms`(目前 tick 實際牆鐘耗時);DU 連不上時 0 |
| `e2` | — | 見 §2 |
| `ue_status` | — | 見 §3 |
| `pm` | — | 見 §4 |
| `bbu_status` | — | 見 §5 |
| `warnings` | 真 | 組裝期間的資料源異常(如 DU/UE 連不上),正常為 `[]` |

## 2. `e2[]` — per-gNB → per-cell → per-UE 無線量測

結構:`e2[] = {gnb_id, timestamp, cells[]}`,`cells[] = {cell_id, ran_name, pci, ues[]}`。

| 欄位 | 等級 | 來源與說明 |
|---|---|---|
| `gnb_id` | 真 | Omniverse 建立的 gNB 名稱(CellConfig.gnb_id) |
| `timestamp` | 真 | epoch 秒 |
| `cell_id` | 真 | CellConfig.nr_cellid 的 15 位 hex(36-bit NCI,同範例格式);無 nr_cellid 時退回字串 cell_id |
| `ran_name` | 真 | gNB 顯示名(= gnb_id) |
| `pci` | 真 | CellConfig.pci |

`ues[]`(只列 RRC=CONNECTED 且 serving 該 cell 的 UE,對齊 O-RAN「KPM 只涵蓋 active UE」語意):

| 欄位 | 等級 | 來源與說明 |
|---|---|---|
| `role` | 真 | 恆 1(CONNECTED)。IDLE UE 不出現在列表 |
| `ue_id` | 真 | UE 名稱 |
| `interfered` | 真(推導) | 任一鄰區 RSRP 進到 serving RSRP **10 dB 以內** → 1。門檻:`_INTERFERED_GAP_DB`。實測弱訊號 UE(SINR -25)正確亮 1 |
| `rsrp` | 真 | Sionna 光追 RSRP,DU 1s window 平均,取整 dBm |
| `rsrq` | 真(計算) | 3GPP 真實版(2026-08-11):`RSRQ = P_target / (12·Σ[P_cell×(1/6+5/6·load)] + noise)` dB —— per-cell RSRP(光追)+ PrbTot% 負載 + noise floor 全為真值;**負載感知**(鄰站閒時 RSRQ 變好);clamp [-43,20]。legacy 公式已棄用 |
| `sinr` | 真 | Sionna 干擾模型 SINR,window 平均,取整 dB |
| `neighbors[]` | 真 | `[{鄰cell_hex_id: {rsrp, rsrq}}]`。RSRP 是 RU 對每支鄰 cell 真實光追量測(經 DU `update_ue_neighbors` 緩存 → F1AP 上報);RSRQ 用 RU 值,RU 沒給時以同公式推導 |
| `dl_throughput` / `ul_throughput` | 真 | DU RLC 實際 drain bytes ÷ window 秒數,Mbps 取整 |
| `rb_start` | 真(推導) | 同 cell 內各 UE 以實際 `rb_width` 依序疊出的虛擬連續配置起點(PF 排程器實際給的 PRB 數是真的;「起始位置」是排列表示法,DU 內部不追蹤實體 RB 起點) |
| `rb_width` | 真 | DU PF 排程器該 window 平均實配 PRB 數 |

## 3. `ue_status[]` — per-UE 綜合狀態

| 欄位 | 等級 | 來源與說明 |
|---|---|---|
| `ue_id` | 真 | UE 名稱 |
| `position` | 真 | UE 容器 `Status/read` 即時位置 [x,y,z](m)。UE 容器連不上時填 [0,0,0] 並記 warnings |
| `serving_gnb` | 真 | serving cell 所屬 gNB 名 |
| `serving_pci` | 真 | serving cell 的 PCI |
| `rsrp_dbm` / `sinr_db` | 真 | 同 §2,保留 1 位小數 |
| `all_rsrp` | 真 | `{gNB名: rsrp}` — serving + 各鄰區量測;同 gNB 多 cell 取最強。只含本次量測有涵蓋的 gNB |
| `throughput_dl_mbps` / `ul` | 真 | 同 §2 |
| `quality` | 真(推導) | SINR ≥10 → `good`,≥0 → `fair`,<0 → `poor`(與範例分級一致) |
| `qos_5qi` | 真 | UeContext.traffic_profile 的 5QI,未指定時預設 9(目前所有 bearer 都建 5QI9) |
| `role` | 真 | 恆 1(CONNECTED) |
| `mcs_dl` | 真 | DU link adaptation 實選 MCS(window 平均) |
| `rb_width_dl` | 真 | 同 §2 rb_width |

## 4. `pm{}` — 每 cell 190 欄 3GPP TS 28.552 計數器

結構:`pm = {"gnb-<gNB名>": [每 cell 一個 dict]}`。**值型別全部是字串**(同範例)。
以下依欄位家族說明;`sum`/`mo-Data` 等衍生欄與家族主欄同源。

### 4.1 檔頭(7 欄)— 真

`cell_id`(同 §2)、`cu/du_timestamp_start/end`(本次 snapshot 時刻,格式 `YYYYMMDD.HHMM+0000`)、`cu/du_filename`(依 3GPP XML 檔名慣例 `A<start>-<end>_<gnb>-cu.xml` 合成,時間內容為真)。

### 4.2 RRC 連線建立(9 欄)— 代理

`cu_RRC.ConnEstabAtt.*` / `ConnEstabSucc.*`:**目前 CONNECTED 在本 cell 的 UE 數**。
語意差異:標準定義是「歷史累計 attach 次數」,模擬器未持久化 per-cell attach 事件,
以現時連線數當代理(每個連線中的 UE 必然完成過一次 attach)。全部歸 `mo-Data`,
`mo-Signalling`/`emergency` 恆 0(模擬器只有 data bearer)。
`cu_RRC.ConnMax`:**真** — process 存活期間該 cell 的連線數高水位(CU 重啟歸零)。
`cu_RRC.ConnMean`:**真** — 當下連線數。

### 4.3 RRC 重建(7 欄)— 0

`ConnReEstabSetup` / `ReEstabAtt` / `ReEstabSuccWith(out)UeContext.*`:模擬器無 RRC re-establishment 流程。

### 4.4 換手 MM.*(7 欄)— 真

來源:`HandoverEvent` 表(A3/RIC-control/手動觸發的每次 HO 都入表),只計 source_cell 仍存在的事件:

| 欄位 | 定義 |
|---|---|
| `cu_MM.HoPrepIntraReq` | 該 cell 為 source 的 HO 事件總數(每次 HO 必經 PREP) |
| `cu_MM.HoPrepIntraSucc` | 進到 EXEC/SUCC/FAIL 的事件數(prep 完成) |
| `cu_MM.HoExeIntraReq` / `HoExeIntraFreqReq` | 進入執行階段的事件數(全部 intra-freq,兩欄同值) |
| `cu_MM.HoExeIntraSucc` / `HoExeIntraFreqSucc` | status=SUCC 的事件數 |
| `cu_gnb.MR.Event.A3` | trigger=A3_TTT 的事件數(RIC control / 手動不計) |

### 4.5 UECNTX / SM / DRB 建立(20 欄)— 代理

`cu_UECNTX.ConnEstab*`:與 §4.2 同源(F1 UE context = RRC 連線 1:1)。
`cu_SM.PDUSessionSetupReq/Succ`、`cu_DRB.EstabAtt/Succ.5QI*`、`InitialEstab*`、`cu_gnb.RRC.ConnEstabSetup.sum`:模擬器每 UE 恰建 1 個 PDU session + 1 個 5QI9 DRB → 值 = 連線數。
`UECNTX.Release.*` / `SM.PDUSessionRelease.*`:0(釋放事件未 per-cell 計數)。

### 4.6 PDCP/SDAP 流量(12 欄)— 真(5QI9);0(5QI1/4)

`cu_DRB.PdcpSduVolumeDL_5QI9` / `Ul_5QI9` / `cu_gnb.DRB.SdapSduVolume*.5QI9`:
**DU pm_aggregator 累計 RLC SDU bytes**(per-5QI 分桶,PDCP≈RLC SDU,差 header 數 byte)。
實測 40 秒 2Mbps×3UE 累計 18,005,769 bytes — 真流量。SDAP 與 PDCP 同值(模擬器無 SDAP 層,同範例行為)。
5QI1/5QI4 欄:0(目前所有流量都是 5QI9;未來掛 5QI1 traffic profile 會自動有值)。

### 4.7 其他 CU 欄(28 欄)— 0

`cu_DRB.PdcpPacketDiscardDL.5QI9`(RLC drop 有統計但未接進本 report,見「已知限制」)、
`PdcpReordDelayUl`、`RelActNbr.*`、`SessionTime.*`、`QF.*`(12 欄,無獨立 QoS flow 流程)、
`ConnReConfig*`、`ConnRelease*`、`SigTime*`(6 欄,模擬器 RRC 訊令無耗時模型)。

### 4.8 PEE 溫度(3 欄)— 代理

`du_169:PEE.AvgTemperature` / `170:Min` / `171:Max`:host CPU 溫度(psutil),
三欄同值(單點量測無 min/max 窗口)。VM 讀不到 sensor 時為 0。
**語意:模擬主機溫度,非真 BBU 硬體。**

### 4.9 MCS 分布(64 欄)— 真

`du_CARR.PDSCHMCSDist.BinTable2.BinMCS0..31`(DL)/ `PUSCHMCSDist.BinTable1.BinMCS0..31`(UL):
DU 排程器**每次實際選定 MCS 就在對應 bin +1**(session 起累計)。
直方圖形狀真實反映通道品質分布 — link adaptation 是照 Sionna SINR 選 MCS 的。

### 4.10 CQI 分布(16 欄)— 真

`du_CARR.WBCQIDist.BinCQI0..15.BinTable2`:每次量測把 SINR 經 CQI 對照表(`sinr_to_cqi`)
映射後在對應 bin +1。與 OAI 的 wideband CQI 統計同語意。

### 4.11 PRB 用量(2 欄)— 真

`du_CARR.PRBUsageDLNbr` / `ULNbr`:DU 累計實配 PRB 數(session 起)。
與現行 KPM 的 `RRU.PrbTotDl`(百分比)不同 — 這裡是**原始累計個數**,同範例語意。

### 4.12 空口延遲(4 欄)— 真(DL 5QI9);0(其餘)

`du_DRB.AirIfDelayDlAvg.5QI9`:該 cell 所有 UE 的 RLC SDU delay(ms)平均 — DU 對每顆 SDU
從進 RLC 到 drain 完成的真實計時。5QI1(無此流量)與 UL(delay 未建模)為 0。

## 5. `bbu_status` — 每 gNB 主機遙測(代理)

`{"gnb-<名>": {...}, "timestamp": "<epoch_ms>"}`,每 gNB 值 = host 量測 ÷ gNB 數(均攤,同 legacy 做法):

| 欄位 | 來源 |
|---|---|
| `cpu` | psutil host CPU% ÷ gNB 數 |
| `cpu_power` | CPU% × 65W TDP 估算 ÷ gNB 數 |
| `cpu_temp` | host CPU 溫度(不均攤) |
| `load_average` | 1-min load ÷ gNB 數 |
| `mem` | host 記憶體 %(不均攤) |
| `tot_power` | cpu_power + GPU 功耗(pynvml 實讀 A40)÷ gNB 數 |

**語意:跑模擬器的 server 資源,非被模擬的 gNB 硬體。** 給 ES xApp 當輸入格式可用,論文中須註明為 proxy。

## 6. 統計摘要

| 區塊 | 真 | 代理 | 0 |
|---|---:|---:|---:|
| top-level(3 資料欄) | 3 | 0 | 0 |
| e2 per-UE(11 欄) | 11 | 0 | 0 |
| ue_status(14 欄) | 14 | 0 | 0 |
| pm(190 欄/cell) | 96 | 32 | 62 |
| bbu_status(6 欄) | 0 | 6 | 0 |

pm 的 62 個 0 欄全屬模擬器無對應事件源的流程(RRC 重建、QoS flow 拆分、訊令耗時、釋放計數),依「量不到就填 0」規格保留欄位。

## 7. 已知限制與未來擴充點

1. **RRC/DRB 建立計數是「現時連線數」代理** — 要變成真歷史累計,需在 CU attach/release 路徑加 per-cell 持久計數器(小改動,尚未做)。
2. **`PdcpPacketDiscardDL` 恆 0** — DU 其實有 RLC drop 統計(AK10 `rlc_drop_sdus`),但目前只留在 DU 本地未上 F1AP;接上即可變真值。
3. **DU 計數器是 session 累計** — MCS/CQI bins、PRB、PDCP bytes 從 sim start 累計,不隨 report 重置;Stop→Start 會歸零(pm_aggregator.reset())。範例的 legacy 系統同為累計語意。
4. **CU 重啟後 `ConnMax` 高水位歸零**(in-process 追蹤)。
5. 本端點是 **HTTP JSON 旁路**,與上 RIC 的 E2SM-KPM ASN.1 wire(9 metrics)並行、互不影響;若要把新欄位推上 E2 wire,需改 e2adapter codec 的 metric 清單並與 RIC 端協調名字。

## 8. 驗證紀錄(2026-08-07)

場景:2 gNB × 2 cell(0°/180° 扇區)、3 UE 方形軌跡、live 模式 1x、每 UE 2 Mbps CBR,40 秒後取樣:

- 8 項結構檢查全過(top-level / e2 / neighbors / ue_status / pm 190 欄 / 字串型別 / bbu / timestamp)
- pm 每 cell 69 個非零欄位;PDCP DL 累計 18.0 MB 與 2Mbps×3UE×40s 量級吻合
- 弱訊號 UE(RSRP -79 / SINR -25)`interfered=1`、`quality=poor` 正確;RSRQ 推導值 -11(好點)/-36(edge)落在合理範圍
- `compute_ms` ≈ 25ms,對 1s polling 無壓力
- 驗證腳本:scratchpad `validate_schema.py`(比對用,未入 repo)
