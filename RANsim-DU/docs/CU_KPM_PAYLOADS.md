# RANsim-CU 對外 KPM / E2 訊息 Payload 完整規格

> 這份對應 O-RAN E2 介面在 CU 側的對外 endpoint。**全部走 HTTP/JSON 取代 SCTP/ASN.1**,但保持 OAI E2AP 三段式語意:Subscribe → Indication → Control。
>
> 真假標記:
> - ✅ 真物理 / 真量測 / 真演算法 / 真值
> - ⚠️ 估算 / proxy / 占位
> - ❌ 假值(沒實作或硬編)
>
> 對齊參考:
> - **3GPP TS 28.552**(5G PM Measurements 命名)
> - **O-RAN WG3 E2SM-KPM v2.0.03**(Format 3 UE-level indication)
> - **OAI** `openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm.c::fill_kpm_ind_msg_frm_3()`

---

## 對外 Endpoint 對照表

| # | 訊息 | 方向 | URL | OAI E2AP 對應 |
|---|---|---|---|---|
| 1 | E2NodeId read | adapter → CU | `POST /api/v0.1/CU/E2/E2NodeId/read` | E2 Setup Request 前置 |
| 2 | KPM Subscription create | xApp → CU | `POST /api/v0.1/CU/E2/Subscription/create` | RIC Subscription Request |
| 3 | KPM Subscription delete | xApp → CU | `POST /api/v0.1/CU/E2/Subscription/delete` | RIC Subscription Delete Request |
| 4 | KPM Indication poll | xApp → CU | `POST /api/v0.1/CU/E2/Indication/poll` | RIC Indication(polling 取代 SCTP push)|
| 5 | KPM Indication push | CU → xApp | WebSocket `/ws/cu/e2/<sub_id>/` | RIC Indication(push 版) |
| 6 | KPM Snapshot read | xApp/Dashboard → CU | `POST /api/v0.1/CU/E2/E2KpmReporter/read` | (RANsim 擴展:整合視圖) |
| 7 | E2 Control request | xApp → CU | `POST /api/v0.1/CU/E2/Control/request` | RIC Control Request |

---

## 1. E2NodeId/read (adapter → CU,啟動時拿 globalE2node-ID)

對應 O-RAN E2AP v2.0.3 §9.1.1.5 — E2 adapter 啟動時拿這個 payload PER-encode 進 E2 Setup Request 的 globalE2node-ID 欄位。

### Schema (response)

```python
{
  "global_e2_node_id": {
    "plmn_id": {
      "mcc": str,                       # 3-digit Mobile Country Code — ✅ 設定值,env PLMN_MCC
      "mnc": str                        # 2~3-digit Mobile Network Code — ✅ 設定值,env PLMN_MNC(自動補零到 3 碼)
    },
    "gnb_id": {
      "value_hex":  str,                # 例 "0x00000038" — ✅ 設定值,env GNB_ID_HEX
      "value_int":  int,                # decimal form — ✅ 真值,從 hex 解析
      "bit_length": int                 # 22..32 bit — ✅ 設定值,env GNB_ID_LENGTH
    }
  },
  "ran_functions": [
    {
      "ran_function_id":       int,     # 整數 ID — ✅ 設定值,env RAN_FUNC_ID_KPM(預設 2)
      "ran_function_oid":      str,     # 標準 OID — ✅ 設定值,"1.3.6.1.4.1.53148.1.2.2.2"(E2SM-KPM v2.0.03)
      "ran_function_revision": int,     # — ✅ 設定值
      "service_model":         str,     # "KPM" / "RC" — ✅ 設定值
      "version":               str      # 例 "v2.0.03" — ✅ 設定值
    },
    ...
  ]
}
```

### 實機 payload(response body)

