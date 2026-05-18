# KPM 模擬 — 移動 / 流量 / 可調設定全紀錄

本文件整理 RAN-sim KPM 指標的三個來源:
1. UE **移動 (Trajectory)** — 影響 RSRP / SINR / serving cell
2. UE **流量 (Traffic)** — 影響 Throughput / Volume / Delay / PRB%
3. 其他 **可調設定** — TX power, scene loss, A3, tick period 等

每項都標清楚: 在哪個容器、哪條 code path、前端是否可調、改了之後 KPM 哪幾欄會變。

---

## 0. 容器分工速查

```
┌──────────────────────────────────────────────────────────────────┐
│ ransim-ue  (port 8105)  — 新加的 UE container                     │
│   - 每 UE 一個 thread                                             │
│   - Trajectory tick (100ms)  ──→ RU /Config/RuController/update_ues
│   - Traffic tick   (100ms)   ──→ DU /RLC/inject_sdu              │
│   - 從 CU /Session/list 拉 active UE (5s polling)                 │
└──────────────────────────────────────────────────────────────────┘
              ↓ position                          ↓ SDU bytes
┌──────────────────────────────┐    ┌──────────────────────────────┐
│ ransim-ru  (port 8104)        │    │ ransim-du  (port 8102)        │
│   FAPI DL TTI pipeline        │    │   RLC entity, segmenter       │
│   path_gain → RSRP/SINR       │    │   tick_runner (500ms)         │
│   call Sionna /channel/solve  │    │   PF scheduler + PRB cap      │
└──────────────────────────────┘    └──────────────────────────────┘
              ↓                                     ↓
       sionna ray-tracing                  PM aggregator (2.5s window)
              ↓                                     ↓
       Channel matrix per UE              throughput / volume / delay
                                                    ↓
                                  ransim-cu MeasurementLog (port 8101)
                                                    ↓
                                  /E2/E2KpmReporter/read  → RIC / Dashboard
```

---

## 1. UE 移動 (Trajectory)

### 1.1 觸發鏈

```
Dashboard /draw 畫 waypoints                Dashboard /editor 拖移 UE
        ↓                                          ↓
        ↓     POST /api/v0.1/UE/Trajectory/set     ↓
        └─────────────→ ransim-ue ←────────────────┘
                              ↓
              trajectory_store.set(ue_id, waypoints, mode)
                              ↓
          ── 每 100ms tick (_trajectory_loop in manager.py:77) ──
                              ↓
                  interp_position(waypoints, elapsed_ms, mode)
                              ↓
                ┌─ batch POST /RU/Config/RuController/update_ues
                │   (ru_client.update_ues_batch)
                │       ↓
                │   RU UePosition DB 寫入 (x, y, z)
                │       ↓
                │   RU dl_tti_pipeline call physics /channel/solve
                │       ↓
                │   Sionna ray-trace per-cell path_gain
                │       ↓
                │   path_gain → RSRP/SINR (dl_tti_pipeline:113)
                │       ↓
                │   CqiIndication 給 DU → MeasurementLog → KPM
                │
                └─ per-UE POST /Kit/move_ue (Omniverse 視覺)
```

### 1.2 Code 細節

| Component | File | 重點 |
|:---|:---|:---|
| 內插 | `RANsim-UE/.../services/interp.py` | 線性內插 + mode (loop/once/stay) |
| Tick loop | `manager.py:77 _trajectory_loop` | 每 `UE_TRAJECTORY_PERIOD_MS` 跑 |
| 寫 RU | `manager.py:135 ru_client.update_ues_batch` | batch 寫所有 RUNNING UE |
| RSRP 計算 | `RANsim-RU/.../dl_tti_pipeline.py:113` | `TX_POWER + ANTENNA_GAIN + path_gain - SCENE_LOSS` |

### 1.3 影響的 KPM 欄位

| 欄位 | 影響方式 |
|:---|:---|
| `RSRP` / `SINR` | UE 越靠 cell beam 中心, path_gain 越高, RSRP 越好 |
| `serving_cell` (KPM `N` 計數) | A3 evaluator 看到 neighbor RSRP > serving + offset → 觸發 HO |
| `DRB.UEThpDl` (throughput) | RSRP↑ → SINR↑ → MCS↑ → bytes_per_PRB↑ → throughput↑ |
| `DRB.RlcSduDelayDl` | RSRP差 → MCS低 → drain慢 → buffer 累積, delay 暴漲 |
| `RRU.PrbTotDl` | 不直接影響 (PF scheduler 通常分滿) |

### 1.4 前端可調?

