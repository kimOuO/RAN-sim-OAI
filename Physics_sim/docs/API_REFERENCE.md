# ranp-sim API Reference

**版本**：v0.1
**Base URL**：`http://<host>:8000`
**HTTP Method**：全部 **POST**（遵守後端鐵則 7-2）
**Content-Type**：`application/json`
**Response Wrapper**：所有 response 都包一層
```json
{ "success": true, "message": "OK", "data": { ... } }
```

---

## 📋 Endpoint 總覽

| # | URL | 用途 | 呼叫頻率 |
|---|---|---|---|
| 1 | `/api/v0.1/RanpSim/RanSignal/ComputeRunner/compute` | **核心 per-tick RAN 計算** | 500 ms / tick |
| 2 | `/api/v0.1/RanpSim/RanSignal/CoverageRunner/compute` | 覆蓋地圖（2D 熱圖資料） | 按需 |
| 3 | `/api/v0.1/RanpSim/RanSignal/ConfigManager/read` | 查目前配置 | 按需 |
| 4 | `/api/v0.1/RanpSim/RanSignal/ConfigManager/reload` | 重讀預設 scene_config.json | 按需 |
| 5 | `/api/v0.1/RanpSim/RanSignal/ConfigManager/push_scene` | 推真實場景 override | 場景切換時 |
| 6 | `/api/v0.1/RanpSim/RanSignal/ConfigManager/reset_to_default` | 取消 override 回預設 | 按需 |
| 7 | `/api/v0.1/RanpSim/RanSignal/HealthChecker/read` | 健康檢查 | 30 s / 次 |

---

## 1️⃣ ComputeRunner/compute — 核心 per-tick 計算 ⭐

### URL
```
POST /api/v0.1/RanpSim/RanSignal/ComputeRunner/compute
```

### 用途
收當下 UE 座標 → Sionna 光追 → 回傳**所有 RAN KPI**（RSRP / SINR / Throughput / MCS / HO 計數 / PDCP byte / BBU 遙測）。

**典型使用場景**：Omniverse Server 每 500 ms 呼叫一次，把結果傳給 RIC / xApp / UI。

### Input

```json
{
  "timestamp_ms": 1776500000123,
  "scene_id": "umi_3sector_v1",
  "ue_positions": [
    {
      "id": "UE_Handover_Path",
      "position": [12.5, 1.5, -20.0],
      "velocity": [1.2, 0, 0],
      "qos_5qi": 9,
      "role": 1
    }
  ]
}
```

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `timestamp_ms` | int64 | ✅ | UNIX 毫秒時間戳 |
| `scene_id` | string | ✅ | 需對應啟動載入的場景 |
| `ue_positions[]` | array | ✅ | 當下所有 UE；上限 50 |
| `.id` | string | ✅ | UE 唯一識別 |
| `.position` | `[x,y,z]` | ✅ | 世界座標，公尺 |
| `.velocity` | `[vx,vy,vz]` | 選 | m/s；預設 0 |
| `.qos_5qi` | int | 選 | 1=voice, 4=video, 9=data；預設 9 |
| `.role` | int | 選 | UE 類型；預設 1 |

### Output 摘要

`data` 裡有 4 個主區塊：
- `e2[]` — 對齊 E2.md 格式的 UE KPI（每 gNB 一組）
- `ue_status[]` — 扁平 UE 狀態（給 UI 顯示）
- `pm{}` — per-gNB ~180 個 3GPP 計數器
- `bbu_status{}` — per-gNB 主機遙測

---

## 2️⃣ CoverageRunner/compute — 覆蓋地圖

### URL
```
POST /api/v0.1/RanpSim/RanSignal/CoverageRunner/compute
```

### 用途
一次算**整個場域**每 5m×5m 的 RSRP 網格，**per gNB** 輸出 2D 陣列。前端可畫熱圖 / 等高線 / 服務區。

**典型使用場景**：UI 要畫覆蓋熱圖、gNB 擺放研究、SLA 驗證。