```json
POST http://cu:8000/api/v0.1/CU/E2/E2NodeId/read

→
{
  "status": "success",
  "data": {
    "global_e2_node_id": {
      "plmn_id": {"mcc": "208", "mnc": "095"},
      "gnb_id": {
        "value_hex":  "0x00000038",
        "value_int":  56,
        "bit_length": 22
      }
    },
    "ran_functions": [
      {
        "ran_function_id":       2,
        "ran_function_oid":      "1.3.6.1.4.1.53148.1.2.2.2",
        "ran_function_revision": 1,
        "service_model":         "KPM",
        "version":               "v2.0.03"
      },
      {
        "ran_function_id":       3,
        "ran_function_oid":      "1.3.6.1.4.1.53148.1.1.2.3",
        "ran_function_revision": 1,
        "service_model":         "RC",
        "version":               "v01.03"
      }
    ]
  }
}
```

### 來源準確度

| 欄位 | 來源 | 真假 | 備註 |
|---|---|---|---|
| `plmn_id.mcc/mnc` | env `PLMN_MCC` / `PLMN_MNC`(預設 208/95) | ✅ 設定值 | 跟標準 O-RAN R-NIB 約定 |
| `gnb_id.value_hex/int` | env `GNB_ID_HEX`(預設 `0x000038`)| ✅ 設定值 | hex/int 兩種格式都能查 |
| `ran_function_oid` (KPM) | hardcode `1.3.6.1.4.1.53148.1.2.2.2` | ✅ **真 OID,標準 KPMv2.0.03** | 不是 FlexRIC 私有 ID |

---

## 2. KPM Subscription/create (xApp → CU)

xApp 訂閱要哪些 metric、多久報一次。對應 OAI `RIC Subscription Request`。

### Schema (request body)

```python
{
  "service_model":    str,                        # "KPM" / "RC" — ✅ xApp 指定
  "ran_function_id":  int = None,                 # 不填會用 _RAN_FUNC_ID_MAP[sm](KPM=2/RC=3)
  "ric_req_id": {
    "requestor_id":   int,                        # — ✅ xApp 指定的 caller ID
    "instance_id":    int                         # — ✅ xApp 給的 instance
  },
  "action_definition": {
    "metrics":          list[str],                # 要報的 KPM 名稱 — ✅ xApp 指定,會被 supported list 驗證
    "ue_filter":        list[str] = []            # 空 = 全 UE — ✅ xApp 指定
  },
  "event_trigger": {
    "report_period_ms": int = 1000                # 多久推一次 — ✅ xApp 指定
  }
}
```

### 支援的 metric(`kpm_indication.METRIC_EXTRACTORS`)

```python
[
  "DRB.UEThpDl",          # DL throughput(kbps)
  "DRB.UEThpUl",          # UL throughput(kbps)
  "DRB.PdcpSduVolumeDL",  # DL PDCP SDU bytes 累計
  "DRB.PdcpSduVolumeUL",  # UL PDCP SDU bytes 累計
  "DRB.RlcSduDelayDl",    # DL RLC dwell delay(ms)
  "RRU.PrbTotDl",         # DL PRB 使用率(%)
  "RRU.PrbTotUl",         # UL PRB 使用率(%)
  "RSRP",                 # 接收強度(dBm)— RANsim 擴展
  "SINR"                  # 訊雜比(dB)— RANsim 擴展
]
```

### 實機 payload(request)

```json
POST http://cu:8000/api/v0.1/CU/E2/Subscription/create
{
  "service_model": "KPM",
  "ran_function_id": 2,
  "ric_req_id": {"requestor_id": 1001, "instance_id": 1},
  "action_definition": {
    "metrics": ["DRB.UEThpDl", "DRB.PdcpSduVolumeDL", "RSRP", "SINR"],
    "ue_filter": []
  },
  "event_trigger": {
    "report_period_ms": 1000
  }
}
```

### CU 回 (response)

```json
{
  "status": "success",
  "message": "subscribed",
  "data": {
    "subscription_id":  "sub-7a3c9f2b1e4d",     # CU 生的 UUID — ✅ 真值
    "ric_req_id":       {"requestor_id": 1001, "instance_id": 1},
    "ran_function_id":  2,
    "status":           "active"
  }
}
```

---

## 3. KPM Subscription/delete

```python
{
  "subscription_id": str    # 要解訂的 sub_id — ✅ xApp 指定,從 create response 帶來
}
```

