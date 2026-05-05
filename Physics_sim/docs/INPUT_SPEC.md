# ranp-sim 輸入規格

**給**：需要呼叫 ranp-sim 的外部平台實作者（Omniverse Extension / FlexRIC xApp / 測試工具）
**版本**：v0.1
**更新日期**：2026-04-18

---

## 1. 服務資訊

| 項目 | 值 |
|---|---|
| Base URL (預設) | `http://<host>:8000` |
| API prefix | `/api/v0.1/RanpSim/RanSignal/` |
| HTTP method (全部) | **POST**（鐵則 7-2） |
| Content-Type | `application/json` |
| 認證 | 無（內部網路；後續可加 token header） |
| 建議呼叫頻率 | **500 ms** per tick（最快 200 ms，最慢 1 s） |
| Request body 上限 | 1 MB |
| 回應時間目標 | < 200 ms（5 UE 場景 < 50 ms） |

---

## 2. 端點清單

### 2.1 `POST /api/v0.1/RanpSim/RanSignal/ComputeRunner/compute`

**每 tick 主計算**。外部平台 500 ms 呼叫一次。

#### Request body
```json
{
  "timestamp_ms": 1713420000500,
  "scene_id": "umi_3sector_v1",
  "ue_positions": [
    {
      "id": "UE_Handover_Path",
      "position": [12.5, 1.5, -20.0],
      "velocity": [1.2, 0.0, 0.0]
    }
  ]
}
```

#### 欄位規格

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `timestamp_ms` | int64 ≥ 0 | ✅ | UNIX 時間戳（毫秒），用於 E2 上報 |
| `scene_id` | string (≤128) | ✅ | 必須對應啟動時載入的場景 id（預設 `umi_3sector_v1`）；不符合回 404 |
| `ue_positions` | array | ✅ | 當下所有 UE 狀態；最多 50 筆，超過回 413 |
| `ue_positions[].id` | string (≤128) | ✅ | UE 名稱；必須對應 scene_config.json 的 `ues[].name`，否則列入 `warnings` 忽略 |
| `ue_positions[].position` | `[x, y, z]` float | ✅ | 世界座標，**單位公尺**，右手系 Y-up |
| `ue_positions[].velocity` | `[vx, vy, vz]` float | 可選 | m/s；未提供視為 `[0,0,0]`（不算 Doppler） |
| `ue_positions[].role` | int | 可選 | UE 類型（1=normal, 2=URLLC, 3=IoT）；預設 1 |
| `ue_positions[].qos_5qi` | int | 可選 | QoS Class Identifier；預設 9（best-effort data） |

