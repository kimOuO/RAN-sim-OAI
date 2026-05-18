# 場景情境建設 — 前端可動態調整能力評估

> 產出日期: 2026-05-16
> 對象: `Physics_sim/Dashboard`(Next.js,docker-compose service `dashboard`)
> 對照清單: `oai_conf_alignment_report.md` 的 A 區(場景情境建設)5 類缺口
> 結論先講: **A 區大部分都有前端入口,只有 3 項真的沒地方點**

---

## TL;DR

| A 區缺口 | 前端能不能動? | 入口位置 |
|---|---|---|
| gNB / cell 物理屬性(XYZ、azimuth、frequency、power、PCI、bandwidth)| ✅ **能** | `/editor` 頁:canvas 拖放 + ObjectForm + cells 子表單 |
| 拓樸選型(縮 scene / 擴 OAI / 純 DT)| ✅ **能(scene 側)** | 增刪 gNB / cell 都能,scene 縮放沒問題 |
| 鄰區關係(`neighbour_list`)| ❌ **不能(隱式)** | 沒有定向 / per-PCI 鄰區編輯 UI |
| A2 量測事件 | ❌ **不能(平台未實作)** | A3ControlPanel 只控 A3,沒 A2 入口 |
| EIRP 口徑反算(RU link budget)| ⚠️ **半能** | `power_dbm` 能在 ObjectForm 改,但 `RU_ANTENNA_GAIN_DBI` / `RU_SCENE_CALIBRATION_LOSS_DB` 還是 compose env |
| **額外實體屬性**: cell `tilt`(下傾角)| ❌ **不能** | 場景 schema 沒這個欄位 |

→ 前端 **能** 動態調的 = 場景幾何 + cell 物理參數 + MIMO + A3
→ 前端 **不能** 動的 = 鄰區、A2、tilt、RU env(三件套裡的 antenna_gain / calibration_loss)

---

## 1. 前端已實作的場景動態調整入口

### 1.1 `/editor` 頁(主編輯器)

從 `Physics_sim/Dashboard/app/editor/page.tsx` 看,提供:

| 物件 | 動作 | 入口 | 改完怎麼生效 |
|---|---|---|---|
| Building | 新增 / 刪除 / 拖放定位 | ObjectForm + TopDownMap canvas | `SceneGateway/init` reload |
| Building | name、material(concrete/brick/glass/metal/wood) | ObjectForm | 同上 |
| Obstacle | 新增 / 刪除 / 拖放、material | 同上 | 同上 |
| **gNB** | 新增 / 刪除 / 拖放 XY 位置 | TopDownMap canvas 拖放 | `SceneGateway/init` reload |
| **gNB** | name、`frequency_ghz`、`power_dbm` | ObjectForm | 同上 |
| **gNB cells**(每個 sector) | `pci`、`azimuth_deg` 編輯 | ObjectForm 的 cells 子表單 | 同上 |
| **gNB bandwidth** | 自動依 frequency 推(n78 → 100 MHz)| 不開放手動,由 `getRecommendedBandwidth()` 決定 | 同上 |
| UE | 新增 / 刪除 / 拖放、name、`speed_mps` | ObjectForm | 同上 |
| UE waypoints(軌跡) | TopDownMap canvas 點擊新增 / 拖放 | TopDownMap | trajectory API |

> 對應到 OAI 缺口:gNB position、azimuth、frequency、power、PCI 這 5 個欄位 **前端全部能點**,等於可以直接把 OAI 端要來的勘測表填進去。

### 1.2 `MimoSettingsPanel`(MIMO 預設)

| 欄位 | UI |
|---|---|
| `gnb_array_rows / cols` | 數字輸入 |
| `gnb_polarization` | V / cross |
| `ue_array_rows / cols / polarization` | 同上 |
| 預設組合 | 1×1 SISO / 4×2 cross / 8×4 cross |

> 對齊 OAI `nb_tx/nb_rx` 完全沒問題,且還能升級到 OAI 沒給的 4×2 / 8×4。

### 1.3 `A3ControlPanel`(A3 即時控制)

| 欄位 | UI | 後端 API |
|---|---|---|
| `enabled` | 開關 | `/api/v0.1/CU/Mobility/A3Controller/set` |
| `offset_db` / `hysteresis_db` / `ttt_ms` | 即時調整 | 同上 |

> **不需要重啟 CU container**(runtime hot reload)。對應 OAI `nr_measurement_configuration.A3`,功能對齊。
> ⚠ 但這只是 CU 端決策值,沒辦法逐 cell 設定不同 A3(OAI 端 `neighbour-config.conf` 可以)。

### 1.4 ObjectForm 內建驗證(防呆)

- **材質-頻率交叉驗證**: 已有 gNB 用 0.617 GHz(n71)時,前端會 disable concrete/brick/metal(這幾個材質 ITU 有效範圍下限 1 GHz),自動擋掉送錯設定
- **頻率→帶寬自動推**: 選 n78 自動填 100 MHz,選 n71 自動填 20 MHz

> 這已經是 OAI conf 沒有的「友善」層,前端做了預驗證。

---

## 2. 前端沒入口的場景項目(真正的缺口)

### 2.1 ❌ 鄰區關係(`neighbour_list`)

- 前端 **沒有定向 / per-PCI 鄰區編輯 UI**
- 目前策略:scene 內所有 `active=true` 的 cell 互為鄰區(隱式)
- 真實 OAI 用 `neighbour_list` 配置 A→B 是鄰、B→A 不是的方向性
- **後端也沒接口** — 不只前端缺,CU 那邊也要硬編

