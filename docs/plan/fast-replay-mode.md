# DT Fast-Forward Mode for xApp Validation

## Context

User 在做 RAN Digital Twin 給 xApp 驗證用。情境:

- 外部模擬系統提供「某一段時間(例:10:00-11:00)」的 UE 軌跡 + traffic profile 作為輸入
- xApp 要在這個 DT 上「先跑過、確認決策合理」,再部署到實體 RAN
- **問題**:這段 1 hr 的 scenario 在 DT 端按正常速度跑就要 1 hr,xApp validation 不能等這麼久
- **目標**:把 1 hr scenario 壓縮成 **2 分鐘(30x)**跑完,跑出來的 history 再用 Playback 攤回正常速度檢視細節
- **關鍵約束**:
  1. KPM 不能偏移太多 — handover / PRB control 的決策必須跟「正常速度跑」結果一致
  2. **不動原有邏輯** — live mode 行為要 0 改動,fast mode 是純粹外掛
- **輸入採用**:**Pre-recorded scenario JSON 劇本**(不採即時 stream)
  - 即時 stream 會強制 Sionna 即時算 → 卡在 ~10x → 達不到 30x
  - 劇本能離線 precompute Sionna,且利於 xApp validation 可重現性

xApp 端的可行性(能否跟得上 30x E2 訊息頻率)**本次先擱置**,只討論 DT 端能不能撐住 30x。

支援的 xApp intent 範疇(`/home/mitlab/XAPP_DT/intents-interface.md`):IM (style 2/6 PRB quota)、CCO (style 3/1 handover)、ES (兩段組合)。這些 intent 都已經有對應的 DT 內 control_action ingest 鏈路。

## 既有 API 對照(audit 過)

| 需求                      | 現有 API                                    | 評估                                       |
|---------------------------|---------------------------------------------|--------------------------------------------|
| Traffic time-series 注入  | `POST /DU/RLC/RlcDataController/inject_sdu_batch` (`RANsim-DU/main/apps/rlc/actors/rlc_data_actor.py:51`) | ✅ **直接拿來用**,timestamp 對齊已支援 |
| UE 位置 time-series 注入 | `UEController/batch_move` (Omniverse) — 一次一筆 snapshot | ⚠️ 要外掛 driver 每 tick 呼叫,或新增 batch ingest |
| UE waypoint trajectory   | `UEController/trajectory`, `Trajectory/set` | ❌ 不適用(waypoints + speed,不是 time-series) |
| Sionna offline precompute | 無                                          | ❌ 全新 service                            |
| Channel cache lookup      | 無                                          | ❌ 全新 module(嵌入 RU)                  |
| Scenario CRUD             | 無                                          | ❌ 全新 endpoint                           |

## 既有元件可以重用

DT 端 Playback 基礎建設**已存在**,直接接得上:

- `SimulationSession` (`Omnivers_platform/.../models/simulation_session.py`) — session 標記
- `SignalHistory` / `PositionHistory` — per-tick UE 狀態落地
- `HandoverHistory` / `ControlAction` — 已串上 CU 推送
- `playback_actor.py:frames_dict` — 已支援 rsrp_map、throughput、handover、control_action、cell_state 攤回
- `useSimPage.ts` — 已會把 KPM neighbor_cells 轉成 rsrp_map dict

也就是說「**Fast mode 跑出的 session,Playback 能無痛還原**」這條已通,只差「跑 30x」這件事本身。

---

## 推薦方案 — 兩階段交付

### Phase A:`SIM_TICK_MS` runtime knob(解鎖 2x ~ 10x 壓縮)

**改動最小,立即可用**。把目前寫死 500ms 的 DU tick interval 變成 runtime 可調。

| 改動位置                                                                                  | 改什麼                                                                            |
|-------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| `RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py`                        | `_sim_tick_ms` 改成 instance attr (受 `_lock` 保護),`_loop()` 每輪重新讀          |
| `RANsim-DU/main/apps/tick/actors/tick_controller_actor.py`                                | 新增 `TickController.set_speed` actor,body `{tick_ms: int}` (clamp 10~500)        |
| `RANsim-DU/main/apps/tick/api/urls.py`                                                    | 註冊 `TickController/set_speed`                                                   |
| `Physics_sim/Dashboard/components/SimControls.tsx`(新增或擴充)                          | Dropdown:1x (500ms) / 2x (250ms) / 4x (125ms) / 10x (50ms),選擇即 POST 給 DU     |
| `Physics_sim/Dashboard/components/PlaybackControls.tsx`                                   | Dropdown 1x/2x/4x/10x 控制 `setInterval` frame advance                            |

