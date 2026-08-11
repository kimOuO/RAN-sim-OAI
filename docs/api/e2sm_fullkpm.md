# E2SM-DTFULLKPM(ran_func 5)— RIC 端對接指南

> 2026-08-07 上線。E2 Setup 已實測 RIC accepted=[2,3,4,5]。
> 目的:RIC 透過**正規 E2 訂閱流程**收到完整 `docs/E2_data_example.md` 格式資料
>(UE 位置、鄰區 RSRP/RSRQ、每 cell 190 個 TS 28.552 PM counter、MCS/CQI 分布、
> HO 統計、BBU 狀態 —— 逐欄位說明見 `docs/E2_full_kpm_fields.md`)。

## 識別資訊

| 項目 | 值 |
|---|---|
| ranFunctionID | **5** |
| OID | `1.3.6.1.4.1.53148.1.1.2.100` |
| shortName | `DT-E2SM-FULLKPM` |
| 編碼 | E2AP 外層標準 ASN.1;SM 內層 payload 全部 **JSON**(比照 O-RAN E2SM-CCC 先例)|

## 訂閱方式(xApp)

與訂 KPM 完全相同的三段式,只是 ran_func_id 換成 5:

1. **RICsubscriptionRequest**(ran_func_id=5)
   - eventTriggerDefinition:建議帶 E2SM-KPM Format1 的 reportingPeriod(ms);
     **解不出來 adapter 預設 1000ms**,所以留空/亂填也能訂
   - actionDefinition:可留空(全量資料,沒有 metric 挑選)
2. 收 **RICsubscriptionResponse**(admitted)
3. 每 period 收 **RICindication**(type=report),**payload 是 zlib 壓縮 + 可分塊**
   (v1.1,2026-08-07:因 OSC e2term SCTP recv buffer 8KB,60KB 裸 JSON 會被截斷):
   - `indicationHeader`(OCTET STRING)= JSON:
     `{"timestamp_ms": 1786..., "sn": 42, "format": "DTFULLKPM-v1",
       "encoding": "zlib", "part": 0, "parts": 1, "raw_bytes": 61129}`
   - `indicationMessage`(OCTET STRING)= **zlib 壓縮位元組**(的第 part 塊)

xApp 解碼(不需要任何 ASN.1 SM decoder):

```python
import json, zlib
hdr = json.loads(indication_header)
# 同一 sn 的 parts 依 part 序 concat(多數情況 parts=1,直接解)
buf_by_sn.setdefault(hdr["sn"], {})[hdr["part"]] = indication_message
if len(buf_by_sn[hdr["sn"]]) == hdr["parts"]:
    comp = b"".join(buf_by_sn.pop(hdr["sn"])[i] for i in range(hdr["parts"]))
    data = json.loads(zlib.decompress(comp))   # ← E2_data_example.md 的 data 區
```

`data` 結構 = `{timestamp_ms, compute_ms, tick_ms, e2:[...], ue_status:[...], pm:{...}, bbu_status:{...}, warnings:[]}`。

## 注意事項

- **PDU 大小**:zlib 後單筆 ~2.5 KB(壓縮率 ~28x),遠低於 e2term 8KB buffer;
  超大場景才會出現 parts>1(每塊 ≤6KB)。
- **速度同步**:sim 跑加速(如 2x)時,adapter 依 sim-time 對齊 —— 牆鐘上 indication
  會變密,模擬時間軸上維持每 period 一筆。
- **資料語意**:哪些欄位是真量測/代理值/恆 0,見 `docs/E2_full_kpm_fields.md`
  (pm 190 欄:96 真 / 32 代理 / 62 個無事件源恆 "0")。
- 與 func 2 的 9-metric KPM **並行**,互不影響;mobiflow 現有 pipeline 不用動。

## Sim 端實作位置(維護用)

- codec:`RANsim-E2Adapter/main/apps/e2_adapter/services/optional/codec/e2sm_fullkpm_codec.py`
- SUB_REQ 分流 + producer:同目錄 `sctp_link/sctp_loop.py`(`_handle_fullkpm_sub_req` / `_fullkpm_producer_loop`)
- 資料源:CU `POST /api/v0.1/CU/E2/E2FullReporter/read`(`full_kpm_reporter.py`)
- gate:e2adapter env `E2SM_FULLKPM_ENABLE`(預設 on;關掉即不進 E2 Setup)
- CU 能力清單:`RANsim-CU/.../global_e2_node_id.py` ran_functions[3]
