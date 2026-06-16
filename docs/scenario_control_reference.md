# RANsim 模擬控制總覽 — 劇本 / 場景 / 流量 / env 分工

> 整理日期 2026-06-09。回答:劇本能控什麼、場景去哪收、流量給誰、env 控什麼、哪些兩邊都管不到。
> 來源:`RANsim-UE/.../scenario/services/scenario_loader.py`(ScenarioSpec)、`scenario_driver.py`、`docker-compose.yml`、`Physics_sim/.../sionna_operations.py`、`RANsim-DU/.../cell_state.py`、`tick_runner.py`。

---

## 1. 劇本(Scenario JSON)能控制的欄位

劇本存在 **Omniverse DB**,`raw_json` 被 `scenario_loader.ScenarioSpec` 解析。可控欄位:

### 1.1 頂層
| 欄位 | 型別 / 預設 | 控制什麼 |
|---|---|---|
| `scenario_id` | str | 劇本識別碼(precompute / cached 都用它對應 npz)|
| `scene_id` | str | 用哪個 3D 場景(如 `twocell_separated`)|
| `duration_sec` | float | 劇本總長(sim 秒)|
| `tick_ms` | int | 母 scenario 一個 tick 多長 sim-time |
| `default_serving_cell` | str=`gnb1_cell0` | UE 啟動自動 attach 的 cell |
| `antenna_pattern` | str / None | `iso`(全向,距離主導)\| `tr38901`(指向性,看 azimuth)。**2026-06-09 修好:precompute 現在真的讀劇本這欄**(run_precompute 用 apply_override 推劇本 gnbs/antenna/buildings)。iso 下 azimuth 失效。 |

### 1.2 UE(`ues[]`)
| 欄位 | 說明 |
|---|---|
| `name` | UE 名 |
| `positions` | `[[t, x, y, z], ...]` 軌跡(內插);靜止給頭尾兩點同座標。**y=高度(m)** |

### 1.3 流量(`traffic[]`)
| 欄位 | 說明 |
|---|---|
| `ue_name` | 對應哪顆 UE |
| `profile` | `[[t_sec, dl_kbps, ul_kbps], ...]` piecewise 流量(分段定速)|

### 1.4 gNB / Cell(`gnbs[]` → `cells[]`)
| gnb 欄位 | 預設 | cell 欄位 | 預設 |
|---|---|---|---|
| `name` | — | `cell_id` | — |
| `position` (x,y,z) | — | `pci` | 0 |
| `frequency_ghz` | 3.5 | `azimuth_deg` | 0(0=正北 90=正東)|
| `bandwidth_mhz` | 40 | `position` (x,y,z) | None→用 gnb 位置 |
| `power_dbm` | 23 | | ⚠️ live/RU SINR 用這個;**必須等於 §1.6 `tx_power_dbm`**(見下方雙欄陷阱)|
| `active` | True | | |
| `target_height_m` | None | | |

### 1.5 建物(`buildings[]`)
`name / position / size / color / rotation_xyz_deg / material / target_height_m`(視場景需要)

### 1.6 ★ per-scenario 行為(可選;省略=安全預設,`scenario_driver.start()` 自動套用+還原)
| 欄位 | 預設 | 用途 |
|---|---|---|
| `cell_quotas` | `[]` | `[{cell_id, max_prb(0-100)}]` — CCO 容量受限 demo(c0 設 20%)|
| `inter_freq` | False | True=不同頻不互擾(CCO 回升要)|
| `discard_timer_ms` | 300 | RLC 丟棄上限(ms);CCO 用 2000 封 delay ~2s |
| `tx_power_dbm` | 23 | 發射功率(dBm),**DU/cached SINR 用**。降低→SINR↓→製造真容量受限(CCO 用 3.0→SINR~17)。⚠️ **必須等於 `gnbs.power_dbm`**(見下)|
| `a3_enabled` | None(=CU env `HO_A3_ENABLED`,預設 **off**)| A3 自動換手開關。**CCO 必須 off**(否則 A3 把 RC 換到較弱 cell 的 UE 彈回強 cell)|
| `rlc_delay_model` | `calib` | `calib`=÷30 對齊 OAI 低 delay;**`subtick`=誠實佇列延遲**(CCO 壅塞 delay 要過 500ms 必用)|