**KPM 影響**:取樣率變高(2 → 4 → 20 個/sim-sec),**精度反而上升**,不會偏。
**真實上限**:Sionna RT latency。預設場景估計 4x 穩、10x 邊緣。

### Phase B:30x 壓縮 — Scenario Driver 住在 RANsim-UE

**設計原則**:整個 fast mode 是「外掛層」,跟 live mode 程式路徑完全分離。
**Scenario driver 放在 RANsim-UE**,因為 UE 位置 + traffic 本來就是 UE 端的職責。

```
RANsim-UE container:
  ┌──────────────────────────────────────────┐
  │ apps/scenario/(新 app)                  │
  │   ├─ services/scenario_driver.py         │ ← thread,每 tick 推資料
  │   ├─ services/scenario_loader.py         │
  │   └─ actors/scenario_controller_actor.py │ ← start/stop endpoint
  │                                          │
  │ apps/ue_lifecycle/services/traffic_gen.py│ ← 既存,driver 呼叫
  │ apps/ue_lifecycle/actors/trajectory_actor│ ← 既存,driver 呼叫
  └──────────┬───────────────────────────────┘
             │ HTTP per scenario_tick(local docker ~1ms RTT)
             ▼
   ┌─────────────────────────────────────────┐
   │ DU /RLC/RlcDataController/inject_sdu_batch│ ← 既存,0 改動
   │ RU /UE/UEPosition/batch_update(視情況加) │
   └──────────┬──────────────────────────────┘
              ▼
   ╔══════════════════════════════════════════╗
   ║  原本的 RAN tick chain                    ║  ← 0 字節改動
   ║  DU tick → MAC → RU                       ║
   ║  → RU 內 branch:Sionna or cache           ║
   ║  → SINR → F1AP → CU → xApp                ║
   ╚══════════════════════════════════════════╝
```

**改動點清單**(僅此 6 處):

| 元件                                       | 改動類型                                          | 影響面          |
|--------------------------------------------|--------------------------------------------------|------------------|
| `RANsim-UE/main/apps/scenario/`(新 app)   | 全新 app,driver + loader + controller          | 0 動原有          |
| `RANsim-UE/apps/ue_lifecycle/`(既存)      | **0 改動**,被 scenario_driver 呼叫              | 0 動原有          |
| `RANsim-DU` `tick_controller_actor.py`     | 新 endpoint `set_speed`(Phase A 加)             | 不改 `start/stop/read` |
| `RANsim-DU` `tick_runner.py`               | `_loop()` 多一行:每輪讀最新 `_sim_tick_ms`      | 純加,default 走原路徑 |
| `RANsim-DU` RLC `inject_sdu_batch`         | **0 改動**(scenario driver 用既有 endpoint)     | 完全不動          |
| `RANsim-RU` `dl_tti_pipeline.py`           | `if RU_CHANNEL_MODE == "cached":` 一段 branch  | default `live`,branch 不進入 |
| `Omnivers_platform` 新增 `Scenario` model + actor | 新 model + 新 endpoints                          | 0 動原有          |
| Dashboard 新增 `/scenarios` page            | 新 page + 新 components                          | 0 動原有          |

**核心 RAN 流程(MAC scheduler、RLC、HARQ、F1AP、E2AP、handover、CU 邏輯)0 改動**。
**RANsim-UE 既有的 traffic_gen / trajectory_actor 也 0 改動**,scenario_driver 只是新的「上層編排器」呼叫它們。

下面是 7 個子工作:

#### B.1 Scenario JSON schema(新)

User 用 JSON 手寫或從外部模擬系統匯出,POST 到 DT。

`Physics_sim/Dashboard/schemas/scenario.schema.json`(新檔):

```json
{
  "scenario_id": "rush_hour_10_11",
  "scene_id": "brownstone_3gnb",
  "duration_sec": 3600,
  "tick_ms": 500,
  "ues": [
    {
      "name": "ue_001",
      "positions": [
        [0,    100.0, 1.5,   200.0],
        [0.5,  100.5, 1.5,   200.0]
      ]
    }
  ],
  "traffic": [
    {
      "ue_name": "ue_001",
      "profile": [
        [0,    5000, 1000],
        [10,   8000, 500]
      ]
    }
  ]
}
```

