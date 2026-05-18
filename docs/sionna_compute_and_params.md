# Sionna RT 計算行為 + 可調參數整理 + 已知 bug

> 產出日期：2026-05-15
> 對應檔案：`Physics_sim/main/apps/ran_signal/services/optional/ran_calculation/`、
> `RANsim-RU/main/apps/{antenna, physics_client, fapi_south}/`、`scene_config.json`
> 目的：把 Sionna 端怎麼算、有哪些旋鈕、目前 pipeline 哪裡漏了，**一次講清楚**。

---

## 1. 座標系統（一段話結論）

| 層 | X 軸 | Y 軸 | Z 軸 | 來源檔 |
|---|---|---|---|---|
| `scene_config.json` | 東西 (`+X=east`) | **高度** (`+Y=up`) | 南北 (`+Z=north`) | 平台原始定義 |
| Mitsuba XML (`umi_3sector.xml`) | 同上 | 同上 (`Y-up right-hand`) | 同上 | `mitsuba_builder.py:56` 註解明示 |
| Sionna PathSolver 內部 | (Sionna 本身用 `Z-up`，但載入 Mitsuba 場景時內部會把 Y/Z 自動 transpose) | — | — | Sionna RT 預設行為 |
| Dashboard SVG (`TopDownMap.tsx`) | **東邊 (+X) 反映到螢幕「左」** | 不畫 | 北邊 (+Z) 反映到螢幕上 | `TopDownMap.tsx:84` `sx = width - ...` |

### 1.1 Azimuth 0° 在哪裡指
- **Sionna 世界**：`azimuth_deg=0` → 沿 `+X` 軸（東）
- **Dashboard 螢幕**：因為 `sx(x) = width - ...` 把 X 軸鏡像，所以 `azimuth=0` **視覺上指向螢幕左邊**
- ✓ 你觀察到的「0 度在前端的左邊」**沒錯，是 Dashboard SVG 故意鏡射 X 軸的結果**

### 1.2 為什麼 Dashboard 要鏡 X 軸
這是早期的設計選擇，可能是為了讓 SVG 方向跟 Omniverse Kit viewport 從某個固定相機角度看下去一致（Omniverse 預設相機是從 `+Y` 朝下看，自然會看到 X 鏡像）。沒有任何 code comment 解釋這選擇，可能是 historical artifact。

**建議**：
- ✗ 如果改 `sx` 拿掉鏡射 → 跟 Omniverse 預設相機視角不一致，會困擾使用者
- ✓ **加一個小圖示提示**「Sionna +X = 螢幕左」 + 在 gNB 點上**畫 azimuth 箭頭**讓使用者一眼看出 sector 方向，比改鏡射安全
- 目前 TopDownMap **完全沒畫 azimuth 箭頭**（agent 確認），這是 UX 缺口

### 1.3 高度 (Y) 在 2D map 看不到
- gNB / building 在 Top-down 圖只顯示 X/Z；Y（高度）被忽略
- gNB_Macro_NW=`[200, 50, 200]` 跟 gNB_Micro_Central=`[0, 30, 0]` 在 2D 圖上看起來都「在地面」，但其實一個 50 m 高、一個 30 m 高
- UE 高度通常是 1.5 m，Coverage solver 在 `coverage_solver.py:91` 寫死 `sample_height_m=1.5`

---

## 2. Sionna 端可調的預設參數（按來源分層）

### 2.1 全域 env（rebuild container 才生效）

