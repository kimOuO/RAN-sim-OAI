# XAPP_DT 兩平台架構與流程總覽(2026-09-22 依現行程式整理)

> 依據:`README.md`、`new_plan/platform_restructure_plan.md`、兩個 Django 後端與兩個 Next.js 前端的實際目錄與 API。

---

## 0. 全貌:兩平台 + 共用模擬核心

```
┌──────────────── 管理平台 ran-scene-management ────────────────┐
│  scene-editor-frontend (:3011, Next.js)                        │
│        │  全 POST                                              │
│        ▼                                                       │
│  scene-management-backend (:8301, Django "registry")           │
│  DB: scene_registry_db(場景設計值的唯一真相)                    │
└────────────────┬───────────────────────────────────────────────┘
                 │ 讀 scene / scene_run / run_knob;回寫 status、run_instance
                 ▼
┌──────────────── 模擬平台 ran-emulation-runtime ───────────────┐
│  run-orchestrator (:8302, Django)  DB: run_orchestrator_db     │
│    ├─ run_lifecycle    起停 run、precompute、E2 槽位、健康輪詢   │
│    ├─ run_telemetry_archive  每 2 s 撈 CU/E2Adapter 落地歸檔    │
│    └─ agent_api        給外部 Agent 的 I-1~I-7 介面             │
│         │ docker SDK spawn                                     │
│         ▼                                                      │
│  per-run 容器:cu-<rid> du-<rid> ru-<rid> ue-<rid> e2adapter-<rid>│
│  共用:physics (:8104, Sionna RT GPU)、postgres/pgbouncer        │
│                                                                │
│  run-monitor-frontend (:3012, Next.js, 唯讀)                    │
│    讀 registry + orchestrator 歸檔 + per-run DU/UE/E2Adapter    │
└────────────────────────────────────────────────────────────────┘
                 │ SCTP + ASN.1 APER
                 ▼
            外部 RIC / xApp
```

- 平台間只傳 UUID(`scene_run_uuid`、`cell_id`、`ue_id`),沒有跨庫外鍵。
- 設定在 run 啟動時凍結;改 registry 要重啟 run。
- 所有 API 都是 POST,路徑 `/api/v0.1/{System}/{Module}/{Controller}/{action}`。

---

## 1. 管理平台(ran-scene-management)

### 1.1 後端 `ran-scene-management-backend`(:8301)

URL 前綴 `/api/v0.1/Scene_management_backend/{Module}/`。七個 Django app,每個 app = 一組資料表 + actors(Controller/Reader)+ services:

| app / Module | 資料表(models/ 一表一檔) | 主要動作 |
|---|---|---|
| `field_scene` / Field_scene | scene、building、material | Scene create/update/duplicate/delete/read/read_full_tree;SceneGeometryReader meshes/bounds/height_map/coverage/mesh_file;劇本 JSON 匯入(scenario_importer)、Mitsuba 幾何 |
| `equipment_ran` / Equipment_ran | gnb → du → cell → ru、neighbor_seed | CRUD |
| `equipment_ue` / Equipment_ue | ue、ue_waypoint、ue_traffic、ue_active_window | CRUD |
| `equipment_preset` / Equipment_preset | antenna_preset、du_config_template、gnb_config_template | CRUD(lookup 表,下拉選單來源) |
| `render_osm_footprint` / Render_osm_footprint | osm_map_asset | geocode(Nominatim)→ generate / preview(Overpass)→ build_scene(osm_to_mitsuba);attach_to_scene |
| `render_scan_mesh` / Render_scan_mesh | scan_asset | import_glb(glb_reader → scan_segmentation → scan_material_classifier → glb_to_mitsuba);use_for_scene / attach_to_scene |
| `simulation_run` / Simulation_run | scene_run、run_knob、run_instance | CRUD;scene_run 是「執行實例」,status 由 orchestrator 回寫 |

另外保留舊路徑 `/api/v0.1/RAN/Scenario/ScenarioController/read|list`(legacy_scenario_store)給舊劇本相容。

階層:`scene → gnb → du → cell → ru(1:1)`、`scene → ue → waypoint/traffic/active_window`、`scene → scene_run → run_knob/run_instance`。

### 1.2 前端 `ran-scene-management-scene-editor-frontend`(:3011)

分層固定:`app/(page) → hooks/feature/* → services/api/* → services/clients/apiClient.ts(post)`。
呼叫兩個後端:registry(:8301)與 orchestrator(:8302);config 裡的 INGEST 也指到 :8301(同一後端)。

