# RAN Digital Twin 模擬加速機制筆記

整理 UE / RU / DU / CU / Physics / e2adapter 各層加速手段、整體效果、以及目前 10x 同步加速下的瓶頸。

---

## 各層加速手段

### 1. UE 層 — `RANsim-UE/main/apps/scenario/services/scenario_driver.py`

| 項目 | 內容 |
|---|---|
| 機制 | `target_wall_tick_ms` runtime 可調的 wall-clock 醒來節奏 |
| 提升什麼 | UE 位置 + traffic profile 從劇本 JSON **按 wall 時間加速推送**到 DU/RU |
| 怎麼做 | 每 `target_wall_tick_ms` 醒一次,interpolate 位置 → batch POST RU,traffic → POST DU `RlcDataController/inject_sdu_batch` |
| 關鍵 | `sim_dt_ms` 固定(劇本決定,通常 500ms),`wall_tick_ms` 縮短就是加速 |

### 2. DU 層 — `RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py`

| 項目 | 內容 |
|---|---|
| 機制 | `wall_tick_ms` runtime 可調(`/DU/Tick/TickController/set_speed`) |
| 提升什麼 | MAC tick(scheduler、HARQ、PRB 分配、PM aggregator)全部按 wall 加速 |
| 怎麼做 | `sim_speed_x = sim_dt_ms / wall_tick_ms` — `wall_tick=50ms, sim_dt=500ms` 就 10x |
| 關鍵 | **這是整個系統的「真實來源」**,CU/adapter 都跟它 pull |

### 3. CU 層 — `RANsim-CU/main/apps/cu_cp/actors/e2_subscription_actor.py` + `services/optional/e2/indication_producer.py`

| 項目 | 內容 |
|---|---|
| 機制 | sim_speed_x background pull DU,改 KPM `effective_period_ms = period_ms / speed` |
| 提升什麼 | KPM Indication 產生頻率從 wall-1Hz 變 sim-time 1Hz(加速後 wall 多 Hz) |
| 怎麼做 | `E2IndicationActor.poll` 每次 build 前檢查 `now - last >= effective_period` |
| 關鍵 | 不改原 wall-clock 邏輯,只把 period 縮放 |

### 4. e2adapter 層 — `RANsim-E2Adapter/main/apps/e2_adapter/services/optional/sctp_link/sctp_loop.py`

| 項目 | 內容 |
|---|---|
| 機制 | sim_speed_x background pull CU,改 SCTP poll cadence `period_sec / speed` |
| 提升什麼 | adapter → CU 拉 indication 的 wall 頻率跟著加速,不會卡 KPM 流出口 |
| 怎麼做 | producer thread 每輪重讀 speed,lower bound 50ms 避免空 poll burst |
| 關鍵 | 不需要 RIC 端感知加速 — adapter 對 RIC 而言就是普通 1Hz sim 一直跑 |

### 5. RU 層 — `RANsim-RU/main/apps/fapi_south/services/optional/dl_tti_pipeline.py`

| 項目 | 內容 |
|---|---|
| 機制 | **mode 切換** — `live` 走 Sionna RT、`cached` 走 precomputed npz lookup |
| 提升什麼 | live mode 一次 Sionna call ~200ms → cached lookup <0.1ms,**消除 Sionna 瓶頸** |
| 怎麼做 | `/RU/Config/RuController/set_channel_mode` + `get_channel_cache()` mmap parquet/npz |
| 關鍵 | **只有 cached mode 才能撐 10x+ 加速**,live mode 上限約 4x |

### 6. Physics 層 — `Physics_sim/precompute/run_precompute.py`

| 項目 | 內容 |
|---|---|
| 機制 | 離線 Sionna precompute → 寫 npz/parquet cache |
| 提升什麼 | 把 Sionna 200ms/call 的成本搬到模擬前的 precompute 階段(可 GPU + 多 worker 平行) |
| 怎麼做 | 讀 scenario JSON → 對每個 tick × UE × cell 算 path_gain/delay/AoA → 寫 cache file |
| 關鍵 | 1 hr scenario × 500ms × 10 UE × 3 cell = 21.6 萬 call,GPU 並行可 ~1.5 hr 跑完 |

### 7. Dashboard 入口

| 入口 | 動作 |
|---|---|
| `/editor` 速度下拉 | 1x/2x/4x/10x → POST DU `set_speed` 一處,CU+adapter auto-pull |
| `/scenarios` Run 按鈕 | startFastRun 帶 `timeCompressionRatio`,fan-out 切 RU mode、起 UE driver、設 DU 速度 |

---

## 整體加速效果(1x vs 10x)

| 環節 | 1x baseline | 10x 同步加速 |
|---|---|---|
| 1 sim-hr 跑完 wall 時間 | 60 min wall | **6 min wall** |
| DU tick 頻率 | 2 Hz wall (500ms) | 20 Hz wall (50ms) |
| KPM indication | 1/wall-sec | **7.7/wall-sec(77% 命中)** |
| UE 位置更新 | 2 Hz wall | 20 Hz wall |
| Sionna call(live) | 2 calls/wall-sec | ❌ 撐不住,要 cached |
| Sionna call(cached) | mmap 查表,跟速度無關 | mmap 查表 |
| RC 閉環延遲(sim-time) | ~280ms sim | ~1.5 sim-sec |

---