#### Response 200
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "timestamp_ms": 1713420000500,
    "compute_ms": 47,

    "e2": [
      {
        "gnb_id": "133",
        "timestamp": 1713420000,
        "cells": [{
          "cell_id": "99f966000214001",
          "ran_name": "gNB_Macro_NW",
          "pci": 133,
          "ues": [
            /* 同一 cell 可有多個 UE（PF scheduler 會分 PRB），
               範例：送 5 UE 都 serving gNB_Macro_NW 時 ues[] 有 5 筆 */
            {
              "role": 1, "ue_id": "UE_Handover_Path",
              "interfered": 0,
              "rsrp": -43, "rsrq": -11, "sinr": 21,
              "neighbors": [{"99f96600021c001": {"rsrp": -85, "rsrq": -14}}],
              "dl_throughput": 161, "ul_throughput": 32,
              "rb_start": 0, "rb_width": 113
            },
            {
              "role": 1, "ue_id": "UE_LOS_Reference",
              "interfered": 1,
              "rsrp": -56, "rsrq": -13, "sinr": 8,
              "neighbors": [{"99f966000220001": {"rsrp": -59, "rsrq": -15}}],
              "dl_throughput": 52, "ul_throughput": 10,
              "rb_start": 0, "rb_width": 64
            },
            {
              "role": 1, "ue_id": "UE_Cell_Edge",
              "interfered": 0,
              "rsrp": -63, "rsrq": -12, "sinr": 7,
              "neighbors": [],
              "dl_throughput": 96, "ul_throughput": 19,
              "rb_start": 0, "rb_width": 87
            }
            /* ... 更多 UE 可續加。ues[] 長度取決於該 cell 當下服務幾個 UE。
               若沒 UE serving 這個 cell（其他 gNB 搶走了），ues 為 []。 */
          ]
        }]
      },
      {
        "gnb_id": "135",
        "cells": [{ "ran_name": "gNB_Macro_SE", "pci": 135, "ues": [/*...*/] }]
      },
      {
        "gnb_id": "137",
        "cells": [{ "ran_name": "gNB_Small_Plaza", "pci": 137, "ues": [] }]  // 無 UE 連
      }
    ],

    "ue_status": [
      {
        "ue_id": "UE_Handover_Path",
        "position": [12.5, 1.5, -20.0],
        "serving_gnb": "gNB_Macro_NW",
        "serving_pci": 133,
        "rsrp_dbm": -76.3, "sinr_db": 23.1,
        "all_rsrp": {
          "gNB_Macro_NW": -76.3,
          "gNB_Macro_SE": -92.5,
          "gNB_Small_Plaza": -105.1
        },
        "throughput_dl_mbps": 420,
        "quality": "excellent"
      }
    ],

    "pm": {
      "gnb-133": [{
        "cell_id": "99f966000214001",
        "cu_RRC.ConnEstabSucc.sum": "2",
        "cu_RRC.ConnMax": "2",
        "cu_MM.HoExeIntraFreqReq": "1",
        "cu_MM.HoExeIntraFreqSucc": "1",
        "cu_gnb.MR.Event.A3": "0",
        "cu_DRB.PdcpSduVolumeDL_5QI9": "162290124",
        "du_CARR.PRBUsageDLNbr": "2730",
        "du_CARR.PDSCHMCSDist.BinTable2.BinMCS20": "2",
        "du_CARR.WBCQIDist.BinCQI14.BinTable2": "5",
        "du_169:PEE.AvgTemperature": "92.25",
        "...": "(總共 ~182 個欄位對齊 3GPP TS 28.552)"
      }],
      "gnb-135": [{...}]
    },

    "bbu_status": {
      "gnb-133": {
        "cpu": 10.0, "cpu_power": 3.25, "cpu_temp": 92.25,
        "load_average": 0.99, "mem": 40.5, "tot_power": 15.99
      },
      "gnb-135": {...},
      "timestamp": "1776502800000"
    },

    "warnings": []
  }
}
```

### 新增 `pm` 區塊說明

對應 3GPP TS 28.552 5G Performance Measurements，每個 gNB **~182 欄位**。分類：

| 類別 | 範例欄位 | 來源 |
|---|---|---|
| **RRC 計數** | `cu_RRC.ConnEstabSucc.sum`、`ConnMax`、`ConnMean` | RrcEventTracker 從 UE presence 推 |
| **Handover** | `cu_MM.HoExeIntraFreqReq/Succ`、`cu_gnb.MR.Event.A3` | 從 serving_gnb 跨 tick 變化推 |
| **PDU/DRB** | `cu_DRB.EstabSucc.5QI9`、`cu_SM.PDUSessionSetupSucc` | 假設每 UE 1 DRB 1 Session |
| **PDCP Volume** | `cu_DRB.PdcpSduVolumeDL_5QI9` | `throughput × tick_ms × 125000` 累積 |
| **MCS 分佈** | `du_CARR.PDSCHMCSDist.BinTable2.BinMCS<n>` | 從 throughput 反推 MCS 累積直方圖 |
| **CQI 分佈** | `du_CARR.WBCQIDist.BinCQI<n>.BinTable2` | SINR → CQI (TS 38.214) 累積 |
| **PRB 使用** | `du_CARR.PRBUsageDLNbr` | `rb_width` 累加 |
| **溫度** | `du_169:PEE.AvgTemperature` | 從 bbu_status 借 |

**不模擬的欄位**（全報 `"0"`）：`ReEstab*`、`SigTimeSetup/ReEstab/Reconfig*`、`PdcpPacketDiscardDL`、`AirIfDelay*`、`TB.TotNbr*`——這些需要真 RRC 狀態機 / HARQ 重傳追蹤。

### 新增 `bbu_status` 區塊說明

每個 gNB 對應一份 host 遙測：

| 欄位 | 單位 | 來源 |
|---|---|---|
| `cpu` | % | `psutil.cpu_percent()` |
| `cpu_power` | W | Intel RAPL / TDP×CPU% fallback |
| `cpu_temp` | °C | `psutil.sensors_temperatures()` |
| `load_average` | — | `os.getloadavg()` 1-min |
| `mem` | % | `psutil.virtual_memory().percent` |
| `tot_power` | W | GPU（`pynvml`）+ CPU 功耗估計 |

⚠️ **限制**：真 RAN 每個 gNB 一台實體 BBU。我們一台容器模 3 個 gNB，所以三個 gNB 的 bbu_status 數值**相同**（按 gNB 數平均分攤 CPU/功耗）。

**欄位說明**：

| 區塊 | 用途 |
|---|---|
| `data.e2[]` | 對齊 `RAN_knowledge/E2.md` 格式；**推薦 FlexRIC / 後端消費** |
| `data.ue_status[]` | 扁平結構，**推薦 Omniverse UI 消費**（畫顏色 / 顯示訊號柱） |
| `data.warnings[]` | 字串警告（如未註冊 UE id、沒 path gain） |
| `data.compute_ms` | 後端花的時間；用於調整 tick 間隔 |

---

### 2.2 `POST /api/v0.1/RanpSim/RanSignal/ConfigManager/read`

#### Request body
```json
{}
```
（空 JSON 即可）

#### Response 200
```json
{
  "success": true,
  "data": {
    "scene_id": "umi_3sector_v1",
    "loaded_at_ms": 1713420000000,
    "gnb_count": 3,
    "ue_count": 5,
    "building_count": 6,
    "gnbs": [...完整 gNB config array...],
    "ues": [...UE name list...],
    "source": "default",                     // "default" or "runtime_push"
    "ttl_expires_at_ms": null,               // runtime_push 時可能有值
    "previous_scene_id": null                // runtime_push 時是前一個 scene_id
  }
}
```

#### Response 503
尚未執行任何 compute 或 reload，Sionna 還沒初始化。

---

### 2.3 `POST /api/v0.1/RanpSim/RanSignal/ConfigManager/reload`

手動重讀 `scene_config.json`。**會重啟 Sionna engine**，耗時約 2~5 秒。

#### Request body
```json
{}
```

#### Response 200
同 `read` 的格式，message 為 `"Reloaded"`。

---

### 2.4 `POST /api/v0.1/RanpSim/RanSignal/ConfigManager/push_scene`

**Runtime override**：外部平台（Omniverse / 測試工具）把真實場景推進來，**暫時覆蓋**預設的 `scene_config.json`。Sionna engine 會重建。可設 TTL 到期自動回預設。

#### Request body
```json
{
  "scene_id": "taipei_daan_v1",
  "override_mode": "full",
  "geometry_source": {
    "type": "buildings_json",
    "buildings": [
      {
        "name": "Office_01",
        "position": [-50, 0, 50],
        "size": [30, 25, 30],
        "material": "concrete"
      },
      {
        "name": "Mall_02",
        "position": [50, 0, 50],
        "size": [40, 18, 40],
        "material": "glass"
      }
    ],
    "ground": {
      "position": [0, 0, 0],
      "size": [500, 500]
    }
  },
  "gnbs": [
    {
      "name": "gNB_Daan_01",
      "pci": 200,
      "cell_id": "99f9660003e8001",
      "position": [25.034, 30.0, 121.536],
      "frequency_ghz": 3.5,
      "power_dbm": 43,
      "bandwidth_mhz": 100
    }
  ],
  "ues": [
    {"name": "UE_Pedestrian_001", "qos_5qi": 9, "role": 1}
  ],
  "ttl_seconds": 3600
}
```

#### 欄位規格

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `scene_id` | string | ✅ | 新場景 ID；覆蓋後 /compute 的 scene_id 必須對齊此值 |
| `override_mode` | `full` / `ran_only` / `geometry_only` | 可選（預設 `full`） | `full` 兩者都換；`ran_only` 只換 gNB；`geometry_only` 只換場景 |
| `geometry_source` | object | `full` / `geometry_only` 必填 | 建築 box 列表（後端自己轉 Mitsuba XML） |
| `geometry_source.type` | `"buildings_json"` | ✅ | 目前唯一支援的 geometry 來源 |
| `geometry_source.buildings[]` | array of box | ✅ | 每棟建築的 box 描述；1~500 棟 |
| `.buildings[].name` | string | 可選 | 建築識別，不給會自動命名 |
| `.buildings[].position` | `[x,y,z]` float | ✅ | 公尺；y=0 代表底面貼地 |
| `.buildings[].size` | `[sx,sy,sz]` float | ✅ | 公尺；寬/高/深 |
| `.buildings[].material` | `concrete`/`glass`/`metal`/`brick`/`wood` | 可選（預設 concrete）| 自動 map 到 ITU-R P.2040-3 |
| `geometry_source.ground` | object | 可選 | 地面 `position[3]` 和 `size[2]`，預設 250×250 |
| `gnbs[]` | array | `full` / `ran_only` 必填 | 同 scene_config.json 的 gnbs 欄位 |
| `gnbs[].pci` | int 0-1007 | ✅ | 3GPP PCI |
| `gnbs[].cell_id` | string | ✅ | 唯一 cell 識別 |
| `gnbs[].position` | `[x,y,z]` | ✅ | 世界座標公尺 |
| `gnbs[].frequency_ghz` | 0.4~100 | ✅ | 載波頻率 |
| `gnbs[].power_dbm` | -30~60 | ✅ | 發射功率 |
| `gnbs[].bandwidth_mhz` | 1~400 | ✅ | 頻寬 |
| `ues[]` | array | 可選 | UE 允許清單（不傳則沿用預設） |
| `ttl_seconds` | int 1~86400 | 可選 | 多少秒後自動退回預設；不傳則永久覆蓋直到 reset |

#### Response 200
```json
{
  "success": true,
  "message": "Scene override applied",
  "data": {
    "scene_id": "taipei_daan_v1",
    "previous_scene_id": "umi_3sector_v1",
    "loaded_at_ms": 1776532487822,
    "override_mode": "full",
    "source": "runtime_push",
    "ttl_expires_at_ms": 1776536087822,
    "sionna_rebuild_ms": 914,
    "gnb_count": 1,
    "ue_count": 1,
    "geometry_source_type": "mitsuba_xml_b64"
  }
}
```

#### Response 400
驗證失敗（如 mode=full 沒帶 geometry_source、pci 超過 1007、geometry_source.type 不合法等）。

---

### 2.5 `POST /api/v0.1/RanpSim/RanSignal/ConfigManager/reset_to_default`

取消 runtime override，立即退回 `scene_config.json` 預設。

#### Request body
```json
{}
```

#### Response 200
同 `read` 的格式，`source` = `"default"`、`message` = `"Reset to default"`。

---

### 2.6 `POST /api/v0.1/RanpSim/RanSignal/CoverageRunner/compute`

產 **per-gNB 2D RSRP 網格**（coverage map），供前端畫熱圖 / 覆蓋等高線 / 服務區。

**特性**：
- Sionna `RadioMapSolver()` 原生支援，~200ms 算 50×50×3gNB
- `rsrp_dbm` 和 `sinr_db` 皆為 2D list，**第一維 = z（北→南），第二維 = x（西→東）**
- `null` 表該格被建築完全遮蔽或 RSRP < `null_threshold_dbm`
- SINR 已 clip 到合理範圍 `[-30, +30] dB`

#### Request body
```json
{
  "scene_id": "umi_3sector_v1",
  "grid": {
    "x_range": [-125, 125],
    "x_step": 5,
    "z_range": [-125, 125],
    "z_step": 5,
    "sample_height_m": 1.5
  },
  "include_sinr": true,
  "max_depth": 3,
  "null_threshold_dbm": -120.0
}
```

#### 欄位規格

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `scene_id` | string | ✅ | 必須對應啟動時載入的場景 |
| `grid.x_range` | `[x_min, x_max]` float | ✅ | 公尺 |
| `grid.x_step` | float 0.5~50 | ✅ | 取樣間距 公尺 |
| `grid.z_range` | `[z_min, z_max]` float | ✅ | 公尺 |
| `grid.z_step` | float 0.5~50 | ✅ | 取樣間距 |
| `grid.sample_height_m` | float 0.1~50 | 可選（預設 1.5）| UE 高度 |
| `include_sinr` | bool | 可選（預設 true）| 一併算每格 serving cell 的 SINR |
| `max_depth` | int 1~5 | 可選（預設 3）| 光追深度；coverage 建議 ≤ 3 省 VRAM |
| `null_threshold_dbm` | float -200~-30 | 可選（預設 -120）| 低於此值改回 null |

#### 格數上限
`((x_max-x_min)/x_step+1) × ((z_max-z_min)/z_step+1)` 上限 **10000**。超過回 400。

#### Response 200（核心 data 區塊對齊外部平台 spec）
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "scene_id": "umi_3sector_v1",
    "ts": "2026-04-18T18:13:50.135685+00:00",
    "compute_ms": 217,
    "grid": {
      "x_range": [-125, 125],
      "x_step": 5.0,
      "z_range": [-125, 125],
      "z_step": 5.0,
      "sample_height_m": 1.5,
      "n_rows": 50,
      "n_cols": 50
    },
    "gnbs": [
      {
        "gnb_name": "gNB_Macro_NW",
        "pci": 133,
        "cell_id": "99f966000214001",
        "frequency_ghz": 3.5,
        "power_dbm": 43,
        "rsrp_dbm": [
          [null, -97.2, -93.5, ...],
          [-98.1, -94.0, -89.3, ...],
          ...
        ],
        "sinr_db": [
          [null, null, -5.2, ...],
          [null, -4.1, 2.3, ...],
          ...
        ]
      },
      {...}
    ]
  }
}
```