| 動作 | 頁面 | 操作 |
|:---|:---|:---|
| 設 trajectory | `/draw` | 在 TrajectoryCanvas 點按 waypoints |
| 編輯 trajectory | `/editor` | UE detail panel → 拖移 UE 重設位置 |
| 清 trajectory | `/editor` | Clear Trajectory 按鈕 |
| 設 mode (loop/once/stay) | ❌ 沒前端 UI | hardcode `'loop'` (`page.tsx:117`) — 要改要動 code |

---

## 2. UE 流量 (Traffic)

### 2.1 觸發鏈

```
Dashboard /draw 或 /editor 改 traffic_profile dropdown
        ↓
        POST /CU/Session/SessionController/update_traffic_profile
              { ue_id, pattern, rate_mbps, sdu_size, bearer_id }
        ↓
   ransim-cu UeContext.traffic_profile_json 寫入
        ↓
   ── 每 5s ransim-ue 從 CU /Session/list polling 拉到新 profile ──
        ↓
   UeThread.update_snapshot → traffic_gen.update_profile()
        ↓
   ── 每 100ms tick (跟 trajectory tick 同 loop) ──
        ↓
   UeTrafficGen.tick()
     bytes_to_inject = rate_mbps × 1e6 × elapsed_ms / 1000 / 8
        ↓
   POST /DU/RLC/RlcEntityController/inject_sdu  (du_client.inject_sdu)
        ↓
   DU RLC entity buffer 累積 bytes
        ↓
   DU PF scheduler 分 PRB, 從 buffer drain bytes 出去
        ↓
   PM aggregator 窗口累積 (5 ticks × 500ms = 2.5s)
        ↓
   MeasurementLog throughput / volume / delay
```

### 2.2 Traffic profile 欄位

| 欄位 | 預設 | 影響 |
|:---|:---|:---|
| `pattern` | `cbr` | 只支援 cbr / idle (bursty 規劃中) |
| `rate_mbps` | 5 | CBR rate — 直接決定 demand |
| `sdu_size` | 1500 | 每 SDU bytes — 影響 RLC segmenter PDU 數 |
| `bearer_id` | 1 | DRB index, sim 都用 1 |

### 2.3 Code 細節

| Component | File | 重點 |
|:---|:---|:---|
| 注 SDU | `traffic_gen.py:53 tick()` | `bytes = rate × elapsed / 8` |
| 安全閥 | `traffic_gen.py:79` | 單 tick 最多 10 MB (避免 system pause 後 burst) |
| Profile 同步 | `manager.py:144 _sync_from_cu` | 5s polling, profile_changed event 強制立即拉 |
| DU drain | `tick_runner.py` PF scheduler + `pm_aggregator.py:88` | bytes × 8 / window_sec / 1e6 = Mbps |

### 2.4 影響的 KPM 欄位

| 欄位 | 影響方式 |
|:---|:---|
| `DRB.UEThpDl` | inject rate 上限, 但**實際看 MCS 能否 drain 跟上** |
| `DRB.PdcpSduVolumeDL` | window 內 drain bytes 累計 |
| `DRB.RlcSduDelayDl` | inject 比 drain 快 → buffer 累積 → enqueue→dequeue 時間拉長 |
| `RRU.PrbTotDl` | inject 0 → buffer 空 → scheduler 不分 PRB → 0% |
| `RSRP` / `SINR` | ❌ 跟 traffic 無關 (純物理層) |

### 2.5 前端可調?

| 動作 | 頁面 | 操作 |
|:---|:---|:---|
| 改 pattern (idle/cbr) | `/draw` 或 `/editor` | UE detail panel dropdown |
| 改 rate_mbps | `/draw` 或 `/editor` | slider (1~100 Mbps) |
| 改 sdu_size | ❌ 沒前端 UI | hardcode 1500 (`page.tsx:118,128`) |
| 改 bearer_id | ❌ 沒前端 UI | hardcode 1 |
| 改 pattern=bursty | ❌ 沒實作 | traffic_gen.py:7 標 "Phase C v2 才實作" |

---

## 3. 其他可調 KPM 設定

按「影響強度」排序:

### 3.1 ⭐⭐⭐ A3 Handover (CU)

| 參數 | env var | default | 影響 |
|:---|:---|:---|:---|
| A3 啟用 | runtime via Dashboard | true | 關掉: RIC HO 不會被 sim 內部 rollback |
| Offset | `HO_A3_OFFSET_DB` | 0.5 | 越大 HO 越難觸發 |
| Hysteresis | `HO_A3_HYSTERESIS_DB` | 0.3 | 越大 HO 越穩定 |
| TTT | `HO_TTT_MS` | 60 | 越大 HO 越慢 trigger |

