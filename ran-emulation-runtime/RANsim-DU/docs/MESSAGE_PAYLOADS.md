# RANsim-DU 訊息 Payload 完整規格

> 每個訊息都列出:dataclass schema(每個欄位含真/假來源註解)+ 實機 payload + 對端回應。
> 真假標記:
> - ✅ 真物理 / 真量測 / 真演算法 / 真值
> - ⚠️ 估算 / proxy / 占位

---

## 訊息對照表

| # | 訊息 | 方向 | URL |
|---|---|---|---|
| 1 | `du_setup` | DU → CU | `POST /api/v0.1/CU/F1AP/F1ApRouter/du_setup` |
| 2 | `du_configuration_update` | DU → CU | `POST /api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update` |
| 3 | `ul_rrc_message` | DU → CU | `POST /api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message` |
| 4 | `measurement_report` | DU → CU | `POST /api/v0.1/CU/F1AP/F1ApRouter/measurement_report` |
| 5 | `ue_context_setup` | CU → DU | `POST /api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup` |
| 6 | `ue_context_release` | CU → DU | `POST /api/v0.1/DU/F1AP/F1ApRouter/ue_context_release` |
| 7 | `dl_tti_request` | DU → RU | `POST /api/v0.1/RU/FAPI/FapiRouter/dl_tti_request` |
| 8 | `cqi_indication` | RU → DU | `POST /api/v0.1/DU/FAPI/FapiRouter/cqi_indication` |
| 9 | `crc_indication` | RU → DU | `POST /api/v0.1/DU/FAPI/FapiRouter/crc_indication` |

---

## 1. `du_setup` (DU → CU,啟動)

### Schema (`F1Setup`)

```python
{
    "gnb_du_id":     int,                  # DU 識別碼 — ✅ 設定值,來自 env SIM_GNB_DU_ID
    "served_cells":  list[CellConfig]      # 服務的 cell 列表 — ✅ 設定值,讀 DU 的 CellState DB
}

# CellConfig 子結構
CellConfig = {
    "cell_id":       str,                  # 例 "gnb_A_c0" — ✅ 設定值,Dashboard 推來
    "pci":           int,                  # Physical Cell ID 0..1007 — ✅ 設定值,Dashboard 推來
    "frequency_ghz": float,                # 中心頻率 GHz — ✅ 設定值,Dashboard 推來
    "bandwidth_mhz": float,                # 頻寬 MHz — ✅ 設定值,Dashboard 推來
    "served_plmn":   str = "00101",        # MCC+MNC — ✅ 設定值
    "gnb_id":        str = "",             # 邏輯 gNB 名 — ✅ 設定值,Dashboard 推來
    "is_active":     bool = True           # cell 開關狀態 — ✅ 真狀態,xApp disable/enable 控制
}
```

### 實機 payload

```json
POST http://cu:8000/api/v0.1/CU/F1AP/F1ApRouter/du_setup
{
  "gnb_du_id": 1,
  "served_cells": [
    {"cell_id":"gnb_A_c0","pci":0,"frequency_ghz":3.5,"bandwidth_mhz":100.0,
     "served_plmn":"00101","gnb_id":"gnb_A","is_active":true},
    {"cell_id":"gnb_B_c0","pci":1,"frequency_ghz":3.5,"bandwidth_mhz":100.0,
     "served_plmn":"00101","gnb_id":"gnb_B","is_active":true}
  ]
}
```

### CU 回 (response body)

```json
{
  "status": "success",
  "message": "F1 Setup accepted",
  "data": {"transaction_id": 1, "accepted": true}
}
```

---

## 2. `du_configuration_update` (DU → CU,cell 變更)

### Schema (`GnbDuConfigurationUpdate`)

```python
{
    "gnb_du_id":              int,                # — ✅ 設定值,env SIM_GNB_DU_ID
    "transaction_id":         int = 0,            # — ✅ 真值,DU module-level 單調 counter
    "served_cells_to_add":    list[CellConfig],   # — ✅ 真實 diff,DU 比對 incoming 跟現有 DB 算出
    "served_cells_to_modify": list[CellConfig],   # — ✅ 真實 diff
    "served_cells_to_delete": list[str]           # — ✅ 真實 diff,要刪掉的 cell_id list
}
```

### 實機 payload