| 路由 | 用途 | 主要元件 / hook |
|---|---|---|
| `/scenes` | 場景列表卡片、active runs、Start / Stop / Precompute | useSceneListPage |
| `/scenes/[id]/environment` | 步驟 1:SourcePicker(地圖 / 掃描)→ map/(OSM 框選、逐棟材質)或 ScanUploadPanel → 3D | useMapBuilder、sceneGeometry |
| `/scenes/[id]/network` | 步驟 2:Palette 拖放 gNB/cell 貼齊地面/屋頂;PropertyPanel 設 PCI/頻率/功率/方位/下傾/天線 preset/A3;DuFields、GnbTemplatePicker;CoveragePanel | useSceneEditorPage、useCoverage |
| `/scenes/[id]/ue` | 步驟 3:UeGeneratorPanel(種子/數量/速度/停留/流量範本)或逐一放置;UeTrafficPanel | ueGenerator |
| `/scenes/[id]/launch` | 步驟 4:LaunchPanel 選 cached/live、倍速、run_knob;Precompute;Start | services/api/runs.ts |
| `/presets` | 天線 preset、材質、DU/gNB 模板 | presets.ts |
| `/imports` | 劇本 JSON / GLB / OSM 匯入 | imports.ts、geometry.ts |
| `/network-elements` | 網元總表 | useNetworkElementsPage |

StepBar / StepGate / CheckList 控制四步驟的門檻(前一步未完成不能進下一步)。

### 1.3 管理平台流程(建場景到啟動)

```
1 環境   地圖:geocode → generate/preview(OSM 建築)→ 逐棟材質/高度/排除 → build_scene(Mitsuba XML)
         掃描:import_glb → 面片分割 → 材質分類 → glb_to_mitsuba → use_for_scene
2 網元   SceneController/… + Equipment_ran CRUD(gNB/DU/cell/RU、天線 preset、A3、DU 模板)
3 UE     Equipment_ue CRUD(產生器或手放;waypoint/traffic/active_window)
4 啟動   SceneRunController/create(一個場景一筆 run 設定;mode、speed_x、sim_dt_ms、duration)
         cached 模式 → orchestrator PrecomputeController/start → status precomputing → ready
         orchestrator LaunchController/start → status starting → running
```

---

## 2. 監控 / 模擬平台(ran-emulation-runtime)

### 2.1 編排器 `ran-emulation-runtime-run-orchestrator`(:8302)

URL 前綴 `/api/v0.1/Run_orchestrator/{Module}/`。三個 app:

| app / Module | 內容 |
|---|---|
| `run_lifecycle` / Run_lifecycle | `LaunchController/start|stop`、`LaunchRequest*`(每次起停一筆紀錄)、`PrecomputeController/start|stop`、`PrecomputeReader/read`、`RicObservationReader/read`。services:container_spawner(docker SDK、建/刪 per-run DB、E2 槽位、DU 模板 → env)、health_monitor(每 run 一條 thread,寫 run_instance.status/last_heartbeat,劇本跑完自動 stop → done,異常自動重啟)、physics_watchdog、platform_clients(打 registry) |
| `run_telemetry_archive` / Run_telemetry_archive | 資料表 run_kpm_sample、run_handover_event、run_control_event、run_pm_snapshot;cu_archiver 每 2 s 輪詢 per-run CU `TelemetryExportReader/read`、`E2FullReporter/read`、UE `ScenarioController/status`、DU `TickController/read`、E2Adapter `ControlAuditReader/read` 落地;archive_retention 控制保留 |
| `agent_api` / Agent_api | 外部 Agent 介面:FieldReader/list、FieldReader/config、ScenarioController/run、RunReader/status、RunReader/events、RunReader/config_changes(需求 I-1~I-7) |

### 2.2 `LaunchController/start` 的實際順序(launch_request_actor.py)

```
1. platform_clients 從 registry 讀 scene_run + run_knob(讀不到 → 502)
2. 建 LaunchRequest(action=start, status=accepted)
3. live 模式檢查是否已有 live run(GPU 只能 1 個)
4. 鎖內配 E2 槽位:查其他 running/starting run 的 gnb_id_hex → allocate_slot
   → registry update_scene_run(status=starting, gnb_id_hex, e2_node_id)
5. DU 設定:registry du_config_template + du.config_override → DU env
6. spawn cu/du/ru/ue 四容器(名稱 {role}-{rid},rid=uuid 後 8 碼;建 cu_/du_/ru_<rid> 三個 DB;
   host port 隨機 → registry run_instance)
7. wait_healthy → 再 spawn e2adapter(host network,port 8400+槽位;向 CU 拿 node id 送 E2 Setup)
8. health_monitor.start_monitor
9. 呼叫 UE driver 起劇本 → LaunchRequest status started/failed
10. registry update_scene_run(status=running, started_at)
11. RIC 閘道登記(E2 Setup 完成後啟用)
12. archive_retention.apply_on_start → cu_archiver.start_archiver
失敗:stop_monitor、teardown 容器、LaunchRequest failed、registry status=failed
```

`stop`:建 LaunchRequest(stop)→ 停 UE 劇本 → stop_archiver → stop_monitor → teardown(移除容器、drop DB)→ registry status=stopped。劇本自然跑完由 health_monitor 走同樣的 stop 再改成 done。

scene_run 狀態機:`draft|pending → precomputing → ready → starting → running → stopped|done|failed`。