## 目前 10x 已知不完美 + 再往上會遇到的問題

### 10x 現在做得到但不完美的部分

| 問題 | 實測 | 為什麼 |
|---|---|---|
| **live mode 設 10x 實質只達到 ~2x** | DU 設 wall_tick=50ms(10x),實際跑 234ms/tick = **21.3% 命中率**,等於 **2.1x 實質加速** | Sionna `compute_paths` 一次 ~200ms,2.6 call/sec 吃掉 ~520ms wall 預算/wall-sec;RU 的 0.5s channel cache 在這速率下只罩 2 tick,擋不住 |
| **KPM 命中率 77%(無 RAN 負載時)** | 從 e2adapter snapshot 看 7.7 ind/wall-sec,目標 10/sec | CU `build_indication()` 每筆要 join 五張表(UeContext / MeasurementLog / HandoverEvent / CellMeasurementLog / BbuTelemetry),ORM query 耗 ~10–20ms;這 77% 是 CU 自己 produce 端的指標,**跟 DU 是否在跑沒關係** |

→ **解法 RU**:走 `/scenarios` Run 路徑 — `startFastRun` 會自動 POST `RU/Config/RuController/set_channel_mode=cached` 並 load `{scenario_id}.npz`,完全跳過 live Sionna。Cache 已 precompute 好的劇本(`precompute=ready`,目前 `cco_1hr` / `im_1hr` 都有)在 10x 完全沒 Sionna 壓力。
→ **解法 KPM**:CU async 預製 indication / 縮 ORM。

### 兩種「命中率」要分清楚

| 指標 | 從哪量 | 反映什麼 |
|---|---|---|
| **DU tick 命中率**(實測 21.3% @ live 10x) | `tick_count` 增長 / wall 時間 | 整個 RAN pipeline(MAC + Sionna + F1AP + DB write)是否跟得上 |
| **KPM produce 命中率**(實測 77% @ 10x) | adapter `total_indications` 增長 / wall 時間 | 只反映 CU 自己 produce 端的速度,跟 DU 有沒有跑無關 |

之前報的「10x 同步加速 OK」是 KPM produce 端的指標 — 那是 KPM 路徑通了,**不代表 RAN pipeline 真的跑在 10x**。要看 RAN 真實負載,看 DU tick 命中率。

### Cached 跟 live 的差別(別搞混)

| 入口 | RU mode | Sionna 壓力 | 10x 可行? |
|---|---|---|---|
| `/editor` 速度下拉(手動 1x/2x/4x/10x) | **live**(預設) | 200ms/call → 跟不上 wall_tick=50ms | 簡單場景 OK,複雜場景 ❌ |
| `/scenarios` 劇本 Run(precompute=ready) | **cached** | mmap 查表 <0.1ms | ✅ 完全可行 |
| `/scenarios` 劇本 Run(precompute=pending) | cached 載不到資料 | 退回 live | 同 live 限制 |

### 再往上(20x / 30x / 60x)會遇到的新瓶頸

| 倍率門檻 | 會壞掉的部分 | 為什麼 |
|---|---|---|
| **>10x(進 cached mode 必須)** | RU live Sionna 完全跟不上 | wall_tick 已 < Sionna single call latency |
| **>10x** | RC 閉環延遲在 sim-time 上爆大 | xApp 下 RC → adapter → CU → DU → 套用,wall 上 ~30–50ms 固定;30x 看 sim-time 是 ~1.5 sim-sec 反應延遲,handover 命令會「遲到」 |
| **>30x** | PostgreSQL SignalHistory 寫入跟不上 | 每 tick × N UE 一筆 row,60x 下單機 Postgres 寫吞吐會到極限,需 batch insert(每 100 tick 一次 bulk_create) |
| **>30x** | xApp 端 SCTP 消化能力 | KPM 從 1Hz wall 變成 30Hz wall,xApp 內部處理 / RIC encode / DB 寫如果不對等加速,xApp 那邊會積壓 |
| **>30x** | Python 解譯器開銷 | MAC scheduler / RLC / HARQ 在 17ms wall_tick 內可能跑不完整個 pipeline,要考慮 cython / C ext 化主路徑 |

---

## 達成不同倍率的配方(實測修正)

| 目標倍率 | live mode 路徑 | cached mode 路徑 |
|---|---|---|
| **2x** | ✓ live Sionna 撐得住(`/editor` 設 250ms) | ✓ |
| **~2.1x(實測 live 上限)** | ⚠️ 設 10x 實際只跑到 ~2x,Sionna 卡關 | — |
| **4x–10x** | ❌ live Sionna 跟不上 | ✓ 走 `/scenarios` Run 已 precompute 的劇本 |
| **30x(plan Phase B)** | ❌ | ✓ cached + Physics precompute + 注意 xApp 跟得上 |
| **60x+** | ❌ | cached + SignalHistory batch insert + cython 化 MAC scheduler 主路徑 |

---

## 已落地 / 待落地

| Phase | 狀態 |
|---|---|
| **Phase A:DU set_speed runtime knob(1x–10x)** | ✓ 落地 |
| **同步加速(CU + adapter 跟 DU)** | ✓ 落地(Task #85–89) |
| **Phase B:cached channel mode(>10x)** | 🚧 in_progress(Task #78) |
| xApp 端加速 hook | ⏸ 擱置(Phase B 之後) |
