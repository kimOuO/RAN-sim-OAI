# E2SM-ANR(ran_func 6)— RIC 端對接指南

> 2026-08-12 上線。E2 Setup 已實測 RIC **accepted=[2,3,4,5,6]**。
> 目的:RIC 透過正規 E2 訂閱收到 ANR情境_v8 卷面全部觀測資料 —— NRT(9.3.38)、
> HO 速率、**RLF/重建、MRO 歸因、HO 失敗原因**、量測聚合、CGI 解析。
> 雙向:同一個 ran_func 6 也承載 **SON 觸發 CONTROL**(ADD/REMOVE/FLAG),見末節。

## 識別資訊

| 項目 | 值 |
|---|---|
| ranFunctionID | **6** |
| OID | `1.3.6.1.4.1.53148.1.1.2.6` |
| shortName | `DT-E2SM-ANR` |
| Indication 編碼 | E2AP 外層標準 ASN.1;SM payload = **JSON + zlib**(比照 func 5 FULLKPM)|
| gate | adapter env `E2SM_ANR_ENABLE`(預設 on)|

## 訂閱方式(xApp,Indication 方向)

與訂 KPM/FULLKPM 完全相同的三段式,ran_func_id 換成 6:

1. **RICsubscriptionRequest**(ran_func_id=6)
   - eventTriggerDefinition:帶 KPM Format1 period(ms)即可;**解不出來預設 1000ms**,留空也能訂
   - actionDefinition:可留空
2. 收 **RICsubscriptionResponse**(admitted)
3. 每 period 收 **RICindication**(type=report),payload zlib 壓縮 + 可分塊:
   - `indicationHeader`(OCTET STRING)= JSON:
     `{"timestamp_ms":…, "sn":…, "format":"DT-ANR-v1", "encoding":"zlib", "part":0, "parts":1, "raw_bytes":…}`
   - `indicationMessage`(OCTET STRING)= **zlib 壓縮位元組**(第 part 塊)

### xApp 解碼(與 func 5 同款,無需 ASN.1 SM decoder)

```python
import json, zlib
hdr = json.loads(indication_header)
buf_by_sn.setdefault(hdr["sn"], {})[hdr["part"]] = indication_message
if len(buf_by_sn[hdr["sn"]]) == hdr["parts"]:
    comp = b"".join(buf_by_sn.pop(hdr["sn"])[i] for i in range(hdr["parts"]))
    anr = json.loads(zlib.decompress(comp))   # ← 下方完整結構
```

> wire 上**不含** `success/message/data` 外層(那是 HTTP API 回應包裝);
> 解壓後第一層即 `timestamp_ms / e2NodeInformation / kpmIndication / rlfKpm / mroKpm / …`。

## indicationMessage 結構(解壓後)