| Env | 預設 | 在哪用 | 影響 |
|---|---|---|---|
| `MITSUBA_SCENE_PATH` | `/app/scenes/umi_3sector.xml` | `sionna_engine.py` 初始化 | 換場景幾何 |
| `ENABLE_FAST_FADING` | `true` | `sionna_engine.py:256` | 開：每 tick 每 path 隨機相位 → 自然 Rayleigh/Rician fading；關：回退 incoherent 能量和（靜態 RSRP，sim 比較穩） |
| `SIM_NOISE_FIGURE_DB` | `7.0` | `coverage_solver.py:135` | 熱雜訊 + NF；只影響 Coverage SINR |
| `RU_TX_POWER_DBM` | `43.0` | `dl_tti_pipeline.py:27` | 🔴 **RU 算 KPM 用的全域 TX 功率，per-gNB power_dbm 完全被忽略**（見 §4） |
| `RU_ANTENNA_GAIN_DBI` | `14.0` | `dl_tti_pipeline.py:28` | 🔴 RU 在 RSRP 計算又加一次天線增益 — **跟 Sionna PlanarArray 內建增益 double-count**（見 §4） |
| `RU_SCENE_CALIBRATION_LOSS_DB` | `50.0` | `dl_tti_pipeline.py:40` | 模擬「Brownstone 場景沒模擬到的」建物穿透/body loss/shadowing；當 `_TX_POWER_DBM=43` + double-counted gain 時剛好讓 RSRP 落到 -65~-95 dBm 真機範圍。**改成 23 dBm 時這個 -50 dB 就會壓垮** |
| `RU_SINR_INTERFERENCE_PENALTY_DB` | `20.0` | `dl_tti_pipeline.py:45` | 補償 sim 沒完整模擬的 inter-cell interference + multipath fading |
| `RU_NOISE_FLOOR_DBM` | `-95.0` | `dl_tti_pipeline.py:26` | RU SINR 計算雜訊地板 |
| `RU_NEIGHBOR_RSRP_FLOOR_DBM` | `-120.0` | `dl_tti_pipeline.py:29` | 比這弱的 neighbor 不報，避免 A3 evaluator 收 noise |
| `RU_CHANNEL_CACHE_TTL_SEC` | `0.5` | `physics_client/.../channel_cache.py` | UE 同位置（50 cm grid）這秒內不重打 Sionna |
| `RU_NUMEROLOGY` | `1` | `phy_low/models/ru_state.py` | 5G NR numerology |

### 2.2 RU 天線預設（也是 env）

| Env | 預設 | 影響 |
|---|---|---|
| `RU_DEFAULT_ANTENNA_ROWS` | `1` | gNB PlanarArray 列數 |
| `RU_DEFAULT_ANTENNA_COLS` | `1` | gNB PlanarArray 行數 |
| `RU_DEFAULT_POLARIZATION` | `V` | gNB polarization (`V` / `H` / `VH` / `cross`) |
| `RU_DEFAULT_PATTERN` | `tr38901` | gNB 天線 pattern（`tr38901` / `dipole` / `iso` / `hw_dipole` / `vh_dipole`） |

→ Dashboard 上的 MimoSettings UI 改這四個會走 `RuController/update_antenna` 蓋過 env

### 2.3 Per-gNB / per-cell（`scene_config.json`，每次 `SceneGateway/init` 生效）

| 欄位 | 影響 | 哪些 pipeline 讀 |
|---|---|---|
| `gnbs[].position` | TX 在世界座標的擺放 | Sionna engine + Coverage solver |
| `gnbs[].frequency_ghz` | 載波頻率（影響 FSPL + 反射係數） | Sionna scene init |
| `gnbs[].bandwidth_mhz` | 通道頻寬（雜訊 = -174 + 10log10(BW)） | Coverage SINR 算 |
| `gnbs[].power_dbm` | TX EIRP 上界 | ✓ **Coverage Solver 用**；🔴 **RU KPM pipeline 完全不讀** |
| `gnbs[].cells[].pci` | Physical Cell ID | 全部 |
| `gnbs[].cells[].azimuth_deg` | sector 朝向 (0°=+X) | Sionna engine `tx.orientation=[az,0,0]` |
| `gnbs[].cells[].cell_id` | 跨平台 unique 字串 | RU `Cell.name` |

### 2.4 Coverage solver hardcoded（須改 code）

| 變數 | 預設 | 在哪 | 影響 |
|---|---|---|---|
| `null_threshold_dbm` | `-120.0` | `coverage_actor.py` call site | 比這弱的 grid cell 在 heatmap 改 `null`（白色） |
| `sample_height_m` | `1.5` | `coverage_solver.py:44, 91` | UE 取樣高度（人腰部高） |
| `max_depth` | `3` (coverage) / 配置 (PathSolver) | `coverage_solver.py:95` / engine init | 光追 bounce 次數 |
| `_HORIZONTAL_PLANE_ORIENTATION` | `[0, 0, π/2]` | `coverage_solver.py:19` | RadioMap 水平面方向（XZ 平面，法線 +Y） |
| Coverage `diffuse_reflection` | `False` | `coverage_solver.py:98` | 省 VRAM；PathSolver 端是 `True` |
| Coverage `diffraction` | `False` | `coverage_solver.py:100` | 同上 |