對應 ingest:
- 新 model `Scenario` (`Omnivers_platform/.../models/scenario.py`):
  - `scenario_id` (PK)
  - `scene_id` (FK 到既有 Scene config)
  - `raw_json` (JSONField,存整份)
  - `duration_sec`, `tick_ms`, `ue_count`(冗餘欄方便 list)
  - `precompute_status` (`pending | running | ready | failed`)
- 新 endpoint:`POST /api/v0.1/RAN/Scenario/upload` (body 直接是 scenario JSON)
- 新 endpoint:`GET /api/v0.1/RAN/Scenario/list`
- 新 endpoint:`POST /api/v0.1/RAN/Scenario/precompute` (body `{scenario_id}`)

#### B.2 Sionna offline precompute job

`Physics_sim/precompute/run_precompute.py`(新):

```
讀 scenario raw_json
讀 scene config (gNB positions, antenna, frequency, BW)
total_ticks = duration_sec * 1000 / tick_ms

for tick_idx in 0..total_ticks:
    for ue in ues:
        ue_pos = interpolate(ue.positions, tick_idx * tick_ms / 1000)
        path_results = sionna.compute_paths(scene, gnbs, ue_pos)
        for cell_id, path in path_results.items():
            cache[tick_idx][ue.name][cell_id] = {
                "path_gain_db": path.gain_db,
                "delay_spread_ns": ...,
                "doppler_hz": ...,
                "azimuth_aoa": ...,
            }

write parquet to /data/channel_cache/{scenario_id}.parquet
update Scenario.precompute_status = "ready"
```

- 跑在獨立 worker process (docker compose 加一個 `precompute_worker` service,或丟到 Sionna container 直接執行)
- 平行化:`multiprocessing.Pool` 按 tick_idx 分片;Sionna 本身 GPU 化部分由 TF 控
- 進度:每 100 ticks 更新一次 DB 的 `precompute_progress` (新欄)
- 失敗時把 status 設 `failed` + `error_msg`
- 預估成本:1 hr scenario × 500ms tick × 10 UE × 3 cell = 21.6 萬次 Sionna call。Sionna 200ms/call → 約 12 hr;若 GPU + 平行 8 路 → ~1.5 hr。**離線跑可接受**。

#### B.3 Cached channel lookup in RU

`RANsim-RU/main/apps/fapi_south/services/optional/dl_tti_pipeline.py` 改造:

```python
RU_CHANNEL_MODE = os.getenv("RU_CHANNEL_MODE", "live")    # live | cached
RU_SCENARIO_ID = os.getenv("RU_SCENARIO_ID", "")

_channel_cache = None
def _load_cache(scenario_id):
    global _channel_cache
    _channel_cache = pd.read_parquet(f"/data/channel_cache/{scenario_id}.parquet")
    _channel_cache.set_index(['tick_idx','ue_name','cell_id'], inplace=True)

def compute_channel(ue_name, cell_id, sim_tick):
    if RU_CHANNEL_MODE == "cached":
        row = _channel_cache.loc[(sim_tick, ue_name, cell_id)]
        return ChannelResult(path_gain_db=row.path_gain_db, ...)
    else:
        return physics_http.compute_paths(...)    # 走原本的 live Sionna 路徑
```

關鍵:**RSRP / SINR 計算下游不動**,只把 path_gain 來源換掉。
這樣 `RU_NOISE_FLOOR_DBM` / `RU_TX_POWER_DBM` / `RU_SCENE_CALIBRATION_LOSS_DB` 等校正參數仍然生效,
cached 跟 live 出來的 RSRP/SINR 應該幾乎一致(差異只在浮點精度)。

#### B.4 Scenario Driver(住在 RANsim-UE 的新 app)

`RANsim-UE/main/apps/scenario/services/scenario_driver.py`(全新檔):