### CU 回

```json
{
  "status": "success",
  "data": {"subscription_id": "sub-7a3c9f2b1e4d", "status": "deleted"}
}
```

---

## 4. KPM Indication / poll(xApp → CU,polling 模式)

xApp 拿 indications。每次 poll 觸發 build,然後 drain buffer。

### Request

```python
{
  "subscription_id": str    # 要 poll 的 sub_id — ✅ xApp 指定
}
```

### Response — KPM Indication 主結構(format 3 UE-level)

```python
{
  "subscription_id":  str,
  "indications":      list[KpmIndication],
  "count":            int    # 這次 drain 拿到幾筆
}

# KpmIndication 子結構(對齊 OAI Format 3)
KpmIndication = {
  "subscription_id":  str,
  "ric_req_id":       {"requestor_id": int, "instance_id": int},
  "ran_function_id":  int,                      # KPM=2
  "indication_header": {
    "timestamp_ms":   int                       # 產 indication 的當下時間戳 — ✅ 真值,time.time()
  },
  "indication_message": {
    "format":               3,                  # OAI Format 3
    "ue_meas_report_lst":   list[UeMeasReport]
  }
}

# UeMeasReport 子結構(每個 UE 一筆)
UeMeasReport = {
  "ue_id":          str,                        # — ✅ 真值,CU UeContext DB
  "rrc_ue_id":      int | None,                 # gNB-CU-UE-F1AP-ID — ✅ 真值,UeContext.rrc_ue_id
  "amf_ue_ngap_id": int | None,                 # AMF-UE-NGAP-ID — ✅ 真值,NGAP attach 時 mock AMF 給的
  "serving_cell":   str,                        # — ✅ 真值,UeContext.serving_cell
  "nr_cell_id":     int,                        # 36-bit NR Cell ID — ⚠️ 估算,從 cell_id 字串 SHA-1 hash
  "meas_data_lst":  list[MeasItem]
}

# MeasItem(metrics 結果)
MeasItem = {
  "name":   str,                                # OAI metric 名稱
  "value":  float | int | None,                 # ← 來源見下表
  "unit":   str                                 # kbps / bytes / % / dBm / dB / ms
}
```

### 實機 payload(request → response)

```
POST http://cu:8000/api/v0.1/CU/E2/Indication/poll
{"subscription_id": "sub-7a3c9f2b1e4d"}

→
```
```json
{
  "status": "success",
  "data": {
    "subscription_id": "sub-7a3c9f2b1e4d",
    "count": 2,
    "indications": [
      {
        "subscription_id": "sub-7a3c9f2b1e4d",
        "ric_req_id": {"requestor_id": 1001, "instance_id": 1},
        "ran_function_id": 2,
        "indication_header": {"timestamp_ms": 1746523874321},
        "indication_message": {
          "format": 3,
          "ue_meas_report_lst": [
            {
              "ue_id": "A3_UE",
              "rrc_ue_id": 12345,
              "amf_ue_ngap_id": 1111129803,
              "serving_cell": "gnb_A_c0",
              "nr_cell_id": 84762547129,
              "meas_data_lst": [
                {"name": "DRB.UEThpDl",         "value": 119040.0, "unit": "kbps"},
                {"name": "DRB.PdcpSduVolumeDL", "value": 372000,   "unit": "bytes"},
                {"name": "RSRP",                "value": -78.3,    "unit": "dBm"},
                {"name": "SINR",                "value": 13.7,     "unit": "dB"}
              ]
            }
          ]
        }
      },
      { /* 下一筆 indication ... */ }
    ]
  }
}
```

### 各欄位來源 / 準確度(關鍵)