### Input

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

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `scene_id` | string | ✅ | 需對應載入場景 |
| `grid.x_range` | `[min,max]` | ✅ | x 範圍公尺 |
| `grid.x_step` | float 0.5~50 | ✅ | x 格距 |
| `grid.z_range` | `[min,max]` | ✅ | z 範圍 |
| `grid.z_step` | float 0.5~50 | ✅ | z 格距 |
| `grid.sample_height_m` | float | 選 | UE 高度；預設 1.5 |
| `include_sinr` | bool | 選 | 一併算 SINR；預設 true |
| `max_depth` | int 1~5 | 選 | 光追深度；預設 3 |
| `null_threshold_dbm` | float | 選 | 低於此改 null；預設 -120 |

**限制**：總格數 `(x_max-x_min)/x_step × (z_max-z_min)/z_step` ≤ 10,000

### Output 摘要

`data.gnbs[].rsrp_dbm` 是 2D list：
- 外層 = z 軸（北→南）
- 內層 = x 軸（西→東）
- `null` = 遮蔽或低於閾值

範例參考 `docs/sample_coverage_map.json`（247 KB）。

---

## 3️⃣ ConfigManager/read — 查配置

### URL
```
POST /api/v0.1/RanpSim/RanSignal/ConfigManager/read
```

### 用途
查目前載入的場景 / gNB / UE 列表，也回傳 override 狀態（default / runtime_push）和 TTL。

**典型使用場景**：admin UI、除錯、健康檢查附帶資訊。

### Input
```json
{}
```
（空 JSON 即可）

### Output 摘要

`data` 包含：`scene_id`、`loaded_at_ms`、`gnb_count`、`ue_count`、`building_count`、完整 `gnbs[]` 和 `ues[]`、`source`（"default" / "runtime_push"）、`ttl_expires_at_ms`、`previous_scene_id`。

---

## 4️⃣ ConfigManager/reload — 重讀預設

### URL
```
POST /api/v0.1/RanpSim/RanSignal/ConfigManager/reload
```

### 用途
強制從 `scene_config.json` **重新載入**預設，重建 Sionna engine + 歸零所有計數器。耗時 2~5 秒（含 OptiX JIT warmup）。

**典型使用場景**：改完 scene_config.json 後想立即生效、測試前歸零狀態。

### Input
```json
{}
```

### Output
同 `/read` 格式，`source="default"`、`message="Reloaded"`。

---

## 5️⃣ ConfigManager/push_scene — 推真實場景 override

### URL
```
POST /api/v0.1/RanpSim/RanSignal/ConfigManager/push_scene
```

### 用途
**外部平台（如 Omniverse）推真實場景** 覆蓋預設。Sionna engine 重建、所有計數器歸零。可設 TTL 自動過期。

**典型使用場景**：Omniverse 匯出真實建築 + gNB 位置 → 即時切換場景；demo 結束後 TTL 自動回預設。

### Input