```python
class ScenarioDriver:
    """獨立 thread,每個 scenario_tick wake 一次,
    透過既有 endpoints 推位置 + traffic 給 DU/RU。
    與既有 traffic_gen / trajectory_actor 完全平行,不改它們。"""

    def __init__(self, scenario, target_tick_ms, du_url, ru_url):
        self.scenario = scenario
        self.target_tick_ms = target_tick_ms     # 17ms for 30x
        self.du_url = du_url                     # http://du:8000
        self.ru_url = ru_url                     # http://ru:8000
        self._stop = threading.Event()
        self._session = requests.Session()       # 連線復用

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        sim_tick = 0
        total_ticks = self.scenario["duration_sec"] * 1000 // self.scenario["tick_ms"]
        while not self._stop.is_set() and sim_tick < total_ticks:
            t0 = time.perf_counter()
            self._push_one_tick(sim_tick)
            elapsed = (time.perf_counter() - t0) * 1000
            sleep_ms = max(0, self.target_tick_ms - elapsed)
            self._stop.wait(sleep_ms / 1000.0)
            sim_tick += 1

    def _push_one_tick(self, tick_idx):
        # 1. 收集所有 UE 位置,batch 推 RU(一次 HTTP)
        positions = []
        for ue in self.scenario["ues"]:
            pos = interpolate_pos(ue["positions"], tick_idx)
            positions.append({"name": ue["name"], "x": pos[0], "y": pos[1], "z": pos[2]})
        self._session.post(
            f"{self.ru_url}/api/v0.1/RU/UE/UEPosition/batch_update",
            json={"tick_idx": tick_idx, "ues": positions},
            timeout=0.5,
        )

        # 2. 收集所有 UE traffic,逐個呼叫既有 inject_sdu_batch
        for traffic in self.scenario["traffic"]:
            sdu_items = self._traffic_to_sdus(traffic, tick_idx)
            self._session.post(
                f"{self.du_url}/api/v0.1/DU/RLC/RlcDataController/inject_sdu_batch",
                json={
                    "ue_id": traffic["ue_name"],
                    "bearer_type": "drb",
                    "bearer_id": 1,
                    "window_ms": self.target_tick_ms,
                    "items": sdu_items,
                },
                timeout=0.5,
            )
```

關鍵設計:
- **走 HTTP 不走 in-process**:RANsim-UE 跟 DU/RU 本來就分開 container,本來就 HTTP 通。docker local network 一輪 ~1ms,17ms tick 綽綽有餘
- **連線復用** (`requests.Session()`):避免每次重新 TCP handshake,實測能把 HTTP 開銷壓到 < 0.5ms
- **既有 endpoint 0 改動**:driver 純粹是 client,只是頻率比平時(Dashboard 推)高很多
- **traffic 沿用既有 traffic_gen 邏輯**:`_traffic_to_sdus()` 可以直接 import `apps/ue_lifecycle/services/traffic_gen.py` 的 packetize function

啟動 endpoint:`POST /api/v0.1/UE/Scenario/ScenarioController/start`,
body `{scenario_id, target_tick_ms}`。
停止:`POST /api/v0.1/UE/Scenario/ScenarioController/stop`。

**RU 端需要新增** `POST /api/v0.1/RU/UE/UEPosition/batch_update`(一次更新多個 UE 位置 + 帶 tick_idx),
這是新 endpoint 但不動既有 RU 邏輯。Cache lookup 就用這個 tick_idx 當 key。

#### B.5 SimSessionController.create 接受 scenario

`Omnivers_platform/.../actors/sim_session_actor.py`:

`create` 加新欄位 `mode` / `scenario_id` / `time_compression_ratio`,寫入 `metadata_json`:

```python
metadata_json = {
    "created_by": "ran_sim",
    "mode": data.get("mode", "live"),            # live | fast_cached
    "scenario_id": data.get("scenario_id"),
    "time_compression_ratio": data.get("time_compression_ratio", 1.0),
}
```

Playback 端讀到 `mode == "fast_cached"` 時:
- `playback_actor.frames_dict` 計算 frame timestamp 用 `tick_idx × scenario.tick_ms`(sim-time)而非 wall-clock
- Dashboard `PlaybackControls` 把 timeline label 改成 sim-time 顯示

#### B.6 Dashboard Scenario 管理 UI

