# Sim Speed Ceiling Test — 2026-05-23

## 目的

實測 cached mode(Sionna 預算好的 channel)前提下,RU / DU / CU / E2adapter
各層能跟得上的真實 sim_speed_x 上限。xApp 端不算。

## 測試條件

| 項目 | 值 |
|---|---|
| Scenario | `full_day_24hr`(scene_id=`twocell_separated`) |
| RU channel mode | `cached:full_day_24hr`(`.mode` file) |
| UE 數 | 1(stationary @ (0, 1.5, 100)) |
| Cell 數 | 2(c0=(0,30,0), c1=(300,30,0)) |
| BW / PRB | 40 MHz / 106 PRB(對齊 OAI band78) |
| TX power | 4 dBm |
| Noise floor | -98 dBm |
| TDD DL ratio | 0.72 |
| Trajectory tick | 100 ms wall(固定,不隨 speed) |
| 取樣 | 每倍速跑 15 秒 wall,量 DU `tick_count` 增量推算實效 wall_tick |

## 結果

| 設定 sim_speed | 目標 wall_tick | 實效 sim_speed | 實效 wall_tick | 評估 |
|---|---|---|---|---|
| **5x** | 100 ms | **4.95x** ✅ | 100.9 ms | 精準達標 |
| 10x | 50 ms | **7.22x** ⚠️ | 69.2 ms | 撞 sustained 上限 |
| 20x | 25 ms | 8.05x ⚠️ | 62.1 ms | 同 |
| 30x | 17 ms | 7.55x ⚠️ | 66.2 ms | 同 |
| 50x | 10 ms | 7.95x ⚠️ | 62.9 ms | 程式 clamp 接受但跑不到 |

## 健康檢查

四個容器 `ransim-du` / `ransim-cu` / `ransim-ru` / `ransim-e2adapter` 整段測試
零 warn / error / exception:

```
=== ransim-du ===      0 warn/err lines
=== ransim-cu ===      0 warn/err lines
=== ransim-ru ===      0 warn/err lines
=== ransim-e2adapter ===  0 warn/err lines
```

## 結論

### 真實 sustained 上限 ≈ **7-8x**

- **不是「崩」是「跑不到」**:RAN 鏈路每一層都正常運作,只是 DU per-tick body
  wall ~63 ms 是 sustained 物理底限。設高也壓不下去,沒有 functional 失敗。
- 設 10x 實際只跑 7.2x → 「設定漂移」會讓 wall-clock duration 跟 sim-time
  estimate 對不上,做 KPM 對照容易誤判。

### Bottleneck 來源(不在 Sionna)

cached mode 已把 Sionna live 200ms/path 拔掉,但其他 RAN 鏈路加總 wall ~65 ms/tick:

1. DU → RU `dl_tti_request` HTTP RTT ≈ 15 ms
2. RU → DU `cqi_indication` callback HTTP ≈ 15 ms
3. DU → omniverse_backend kit ingest HTTP ≈ 20-30 ms(跨容器 + Postgres write)
4. DU 內 scheduler + PM aggregate ≈ 5 ms

合計 55-65 ms,匹配實測 62-69 ms wall_tick。

### 實用建議

| 用途 | 建議倍速 | 原因 |
|---|---|---|
| KPM 對照 / 24hr 壓縮 | **5x** | 設定 = 實效,wall-clock duration 可預測 |
| 純壓時間驗證 | 5x | 同上 |
| 即時觀察 | 1x | wall = sim,所見即所得 |
| **避免使用** | ≥10x | 設定漂移、wall-time estimate 失準 |

### 進一步提速(本次測試後可選的改造,未實作)

要把 sustained 上限拉到 15-30x 需要的改造方向:

- DU↔RU 改 async / in-process channel(消除 HTTP RTT)
- Kit ingest batch + 後台 thread 寫,不擋 tick loop
- gunicorn sync worker → uvicorn async worker
- `UE_TRAJECTORY_PERIOD_MS` 跟 speed_x 連動(目前 100ms wall 固定)

## 對前端的影響

基於本測試,**前端速度選項調整**:

- `/scenarios` page:`[2, 4, 10]` → `[5]`(只留實測達標倍速)
- `/editor` page:`[1x, 2x, 4x, 10x]` → `[1x, 5x]`(保留 real-time + 5x 加速)

避免使用者選 10x 卻只跑到 7x,導致 wall-clock estimate 跟實際對不上。

## 關聯記憶

- `memory/oai_alignment_params.md`:本場景的物理層參數對照
- `memory/full_day_24hr_kpm_result.md`:24hr 對照結果
- `memory/unified_sim_architecture.md`:SimController 統一入口