> **一般劇本這些不用填**;只有特殊 demo 才加。driver 啟動「一定送」(含還原預設),避免上一支劇本殘留。

#### ⚠️ tx_power「雙欄陷阱」(2026-06-09 踩過)
功率有**兩個欄位**,兩條 SINR 路徑各讀一個 —— **值不一致會讓 cached/live 差 = 兩值之差(dB)**:
| 欄位 | 哪條路徑讀 |
|---|---|
| `tx_power_dbm`(§1.6 top-level)| **DU / cached** SINR(`channel_cache_du._TX_POWER_DBM`)|
| `gnbs[].power_dbm`(§1.4 per-gNB)| **RU / live** SINR(`dl_tti cell_to_power`)|
**設定時兩個務必相同**(CCO 兩個都設 3.0)。根因是 DU SINR 偷懶用單一全域功率、RU 用 per-cell;正解應合併成一個來源(`gnbs.power_dbm`),目前先靠「兩欄一致」。see memory `cco_demo`。

#### ★ CCO 觸發物理(2026-06-09 學到)
要 c0 真容量受限:**offered 流量 > c0 被 quota cap 後的容量**。容量 = capped PRB × 該 SINR 的 MCS 速率。
- SINR 太高(~44)→ MCS 拉滿 → 21 PRB 送 ~36M → 25M 送得完 → **不塞**(演不出)
- 中等 SINR(~16,靠降 tx_power)→ MCS~20 → 21 PRB ~19M < 25M → **真塞** → delay 真爬 → 觸發
- 別用 co-channel 開干擾降效率:會破壞 c1 回升。用降 tx_power。

---

## 2. 劇本 / 場景去哪「收成」(資料流)

```
docs/scenarios/*.json
   │  (1) upload  POST /api/v0.1/RAN/Scenario/ScenarioController/upload
   ▼
Omniverse backend (port 8001) ── 存進 Omniverse DB ◀── 唯一真實來源
   │
   ├─(2) RANsim-UE 跑模擬時 fetch:
   │      scenario_loader.fetch() → POST .../ScenarioController/read {scenario_id}
   │      位址 env: OMNIVERSE_URL (預設 http://host.docker.internal:8001)
   │
   └─(3) Physics precompute 也 fetch 同來源:
          run_precompute.py → _fetch_scenario() → 同 read API
          算出 channel → /app/data/channel_cache/{scenario_id}.npz
```

**重點**
- **模擬器不讀檔、讀 DB**。改 `docs/scenarios/*.json` 後**一定要 upload** 才生效。
- scene 另有兩層(memory `coverage_data_flow`):Layer1 `scene_config.json` / Layer2 前端 initScene。**天線設定在這層(不是劇本)**。

---

## 3. 流量(traffic profile)給誰

```
劇本 traffic[].profile = [[t, dl_kbps, ul_kbps]]
   │  scenario_driver._build_piecewise_profile()  → 轉 piecewise
   ▼
UeLifecycleManager.push_sync({traffic_profile, ...})   ← 每 UE 帶自己的 profile
   │
   ▼
ue_thread → UeTrafficGen.update_profile()
   │  每 tick: traffic_gen.tick() 按當前段速率產 SDU
   ▼
inject_sdu → DU RLC entity（注入下行緩衝）→ slot 引擎排程送出
```

**注意**
- 注入速率要用 **achieved_speed_x(實際達成倍速)**,非設定 speed_x,否則過量注入(memory `p0a_p1_drift_fix`)。
- traffic_gen 有兩道 gate:`start()` + `push_sync(sim_start)`,漏第二個 → traffic 永遠 0(memory `sim_start_event_gate`)。

---

## 4. env 能控制什麼(docker-compose.yml,分容器)