#### Response 規格
- **`data.ts`**：ISO 8601 UTC 字串（**注意**：不是 timestamp_ms）
- **`data.gnbs[].rsrp_dbm`**：`n_rows × n_cols` 的 2D list；`null` = 遮蔽 / 低於閾值
- **`data.gnbs[].sinr_db`**：同形狀，只在 serving-area 內的格子有值，其他 `null`
- 第一維（外層）= z 軸，index 0 = `z_max`（北），last index = `z_min`（南）
- 第二維（內層）= x 軸，index 0 = `x_min`（西），last index = `x_max`（東）

#### 範例資料
完整 sample JSON 在 `docs/sample_coverage_map.json`（247 KB，50×50×3gNB）。

#### 典型使用場景
- 前端**熱圖**（heatmap）：每格依 RSRP 染色
- **等高線**（contour）：畫 -80/-90/-100 dBm 三條線（建議畫法）
- **服務區**（serving cell zones）：per cell 找 argmax(RSRP) 的 gNB，合併同色區

---

### 2.7 `POST /api/v0.1/RanpSim/RanSignal/HealthChecker/read`

#### Request body
```json
{}
```

#### Response 200
```json
{
  "success": true,
  "data": {
    "ready": true,
    "scene_id": "umi_3sector_v1",
    "loaded_at_ms": 1713420000000,
    "gpu": {
      "available": true,
      "name": "NVIDIA RTX A5000",
      "total_memory_mb": 24576,
      "capability": "8.6"
    }
  }
}
```