```json
POST http://cu:8000/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update
{
  "gnb_du_id": 1,
  "transaction_id": 2,
  "served_cells_to_add": [],
  "served_cells_to_modify": [
    {"cell_id":"gnb_A_c0","pci":0,"frequency_ghz":3.5,"bandwidth_mhz":100.0,
     "served_plmn":"00101","gnb_id":"gnb_A","is_active":true},
    {"cell_id":"gnb_B_c0","pci":1,"frequency_ghz":3.5,"bandwidth_mhz":100.0,
     "served_plmn":"00101","gnb_id":"gnb_B","is_active":true}
  ],
  "served_cells_to_delete": []
}
```

### CU 回 (`GnbDuConfigurationUpdateAcknowledge`)

```json
{"status":"success","data":{"transaction_id": 2, "accepted": true}}
```

---

## 3. `ul_rrc_message` (DU → CU,UE 上行 RRC PDU 中繼)

### Schema (`UlRrcMessageTransfer`)

```python
{
    "ue_id":       str,    # — ✅ 真值,從 UE simulator 注入帶來
    "rrc_msg_b64": str     # base64 of opaque RRC PDU — ✅ 真內容,DU 不解內容透傳
}
```

### 實機 payload(初次 attach 流程)

```json
POST http://cu:8000/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message
{
  "ue_id": "UE_NGAP",
  "rrc_msg_b64": "UlJDU2V0dXBSZXF1ZXN0..."
}
```

> b64 解開 = `"RRCSetupRequest..."`

### CU 回(收 InitialUEMessage 觸發 NGAP mock AMF)

```json
{
  "status": "success", "message": "OK",
  "data": {
    "ue_id": "UE_NGAP",
    "rrc_state": "CONNECTED",
    "ran_ue_ngap_id": 1111129803,
    "ngap_triggered": true
  }
}
```

---

## 4. `measurement_report` (DU → CU,每 5 tick = 2.5 秒一次)

### Schema (`GnbDuMeasurementReport`)

```python
{
    "ue_id":                str,           # UE 識別 — ✅ 真值
    "rsrp_dbm":             float,         # window 平均 — ✅ 真物理,RU Sionna path_gain + link budget
    "sinr_db":              float,         # window 平均 — ✅ 真物理,RU Sionna ||H_eff||²/noise
    "throughput_dl_mbps":   float,         # — ⚠️ 估算,bytes_sum × 8 / window_s / 1e6
    "throughput_ul_mbps":   float = 0.0,   # — ⚠️ 估算,同上
    "mcs_dl":               int = 0,       # window 平均 — ✅ 真演算法,BLER 閉環推
    "rb_width_dl":          int = 0,       # window 平均 PRB — ✅ 真演算法,PF scheduler 配
    "mimo_rank":            int = 1,       # window 平均 — ✅ 真物理,RU 的 SVD effective rank
    "pdcp_sdu_volume_dl":   int = 0,       # 累計 bytes — ⚠️ proxy,RLC SDU bytes 當 PDCP 替代
    "pdcp_sdu_volume_ul":   int = 0,       # — ⚠️ proxy
    "rlc_sdu_delay_dl_ms":  float = 0.0,   # — ✅ 真量測,now() − SduItem.enqueue_ts_ms
    "neighbor_cells":       list[NeighborMeas]   # — ✅ DU 不算 neighbor,通常為空
}
```

### 實機 payload

```json
POST http://cu:8000/api/v0.1/CU/F1AP/F1ApRouter/measurement_report
{
  "ue_id": "A3_UE",
  "rsrp_dbm": -78.3,
  "sinr_db": 13.7,
  "throughput_dl_mbps": 119.04,
  "throughput_ul_mbps": 23.81,
  "mcs_dl": 18,
  "rb_width_dl": 100,
  "mimo_rank": 1,
  "pdcp_sdu_volume_dl": 372000,
  "pdcp_sdu_volume_ul": 74400,
  "rlc_sdu_delay_dl_ms": 0.0,
  "neighbor_cells": []
}
```

---

## 5. `ue_context_setup` (CU → DU)

### Schema (`UeContextSetup`)