新頁 `/scenarios`:
- 上傳 JSON 檔
- 列表顯示 scenario_id / scene_id / duration / precompute_status
- 「Precompute」按鈕(disabled 當 status=running)
- 「Start Fast Run」按鈕(disabled 當 status≠ready):
  1. 建立 SimulationSession(mode=fast_cached, ratio=30)
  2. POST RU `/setup/set_mode {mode: cached, scenario_id}`
  3. POST UE `/Scenario/ScenarioController/start {scenario_id, target_tick_ms: 17}`
  4. POST DU `/Tick/TickController/set_speed {tick_ms: 17}`
  5. POST DU `/Tick/TickController/start`

#### B.7 xApp 對接(本次擱置,但留 hook)

xApp 走 E2AP SCTP 跟 CU 直連,DT 加速時 xApp 會收到 30x 頻率的 KPM RIC-INDICATION。
這次先**不**改 xApp,但留下兩個 hook 讓未來能擴充:

- DU `set_speed` 時順便廣播 `compression_ratio` 給 CU,CU 之後可在 E2 訊息 metadata 加註(讓 xApp 知道收到的是壓縮時間軸)
- KPM `measurement_window_ms` 在 fast mode 仍以 **sim-time** 為單位回報(例如 1000ms = 1 sim-sec),xApp 看到的「window」跟 live 時一致

#### B.8 變動檔案清單

| 系統           | 新增                                          | 修改                                                          |
|----------------|-----------------------------------------------|---------------------------------------------------------------|
| Omniverse 後端 | `models/scenario.py`, `actors/scenario_actor.py`, `migrations/00XX_scenario.py` | `actors/sim_session_actor.py` (新增 optional metadata 欄),`api/urls.py` |
| **RANsim-UE**  | `apps/scenario/` 整個新 app(driver + loader + controller) | **無**(既有 traffic_gen / trajectory_actor 0 改動)            |
| RANsim-DU      | —                                             | `tick_runner.py` (Phase A:讀最新 tick_ms), `tick_controller_actor.py` (Phase A:set_speed endpoint),`api/urls.py` |
| RANsim-RU      | `services/optional/channel_cache_loader.py`(parquet 載入) | `dl_tti_pipeline.py`(`RU_CHANNEL_MODE` branch),新 endpoint `UEPosition/batch_update` |
| Physics_sim    | `precompute/run_precompute.py`, `precompute/scenario_loader.py` | docker-compose 加 `precompute_worker` service                |
| Dashboard      | `app/scenarios/page.tsx`, `components/ScenarioUpload.tsx`, `components/FastRunButton.tsx` | `app/playback/page.tsx` (sim-time label), `hooks/feature/usePlaybackPage.ts` |

**完全不動的元件**:CU 全部、MAC scheduler、RLC、HARQ、F1AP、E2AP、handover_executor、a3_handover_calc、PM accumulator、既有 SimulationSession 流程、既有 Scene config 流程。

#### B.9 風險與緩解

| 風險                                                                  | 緩解                                                                |
|-----------------------------------------------------------------------|---------------------------------------------------------------------|
| Sionna precompute 一次跑數小時                                       | 平行化 + GPU,scenario 設計時 tick_ms 可拉大(1s)減少呼叫次數      |
| Parquet 檔案大(1hr × 500ms × 100 UE × 9 cell × 6 欄位 ~ 數百 MB)    | 用 column compression(parquet 內建 snappy);記憶體只 mmap 不全載 |
| Cached lookup 在 RU per-TTI 太慢                                     | 預載入時 reindex 成 dict-of-dict,O(1) 查表;benchmark 應 < 0.1ms   |
| 30x tick 下 Python overhead 變成瓶頸                                 | 17ms tick 有 ~12ms headroom,基本不會卡;若超出再考慮 batch insert |
| Postgres 寫入 SignalHistory 跟不上(30x × N UE × per-tick)            | 600 inserts/sec,單條 insert 還來得及;真不行改 bulk_create        |
| Cell on/off 影響干擾,cache 是固定的                                  | precompute 對每個 cell 各自存 path_gain,runtime 干擾合成讀當下 cell_state |
| 時序計時器混用 wall-clock 跟 sim-time                                | Phase B 開工前 grep `datetime.now\|time.time\(\)` 把 critical path 全換掉 |

---

## 關鍵設計決策

### 為什麼 Phase A 走「壓縮 tick interval」而不是「拉長 sim-time per tick」

前者 KPM 取樣率變高,精度上升;後者取樣變稀,精度下降。對 xApp 驗證來說精度是 hard requirement。