### CU(cu)
`PLMN_MCC/MNC`、`GNB_ID_HEX/LENGTH`、`RAN_FUNC_ID_KPM=2/RC=3`、`SERVED_TAC`、`SST`、`HO_TTT_MS=3000`、`OMNIVERSE_URL`

### DU(du)
| env | 現值 | 控制 |
|---|---|---|
| `SIM_TICK_MS` | 50 | DU 內部 tick |
| `PM_WINDOW_SEC` | 1.0 | KPM 統計視窗 |
| `PRB_OAI_CALIB` | 1.0 | PRB% 校正係數(已退,106 PRB 後不需)|
| `RLC_TX_MAXSIZE_BYTES` | 10000000 | RLC 緩衝上限 |
| `RLC_DELAY_MODEL` | calib | delay 模型 |
| `SLOT_ENGINE_SHADOW/TAKEOVER` | on/on | slot 引擎接管 delay/MCS |
| `DU_INPROCESS_SINR` | on | DU 內算 SINR(免 HTTP)|
| `DU_RU_INPROCESS` | on | DU/RU 同 process |
| `SLOT_DISCARD_TIMER_MS` | 300 | RLC 丟棄上限(可被劇本 per-scenario 覆寫)|
| `SLOT_OP_PRB_FLOOR` | 12(code 預設)| MIN_PRB 地板,低載不餓死 |

### RU(ru)
| env | 現值 | 控制 |
|---|---|---|
| `RU_DEFAULT_PATTERN` | tr38901 | RU 端天線(live 路徑)|
| `RU_DEFAULT_ANTENNA_ROWS/COLS` | 1/1 | 天線陣列 |
| `RU_DEFAULT_POLARIZATION` | V | 極化 |
| `RU_NUMEROLOGY` | 1 | SCS(1=30kHz)|
| `RU_NOISE_FLOOR_DBM` | -98 | 噪聲底(對齊 OAI)|
| `RU_TX_POWER_DBM` | 23 | 發射功率(對齊 OAI rxgain;可被劇本覆寫)|
| `RU_SCENE_CALIBRATION_LOSS_DB` | 0 | 場景校正損耗(rfsim AWGN=0)|
| `RU_CHANNEL_CACHE_TTL_SEC` | 0.5 | cache TTL |
| `RU_CHANNEL_MODE` | live(預設)| live/cached(driver 啟動會依 precompute 狀態切)|
| `RU_SCENARIO_ID` / `RU_CACHE_DIR` | — / /data/channel_cache | cached 載哪個 npz |

### Physics(physics)
`MITSUBA_SCENE_PATH=/app/scenes/umi_3sector.xml`、`SCENE_CONFIG_PATH`、`SCENE_ID`、`SIM_MAX_DEPTH`(code 預設 5)、`NVIDIA_DRIVER_CAPABILITIES`、`OMNIVERSE_URL`

### 啟動時 API 給(既非 env 也非劇本檔)
| 值 | 在哪 |
|---|---|
| `speed_x`(2.0)、`sim_dt_ms`(250)、`source`、`scenario_id` | `SimController/start` 的 body |

---

## 5. ★ env 控不到、劇本也沒有的(hardcoded / 全域,要改 code 或 scene_config)