```jsonc
{
  "timestamp_ms": 1786466609342,
  "e2NodeInformation": {                    // §9.3.38 + 卷面延伸
    "servingCells": [{ncgi, physicalCellId, arfcn, radioAccessTechnology}],
    "frequencyRelations": [{radioAccessTechnology, arfcn}],
    "neighbourCellRelations": [{
      sourceCellNcgi, targetCellGlobalId, targetPhysicalCellId, targetArfcn,
      targetRadioAccessTechnology,
      isHoAllowed, isRemoveAllowed, isXnAllowed,      // 卷面延伸(管理面視圖)
      xnX2Established, hoValidated, version,           // §9.3.38 正式
      flags: {hoBlocklist, noRemove, xnBlocklist}
    }],
    "relationChangeEvents": [{action, targetCellGlobalId, by, at, detail}]
  },
  "kpmIndication": {                        // HO 速率/成功比 + 失敗原因
    "cellLevel": {"<cell>": {
        "MM.HoExeAttRatePerMin", "MM.HoExeSuccRatio_last50", "sampleCount_last50",
        "handoverFailureCauseRatePerMin": {"<cause>": <rate>},
        "handoverFailureCauseCumulativeSinceCreation": {"<cause>": <count>} }},
    "perNeighbourRelation": [{sourceCellNcgi, targetCellGlobalId, ...同上}]
  },
  "rlfKpm": {                               // P1:RLF / 重建
    "cellLevel": {"<cell>": {
        "RLF.DetectedRate", "RLF.DropWithoutReestablishmentRate",
        "RRC.ConnReEstabInboundRatePerMin" }},
    "reestablishmentInboundByPreviousPci": [
      {cellNcgi, byPreviousPci: [{previousPhysicalCellId, ratePerMin}]}]
  },
  "mroKpm": {                               // P2:MRO 歸因三聯
    "cellLevel": {"<cell>": {
        "HO.IntraSys.TooEarlyRate", "HO.IntraSys.TooLateRate",
        "HO.IntraSys.ToWrongCellRate" }},
    "total": { …同上三項… }
  },
  "e2MessageCopyAggregate": {               // 鑽取:依 reported PCI 的 RSRP 統計
    "measurementReportAggregate": [{
      reportedPhysicalCellId, reportedArfcn, sampleRatePerMin,
      rsrpPercentile50Dbm, rsrpPercentile90Dbm, rsrpStandardDeviationDb,
      servingRsrpPercentile50Dbm }]
  }
}
```

### 失敗原因值(handoverFailureCause*)
`CellNotAvailable`(target cell 關閉)、`RandomAccessProblem`(target RSRP 過低)、
`TXnRELOCprepExpiry`(prep 逾時,接口就位)、`HandoverToWrongCell`(MRO ToWrongCell 回填)。

## CGI 解析(獨立查詢,非 indication)

PCI confusion 判定走獨立端點(non-periodic,xApp 按需查):
`POST /CU/E2/Anr/cgi_resolve {pci, arfcn?}` → `{results: {<NCGI|FAIL>: 次數}, confusion: bool}`。
(若要走 E2 wire,可用 RC QUERY;目前提供 HTTP 直查。)

## SON 觸發(CONTROL 方向,ran_func 6)

xApp → gNB 的 ADD/REMOVE/FLAG 走 **RIC Control**(非 indication),payload JSON,
adapter 解碼後 POST `/CU/E2/Anr/control`。三種 requestType:
- `ADD`:新增/更新 NrCellRelation(缺漏鄰區偵測後補建)
- `REMOVE`:移除(命中 isRemoveAllowed=false / noRemove → 拒絕,升 SMO_NOTIFY)
- `FLAG`:set/clear hoBlocklist / noRemove / xnBlocklist(封而不刪)
生效以 NRT `version` 變化 / 條目出現消失確認(卷面 confirm 慣用式)。

## 注意事項

- **PDU 大小**:zlib 後單筆約 0.7~3 KB(視 cell/UE/事件數),遠低於 e2term 8KB buffer;超大才分塊(每塊 ≤6KB)。
- **速率語意**:`*RatePerMin` 是牆鐘分鐘;sim 加速時 xApp 需自行除 speed_x 換算 sim-time。
- **空場景**:sim 未跑時結構完整但速率為 0。要看到 RLF/MRO 真數字,搭配 `scenarios/anr_missing_neighbor.json`(缺漏鄰區)或 `anr_pci_confusion.json`。
- **與 func 2/5 並行**:三條訂閱互不影響。

## Sim 端實作位置(維護用)

- 資料源:CU `POST /CU/E2/Anr/indication`(`anr_query_actor.indication`,聚合 `anr_kpm.py` + `mro.py`)
- codec:`RANsim-E2Adapter/.../codec/e2sm_anr_codec.py`(`build_indication_payloads` / control decode)
- producer:`.../sctp_link/sctp_loop.py`(`_handle_anr_sub_req` / `_anr_producer_loop`)
- 能力清單:`RANsim-CU/.../global_e2_node_id.py` ran_functions(id=6)
- 相關:`e2sm_fullkpm.md`(同款 JSON/zlib 信封)、`kpm_field_notes*.md`、`anr_e2_data_gap.md`