```json
{
  "scene_id": "taipei_demo",
  "override_mode": "full",
  "geometry_source": {
    "type": "buildings_json",
    "buildings": [
      {
        "name": "Office_01",
        "position": [-50, 0, 50],
        "size": [30, 25, 30],
        "material": "concrete"
      }
    ],
    "ground": {"position": [0,0,0], "size": [500, 500]}
  },
  "gnbs": [
    {
      "name": "gNB_Taipei_01",
      "pci": 200,
      "cell_id": "99f9660003e8001",
      "position": [0, 30, 0],
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

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `scene_id` | string | ✅ | 新場景 ID |
| `override_mode` | `full` / `ran_only` / `geometry_only` | 選 | 預設 full |
| `geometry_source` | object | full/geometry_only 必填 | 見下 |
| `.type` | `"buildings_json"` | ✅ | 目前唯一支援 |
| `.buildings[]` | array of box | ✅ | 每個含 `name`/`position`/`size`/`material` |
| `.ground` | object | 選 | 地面 `position[3]` + `size[2]` |
| `gnbs[]` | array | full/ran_only 必填 | 同 scene_config.json gnbs 格式 |
| `ues[]` | array | 選 | UE 允許清單 |
| `ttl_seconds` | int 1~86400 | 選 | 多久後自動回預設；不傳=永久 |

### Output 摘要

回傳 `scene_id`、`previous_scene_id`、`loaded_at_ms`、`sionna_rebuild_ms`、`source="runtime_push"`、`ttl_expires_at_ms`。

---

## 6️⃣ ConfigManager/reset_to_default — 取消 override

### URL
```
POST /api/v0.1/RanpSim/RanSignal/ConfigManager/reset_to_default
```

### 用途
取消目前的 runtime_push 覆蓋，立即退回 `scene_config.json` 預設場景。

**典型使用場景**：demo 結束、想中止 override、或 TTL 還沒到但要提早回預設。

### Input
```json
{}
```

### Output
同 `/read`，`source="default"`，`message="Reset to default"`。

---

## 7️⃣ HealthChecker/read — 健康檢查

### URL
```
POST /api/v0.1/RanpSim/RanSignal/HealthChecker/read
```

### 用途
查服務健康狀態 + GPU 資訊 + 是否已載入場景。Docker healthcheck 用這個。

**典型使用場景**：docker compose healthcheck、Prometheus liveness、啟動完成確認。

### Input
```json
{}
```

### Output 摘要

```json
{
  "success": true,
  "data": {
    "ready": true,                ← Sionna engine 可用
    "scene_id": "umi_3sector_v1",
    "loaded_at_ms": 1776499820000,
    "source": "default",
    "gpu": {
      "available": true,
      "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
      "total_memory_mb": 7805,
      "capability": "8.9"
    }
  }
}
```

---

## 🔴 HTTP 錯誤碼表

| Code | 情境 | 處理建議 |
|---|---|---|
| 400 | 輸入驗證失敗（欄位型別錯、超出範圍） | 檢查 request body |
| 404 | `scene_id` 不存在 | 先 reload 或 push_scene |
| 413 | `ue_positions[]` 超過 50 筆 | 分批呼叫 |
| 415 | Content-Type 非 JSON | 加 `-H "Content-Type: application/json"` |
| 500 | 內部錯誤 | 看 docker log |
| 503 | GPU OOM / Sionna 未初始化 | 先 `/reload`；或關掉 Omniverse Kit 釋放 VRAM |

---

## 🧪 快速測試 cheat sheet

```bash
BASE="http://localhost:8000/api/v0.1/RanpSim/RanSignal"

# 1. 健康
curl -s -X POST $BASE/HealthChecker/read -H "Content-Type: application/json" -d '{}'

# 2. 初始化
curl -s -X POST $BASE/ConfigManager/reload -H "Content-Type: application/json" -d '{}'

# 3. 查配置
curl -s -X POST $BASE/ConfigManager/read -H "Content-Type: application/json" -d '{}'

# 4. 核心 compute
curl -s -X POST $BASE/ComputeRunner/compute -H "Content-Type: application/json" -d '{
  "timestamp_ms": 1776500000000,
  "scene_id": "umi_3sector_v1",
  "ue_positions": [
    {"id": "UE1", "position": [15, 1.5, 15]}
  ]
}'

# 5. 覆蓋地圖
curl -s -X POST $BASE/CoverageRunner/compute -H "Content-Type: application/json" -d '{
  "scene_id": "umi_3sector_v1",
  "grid": {"x_range":[-125,125],"x_step":5,"z_range":[-125,125],"z_step":5}
}'

# 6. 推場景
curl -s -X POST $BASE/ConfigManager/push_scene -H "Content-Type: application/json" -d '{
  "scene_id": "demo",
  "override_mode": "ran_only",
  "gnbs": [...]
}'

# 7. 回預設
curl -s -X POST $BASE/ConfigManager/reset_to_default -H "Content-Type: application/json" -d '{}'
```

---

## 📎 完整欄位規格

- 各端點完整 schema：見 `INPUT_SPEC.md`
- Use case flow 圖：見 `plantuml/UC*.puml`
- Coverage map sample：見 `sample_coverage_map.json`
- Bug 清單：見 `BUGS.md`
