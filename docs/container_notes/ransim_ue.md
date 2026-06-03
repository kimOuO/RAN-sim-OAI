# RANsim-UE 容器筆記

> 路徑:`/home/mitlab/XAPP_DT/RANsim-UE/`
> 容器名:`ransim-ue`,image `ransim-ue:platform`
> 一句話:**in-memory UE farm + sim 啟停總控**。沒有 DB,所有狀態活在 Django 進程 thread 裡。

---

## 1. Port

| 對外 (host) | 對內 (container) | 說明 |
|---|---|---|
| `8105` | `8000` | Django HTTP (`runserver 0.0.0.0:8000 --noreload`) |

(對照:CU=8101 / DU=8102 / RU=8103 / Physics=8104 / UE=8105)

---

## 2. 它會做的事

### 2.1 啟動就跑的背景 thread(`UeLifecycleManager` singleton, in `apps/ue_lifecycle/services/manager.py`)

`AppConfig.ready()` 起兩條 daemon thread:

| Thread | 週期 | 動作 |
|---|---|---|
| `ue-lifecycle-mgr` (`_poll_loop`) | `UE_LIST_POLL_PERIOD_SEC`=5s | 打 CU `/Session/SessionController/list`,diff 出 `rrc_state==CONNECTED` 的 UE。新加 → `_spawn_thread`、消失 → `stop()`、沿用 → `update_snapshot`(同時把 `traffic_profile` 灌進 `UeTrafficGen`) |
| `ue-trajectory-tick` (`_trajectory_loop`) | `UE_TRAJECTORY_PERIOD_MS`=100ms | 對所有 `RUNNING` UE:① 算位置(`TrajectoryStore` waypoints → `interp_position` 線性內插;沒設就用當前 `ue.position`)② 收集後 batch POST RU `update_ues_batch` ③ per-UE POST Kit `move_ue` ④ 呼叫 `traffic_gen.tick()` 注 SDU 到 DU ⑤ 每 5 tick (~500ms) 從 DU 拉 per-UE signal bundle 位置 POST Omniverse `SignalIngestor`(寫 signal_history,Playback / KpmSummaryLine / `/scenarios` chart 都靠這份) |

每個 active UE 一個 `UeThread`(三態 `STANDBY` / `RUNNING` / `STOPPED`),主迴圈只做 30s 心跳 log;真正的 per-tick 動作集中在 `_trajectory_loop` 統一跑。

### 2.2 兩個 Django app

- **`ue_lifecycle`** — UE 模擬本體(per-UE thread、trajectory、traffic_gen、signal ingest)
- **`scenario`** — sim 啟停總機 + 舊版劇本驅動(`SimController` 是 Stage 2 統一入口、`ScenarioController` 是 Phase B 留下來的單獨入口)

### 2.3 `UeTrafficGen` (`apps/ue_lifecycle/services/traffic_gen.py`)

Pattern 支援:`idle` / `cbr` / `piecewise`(`bursty` 留給未來)
- `bytes_to_inject = rate_mbps × 1e6 × elapsed_sim_ms / 1000 / 8`
- **`sim_speed_x` 還原**(2026-05-23 bugfix):wall→sim-time 換算對齊 OAI KPM,否則 PRB%/avg throughput 偏低
- `INJECT_BATCH_MODE` env(`on/1/yes`)切 batch / single SDU 路徑
- inject 失敗回 `no_entity`(DU restart 後 RLC entity 不見)時,10s cooldown 內自動呼 CU `update_traffic_profile` 走 F1AP 重建

### 2.4 對外依賴(全 HTTP client)

| 對象 | client 模組 | 主要 call |
|---|---|---|
| CU (`SIM_CU_URL`, default `http://cu:8000`) | `cu_client` | `list_sessions` / `release_stale` / `rrc_attach` / `force_serving_cell` / `update_traffic_profile` |
| DU (`SIM_DU_URL`) | `du_client` | `tick_start/stop` / `set_speed` / `inject_sdu(_batch)` / `fetch_ue_signals` |
| RU (`SIM_RU_URL`) | `ru_client` | `update_ues_batch`(每 100ms 批次位置) |
| Omniverse backend (`OMNIVERSE_URL`, default `http://host.docker.internal:8001`) | `omniverse_client` | `SignalIngestor.create`、`SimSessionController.create/end`、`GNBReader.read`、`UEReader.read` |
| Kit (`OMNIVERSE_KIT_URL`, default `http://localhost:8080`) | `kit_client` | `move_ue`(USD viewport 同步) |

---

## 3. API Table

> Base prefix:`http://<host>:8105/api/v0.1/UE/`
> 所有 endpoint 都 `@csrf_exempt`、回 `{success, message, data?, errors?}` JSON。

### 3.1 Lifecycle — `/api/v0.1/UE/Lifecycle/...`
(`apps/ue_lifecycle/actors/lifecycle_actor.py`)

| Method | Path | Body | 用途 |
|---|---|---|---|
| POST | `Lifecycle/sync` | `{event, ue_id?}` | 通用 push 同步入口。`event ∈ {attach, detach, profile_changed, sim_start, sim_stop}`。`attach/profile_changed` 立即觸發一次 CU diff;`detach` 砍 thread;`sim_start/stop` 走 `_handle_sim_lifecycle`(所有 thread 切 RUNNING/STANDBY) |
| POST | `Lifecycle/start` | `{}` | 等同 `sync(event=sim_start)` — STANDBY → RUNNING |
| POST | `Lifecycle/stop` | `{}` | 等同 `sync(event=sim_stop)` — RUNNING → STANDBY |