### 2.3 一個 tick 的模擬資料流(per-run 容器內)

```
UE driver 推時間、更新位置 → DU tick(RLC → 排程)→ DlTtiRequest → RU
RU 查通道(cached npz / live Physics)→ 天線三層 → 波束 → SINR/RSRP → CqiIndication → DU
DU 查 BLER → 吞吐/延遲 → T310 → 每秒量測報告 → CU(A3 換手 / 重建 / KPM)
CU → E2 Adapter(SCTP + ASN.1)→ RIC;xApp 控制命令回送
orchestrator cu_archiver 每 2 s 撈 CU/E2Adapter → run_orchestrator_db → 監控前端
```

### 2.4 監控前端 `ran-emulation-runtime-run-monitor-frontend`(:3012,唯讀)

同樣 `app → hooks/feature → services/api → apiClient.post`。資料來源:

| 來源 | 拿什麼 |
|---|---|
| registry(:8301) | scene_run 清單、scene 完整樹(read_full_tree)、run_instance(host_port)、場景 mesh |
| orchestrator(:8302) | run_kpm_sample / run_handover_event / run_control_event / launch_request、RicObservationReader、精算後的 precompute 狀態 |
| per-run DU / UE / E2Adapter | 經 run_instance.host_port 直打:DU TickController/read(達成倍速)、UE ScenarioController/status、E2Adapter AdapterStatusReader |

| 路由 | 內容 | hook |
|---|---|---|
| `/runs` | 所有 run:狀態、場景、倍速(設定→達成)、封存視窗數 | useRunListPage |
| `/runs/[id]` | 單 run dashboard:Full KPM per-cell(可展 per-UE)、RIC 命令時間軸、RIC 觀測、cell 負載、E2 面、換手/RLF、波束使用 | useRunDashboardPage(3 s 輪詢;RIC 閘道 30 s) |
| `/runs/[id]/live3d` | 3D 即時:UE 位置、服務 cell、覆蓋層 | useRunLive3dPage、live3d.ts |
| `/runs/[id]/playback` | 逐視窗回放 slider(讀 run_orchestrator_db 歸檔) | usePlayback3d |
| `/runs/[id]/events` | 事件流(HO / RLF / RIC 命令 / 起停) | |
| `/compare` | 2–4 個 run 同指標並排(sim-time 對齊) | useComparePage |

元件:`components/dashboard`(StatTile、GnbLoadBoard、RicCommandTimeline、RicObservationPanel、UeSmallMultiples、BeamUsagePanel…)、`components/charts`(TimeSeries、Bar、Column、Gauge、Sparkline、ServingStrip)、`components/scene3d`(LiveScene3D、SceneMeshes、CoverageLayer)。

---

## 3. 端到端流程一張圖

```
[管理平台 :3011] 建場景 4 步驟 ──POST──▶ [registry :8301] scene_registry_db
        │ 步驟 4 按 Precompute / Start
        ▼
[orchestrator :8302] 讀 scene_run → 配 E2 槽位 → docker spawn 5 容器 + 3 DB
        │                                   │
        │ health_monitor(狀態回寫 registry)  │ UE driver 起劇本 → CU/DU/RU tick → E2Adapter ⇄ RIC
        │ cu_archiver(每 2 s 歸檔)            │
        ▼                                   ▼
[run_orchestrator_db] ◀────────────── CU / E2Adapter 落地表
        │
        ▼
[監控前端 :3012] /runs → dashboard / live3d / playback / events / compare(3 s 輪詢,零控制)
        │
        └── 也直打 per-run DU/UE/E2Adapter host_port(registry run_instance 提供)
```

---

## 4. 觀察到的邊界與注意點

- **控制權分離乾淨**:編輯器負責「設計 + 觸發起停」,監控前端「只讀」;起停實際邏輯全部在 orchestrator。
- **狀態回寫走 registry**:orchestrator 不擁有 scene_run,只透過 platform_clients 改 status / gnb_id_hex / run_instance;因此 registry 掛掉起不了 run(502)。
- **兩個資料庫視角**:registry 是設計值,run_orchestrator_db 是執行後紀錄,per-run cu_/du_/ru_ 是執行中狀態且 stop 即 drop;回放只能靠歸檔。
- **監控前端直打 per-run 容器**:依 run_instance.host_port,host 由 NEXT_PUBLIC_RUNTIME_HOST 決定;跨機部署時要設。
- **E2 槽位與 gNB ID**:orchestrator 用鎖分配,避免 2026-09-16 那種兩 run 撞 meid 的事故;場域可釘槽位。
- **DU 模板從 2026-09-19 起真正生效**(registry 模板 → DU env),之前是裝飾。
- **Physics 共用**:live 模式只能 1 個 run;多 run 並行要 cached + 先 precompute。
- 前端 config 的 `INGEST_BASE_URL` 預設 8303 但 compose 指回 8301,實際沒有獨立 ingest 服務(OSM / 掃描匯入都在 registry 內)。