---

## 3. Sionna 怎麼算 RSRP / SINR（兩條獨立 pipeline）

```
                  ┌─────────────────────────┐
                  │  scene_config.json       │
                  │  + Dashboard updates     │
                  └────────┬────────────────┘
                           │
                  ┌────────▼────────────────┐
                  │  Sionna PathSolver       │
                  │  (per-tick, 1×UE)        │
                  │                          │
                  │  返回 path_gain_linear    │
                  │  (純傳播衰減，不含 TX     │
                  │   功率，但**包含天線     │
                  │   pattern 增益**)        │
                  └────────┬────────────────┘
                           │
                ┌──────────┴──────────────┐
                │                          │
        【Pipeline A】              【Pipeline B】
        Coverage Heatmap            RU realtime KPM
        (Physics 內部)              (RANsim-RU)
                │                          │
        ┌───────▼──────────┐       ┌───────▼──────────────┐
        │ coverage_solver.py│       │dl_tti_pipeline.py    │
        │                   │       │_path_gain_to_rsrp_dbm│
        │ RSRP = path_gain_db  │       │ RSRP = path_gain_db  │
        │       + gnb.power_dbm│       │      + RU_TX_POWER   │
        │ ✓ per-gNB 功率    │       │      + RU_ANTENNA_GAIN│
        │ ✓ 無額外校正      │       │      - RU_SCENE_CALIB │
        │                   │       │                       │
        │                   │       │ 🔴 power 固定 env 值  │
        │                   │       │ 🔴 雙重 antenna gain │
        │                   │       │ 🔴 -50 dB 校正壓死   │
        └───────────────────┘       └───────────────────────┘
                │                          │
                ▼                          ▼
        Dashboard heatmap          DU measurement_report
        (UI 顯示)                   → CU A3 / KPM / e2adapter
```

---

## 4. 已知 bug（power 改 23 dBm → 覆蓋崩潰）

### 4.1 兩條 pipeline 結果背離

| 設定 | Coverage Heatmap | RU 即時 KPM |
|---|---|---|
| 預設（gNB power=43） | 大範圍藍紅熱圖，~500 m+ 半徑 | RSRP -65~-95 dBm，正常 |
| 改 power=23（你的實驗） | **同 pipeline 跟著掉 20 dB → 熱圖收縮**（heatmap 確實小，但「100×100 m」可能還有更深原因，見 §4.4） | **完全沒變化**（RU 端硬 code 43 dBm） |

### 4.2 Cell model 沒有 power_dbm 欄位

```
ru_cell schema:
  pci, azimuth_deg, gnb_id, position_*, frequency_ghz, bandwidth_mhz
  ❌ power_dbm 缺
```
→ Dashboard 的 `update_cells` 即使想推 power_dbm 也存不下；RU 永遠用 env 的 43。

### 4.3 雙重 antenna gain

Sionna PlanarArray 已在 `path_gain` 內套用天線 pattern（含方向增益）。RU 在 `_path_gain_to_rsrp_dbm` 又加 `+RU_ANTENNA_GAIN_DBI=14`。**double-count 14 dB**。原本 `RU_SCENE_CALIBRATION_LOSS_DB=50` 是為了把這 +14 dB 連同 building penetration / body loss 一起吃掉，**結果是個「巧合校正」**，不是真的代表 50 dB 額外損耗。

### 4.4 為什麼 23 dBm + 3.5 GHz heatmap < 100×100 m？

Coverage 公式：`RSRP = 10log10(path_gain) + power_dbm`，閾值 `-120 dBm`。

理論計算（3.5 GHz、boresight、tr38901 ~8 dBi peak）：
| 距離 | FSPL | path_gain_db（含 ~8 dBi） | RSRP @ 23 dBm |
|---|---|---|---|
| 100 m | 83 dB | ~-75 | **-52 dBm** ✓ |
| 500 m | 97 dB | ~-89 | **-66 dBm** ✓ |
| 1 km | 103 dB | ~-95 | **-72 dBm** ✓ |
| 5 km | 117 dB | ~-109 | **-86 dBm** ✓ |