**修法**:
1. 後端先在 CU `mobility/` 加 neighbour relation API(`/api/v0.1/CU/Mobility/NeighbourController/set`)
2. 前端在 `/editor` 加一個 NeighbourMatrixPanel(A→B 勾選矩陣)

### 2.2 ❌ A2 量測事件

- 前端 `A3ControlPanel` 只有 A3
- 後端 `a3_handover_calculation.py` 也只算 A3
- **整條 A2 邏輯都不存在**

**修法**(要不要做先看 OAI 那邊是否實際用 A2):
1. CU 加 `a2_measurement_calculation.py`(門檻判斷)
2. UE → CU MeasurementReport 加 A2 event 欄位
3. 前端加 A2Panel,類似 A3Panel(threshold / hysteresis / TTT)

### 2.3 ❌ Cell 下傾角(`tilt`)

- 前端 cells 子表單只有 `pci` + `azimuth_deg`,**沒有 `tilt_deg`**
- scene_config.json schema 也沒這個欄位
- Sionna RT 可以吃 elevation tilt 但 XAPP_DT 沒接出來

**修法**:
1. scene_config 加 `cells[].tilt_deg`(預設 0)
2. ObjectForm cells 子表單加一欄
3. RU `update_antenna` API + ran-sim-protocol AntennaArrayConfig 加 `tilt` 欄位
4. Physics PathSolver 把 tilt 傳給 Sionna AntennaArray

### 2.4 ⚠️ RU link budget 環境變數(半缺口)

| 欄位 | 前端能改? | 目前位置 |
|---|---|---|
| scene `gnbs[].power_dbm` | ✅ ObjectForm `power_dbm` 欄 | scene_config |
| `RU_TX_POWER_DBM` | ❌ 只在 compose env(冷調) | docker-compose.yml |
| `RU_ANTENNA_GAIN_DBI` | ❌ 同上 | 同上 |
| `RU_SCENE_CALIBRATION_LOSS_DB` | ❌ 同上 | 同上 |
| `RU_NOISE_FLOOR_DBM` | ❌ 同上 | 同上 |

→ 用戶從前端改 `power_dbm` 確實會走 scene reload 進 Sionna,
**但**:RU 算 RSRP 是 `TX_POWER + ANTENNA_GAIN + path_gain - CALIBRATION_LOSS`,後三項要重啟 RU container 才會更新。

**修法**:
1. RU 加 `/api/v0.1/RU/Config/RuController/update_link_budget` API
2. 前端加 LinkBudgetPanel(類似 A3Panel),四個欄位即時調整

---

## 3. 結論

把 OAI 缺口 5 類 + 前端能力一起看:

| OAI 缺口 | 前端是否動態可調? | 缺什麼 |
|---|---|---|
| ① gNB 物理屬性(XYZ、azimuth、freq、power、PCI、bw)| ✅ **全部能改** | 只缺 `tilt`(下傾角) |
| ② 拓樸選型(2 vs 9 cell)| ✅ **能,scene 端隨時增刪** | — |
| ③ `neighbour-config.conf`(鄰區 + A3)| 一半 — A3 能,鄰區不能 | 鄰區編輯 UI + 後端 API |
| ④ A2 事件 | ❌ **完全沒有** | A2 panel + CU 邏輯 + UE 上報 |
| ⑤ EIRP 三件套(antenna gain / calibration / noise)| ⚠️ **只能改 scene power,RU env 改不了** | RU LinkBudget API + Panel |

→ **真正只剩 3 個前端要補的洞**:
1. 鄰區編輯 UI(+ 後端 API)
2. A2 panel(+ CU 邏輯,先確認 OAI 端用不用)
3. RU LinkBudget Panel(+ RU API,讓 antenna_gain / calibration_loss runtime 可調)

→ **不用補的**:
- gNB position、azimuth、frequency、power、PCI 全部都有 ObjectForm + canvas 編輯
- A3 (offset/hys/ttt) 有 A3ControlPanel runtime 即時調整
- MIMO 有 MimoSettingsPanel
- 材質、UE 軌跡、bandwidth 都有

---

## 4. 場景動態調整 SOP(目前流程)

新場景上線 / 換實驗 case 時:

```
1. 進 /editor 頁
2. canvas 拖放新增 gNB / Building / UE / Obstacle
3. ObjectForm 內填:
   - gNB: frequency / power / cells[*]{pci, azimuth_deg}
   - Building / Obstacle: material
   - UE: speed_mps
4. TopDownMap 點擊新增 UE waypoints(軌跡)
5. MimoSettingsPanel 設天線陣列(1×1 / 4×2 / 8×4)
6. 按 SceneGateway/init reload → 場景進 Sionna
7. A3ControlPanel 即時調 A3(不需 reload)
8. (如需)compose 改 RU env → 重啟 ru container 套用
```

→ 步驟 1-7 都是前端動,只有步驟 8 還需要碰 docker-compose。

---

## 5. 建議下一步

照「對使用者體驗」的影響排序:

1. **★★★ RU LinkBudget Panel**(把 step 8 從前端做掉)— 影響 RSRP 校準,跟 OAI 對齊時最常動
2. **★★ 鄰區編輯 UI** — 目前隱式策略對純 DT 還行,但對接 OAI `neighbour-config.conf` 後就需要
3. **★ A2 Panel** — 看 OAI 端是否實際用 A2 再決定要不要做
4. **★ cell tilt 欄位** — 要做 vertical beam 形狀驗證才需要