**前端: ✓ /logs page → § H+ A3ControlPanel** (AK11), runtime 改, 不需 restart。

```
影響 KPM:
  ↓ serving_cell 變動頻率 (每 cell N 隨 HO 變)
  ↓ HO event count → MM.HoExeIntraReq / MM.HoExeIntraSucc / gnb.MR.Event.A3
  ↑ 短期 throughput dip (HO 中斷)
```

### 3.2 ⭐⭐⭐ RU 物理層常數 (RU)

| 參數 | env var | default | 影響 |
|:---|:---|:---|:---|
| TX power | `RU_TX_POWER_DBM` | 43 (20W macrocell) | RSRP absolute 移動 |
| Antenna gain | `RU_ANTENNA_GAIN_DBI` | 14 | RSRP absolute 移動 |
| Scene calibration loss | `RU_SCENE_CALIBRATION_LOSS_DB` | 50 | 補 Sionna scene 沒模擬到的 building penetration |
| Noise floor | `RU_NOISE_FLOOR_DBM` | -95 | SINR 計算 baseline |

**前端: ❌ 不可調**, 改要 edit docker-compose.yml env + restart ransim-ru。

```
影響 KPM:
  ± RSRP / SINR absolute scale (不影響 relative diff)
  ↓ SCENE_LOSS 太大 → 全部 UE SINR < -10 dB → MCS 0 → throughput 全卡
```

### 3.3 ⭐⭐ DU Tick period (DU)

| 參數 | env var | default | 影響 |
|:---|:---|:---|:---|
| Sim tick | `SIM_TICK_MS` | 500 ms | 排程粒度 + PM window size |
| PM window | hardcoded `5 ticks` | 2500 ms | KPM update 頻率 |

**前端: ❌ 不可調**, 改要 edit env + restart ransim-du。

```
影響 KPM:
  ↑ tick 縮短 → throughput 更新更快, 但 CPU 高
  ↑ tick 拉長 → KPM 更穩 (averaging), 但反應慢
```

### 3.4 ⭐⭐ UE container tick (UE)

| 參數 | env var | default | 影響 |
|:---|:---|:---|:---|
| Trajectory + traffic tick | `UE_TRAJECTORY_PERIOD_MS` | 100 ms | 位置與 SDU 注入頻率 |
| CU polling | `UE_LIST_POLL_PERIOD_SEC` | 5 s | traffic_profile 改變後幾秒生效 |

**前端: ❌ 不可調**, 改要 edit env + restart ransim-ue。

```
影響 KPM:
  ↓ tick 拉長 → 同 rate_mbps 下單次 inject 更大 → segmenter PDU 數變多
  ↑ polling 縮短 → profile 改後更快生效, 但 CU CPU 高
```

### 3.5 ⭐⭐ PRB total (DU)

NR 100 MHz hardcoded **273 PRB** (`kpm_indication.py:46`, `tick_runner.py:210`)。

- 影響 `RRU.PrbTotDl` 百分比 (用 `rb_width_dl / 273 × 100` 算)
- 改帶寬要動 code, 不只 env

**前端: ❌ 不可調**。

### 3.6 ⭐⭐ Sionna 場景 (Physics)

| 設定 | 位置 | 影響 |
|:---|:---|:---|
| 場景 USD | `scene_config.json` | 哪個 building 進 ray-tracing |
| Building obstacle | (AC2 pending) | 改變 LOS / NLOS pattern → path_gain 變動 |
| gNB 位置/朝向 | Dashboard `/scene_editor` | beam direction → 每 cell 不同方向 cover |

**前端: ✓ 部分可調**, Dashboard `/scene_editor` 可加減 gNB + 改方向 (AK6 後 createGNB 自動觸發 initScene)。Building obstacle 暫時要動 scene_config.json。

```
影響 KPM:
  ↑ 加 building 擋 north → c1 SINR 變差 (5/11 報告觀察到的現象)
  ↑ gNB beam azimuth 改 → cell cover 範圍變
```

### 3.7 ⭐ PRB quota (RIC 控制, 不算 sim 設定)

RIC E2 Control Style=2 Action=6 設 per-UE PRB cap (L1-L4)。

- 觸發: xApp `set_prb_quota` → CU → DU `PrbQuotaStore`
- 影響: `tick_runner.py:210` cap 該 UE 拿的 PRB 數

**前端: 透過 IM 觸發, 沒直接 UI 設 quota**。

---

## 4. 整理: 我要調 XX, 改哪裡?

### 我要 SINR 變好 / 變差