**理論上 23 dBm 在 free space 也該有公里級覆蓋**。實際縮到 <100×100 m 表示：
- 可能 buildings 把絕大多數 ray 都遮住（Brownstone 場景密集都市）
- 可能 azimuth 朝向跟 UE 取樣 grid 沒對齊 → 只 sidelobe 接收
- 可能 max_depth=3 太低，繞射/反射不夠 → NLOS 區直接斷
- 可能 PlanarArray 1×1 V 極化單元天線 pattern 在側面就 -30 dB 以上

→ **建議**：用更大 `max_depth`（試 5–6）+ 多元極化 `cross` + 多 antenna `4×2` 看是否覆蓋擴張。如還是這麼小，就是場景密集都市 + 23 dBm 物理上就是這麼短。

### 4.5 為什麼「實際模擬所有 cell 都沒 Log 變化」？

這個現象比較複雜，可能性：
1. **RU 端 power 沒變化** → RSRP 維持原本（因為 RU 硬 code 43 dBm + 14 - 50 = 7 dBm net），所以 KPM 數字跟改 power 前一模一樣，使用者直覺認為「沒效果」=「沒 Log」
2. **Sionna 場景 rebuild 失敗** → path_gain 變 0 或 NaN → RSRP=-200 sentinel → DU/CU 過濾掉
3. **PCI / cell_id 衝突** → update_cells 把舊 cell 砍掉但新的還沒注入 → DU 找不到對應 cell 報不出來

請告訴我具體現象，最容易判斷的是去看 `ransim-ru/logs/*.log` 抓 `RSRP` 字串（如果有的話），或看 `e2adapter` 還在不在送 RIC_INDICATION（如果在送但 RSRP 值不變 → 屬於 (1)；如果完全沒送了 → 屬於 (2)/(3)）。

---

## 5. 建議的修法

### 5.1 最小修法（解 §4.1、§4.2，~30 行 + migration）

1. **Cell model 加 `power_dbm` 欄位**（`RANsim-RU/main/apps/antenna/models/cell.py`，default=43.0）
2. **`update_cells` API 接 power_dbm**（actor + serializer + payload_builder）
3. **`_path_gain_to_rsrp_dbm` 改成 per-cell**：
   ```python
   def _path_gain_to_rsrp_dbm(path_gain_linear, *, cell_power_dbm: float = _TX_POWER_DBM) -> float:
       ...
       return cell_power_dbm + _ANTENNA_GAIN_DBI + path_gain_db - _SCENE_CALIBRATION_LOSS_DB
   ```
4. **Dashboard `update_cells` payload 加 power_dbm**（從 gNB 的 power_dbm 帶下來，per-cell 等於 per-gNB power）
5. **Django migration**：`python manage.py makemigrations antenna && migrate`

→ 完成後，Dashboard 改 power → Coverage 跟 KPM **同步反映**，不再背離。

### 5.2 進階修法（解 §4.3，可選）

校正常數重新拆解。把目前 `-50 dB` 拆成：
- `RU_ANTENNA_GAIN_DBI=0`（不要再雙加，Sionna 已含）
- `RU_SCENE_CALIBRATION_LOSS_DB=36`（剩下的真實校正：18 dB 建物穿透 + 8 dB body loss + ~10 dB shadowing）
- → 數學等效：原本 `+14 - 50 = -36`；新 `+0 - 36 = -36`

優點：意義清楚，當未來把場景換成更真實的 outdoor scene 時可以精確調整 calibration 值，不會跟天線 gain 糊在一起。

### 5.3 架構修法（解 §3 兩 pipeline 背離，重 refactor 不建議現在做）

把 RSRP 計算搬到 Physics 端：`PathSolver` response 直接回 `rsrp_dbm`（per UE per cell），RU 不再 reconvert。Coverage 和 KPM 共用同一個 `path_gain → rsrp_dbm` 函式。

→ 缺點：要動 `ran-sim-protocol` PathSolverResponse DTO 跟 CU/DU/RU 全鏈整合測；建議 v2 platform 再做。

---

## 6. 你接下來該做的

1. **先決定要不要做 §5.1 最小修法**（讓 power 改動真正在 KPM 反映）
2. 給我 `ransim-ru` 改 power 後的 log 片段，判定 §4.5 是哪一種情況
3. 如要驗證 §4.4（heatmap 太小），把 `max_depth` 試 5、antenna 試 `4×2 cross` 跑一張 heatmap 比對