| metric | 計算式 / 來源 | 真假 | 準確度說明 |
|---|---|---|---|
| `DRB.UEThpDl` | `MeasurementLog.throughput_dl_mbps × 1000` | ⚠️ **估算** | 來源是 DU `bytes_sum × 8 / window_s / 1e6`,沒真 LDPC,但範圍對齊 OAI |
| `DRB.UEThpUl` | `throughput_ul_mbps × 1000` | ⚠️ **估算 / 占位** | 目前沒 UL traffic,常為 0 或 DL 的 1/5 占位 |
| `DRB.PdcpSduVolumeDL` | `MeasurementLog.pdcp_sdu_volume_dl` | ⚠️ **proxy** | DU 用 RLC SDU bytes 當 PDCP 替代(沒做 PDCP layer),差幾 byte PDCP header |
| `DRB.PdcpSduVolumeUL` | `pdcp_sdu_volume_ul` | ⚠️ **proxy** | 同上,且 UL 流量目前 idle,常為 0 |
| `DRB.RlcSduDelayDl` | `MeasurementLog.rlc_sdu_delay_dl_ms` | ✅ **真量測** | DU `now() − SduItem.enqueue_ts_ms`,真實 dwell time |
| `RRU.PrbTotDl` | `rb_width_dl / 273 × 100` | ✅ **真演算法** | DU PF scheduler 配的 PRB / 該 cell 總 PRB(預設 273 = 100 MHz @ 30 kHz SCS) |
| `RRU.PrbTotUl` | `rb_width_dl / 273 × 100 / 5` | ⚠️ **估算** | UL idle,用 DL 的 1/5 估 |
| `RSRP` | `MeasurementLog.rsrp_dbm` | ✅ **真物理** | 來源 RU 的 `TX_power + antenna_gain + 10·log10(path_gain)`,Sionna ray-tracing |
| `SINR` | `MeasurementLog.sinr_db` | ✅ **真物理** | 來源 RU 的 `\|\|H_eff\|\|² / noise`,Sionna H matrix |
| `nr_cell_id`(UE-level)| `SHA-1(cell_id_str)[:5] & 36-bit mask` | ⚠️ **deterministic hash** | 不是真 OAI gnb_id+local_cell_id 拼出的,但 collision < 1e-7,xApp 拿來 group 是夠的 |
| `rrc_ue_id` | `UeContext.rrc_ue_id` | ✅ 真值 | F1AP UE Context Setup 時生 |
| `amf_ue_ngap_id` | `UeContext.amf_ue_ngap_id` | ✅ **真值(mock AMF)** | NGAP InitialUEMessage 後 mock AMF 給的隨機 32-bit ID |

---

## 5. KPM Indication / push(WebSocket,即時推給 xApp)

### URL

```
ws://cu:8000/ws/cu/e2/<subscription_id>/
```

### Message frame(JSON over WebSocket)

```python
{
  "type":         "kpm.indication",
  "indication":   KpmIndication        # 跟 polling 的 indication 結構完全相同
}
```

producer 設計(`indication_producer.py`):
- daemon thread 跑 asyncio loop
- 每 100 ms 掃一次所有有 ws consumer 的 sub
- 看 `event_trigger.report_period_ms` 決定要不要 build 新 indication
- build 完直接 push 給該 sub 的所有 ws consumer + 累積進 buffer 給 polling 拿

---

## 6. E2KpmReporter/read(整合 snapshot — RANsim 擴展)

這個不是標準 E2,是 RANsim 給 Dashboard 用的整合視圖,**一次拿全部**:UE 列表 + per-cell PM + bbu_status。

### Response Schema