```python
{
    "ue_id":           str,                # — ✅ 真值,CU 給的 UE 識別
    "drbs":            list[DrbConfig],    # — ✅ 設定值,CU 從 PDU Session 決策
    "rrc_message_b64": str = ""            # opaque RRC container — ✅ 真內容,CU 透傳
}

DrbConfig = {
    "drb_id":   int,                       # 1..32 — ✅ 設定值,CU 分配
    "qos_5qi":  int,                       # 5G QoS Indicator — ✅ 設定值,從 PDU Session 帶來
    "rlc_mode": str = "AM"                 # AM / UM / TM — ✅ 設定值,CU 決策
}
```

### 實機 payload

```json
POST http://du:8000/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup
{
  "ue_id": "UE_NGAP",
  "drbs": [
    {"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}
  ],
  "rrc_message_b64": ""
}
```

### DU 回 (`UeContextSetupResponse`)

```json
{
  "status": "success", "message": "OK",
  "data": {
    "ue_id": "UE_NGAP",
    "success": true,
    "drb_setup_list": [1]
  }
}
```

---

## 6. `ue_context_release` (CU → DU)

### Schema (`UeContextRelease`)

```python
{
    "ue_id": str,                          # — ✅ 真值
    "cause": str = "normal"                # 釋放原因 — ✅ 設定值,CU 決策
}
```

### 實機 payload

```json
POST http://du:8000/api/v0.1/DU/F1AP/F1ApRouter/ue_context_release
{"ue_id": "UE_NGAP", "cause": "normal"}
```

---

## 7. `dl_tti_request` (DU → RU,每 tick 一次)

### Schema (`DlTtiRequest` + `DlPduConfig`)

```python
{
    "sfn":  int,                              # 0..1023 SFN — ✅ 真值,DU tick counter 推進
    "slot": int,                              # 0..19 slot — ✅ 真值,DU tick counter 推進
    "pdus": list[DlPduConfig]
}

DlPduConfig = {
    "ue_id":              str,                # — ✅ 真值,被排到的 UE
    "prb_start":          int,                # — ✅ 真演算法,PF scheduler 配的起始 PRB index
    "prb_count":          int,                # — ✅ 真演算法,PF metric 算出 PRB 數量
    "mcs":                int,                # 0..27 — ✅ 真演算法,BLER 閉環選的 MCS
    "layers":             int = 1,            # 1..4 — ✅ 真物理,沿用 RU 的 SVD rank
    "pmi":                int = 0,            # — ✅ 真物理,沿用 RU codebook 結果
    "payload_size_bytes": int = 0,            # TBS — ⚠️ 估算,n_rb × 12 × 12 × bps_re × 0.85 公式
    "harq_pid":           int = 0             # 0..15 — ✅ 真值,HARQ manager 配的 process id
}
```

### 實機 payload(2 UE 同時排程)

```json
POST http://ru:8000/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request
{
  "sfn": 3,
  "slot": 11,
  "pdus": [
    {"ue_id":"A3_UE","prb_start":0,"prb_count":100,"mcs":18,"layers":1,"pmi":0,
     "payload_size_bytes":18750,"harq_pid":0},
    {"ue_id":"ue-2","prb_start":100,"prb_count":173,"mcs":9,"layers":1,"pmi":0,
     "payload_size_bytes":6500,"harq_pid":1}
  ]
}
```

---

## 8. `cqi_indication` (RU → DU,每個 dl_tti 之後)

### Schema (`CqiIndication`)

```python
{
    "ue_id":        str,                     # — ✅ 真值
    "sinr_db":      float,                   # — ✅ 真物理,RU 從 Sionna ||H_eff||²/noise 算
    "cqi":          int,                     # 0..15 — ✅ 真物理(查表),38.214 從真 SINR 反推
    "rank":         int = 1,                 # 1..4 — ✅ 真物理,RU SVD H_eff effective rank
    "pmi":          int = 0,                 # — ✅ 真物理,RU codebook 比對最強 precoder
    "rsrp_dbm":     float = -200.0,          # — ✅ 真物理,Sionna path_gain + link budget;-200 = sentinel(舊版 RU 沒帶)
    "serving_cell": str = "",                # — ✅ 真值,RU 從所有 path_gain 挑最強的 gNB
    "neighbors":    list[dict]               # A3 evaluator 用
}

# neighbors 子結構
neighbor_item = {
    "cell_id":  str,                          # — ✅ 真值,RU 把 gnb_name 翻譯成 cell_id
    "rsrp_dbm": float,                        # — ✅ 真物理,Sionna 對該 gNB 的 path_gain 算
    "rsrq_db":  float = 0.0                   # — ⚠️ 占位,沒實作 RSRQ 計算
}
```