- `ready = false` 表示 Sionna 尚未初始化（首次 compute 或 reload 前）
- `gpu.available = false` 表示沒有 CUDA GPU 可用（Sionna 會 fallback 到 CPU 但很慢）

---

## 3. 錯誤碼

| HTTP | message | 原因 | 處理建議 |
|---|---|---|---|
| 400 | Validation failed | JSON 型別錯 / 必填缺 | 看 `errors` 詳細欄位 |
| 404 | scene_id '...' not loaded | scene_id 對不上 | 呼叫 `/ConfigManager/reload` |
| 413 | ue_positions[] has N items; limit is 50 | UE 超量 | 分批 POST |
| 415 | Unsupported media type | 沒帶 `Content-Type: application/json` | 補 header |
| 500 | Reload failed: ... | scene_config.json 壞 | 檢查檔案 |
| 503 | GPU out of memory | VRAM 不夠 | 降 UE 數量或 max_depth |
| 503 | No scene loaded yet | 還沒初始化 | 先呼叫 reload 或 compute |

---

## 4. 啟動前提（給運維）

1. 在 ranp-sim 外部平台準備 `scene_config.json`（專案根目錄）
2. 每個 gNB 必須包含：
   ```json
   {
     "name": "gNB_Macro_NW",
     "pci": 133,                       ← 建議手寫（0-1007）
     "cell_id": "99f966000214001",     ← 建議手寫
     "position": [-90, 30, 90],
     "frequency_ghz": 3.5,
     "power_dbm": 43,
     "bandwidth_mhz": 100
   }
   ```
   若未指定 `pci` / `cell_id` 會自動由 name hash 分派（不保證穩定）。