```python
{
  "timestamp": str,                              # ISO 8601 — ✅ 真值,服務當下時間
  "ue_status": list[UeSnapshot],                 # 每個 UE 一筆 — ✅ 真值
  "pm":  dict[cell_id, dict[metric_name, int]],  # per-cell PM counters
  "bbu_status": dict[cell_id, BbuStatus]         # per-cell 硬體遙測
}

# UeSnapshot
UeSnapshot = {
  "ue_id":                str,                   # — ✅ 真值
  "rrc_state":            str,                   # IDLE / CONNECTED — ✅ 真值,UeContext.rrc_state
  "serving_cell":         str,                   # — ✅ 真值
  "rsrp_dbm":             float | None,          # — ✅ 真物理,RU Sionna(同 measurement_report)
  "sinr_db":              float | None,          # — ✅ 真物理
  "throughput_dl_mbps":   float,                 # — ⚠️ 估算
  "throughput_ul_mbps":   float,                 # — ⚠️ 估算
  "mcs_dl":               int,                   # — ✅ 真演算法
  "rb_width_dl":          int,                   # — ✅ 真演算法
  "mimo_rank":            int,                   # — ✅ 真物理
  "pdcp_sdu_volume_dl":   int,                   # — ⚠️ proxy(RLC bytes)
  "pdcp_sdu_volume_ul":   int,                   # — ⚠️ proxy
  "rlc_sdu_delay_dl_ms":  float,                 # — ✅ 真量測
  "neighbor_cells":       list[NeighborMeas],    # — ✅ 真物理(來源 RU)
  "measured_at":          str | None             # 該筆量測的 ISO 時間 — ✅ 真值
}

# pm[cell_id] 子結構(來自 HandoverEvent + UeContext 統計)
PmPerCell = {
  "MM.HoExeIntraReq":    int,                    # 該 source_cell 的 HO 嘗試次數 — ✅ 真值,DB count
  "MM.HoExeIntraSucc":   int,                    # 成功次數 — ✅ 真值,status=SUCC count
  "gnb.MR.Event.A3":     int,                    # A3 觸發次數 — ✅ 真值,trigger=A3_TTT count
  "RRC.ConnMean":        int,                    # 該 cell 當下連線 UE 數 — ✅ 真值,UeContext.filter(state=CONNECTED)
  "RRC.ConnMax":         int                     # 連線數歷史峰值 — ⚠️ 估算,只取當下 max,沒做時間視窗
}

# bbu_status[cell_id] 子結構(host 真實感測,平均到每 cell)
BbuStatus = {
  "cpu":           float,                        # CPU 使用率 % — ✅ 真量測,psutil
  "cpu_power":     float,                        # CPU 功耗估算(W)— ⚠️ 估算,cpu_pct × 65 W TDP
  "cpu_temp":      float,                        # CPU 溫度(°C)— ✅ 真量測,psutil sensors_temperatures
  "load_average":  float,                        # 1-min load avg — ✅ 真量測,os.getloadavg
  "mem":           float,                        # 記憶體使用率 % — ✅ 真量測,psutil virtual_memory
  "tot_power":     float                         # CPU+GPU 總功耗(W)— ⚠️ 估算(CPU)+ 真量測(GPU pynvml)
}
```

### 實機 payload(response)

```json
POST http://cu:8000/api/v0.1/CU/E2/E2KpmReporter/read

→
{
  "status": "success",
  "message": "kpm snapshot",
  "data": {
    "timestamp": "2026-05-06T08:30:50.123456+00:00",
    "ue_status": [
      {
        "ue_id": "A3_UE",
        "rrc_state": "CONNECTED",
        "serving_cell": "gnb_A_c0",
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
        "neighbor_cells": [
          {"cell_id": "gnb_B_c0", "rsrp_dbm": -95.2, "rsrq_db": 0.0}
        ],
        "measured_at": "2026-05-06T08:30:48.500000+00:00"
      }
    ],
    "pm": {
      "gnb_A_c0": {
        "MM.HoExeIntraReq": 4,
        "MM.HoExeIntraSucc": 3,
        "gnb.MR.Event.A3": 2,
        "RRC.ConnMean": 1,
        "RRC.ConnMax": 1
      },
      "gnb_B_c0": {
        "RRC.ConnMean": 0,
        "RRC.ConnMax": 0
      }
    },
    "bbu_status": {
      "gnb_A_c0": {
        "cpu": 24.5, "cpu_power": 15.93, "cpu_temp": 58.0,
        "load_average": 1.42, "mem": 67.3, "tot_power": 32.18
      },
      "gnb_B_c0": {
        "cpu": 24.5, "cpu_power": 15.93, "cpu_temp": 58.0,
        "load_average": 1.42, "mem": 67.3, "tot_power": 32.18
      },
      "timestamp": "2026-05-06T08:30:50.123456+00:00"
    }
  }
}
```

---

## 7. E2 Control / request(xApp → CU,RC service model)

