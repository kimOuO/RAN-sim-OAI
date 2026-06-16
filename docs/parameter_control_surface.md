# RAN Digital Twin 參數控制面報告

> 整理日期：2026-06-11
> 目的：說明每個參數「由誰控制(env / API / 寫死)」以及「在調整什麼」。
> 值取自 `docker-compose.yml`、scene config 與 code 實測。

---

## 0. 報告框架：參數其實有「三層」優先序

不是只有「env vs 寫死」兩類，實際是 **三層，後者覆寫前者**：

```
env 預設值  →  劇本欄位覆寫  →  API start body(啟動當下)
```

很多 env 看起來定死了，其實 **劇本會蓋過它**(下面標 ⚠️ 的就是)。
另有一批物理/演算法常數寫死在 code，改 JSON / docker-compose 改不到。

---

## 1. 🟦 env / API 可控(容器層級)

### CU — 身分 + RIC + 換手

| 參數 | 值 | 在調整什麼 |
|---|---|---|
| `PLMN_MCC` / `PLMN_MNC` | 208 / 95 | 電信商識別碼(PLMN 208-95)，編進 NGAP / cell 身分 |
| `GNB_ID_HEX` / `GNB_ID_LENGTH` | 0x000e00 / 22 | 基地台 ID，組成 RIC 看到的 globalE2node-ID + NCI 高位 |
| `RAN_FUNC_ID_KPM` / `_RC` | 2 / 3 | E2 服務模型 ID：KPM=量測上報、RC=控制(換手/quota)。xApp 靠這認功能 |
| `HO_A3_OFFSET_DB` | 5.0 | A3 換手門檻：鄰區要比服務區強 5 dB 才考慮換手 |
| `HO_A3_HYSTERESIS_DB` | 6.0 | 遲滯帶，避免邊界乒乓換手 |
| `HO_TTT_MS` | 3000 | Time-To-Trigger：A3 條件要連續成立 3 秒才真的換手 |
| `OMNIVERSE_URL` | :8001 | 場景幾何 / 劇本的來源後端 |

### DU — 模擬節拍 + KPM + RLC delay

| 參數 | 值 | 在調整什麼 |
|---|---|---|
| `SIM_TICK_MS` | 50 | 基礎 wall tick(⚠️ 實際每 tick sim-time 由 start body `sim_dt_ms` 決定) |
| `PM_WINDOW_SEC` | 1.0 | KPM 平均視窗：每 1 秒算一次 delay/throughput/PRB 平均上報 |
| `RLC_DELAY_MODEL` | calib | delay 模型：`calib`(舊 ÷30)或 `subtick`(slot 引擎)⚠️ 劇本可覆寫(cco=subtick) |
| `SLOT_ENGINE_SHADOW` / `_TAKEOVER` | on / on | 是否讓 0.5ms slot 引擎接管 delay 計算(取代 ÷30) |
| `SLOT_DISCARD_TIMER_MS` | 300 | RLC 丟包門檻：封包等超過這時間就丟 ⚠️ 劇本覆寫(cco=2000) |
| `DU_INPROCESS_SINR` | on | DU 自己算 SINR(不靠 RU HTTP)做驗證 |
| `RLC_TX_MAXSIZE_BYTES` | 10000000 | RLC 佇列上限(bytes) |
| `PRB_OAI_CALIB` | 1.0 | PRB 計數校正係數(對齊 OAI) |

### RU — 訊號強度換算 + 通道模式

| 參數 | 值 | 在調整什麼 |
|---|---|---|
| `RU_CHANNEL_MODE` | live / cached | `live`=即時跑 Sionna；`cached`=讀預算好的 npz |
| `RU_TX_POWER_DBM` | 23.0 | 發射功率(RSRP = power + path_gain)⚠️ 劇本 `power_dbm` 覆寫(cco=3) |
| `RU_NOISE_FLOOR_DBM` | -98 | 噪音地板(SINR = RSRP − noise)，決定噪音受限的 SINR 上限 |
| `RU_DEFAULT_ANTENNA_ROWS` / `COLS` | 1 / 1 | 天線陣列大小(1×1 = 單天線，無波束成形增益) |
| `RU_SCENE_CALIBRATION_LOSS_DB` | 0.0 | RSRP 整體校正偏移(對齊基準用) |
| `RU_CACHE_DIR` | /data/channel_cache | cached npz 存放位置 |
| `RU_CHANNEL_CACHE_TTL_SEC` | 0.5 | 通道快取新鮮度 |

### Physics — Sionna 場景

| 參數 | 值 | 在調整什麼 |
|---|---|---|
| `MITSUBA_SCENE_PATH` | umi_3sector.xml | 預設 3D 場景幾何檔 |
| `OMNIVERSE_URL` | :8001 | 場景來源 |
| max reflection depth / num_samples | API / code | Sionna 射線反射深度、射線數 |

---

## 2. 🟩 API start body(啟動當下傳入，env / 劇本都沒有)

`POST /api/v0.1/UE/Sim/SimController/start`

| 參數 | 在調整什麼 |
|---|---|
| `scenario_id` | 要跑哪個劇本 |
| `source` | scenario / editor 來源 |
| `speed_x` | 模擬加速倍率(2x…) |
| `sim_dt_ms` | 每 tick 代表多少 sim-time(500=原生，250=半)⚠️ 覆寫 env `SIM_TICK_MS` |

---

## 3. 🟧 env / 劇本管不到(寫死 or scene config)

| 項目 | 位置 / 值 | 在調整什麼 |
|---|---|---|
| `total_prb = 106` | `cell_state.py` | cell 容量上限(40MHz @ 30kHz SCS，對齊 OAI band78)。改頻寬不會自動改它 |
| `÷30 calib` | `tick_runner.py` | 舊的 delay 硬壓係數(對齊 OAI 低 delay)。slot 引擎接管後被繞過 |
| `TDD_DL_SLOT_RATIO = 0.72` | `mcs_table.py` | TDD 中 DL 佔的 slot 比例(上下行時隙配比) |
| `overhead = 0.80` | `mcs_table.py` | MAC/PHY 額外開銷係數(實際吞吐打 8 折) |
| MCS table / controller / OLLA | `link_adaptation/` | SINR→MCS 對照 + 外環調整(依 BLER 微調 MCS) |

---

## 4. ⚠️ 三個必須點出的修正 / 重點

1. **A3 offset / hysteresis 不是寫死的** —— 它們是 CU 的 env
   (`HO_A3_OFFSET_DB=5.0`、`HO_A3_HYSTERESIS_DB=6.0`、`HO_TTT_MS=3000`)，可改。

2. **很多 env 會被劇本覆寫**(precedence：env → 劇本 → start body)：
   - delay 模型、discard timer、tx power 都是 env 給「預設」，劇本才是最終值
     (cco：`rlc_delay_model=subtick` / `discard_timer_ms=2000` / `power_dbm=3`)。

3. **precompute 已修**:以前 precompute 不一定吃劇本的
   `antenna_pattern` / `gnbs` / `buildings` → 改劇本但 cached channel 沒變。
   現已修正，cached channel 會符合劇本設定(列為「已解決的風險」)。

---

## 5. 一句話總結

> 設定分三層 —— 容器 env 給預設、劇本覆寫成情境值、start body 決定啟動參數；
> 另有一批物理/演算法常數(PRB 容量、TDD 配比、MCS、÷30)寫死在 code，
> 改 JSON 改不到。要改 demo 行為(如 CCO 壅塞)得靠**劇本能覆寫的那幾個**
> (`rlc_delay_model`、`discard_timer_ms`、PRB quota)，而非動寫死的常數。