### 為什麼 30x(而非 60x)是工程甜蜜點

| Compression | tick_ms 上限 | Python 開銷       | Sionna per-call 預算 |
|-------------|--------------|-------------------|----------------------|
| 4x          | 125ms        | 🟢 很寬          | 125ms ✅            |
| 10x         | 50ms         | 🟢 寬            | 50ms ⚠️             |
| 30x         | 17ms         | 🟢 ~12ms headroom | 17ms — 走 cache     |
| 60x         | 8ms          | 🔴 緊             | 8ms — 走 cache     |

30x 不需做 C extension / asyncio rewrites,工程風險低。60x 是未來「升級到 8ms tick」的 free upgrade,只是調 number。

### 為什麼把 UE position 切「外部驅動」

Scenario file 已經把 UE 位置寫死在每個 tick,DT runtime 不需要再用 waypoint + speed_mps 重算 — 直接每 tick 讀 scenario 的位置欄。這也跟 cached channel 完全對齊(channel cache 的 key 就是 tick_idx,前提是 UE 在 tick_idx 的位置確定)。

### 為什麼 scenario_driver 住在 RANsim-UE 而非 DU

RANsim-UE 本來就是 UE-side 模擬(管位置 + traffic generation),scenario driver 是它的進階版。DU 應該保持「乾淨的 gNB 模擬」,不該知道 scenario 怎麼定義 UE 行為。layer 分工才乾淨。

---

## 不選的方案 & 為什麼

- **單純拉長 sim-time per tick**:KPM 取樣稀釋 → 違反「KPM 不能偏移」。
- **即時 stream input(外部系統邊跑邊推)**:強制 Sionna 即時算 → 卡在 ~10x。
- **Sionna 平行化(多 worker)**:複雜度爆,而且 RT 本身有共享 scene state 限制。
- **完全跳過 Sionna 用 free-space path loss**:RSRP 失真嚴重,IM/ES 邏輯依賴 PRB 占用 + delay,跟 RSRP 模型強相關。
- **scenario_driver 放 DU**:違反 layer 分工(DU 是 gNB-side,不該管 UE 行為)。
- **xApp side speedup**:本次先擱置。

---

## Verification(分階段測)

### Phase A 驗證
1. `curl -XPOST .../TickController/set_speed -d '{"tick_ms":125}'` → 確認 `/read` 回報生效
2. 跑 1 分鐘 sim,確認 tick_count ≈ 480 (4x baseline 120)
3. 對比 1x 跑 4 分鐘 vs 4x 跑 1 分鐘 的 SignalHistory:
   - 數據筆數應該 4x 跑出來是 1x 的 ~4 倍
   - 同位置 RSRP/SINR 應該一致(±誤差)
4. Handover 觸發點 wall-time 應該 4x 提前,sim-time 應該一致

### Phase B 驗證
1. 上傳 60min scenario file → 跑 precompute → 確認 cache 落地大小合理
2. RU 切 cached mode,跑全段 → 應該 ≤ 2 min wall-clock 跑完
3. 開 Playback,選 fast_cached session → 應該能像 live session 一樣攤平看
4. 拿同一 scenario 用 1x live 跑 vs 30x cached 跑,對比 KPM 主要指標:
   - `RRU.PrbTotDl`:差距應 < 5%
   - `DRB.UEThpDl`:差距應 < 10%
   - `DRB.RlcSduDelayDl`:差距應 < 20ms 或 < 10%
   - Handover 數量:應一致(±1)
   - Control action 數量:應一致(±1)

如果 (4) 差距超標,表示 cache lookup 時序對齊有問題,要回頭調 RU 的 SINR 計算 pipeline。

---

## Phasing 建議

| 階段 | 工作量    | 解鎖能力                            | 是否需要 scenario file |
|------|-----------|-------------------------------------|------------------------|
| A    | ~1 天     | 2x ~ 10x 壓縮(live Sionna)         | 否                     |
| B    | ~7 天     | 30x 壓縮(cached Sionna)            | 是                     |
| B+(未來)| +3 天 | 60x 壓縮(只是 tick_ms 從 17 → 8)  | 是                     |

建議先做 A 拿到立即可用的 4x,實測 Sionna 在你場景的真實上限是多少,再決定 B 要不要做。