xApp 下控制指令給 RAN(handover、cell on/off、PRB quota...)。對應 OAI E2-SM-RC RIC Control Request。

### Schema (request)

```python
{
  "ric_req_id":       {"requestor_id": int, "instance_id": int},
  "ran_function_id":  int = 3,                   # RC = 3
  "control_header": {
    "control_style":     int,                    # 1 / 2 / 3
    "control_action_id": int,                    # 取決於 style
    "ue_id":          str = None,                # UE-level control 用
    "ngap_id":        int = None,                # 替代,xApp wrapper 格式
    "f1ap_id":        int = None,                # 替代,xApp wrapper 格式
    "cell_id":        str = None                 # cell-level control 用
  },
  "control_message": dict                        # 看 (style, action) 不同結構
}
```

### 支援的 (style, action) 組合

| Style | Action | 用途 | OAI 對應 | 實作狀態 |
|---|---|---|---|---|
| 1 | 2 | Radio Bearer Control / QoS flow mapping | `ran_func_rc.c::write_ctrl_rc_sm` | ✅ 標準 |
| 2 | 6 | Slice-level PRB Quota(IM/ES xApp 用) | OAI 規範,RANsim 補完 | ✅ 擴展 |
| 2 | 7 | Cell On/Off(Energy-saving xApp 用)| OAI 規範,RANsim 補完 | ✅ 擴展 |
| 3 | 1 | Mobility Control / Handover Control | OAI 有定義未實作,RANsim 補上 | ✅ 擴展 |

### Style 3 / Action 1 — Handover Control 範例

```json
POST http://cu:8000/api/v0.1/CU/E2/Control/request
{
  "ric_req_id": {"requestor_id": 1002, "instance_id": 5},
  "ran_function_id": 3,
  "control_header": {
    "control_style": 3,
    "control_action_id": 1,
    "ue_id": "A3_UE"
  },
  "control_message": {
    "target_cell": "gnb_B_c0"
  }
}
```

### Style 2 / Action 6 — PRB Quota 範例

```json
{
  "ric_req_id": {"requestor_id": 1003, "instance_id": 1},
  "ran_function_id": 3,
  "control_header": {
    "control_style": 2,
    "control_action_id": 6,
    "cell_id": "gnb_A_c0"
  },
  "control_message": {
    "min_prb": 10,
    "max_prb": 80,
    "dedicated_prb": 0
  }
}
```

### Style 2 / Action 7 — Cell Off 範例

```json
{
  "ric_req_id": {"requestor_id": 1004, "instance_id": 1},
  "ran_function_id": 3,
  "control_header": {
    "control_style": 2,
    "control_action_id": 7,
    "cell_id": "gnb_B_c0"
  },
  "control_message": {
    "action": "disable"
  }
}
```

---

## 訊息資料流總圖