### 3.2 Status — `/api/v0.1/UE/Status/...`
| Method | Path | Body | 回傳 `data` |
|---|---|---|---|
| GET/POST | `Status/read` | `{}` | `{sim_running, thread_count, threads:[{ue_id, state, serving_cell, rrc_state, traffic_profile, injected_sdu_count, last_synced_at_ms, position}]}` |

### 3.3 Trajectory — `/api/v0.1/UE/Trajectory/...`
(`apps/ue_lifecycle/actors/trajectory_actor.py`,Dashboard 設 waypoints 用)

| Method | Path | Body | 用途 |
|---|---|---|---|
| POST | `Trajectory/set` | `{ue_id, waypoints:[{x,y,z,t_ms},...], mode?, start_at_ms?}` | 把軌跡寫進 `TrajectoryStore`(in-memory)。`mode ∈ {loop, once, stay}` 預設 `loop`;`t_ms` 必須非遞減 |
| POST | `Trajectory/clear` | `{ue_id}` | 清掉該 UE 的軌跡 |
| GET/POST | `Trajectory/list` | `{}` | 列所有軌跡的 `{waypoints_count, mode, start_at_ms, duration_ms}` |

### 3.4 Sim(統一入口)— `/api/v0.1/UE/Sim/...`
(`apps/scenario/actors/sim_controller_actor.py` → `apps/scenario/services/sim_orchestrator.py`)

| Method | Path | Body | 用途 |
|---|---|---|---|
| POST | `Sim/SimController/start` | `{source, scenario_id?, speed_x?, sim_dt_ms?}` | **Stage 2 統一 sim start**。`source ∈ {live_db, scenario}`。`live_db` 走 Omniverse 三表 → `SceneApplyService.apply` → `UeAttachService.attach_all` → push trajectory → DU `tick_start` → `mgr.start()` + `push_sync(sim_start)`;`scenario` 委派 `scenario_driver.start_scenario`。順帶 `_broadcast_speed`(DU sim_tick_ms + CU `KpmSpeed/set`)+ Omniverse `SimSession.create`(拿 session_uuid 給 Playback group) |
| POST | `Sim/SimController/stop` | `{}` | 停 scenario driver + `push_sync(sim_stop)` + `mgr.stop()` + DU `tick_stop` + Omniverse `SimSession.end` |

錯誤碼:`400` source/payload 錯;`409` 已有 sim 在跑(`RuntimeError`);`500` 其他 exception。

### 3.5 Scenario(舊版獨立入口)— `/api/v0.1/UE/Scenario/...`
(`apps/scenario/actors/scenario_controller_actor.py`,Stage 3 會被 `SimController` 完全吃掉)

| Method | Path | Body | 用途 |
|---|---|---|---|
| POST | `Scenario/ScenarioController/start` | `{scenario_id, target_wall_tick_ms?}` | 直接走 `scenario_driver.start_scenario`(自帶 tick loop) |
| POST | `Scenario/ScenarioController/stop` | `{}` | 停 driver |
| POST | `Scenario/ScenarioController/status` | `{}` | 回 driver `state` |

---

## 4. 設定 / 環境變數
(`main/settings/base.py`)

| Var | Default | 用途 |
|---|---|---|
| `SIM_CU_URL` | `http://cu:8000` | CU base URL |
| `SIM_DU_URL` | `http://du:8000` | DU base URL |
| `SIM_RU_URL` | `http://ru:8000` | RU base URL |
| `SIM_PHYSICS_URL` | `http://physics:8000` | Physics base URL |
| `OMNIVERSE_KIT_URL` | `http://localhost:8080` | Kit viewport |
| `OMNIVERSE_URL` | `http://host.docker.internal:8001` | Omniverse Django backend(scene + signal/session 寫回) |
| `UE_TRAJECTORY_PERIOD_MS` | `100` | trajectory tick 週期 |
| `UE_MEASUREMENT_PERIOD_MS` | `80` | (保留,目前未用) |
| `UE_LIST_POLL_PERIOD_SEC` | `5` | CU UE list diff 週期 |
| `INJECT_BATCH_MODE` | `off` | `on/1/yes` 走 batch SDU 路徑(per-packet ts,對齊 OAI) |
| `DJANGO_DEBUG` / `DJANGO_SECRET_KEY` / `DJANGO_ALLOWED_HOSTS` | — | 標 Django |

---

## 5. 不會做的事(避免誤解)

- **沒有 DB**(`:memory:` SQLite 只是為了 Django 啟動門檻);UE list 在 CU、scene 在 Omniverse、history 在 Omniverse,UE 容器本身重啟全部歸零。
- **不算 PHY / 不算 channel**:訊號是 RU(透過 Physics/Sionna)算完,UE 容器只是把位置餵 RU,然後從 DU 拉算好的 RSRP/SINR 寫回 history。
- **不負責 RRC 訊息語義**:`cu_client.rrc_attach` 只是包 base64 JSON 打 CU 的 F1AP 入口,真正狀態機在 CU。