### 實機 payload

```json
POST http://du:8000/api/v0.1/DU/FAPI/FapiRouter/cqi_indication
{
  "ue_id": "A3_UE",
  "sinr_db": 13.7,
  "cqi": 9,
  "rank": 1,
  "pmi": 0,
  "rsrp_dbm": -78.3,
  "serving_cell": "gnb_A_c0",
  "neighbors": [
    {"cell_id": "gnb_B_c0", "rsrp_dbm": -95.2, "rsrq_db": 0.0}
  ]
}
```

### DU 回(actor 處理後的 ack)

```json
{
  "status": "success", "message": "OK",
  "data": {
    "ue_id": "A3_UE",
    "new_mcs": 10,
    "smoothed_bler": 9.86e-10
  }
}
```

---

## 9. `crc_indication` (RU → DU,UL HARQ feedback)

### Schema (`CrcIndication`)

```python
{
    "ue_id":    str,                         # — ✅ 真值
    "harq_pid": int,                         # 0..15 — ✅ 真值,RU 從 dl_tti.harq_pid 對映
    "success":  bool                         # CRC pass/fail — ✅ 真模擬,RU 從 BLER 抽樣
}
```

### 實機 payload

```json
POST http://du:8000/api/v0.1/DU/FAPI/FapiRouter/crc_indication
{"ue_id": "A3_UE", "harq_pid": 3, "success": true}
```

### DU 回

```json
{
  "status": "success", "message": "OK",
  "data": {"ue_id": "A3_UE", "harq_pid": 3, "state": "DONE"}
}
```

---

## 跨階段資料流總圖

```
┌──── (1) Boot 階段 ────────────────────────────────────────────────┐
│ DU → CU: F1Setup                                                  │
│   {gnb_du_id, served_cells:[{cell_id,pci,freq,bw,plmn,gnb_id}]}   │
│ CU → DU: F1SetupResponse  {transaction_id, accepted}              │
└───────────────────────────────────────────────────────────────────┘

┌──── (2) Cell 配置動態變更 ─────────────────────────────────────────┐
│ DU → CU: GnbDuConfigurationUpdate                                 │
│   {gnb_du_id, transaction_id,                                     │
│    served_cells_to_{add/modify/delete}}                           │
└───────────────────────────────────────────────────────────────────┘

┌──── (3) UE Attach 流程 ───────────────────────────────────────────┐
│ UE-sim → DU: ul_rrc_message  (is_initial=True, RRCSetupRequest)   │
│     ↓                                                             │
│ DU → CU: UlRrcMessageTransfer  {ue_id, rrc_msg_b64}               │
│     ↓ (CU 觸發 NGAP InitialUEMessage)                              │
│ CU → DU: UeContextSetup  {ue_id, drbs:[{drb_id,5qi,mode}]}        │
│     ↓                                                             │
│ DU → CU: UeContextSetupResponse  {ue_id, success, drb_setup_list} │
└───────────────────────────────────────────────────────────────────┘

┌──── (4) Steady state(每 500 ms 一輪 tick)──────────────────────────┐
│ DU → RU: DlTtiRequest                                             │
│   {sfn, slot, pdus:[{ue_id, prb_start, prb_count, mcs,            │
│                       layers, pmi, payload_size, harq_pid}]}      │
│     ↓ (RU.dl_tti_pipeline 跑 Sionna)                               │
│ RU → DU: CqiIndication                                            │
│   {ue_id, sinr_db, cqi, rank, pmi,                                │
│    rsrp_dbm, serving_cell, neighbors:[{cell_id,rsrp,rsrq}]}       │
│     ↓ (DU.mcs_controller + tick_runner._ue_registry 更新)          │
│                                                                   │
│ 每 5 tick(2.5 秒)觸發一次:                                        │
│ DU → CU: GnbDuMeasurementReport                                   │
│   {ue_id, rsrp_dbm, sinr_db, throughput_dl/ul_mbps,               │
│    mcs_dl, rb_width_dl, mimo_rank,                                │
│    pdcp_sdu_volume_dl/ul, rlc_sdu_delay_dl_ms,                    │
│    neighbor_cells:[]}                                             │
└───────────────────────────────────────────────────────────────────┘

┌──── (5) UL HARQ feedback(UL traffic 才會觸發)─────────────────────┐
│ RU → DU: CrcIndication  {ue_id, harq_pid, success}                │
│   ↓ DU.harq_manager.handle_feedback                               │
└───────────────────────────────────────────────────────────────────┘

┌──── (6) UE Release ────────────────────────────────────────────────┐
│ CU → DU: UeContextRelease  {ue_id, cause}                         │
│   ↓ DU 清 UeMacState + RlcEntity + HARQ pool + PM window          │
└───────────────────────────────────────────────────────────────────┘
```