```
┌── (1) E2 Setup 階段 ────────────────────────────────────────────┐
│ adapter → CU: E2NodeId/read                                     │
│   ← {global_e2_node_id, ran_functions:[{KPM=2,RC=3}]}           │
│                                                                 │
│ adapter 拿到後 PER-encode 進 E2 Setup Request 送 RIC             │
└─────────────────────────────────────────────────────────────────┘

┌── (2) xApp 訂閱 ────────────────────────────────────────────────┐
│ xApp → CU: Subscription/create                                  │
│   {service_model:"KPM", action_def:{metrics:[...],period_ms}}   │
│   ← {subscription_id, status:"active"}                          │
└─────────────────────────────────────────────────────────────────┘

┌── (3) Indication 推送(兩種模式)───────────────────────────────┐
│                                                                 │
│ 模式 A — polling:                                                │
│   xApp → CU: Indication/poll {subscription_id}                  │
│   ← {indications:[KpmIndication, ...], count}                   │
│                                                                 │
│ 模式 B — WebSocket push:                                         │
│   producer thread 每 100ms 掃 active subs                       │
│   到期 → build → ws.send_json(KpmIndication)                    │
│                                                                 │
│ KpmIndication 結構(format 3):                                  │
│   ├ indication_header.timestamp_ms                              │
│   └ indication_message.ue_meas_report_lst[]                     │
│       ├ ue_id, rrc_ue_id, amf_ue_ngap_id                        │
│       ├ serving_cell, nr_cell_id                                │
│       └ meas_data_lst[{name, value, unit}]                      │
└─────────────────────────────────────────────────────────────────┘

┌── (4) xApp 下控制 ──────────────────────────────────────────────┐
│ xApp → CU: Control/request                                      │
│   {control_style, control_action_id, control_header,...}        │
│   ← {success, action_taken}                                     │
└─────────────────────────────────────────────────────────────────┘

┌── (5) Dashboard 整合視圖 ───────────────────────────────────────┐
│ Dashboard → CU: E2KpmReporter/read                              │
│   ← {ue_status:[...], pm:{cell:metrics}, bbu_status:{...}}      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 真假來源總表(KPM 訊息所有欄位)

| 訊息.欄位 | 來源 / 計算 | 真假 | 鏈路 |
|---|---|---|---|
| **E2NodeId** | | | |
| `global_e2_node_id.plmn_id.mcc/mnc` | env `PLMN_MCC` / `PLMN_MNC` | ✅ 設定值 | hardcode |
| `global_e2_node_id.gnb_id.value_*` | env `GNB_ID_HEX`(預設 0x000038) | ✅ 設定值 | hardcode |
| `ran_functions[].ran_function_oid` | `1.3.6.1.4.1.53148.1.2.2.2`(KPM 標準) | ✅ 真 OID | 對齊 O-RAN WG3 |
| **KPM Indication header** | | | |
| `indication_header.timestamp_ms` | `time.time() × 1000` | ✅ 真值 | 系統時鐘 |
| **KPM Indication UE-level** | | | |
| `ue_meas_report_lst[].ue_id` | `UeContext.ue_id` | ✅ 真值 | DB |
| `ue_meas_report_lst[].rrc_ue_id` | `UeContext.rrc_ue_id` | ✅ 真值 | F1AP UE Context Setup 時 CU 生 |
| `ue_meas_report_lst[].amf_ue_ngap_id` | `UeContext.amf_ue_ngap_id` | ✅ 真值(mock AMF) | NGAP InitialUEMessage 後給 |
| `ue_meas_report_lst[].serving_cell` | `UeContext.serving_cell` | ✅ 真值 | 從 measurement_report 累計來 |
| `ue_meas_report_lst[].nr_cell_id` | `SHA-1(cell_id)[:5]` & 36-bit mask | ⚠️ deterministic hash | OAI 真實是 gnb_id + local_cell_id 拼,我們 hash |
| **KPM metric values**(對齊 28.552) | | | |
| `DRB.UEThpDl` | `MeasurementLog.throughput_dl_mbps × 1000` | ⚠️ 估算 | 來源 DU `bytes_sum × 8 / window_s` |
| `DRB.UEThpUl` | `throughput_ul_mbps × 1000` | ⚠️ 估算 / 占位 | UL idle 多為 0 |
| `DRB.PdcpSduVolumeDL` | `MeasurementLog.pdcp_sdu_volume_dl` | ⚠️ proxy | DU 用 RLC SDU bytes 當 PDCP |
| `DRB.PdcpSduVolumeUL` | `pdcp_sdu_volume_ul` | ⚠️ proxy | 同上 |
| `DRB.RlcSduDelayDl` | `MeasurementLog.rlc_sdu_delay_dl_ms` | ✅ 真量測 | DU `now() − enqueue_ts_ms` |
| `RRU.PrbTotDl` | `rb_width_dl / 273 × 100` | ✅ 真演算法 | DU PF scheduler 配的 PRB |
| `RRU.PrbTotUl` | DL 的 1/5 | ⚠️ 估算 | UL idle |
| `RSRP` | `MeasurementLog.rsrp_dbm` | ✅ 真物理 | RU `TX + Gain + 10·log10(path_gain)`,Sionna |
| `SINR` | `MeasurementLog.sinr_db` | ✅ 真物理 | RU `\|\|H_eff\|\|² / noise`,Sionna |
| **E2KpmReporter snapshot 額外欄位** | | | |
| `pm[cell].MM.HoExeIntraReq` | `HandoverEvent.filter(source=cell).count` | ✅ 真值 | DB query |
| `pm[cell].MM.HoExeIntraSucc` | `HandoverEvent.filter(status=SUCC).count` | ✅ 真值 | DB query |
| `pm[cell].gnb.MR.Event.A3` | `HandoverEvent.filter(trigger=A3_TTT).count` | ✅ 真值 | DB query |
| `pm[cell].RRC.ConnMean` | 當下 `UeContext.filter(state=CONNECTED).count` | ✅ 真值 | DB query |
| `pm[cell].RRC.ConnMax` | 取當下 max | ⚠️ 估算 | 沒實作時間視窗 |
| **bbu_status**(host 硬體遙測,per-cell 平均) | | | |
| `cpu` | `psutil.cpu_percent` | ✅ 真量測 | OS |
| `cpu_power` | `cpu_pct × 65 W TDP` | ⚠️ 估算 | 假設 TDP=65W,沒讀真 RAPL |
| `cpu_temp` | `psutil.sensors_temperatures` | ✅ 真量測 | lm-sensors |
| `load_average` | `psutil.getloadavg()[0]` | ✅ 真量測 | Linux kernel |
| `mem` | `psutil.virtual_memory().percent` | ✅ 真量測 | OS |
| `tot_power` | CPU 估算 + GPU pynvml | ⚠️ 半真 | GPU 真,CPU 估算 |

---

## 與真 OAI / FlexRIC 的差異

| 維度 | RANsim-CU | 真 OAI + FlexRIC |
|---|---|---|
| **wire format** | HTTP POST + JSON | SCTP + ASN.1 PER |
| **service models** | KPM v2.0.03 + RC v01.03 標準 | KPM standard + FlexRIC 私有 SM 142~148 |
| **`ran_function_oid`** | `1.3.6.1.4.1.53148.1.2.2.2`(標準) | 同(若用 standard);FlexRIC 私有用其他 OID |
| **KPM Format** | Format 3 (UE-level) | Format 1~5 都支援 |
| **metric 命名** | 對齊 3GPP TS 28.552 | 同(若用 standard);FlexRIC 私有用 OAI struct field 名 |
| **Indication 推送** | polling + WebSocket push | SCTP server-initiated push |
| **`nr_cell_id`** | SHA-1 hash from cell_id str | 真 gnb_id + local_cell_id bit-packed |
| **`amf_ue_ngap_id`** | mock AMF self-respond 隨機產 | 真 5GC AMF 配 |
| **真 PHY 量測** | RU Sionna ray-tracing | 真 RF + IQ samples 量測 |
| **HARQ rounds 統計** | (沒輸出到 KPM) | OAI 真讀 dlsch_rounds[8] |

---

## 結論

這份 KPM 對外介面 **schema 完全對齊 O-RAN WG3 E2SM-KPM v2.0.03 standard**(不是 FlexRIC 私有版),且 RAN Function OID 用標準 `1.3.6.1.4.1.53148.1.2.2.2`。

**真物理量測欄位**:`RSRP`、`SINR`、`neighbor_cells.rsrp_dbm`(來自 RU Sionna)。
**真演算法欄位**:`RRU.PrbTotDl`、`mcs_dl`、`rb_width_dl`(DU PF + BLER 閉環)。
**真量測欄位**:`DRB.RlcSduDelayDl`、HO 計數、CPU 使用率/溫度。
**估算 / proxy 欄位**:`DRB.UEThp*`(throughput)、`DRB.PdcpSduVolume*`(用 RLC bytes)、`cpu_power`(用 TDP 估)、`nr_cell_id`(hash)。

要拿這份 KPM 做 **xApp 演算法驗證 / handover 決策實驗 / RRM PRB 配置研究** → ✅ 信號品質、PRB 分配、HO 統計都是真值或真演算法,可信。
要拿來做 **絕對 throughput accuracy 研究 / PDCP layer profiling / 真實 cpu_power monitoring** → ❌ 估算或 proxy,不可信。