3. 執行 `./shell/init_project.sh` 把 scene_config.json 轉成 Mitsuba XML
4. `docker compose up -d`
5. 第一次 POST `/HealthChecker/read` 驗證 `ready=true`

---

## 5. 呼叫範例

### 5.1 curl

```bash
curl -X POST http://localhost:8000/api/v0.1/RanpSim/RanSignal/ComputeRunner/compute \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp_ms": 1713420000500,
    "scene_id": "umi_3sector_v1",
    "ue_positions": [
      {"id": "UE_Handover_Path", "position": [12.5, 1.5, -20.0], "velocity": [1.2, 0, 0]}
    ]
  }'
```

### 5.2 Python `requests`

```python
import requests
import time

BASE = "http://localhost:8000/api/v0.1/RanpSim/RanSignal"

# 健康檢查
h = requests.post(f"{BASE}/HealthChecker/read", json={})
assert h.json()["data"]["ready"]

# per-tick 呼叫
while True:
    payload = {
        "timestamp_ms": int(time.time() * 1000),
        "scene_id": "umi_3sector_v1",
        "ue_positions": [
            {"id": "UE_Handover_Path", "position": [12.5, 1.5, -20.0], "velocity": [1.2, 0, 0]},
            {"id": "UE_NLOS_Shadow",   "position": [-80,  1.5,  30.0], "velocity": [0, 0, -2]},
        ],
    }
    r = requests.post(f"{BASE}/ComputeRunner/compute", json=payload)
    data = r.json()["data"]
    for ue in data["ue_status"]:
        print(f"{ue['ue_id']}: RSRP={ue['rsrp_dbm']} dBm  SINR={ue['sinr_db']} dB  quality={ue['quality']}")
    time.sleep(0.5)
```

---

## 6. 疑難排解

| 症狀 | 原因 | 解法 |
|---|---|---|
| compute 每次回 404 | scene_id 不符或尚未初始化 | POST `/ConfigManager/reload` |
| compute_ms > 500ms | Sionna 場景太複雜或 UE 過多 | 降 `SIM_MAX_DEPTH` 或分批 |
| RSRP 全為 -999 | path gain = 0，可能場景載入失敗 | 檢查 `scenes/umi_3sector.xml` 是否存在 |
| 容器啟動就 OOM | GPU 上已有其他 workload 佔用 | `docker compose down` + 確認 `nvidia-smi` |
| Warning: ue 'X' not in CIR | UE id 不在 Sionna scene 的 receivers | 檢查 UE 位置是否在場景範圍內 |

---

## 7. 版本承諾

- v0.1（當前）— 欄位可能微調
- v0.2 — 預期加：`neighbors[]` 格式調整、可選 `include_cir=true` 取原始 CIR
- 重大變更會加新版本路徑 `/api/v0.2/`，v0.1 保留 3 個月

---

## 8. 聯絡

技術文件：`docs/ARCHITECTURE.md`
後端規範：`backend_rule.md`
研究筆記：`../LLM_learning/`