| 想做 | 改 |
|:---|:---|
| 整體 SINR 上拉 | env `RU_SCENE_CALIBRATION_LOSS_DB` 降到 30 (RU restart) |
| 特定 UE SINR 好 | Dashboard `/draw` 把 UE waypoint 移到 cell beam 中心 |
| 特定 cell SINR 差 | scene_config 加 building 擋該 beam 方向 (AC2 pending) |

### 我要 Throughput 高 / 低

| 想做 | 改 |
|:---|:---|
| 高 throughput | Dashboard UE detail panel 拉高 rate_mbps + waypoint 靠近 cell |
| 低 throughput | rate_mbps 降低, 或 UE 移遠 (SINR 差 → MCS 低 → drain 慢) |

### 我要 HO 多 / 少

| 想做 | 改 |
|:---|:---|
| HO 多 | Dashboard `/logs` A3 panel → offset 降, TTT 降 |
| HO 少 | offset 升, TTT 升 |
| 完全關 A3 | A3 panel toggle disable (RIC 自由 HO, 不被 sim rollback) |

### 我要 Delay 高 / 低

| 想做 | 改 |
|:---|:---|
| 高 delay | rate_mbps 拉高超過 MCS 能 drain 的量 → buffer 累積 |
| 低 delay | rate_mbps 降低, 或 SINR 拉高 (MCS 升 → drain 跟上) |

### 我要 PRB 滿 / 空

| 想做 | 改 |
|:---|:---|
| PRB 滿 (~100%) | rate_mbps 拉到 demand > capacity, 自然分滿 |
| PRB 空 | traffic profile 改 idle (沒 buffer scheduler 不分) |

---

## 5. 前端可調總表

| 設定 | 前端 ✓ | 頁面 | runtime? |
|:---|:---|:---|:---|
| UE trajectory | ✓ | /draw, /editor | 即時 |
| UE traffic rate | ✓ | /draw, /editor | 5s 內生效 |
| UE traffic pattern (cbr/idle) | ✓ | /draw, /editor | 5s 內生效 |
| UE 位置 (拖移) | ✓ | /editor | 即時 |
| A3 enable / offset / hys / ttt | ✓ | /logs §H+ | runtime |
| Cell enable / disable | ✓ | /scene_editor (E2 Control) | 即時 |
| gNB 加減 / 朝向 | ✓ | /scene_editor | 自動 initScene |
| Trajectory mode (loop/once/stay) | ❌ | hardcoded 'loop' | 要動 code |
| SDU size / bearer_id | ❌ | hardcoded 1500 / 1 | 要動 code |
| RU TX power / antenna gain | ❌ | env var | restart RU |
| RU scene calibration loss | ❌ | env var | restart RU |
| RU noise floor | ❌ | env var | restart RU |
| DU SIM_TICK_MS | ❌ | env var | restart DU |
| UE_TRAJECTORY_PERIOD_MS | ❌ | env var | restart UE |
| UE_LIST_POLL_PERIOD_SEC | ❌ | env var | restart UE |
| Sionna scene building | ❌ | scene_config.json | restart Physics |
| PRB 總量 (273) | ❌ | hardcoded | 要動 code |
| PM window size (5 ticks) | ❌ | hardcoded | 要動 code |

---

## 6. 對應到 5/11 採樣報告觀察

| 觀察 | 來源設定 |
|:---|:---|
| c1 north SINR 普遍 -10 dB | scene_config 沒加 north building, 但 ray-trace 仍有路徑損耗; 或 antenna pattern 主瓣窄 |
| c0 throughput 接近 demand 30M×4 | rate_mbps × 4 UE = 120M, MCS 高 (SINR +10) drain 跟上 |
| c1 delay 飆到 90s | rate_mbps=10 但 SINR -10 → MCS 低 → drain ~ 2 Mbps → buffer 累積 |
| PRB 全 ~100% | PF scheduler 對 active UE 分滿, demand 低也分 |
| UE 分布動態 | trajectory loop (demo_0509, demo_0516) 跨 cell + A3 HO |

---

## 7. 待完善 (前端化建議)

按優先序:

1. **RU 物理常數面板** — TX power / scene loss / noise floor 拉到 Dashboard, 像 A3 panel 那樣 runtime control。改 ray-trace 校正不用 restart。
2. **Trajectory mode dropdown** — UI 加 loop/once/stay 選項 (現在 hardcode 'loop')
3. **Traffic pattern bursty** — traffic_gen.py 補 burst 模式 (週期性流量峰)
4. **PRB total 可調** — 支援 100/200/400 MHz, 影響 capacity baseline
5. **Sionna building obstacle 編輯器** — `/scene_editor` 加 building 增刪 (AC2)