| 項目 | 在哪(寫死/全域)| 注意 |
|---|---|---|
| ~~天線 pattern 被忽略~~ | — | ✅ **已修(2026-06-09)**:precompute 現在讀劇本 `antenna_pattern`/`gnbs`/`buildings`(run_precompute apply_override)。劇本沒設則 scene_config 預設 tr38901 |
| **場景 mesh** | `MITSUBA_SCENE_PATH=umi_3sector.xml`(全域)+ scene_config 6 棟樓 | 劇本 `buildings:[]`(空)→ precompute 建平地 mesh=自由空間;有 buildings 才有樓 |
| **precompute 隨機性** | 地面反射 + diffuse 取樣非確定性 | 同劇本每次 channel 略飄(margin);幾何正確後不翻 cell。跑前驗 c0>c1(memory `precompute_nondeterminism`)|
| **total_prb=106** | `cell_state.py:10` 寫死(對齊 40MHz/30kHz)| 對應 bandwidth_mhz=40 |
| **delay calib ÷30(calib 模式)** | `tick_runner.py` 寫死 | 壓平壅塞 delay 對齊 OAI;**CCO 要 delay 爬請用劇本 `rlc_delay_model:subtick`**(memory `oai_slot_delay_calib_dont_touch`)|
| **Volume kbit 換算 ×8/1000** | CU `kpm_indication.py` 寫死 | 改單位才動 |
| **MCS controller(OLLA)** | `mcs_controller.py`(INITIAL 9, MAX 27)| 閉環,SINR 高會爬到 27(~18 tick);決定容量,SINR44→MCS27→不塞 |
| **TDD DL slot 比 / MAC overhead 0.80 / MCS table 簡化** | `mcs_table.py`/`pf_scheduler.py` 寫死 | 對齊 OAI band78 |
| **A3 offset/hys/enabled** | CU `a3_handover_calculation`(enabled 改 env `HO_A3_ENABLED` 預設 off;劇本 `a3_enabled` 可覆寫)| handover 觸發門檻 |

---

## 6. 附:每次跑劇本的 pre-flight checklist(因 §5 的坑而必要)

```
1. upload 劇本 → omniver:8001                         (改檔必做)
2. precompute,反覆驗到 npz path_gain c0 > c1 +5dB 才鎖定  (防 SINR 翻負)
3. 若重 precompute 過 → docker restart ransim-du ransim-ru (清 stale 單例)
4. SimController/start(帶 speed_x=2.0/sim_dt=250)→ RU set_channel_mode cached
5. pre-flight 驗:achieved≈2x / SINR 正 / serving=c0 / RIC KPM 流動  (全綠才開長跑)
6. 背景 collector:ric_total 判存活、每筆 flush 落盤;docker logs 兜底
```

### 量測注意
- RIC snapshot thp 是瞬時視窗值;算相位均**別過濾 thp>0**(會排除 bursty idle 空檔 → 嚴重高估)。
- idle 樣本無 SLOT_SHADOW sim_sec → 用 wall→sim 線性(斜率≈achieved)重建歸位。
- 權威視窗均在 RIC InfluxDB(10.3.0.71),host 端目前連不到。

---

## 7. ★ cached vs live(2026-06-09 徹查結論)

通道有**兩條獨立計算路徑**,結果不會位元級相同:

| | cached | live |
|---|---|---|
| 通道來源 | precompute **凍結 npz**(同 scenario 每次一樣)| RU **即時 Sionna 重算**(每 tick 重擲,有隨機)|
| 算 SINR 的模組 | DU `channel_cache_du`(單 worker)| RU `dl_tti_pipeline`(gunicorn **2 worker**)|
| 適合 | **對照 / demo / 可重現**(全用這個)| 即時視覺 / 概略 |

**這 session 修掉的 live≠cached 大差距(本來差 ~36dB):**
1. **inter_freq 沒接到 live(差 ~16dB)** → RU 2 worker,旗標 per-process。改用**共享檔 `.inter_freq`**(仿 `.mode`)讓兩 worker 共讀。`scenario_driver` 經 `ru_client.set_inter_freq` 設。
2. **tx_power 雙欄不一致(差 ~20dB)** → `tx_power_dbm`(cached)vs `gnbs.power_dbm`(live),見 §1.6 雙欄陷阱。設一致即可。
3. **live 原本用靜態 scene_config(無視劇本幾何)** → `scenario_driver` 切 live 時呼 `physics_client.push_scene` 把劇本 gnbs/buildings/antenna 推給 Physics live 引擎。

**修完後剩餘差異** = Sionna 即時重擲的 ~幾 dB 抖動(live 本質,非 bug)。**要精確/可重現一律用 cached。**

---

相關 memory:`scenario_source_omniverse_db`、`precompute_nondeterminism`、`oai_alignment_params`、`oai_2x_clean_result`、`sim_speed_x_max_2x`、`physics_docker_gotchas`、`unified_sim_architecture`。