---

## 真假來源總表

| 訊息.欄位 | 來源 | 真假 |
|---|---|---|
| `du_setup.served_cells[].pci/freq/bw/cell_id/gnb_id` | DU CellState DB | ✅ 設定值 |
| `du_setup.served_cells[].is_active` | xApp disable/enable 控制 | ✅ 真狀態 |
| `du_setup.gnb_du_id` | env `SIM_GNB_DU_ID` | ✅ 設定值 |
| `du_configuration_update.transaction_id` | DU module-level 單調 counter | ✅ 真值 |
| `du_configuration_update.served_cells_to_*` | DU 比對 DB 算的真實 diff | ✅ 真實 diff |
| `ul_rrc_message.rrc_msg_b64` | UE simulator 注入,DU 不解內容透傳 | ✅ 真內容 |
| `cqi_indication.sinr_db` | RU `\|\|H_eff\|\|² / noise`(Sionna H matrix) | ✅ 真物理 |
| `cqi_indication.rsrp_dbm` | RU `TX_power + antenna_gain + 10·log10(path_gain)` | ✅ 真物理 |
| `cqi_indication.cqi` | RU `sinr_to_cqi(sinr)`,38.214 從真 SINR 反推 | ✅ 真物理(查表) |
| `cqi_indication.rank` | RU SVD effective rank | ✅ 真物理 |
| `cqi_indication.pmi` | RU codebook 比對最強 precoder | ✅ 真物理 |
| `cqi_indication.serving_cell` | RU 挑最強 path_gain 的 gNB | ✅ 真值 |
| `cqi_indication.neighbors[].rsrp_dbm` | Sionna 所有非 serving gNB 的 path_gain | ✅ 真物理 |
| `cqi_indication.neighbors[].rsrq_db` | 沒實作 RSRQ 計算 | ⚠️ 占位 |
| `crc_indication.success` | RU 從真 SINR 對應 BLER 抽樣 | ✅ 真模擬 |
| `dl_tti_request.sfn / slot` | DU tick counter 推進 | ✅ 真值 |
| `dl_tti_request.pdus[].mcs` | DU `mcs_controller` BLER 閉環 | ✅ 真演算法 |
| `dl_tti_request.pdus[].prb_start/count` | DU `pf_scheduler` PF metric | ✅ 真演算法 |
| `dl_tti_request.pdus[].layers/pmi` | 沿用 RU 物理算的值 | ✅ 真物理 |
| `dl_tti_request.pdus[].payload_size_bytes` | 公式 `n_rb × 12 × 12 × bps_re × 0.85` | ⚠️ 估算 |
| `dl_tti_request.pdus[].harq_pid` | DU HarqManager 配 | ✅ 真值 |
| `measurement_report.rsrp_dbm` | window 平均(來源 RU 真物理) | ✅ 真 |
| `measurement_report.sinr_db` | window 平均(來源 RU 真物理) | ✅ 真 |
| `measurement_report.mcs_dl` | window 平均(DU 真演算法) | ✅ 真 |
| `measurement_report.rb_width_dl` | window 平均(DU 真演算法) | ✅ 真 |
| `measurement_report.mimo_rank` | window 平均(來源 RU 真物理) | ✅ 真 |
| `measurement_report.throughput_dl/ul_mbps` | `bytes_sum × 8 / window_s / 1e6` | ⚠️ 估算 |
| `measurement_report.pdcp_sdu_volume_dl/ul` | RLC bytes 當 PDCP proxy | ⚠️ proxy |
| `measurement_report.rlc_sdu_delay_dl_ms` | `now() − SduItem.enqueue_ts_ms` | ✅ 真量測 |
| `ue_context_setup.drbs[].drb_id/qos_5qi/rlc_mode` | CU 從 PDU Session 決策 | ✅ 設定值 |
