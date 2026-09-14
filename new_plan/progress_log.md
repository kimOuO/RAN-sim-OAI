# 平台重構執行紀錄

> 每個階段開始、每個可驗收的步驟完成、每個偏離計畫的決定,都記在這裡。
> 計畫本體:[`platform_restructure_plan.md`](platform_restructure_plan.md)。branch:`refactor/platform-split`。
> 格式:日期 / 階段 / 做了什麼 / 驗證方式與結果 / 偏離計畫之處。

---

## P0 拍板 + 搬家(開始 2026-09-12)

### 2026-09-12 — P0-1 現場 commit ✅
- `feature/e2sm-anr` 上 4 個 commit:`16a3657 feat(phy)`、`42a090f fix(ue,precompute)`、`0ad8684 docs(architecture)`、`1508385 docs(plan)`。
- 刻意未納入:`channel_cache/*.npz`、根目錄 `image.png`、執行期狀態檔。

### 2026-09-12 — P0-2 branch ✅
- 發現 `main` 純粹落後 251 commit(7/2→9/12),改為 `git branch -f main feature/e2sm-anr`。
- `refactor/platform-split` 基於 1508385。
- 偏離:計畫原寫「從 main 開」,前提(main 是主線)不成立,已改記於 §12 #16。

### 2026-09-12 — P0-3 搬家 ✅(commit 見 git log)
- `git mv` 1044 個路徑進三平台結構;.venv / node_modules / _vendored 等 ignored 內容隨目錄 rename 一併移動。
- 停掉 ransim 容器後才搬(bind mount 不能在動)。
- **偏離 §1 兩處**:
  1. `channel_cache` 留在 `ran-emulation-runtime/Physics_sim/data/`,未拉到根目錄 `sionna-channel-cache/` —— 父目錄 `Physics_sim/data` 是 root:root 755,mitlab 無法 rename。待 `sudo chown -R mitlab:mitlab ran-emulation-runtime/Physics_sim/data` 後補做。
  2. `Omnivers_platform/` 未動 —— 它不是本 repo tracked 的(0 個 tracked 檔,自帶 .git),且 omniver_kit / omniver_backend 容器執行中。留到 ran-3d-rendering 階段。
- 路徑修正(第二個 commit):根 compose 22 處、DU/RU/Physics Dockerfile、DU requirements、CU/DU 各自 compose、RU init_project.sh、.gitignore、新增根 .dockerignore。
- **協定套件安裝方式統一**:原本四種(DU COPY /opt、CU mount /tmp、Physics 內嵌 /app/ran-sim-protocol、RU rsync 到 _vendored)→ 一律 root build context COPY 到 `/opt/ran-sim-protocol` + runtime 同路徑 bind mount。RU 的 `_vendored/` 廢止(已是過期複本:缺 rsrp_model.py,三個檔內容不同)。
- 驗證:`docker compose config -q` 通過;映像重建與 cco_20min 對照在 P0-6。
### 2026-09-12 — P0-4 network-element-registry 骨架 ✅
- 新 repo `ran-scene-management/ran-scene-management-network-element-registry/`,照 `backend_rule` tree:5 app、17 張表(每表一檔)、Write/Read serializer、`<Model>Controller`(create/update/delete)+ `<Model>Reader`(read)、通用 `SqlDbBusinessService`(沿用 CU 的)、common services、tests、settings/utils(沿用 CU)、Dockerfile、獨立 compose(port 8301)。
- FK 一律 `to_field=<parent>_uuid` / `db_column=f_<parent>_uuid`;`neighbor_seed` 兩個 FK 同指 Cell → `f_source_cell_uuid` / `f_target_cell_uuid`。
- 對外 API 全 POST:`/api/v0.1/Network_element_registry/{Module}/{Model}Controller/{create|update|delete}`、`{Model}Reader/read`(read 支援 `<t>_uuid` 單筆、`f_<fk>_uuid` 過濾、任意欄位過濾)。
- 驗證:`makemigrations` 17 個 model、`manage.py check` 無問題、`manage.py test` OK、端到端 smoke(material→scene→gnb→du→cell→ru,再以 `f_du_uuid` 讀回 cell,`tilt_deg` 正確)通過。用的是 CU 的 venv(Django 5.0.7 / DRF 3.15.2)。
- 尚未做:預載 lookup 資料(3GPP 天線 preset、ITU 材質、OAI band78 DU 模板)→ 排 P1 的劇本匯入器一起做(fixture)。
### 2026-09-12 — P0-5 run-orchestrator 骨架 ✅
- 新 repo `ran-emulation-runtime/ran-emulation-runtime-run-orchestrator/`:2 app、4 表。`run_lifecycle.launch_request`(start/stop 請求紀錄,P2 才接 docker SDK)、`run_telemetry_archive.{run_kpm_sample, run_control_event, run_handover_event}`(§10.4 的 run 級封存)。
- `scene_run` 本體在 registry;此處只存 `f_scene_run_uuid` CharField(跨 repo,backend_rule §12-2)。settings 已預留 `HTTP_REGISTRY_HOST/PORT`(§8-2)。
- 驗證:makemigrations 4 model、check 無問題、test OK、smoke(POST 一筆 kpm sample → 以 `f_scene_run_uuid` 讀回)通過。
- 映像重建完成:`ransim-du:platform`、`ransim-ru:platform`、`ransim-physics:platform`(root build context + `/opt/ran-sim-protocol`);Physics 內 sionna-rt 2.1.0 / mitsuba 3.9.1。
### 2026-09-12 — P0-6 驗收:搬家後舊流程照跑 ✅
- `docker compose up -d` 9 個容器全 Up(postgres healthy)。DU/RU/Physics 三個重建映像內 `import ran_sim_protocol` 正常(DU/RU 由 entrypoint 從 `/opt` mount 重灌;Physics editable 指向 `/opt`)。
- 跑 `corridor_16_24`(cached、2×、sim_dt 500)三次,每次 80–110 s 牆鐘:DU tick 212 / 264 / 304,達成倍速 ≈1.43×;18 UE attach、17 進 DU registry;流量注入後 `ues_with_bo=8`;DU→CU `measurement_report` / `cell_measurement_report` 200 OK;CU/DU/RU/UE/Physics **零 Traceback**。
- **兩條獨立 SINR 路徑一致**(`[DU_SINR_CMP]` http_sinr == inproc_sinr,例 p03 29.87 / p12 28.98 / p13 12.51)→ RU 的 HTTP cache 路徑與 DU 直讀 cache 路徑搬家後都解析到同一個 npz。
- DU `dump_pm.ue_latest` 17 筆(serving / sinr / rsrp / neighbors)。多數 UE SINR ≈ −77 dB 是**劇本設計**:npz 內 p01@tick250 對 `nbr` −66 dB、對 `src` −144 dB,而預設 attach 在 `src`(ANR/換手測試前置狀態),與搬家無關。
- **未達成 / 已知**:
  1. 沒有搬家前的 KPM 位元級基準可比(當時未擷取);以上述「雙路徑一致 + 零 traceback + 數值可由 npz 解釋」作為 P0 的一致性證據。
  2. E2Adapter `KpmSnapshot` 為空:對 RIC 10.3.0.71 的 SCTP 被 reset(外部),無訂閱就不 collect —— 搬家前 `connected:false` 亦然。
  3. `cco_20min` 不在 Omniverse 劇本倉庫(倉庫只有 corridor_* 與 anr_*),故改用 `corridor_16_24` 驗收。
  4. Physics 在 cached 模式 run 期間本來就不載場景(`No scene loaded yet` 正常)。

## P0 完成(2026-09-12)。下一階段 P1:DB 為權威(劇本匯入器、bundle/reader、反向工具、building_ingest 搬出 Omniverse)。

## P1 DB 為權威(開始 2026-09-12)

### 2026-09-12 — P1-1 劇本匯入器 + 反向匯出 ✅
- 位置:registry `scene_layout/services/optional/scenario_import/`(`scenario_v1.py` 匯入/匯出、`roundtrip.py` 正規化比對)、actor `ScenarioImporter.import_v1 / export_v1`(POST)、management command `import_scenarios --dir … --roundtrip`。
- 語意完全對齊 RANsim-UE `scenario_loader.fetch()`:3 元素 positions 補時間軸公式、gnb→cell 繼承(frequency/bandwidth/power)、倉庫版 flat gnb、`active` 時窗、`target_height_m`→`antenna_height_m`、`loop`/`speed_mps`。
- 欄位對映(§5 表更新):`default_serving_cell / antenna_pattern / cell_quotas / inter_freq / discard_timer_ms / tx_power_dbm / rlc_delay_model / anr_fixture / _metadata.trigger_config` → `run_knob`(掛在匯入時建立的 draft `scene_run`);`duration_sec / tick_ms` → draft run;`a3_*` → gnb;劇本 `antenna_pattern` → 自動建 `legacy-<pattern>-1x1-V` 天線 preset 掛在每個 ru。
- **schema 修正(由 44 份劇本聯集逼出)**:`scene.{legacy_scenario_id, geometry_scene_id, geometry_source}`、`gnb.{is_active, color}`、`cell.center_frequency_ghz`(ARFCN 是 5/15 kHz raster 量化值,3.5 GHz 這種非 raster 值要保留原值才無損;arfcn 由 38.104 §5.4.2.1 推導)、`ue.{loop, speed_mps}`;`gnb.a3_*` 改 **nullable**(None = 劇本未指定 → CU env 預設;原本非空欄位造成 24 份往返不合)。
- 驗證:`docs/scenarios/*.json` **44/44 匯入成功、44/44 往返相等**(以 loader 語意正規化後比對);Omniverse 倉庫版 `corridor_16_24`(18 UE、active 時窗)、`corridor_24h`、`anr_missing_neighbor`(anr_fixture)三份往返相等;registry 測試 OK。
- 尚未:實際跑一次「export 出來的 JSON」讓 UE driver 跑,比 KPM(P1 驗收第二半,需先把 export 結果放進劇本倉庫或做 `SCENARIO_STORE_URL` 指向 registry —— 排 P1-3 反向工具接線)。
### 2026-09-12 — P1-2 整棵樹 reader ✅
- `POST /api/v0.1/Network_element_registry/Scene_layout/SceneReader/read_full_tree`,body `{scene_uuid}` 或 `{scene_run_uuid}`。
- 形狀:`scene(+ground_material) / buildings[+default_material] / gnbs[dus[+config_template, cells[+ru{+antenna_preset}]]] / neighbor_seeds / ues[waypoints[[t,x,y,z]], traffic, active_windows[[t0,t1]]] / run{knobs{}, instances[]}`。
- 軌跡與時窗刻意用緊湊陣列:corridor_16_24(18 UE、8846 waypoints)完整序列化是 2.7 MB / 3.4 s,緊湊後 **315 KB / 95 ms**。消費端(DU/RU/UE driver)只要數值。
- 測試:47 個全過(含匯入 cco_20min 後檢查巢狀與 knobs)。
### 2026-09-12 — P1-3 反向工具接線:UE driver 不改一行改吃 registry ✅
- registry 提供**舊劇本倉庫同路徑同形狀**的相容端點 `POST /api/v0.1/RAN/Scenario/ScenarioController/read|list`(`legacy_scenario_store_actor.py`,標明過渡用、P2 刪;URL 故意不照 backend_rule §7-1)。回傳 `raw_json` = `export_scenario()`,`precompute_status` 由 draft run 的 mode 推(cached→ready),`cache_path` 沿用匯入值。
- `import_scenarios --from-store <URL>`:把 Omniverse 倉庫的劇本連同 precompute 狀態一併匯入。registry postgres 現有 **64 份(44 檔案 + 20 倉庫版,0 失敗,往返全對)**,去重後 49 個 scenario_id。
- 根 compose 新增 `network-element-registry`(:8301,DB `scene_registry_db`)與 `run-orchestrator`(:8302,DB `run_orchestrator_db`);`postgres-init.sql` 加兩個 DB(現有 volume 已手動 CREATE)。UE 的 `SCENARIO_STORE_URL` 可切換,**預設維持 Omniverse**(行為不變)。
- 踩到兩個坑:(1) bind mount `.:/app` 蓋掉映像的 chmod → host 檔要有執行位元(已 chmod 並進版控);(2) 我把 env 加到 CU 區塊而非 UE,第一次「驗收」其實還在讀 Omniverse —— 交集全等是假的,已重做。
- **驗收**:`SCENARIO_STORE_URL=http://network-element-registry:8000` 重建 UE 後跑 `corridor_16_24`:18/18 attach、tick 332、零 traceback。與 Omniverse 來源那場以 (tick, ue) 交集比 `inproc_sinr`:**32 筆中 31 筆相等**;唯一差異 (tick 220, p09) 9.78 vs −23.49 查證為 p09 在 15:01:19–15:02:01 經歷 RLF→重建(src_c0→src→nbr→src),tick 220 落在 nbr→src 切換點 —— T310 依牆鐘觸發的既有非決定性,與來源無關。`http_sinr` 欄不納入比對(已知 1-tick callback 落差)。
- 未做:P1-4 `building_ingest` 從 Omniverse backend 搬出(GLB 分割/材質分類/Mitsuba、OSM geocode/generate)。
### 2026-09-12 — P1-4 building-geometry-ingest 從 Omniverse 複製出來 ✅
- 新 repo `ran-scene-management/ran-scene-management-building-geometry-ingest/`(:8303,DB `building_ingest_db`),兩個 app:
  - `scan_mesh_ingest`:`glb_reader`(自 `glb_to_usd.py` 抽出 1–282 行純 numpy 部分)→ `scan_material_classifier` → `scan_segmentation` / `scan_openings` / `scan_segment_render.plane_basis` → `glb_to_mitsuba`;表 `scan_asset`。
  - `osm_footprint_ingest`:`nominatim_client` → `overpass_client` → `osm_to_mitsuba`(自 `osm_to_usd.py` 去掉 `write_usd/_viridis/_make_band_materials`);表 `osm_map_asset`。
- **零 USD/pxr 依賴**;依賴只有 numpy / shapely / mapbox_earcut / Pillow。產物落 `scanned-building-assets/{scan,osm}/`(已 .gitignore)。Omniverse 側原樣保留(決策:並存到退場)。
- `attach_to_scene` 跨 repo 呼叫 registry `BuildingController/create`,只傳 uuid(backend_rule §12-2)。
- **與原版的刻意差異(兩處)**:(1) `osm_to_mitsuba` 的 footprints 路徑手動剝 `.mitsuba.xml`(`with_suffix` 只換最後一個副檔名);(2) classifier evidence 的 `round()` 只對數值做 —— 原版在 structural pass 失敗時會 `round(str)` 炸掉並**蓋掉真正的錯誤**(Omniverse 原碼同樣有此問題)。
- 複製時漏掉的 lazy import 模組靠實跑抓出:`scan_openings`、`scan_segment_render`、`MATERIAL_MAP` 常數(被 drop() 連同相鄰 def 吞掉)、`_write_ply` 跨 app 引用。生成腳本存 scratchpad,可重跑。
- **驗證**:
  - GLB:`scan_20260906.orig.glb`(26.7 MB,90,726 面)→ 逐面材質標籤與 Omniverse 側現成結果 **100.000% 相同**,ruleset 9、structural_pass True、buckets 完全一致(wall 433.4 / slanted 159.2 / floor_ceiling 474.7 / wood 68.2 m²),材質 94.67% concrete / 5.33% wood。
  - OSM:台科大附近 600 m 框 → Overpass 9 s → 331 棟 → Mitsuba XML + footprints。
  - attach_to_scene → registry `building` 一列(source=glb_scan、geometry_ref、materials_npz 正確),刪 scene 時 CASCADE 帶走。
  - 容器內 8 個測試 OK(含不連網的 OSM 擠出、GLB 讀取、bbox 正規化)。
- 未做:前端用的 GLB/glTF 輸出(決策:等 P3 需要再加);`import_glb` 為同步呼叫(26.7 MB 約 10 s),大檔要改背景 job 留 P3。

## P1 完成(2026-09-12)。下一階段 P2:模擬端直接吃 registry(CU/DU/RU/UE 啟動讀 `read_full_tree`,不再讀劇本 JSON;orchestrator 單 run 版;`run_telemetry_archive` 接 E2Adapter)。

## P2 模擬端直接吃 registry(開始 2026-09-13)

### 2026-09-13 — P2-1 orchestrator 單 run 版 + P2-2 UE 從 registry 整棵樹組 spec ✅
- UE:`scenario_loader.fetch_by_run(scene_run_uuid)` 打 registry `read_full_tree` 組 `ScenarioSpec`,欄位語意與 `fetch()` 逐項相同(scenario_id 取 `legacy_scenario_id` 供 RU cache 檔名;precompute_status 由 run.mode 推;在場時段從樹帶出,不再打 Omniverse)。`start_scenario / start_sim / SimController.start` 加 `scene_run_uuid`;**沒帶時走舊路徑,劇本倉庫相容端點保留**。env `REGISTRY_URL`。
- orchestrator:`LaunchController.start`(registry `read_full_tree` 驗證 scene 完整性 → 記 `launch_request` → 打 UE `SimController/start{scene_run_uuid}` → registry `SceneRunController/update status=running`)、`stop`(UE stop → status=stopped)。P2 仍共用 CU/DU/RU 容器;P4 改 spawn。env `HTTP_UE_DRIVER_HOST/PORT`。
- **驗證**:orchestrator 起 `corridor_16_24`(scene_run-7de7da10…)→ registry 狀態 pending→running(started_at)→ stopped(stopped_at);`launch_request` (start, started)/(stop, stopped);tick 286、17 UE、零 traceback。inproc SINR 與先前三場交集 48 筆,2 筆不同 —— (220,p09) 與 (280,p11) 皆查證為 RLF 重建時機(p11 於 16:04:38 src→nbr,對應 tick 280)。
- **走 registry 的直接證據**:帶不存在的 `scene_run_uuid` 起 sim → 錯誤指向 `network-element-registry:8000/.../SceneReader/read_full_tree` 404;`fetch_by_run` 亦加了 log 行。
- 未做:P2-3 `run_telemetry_archive` 接 E2Adapter;run uuid 傳給 DU/CU。
### 2026-09-13 — P2-3 run 級遙測封存(CU 落地表 → orchestrator)✅
- **封存來源改為 CU,不是 E2Adapter**:E2Adapter 的 KPM 快照是 indication 驅動(RIC 有訂閱才有),RIC 不通就永遠空;CU 的 `MeasurementLog / CellMeasurementLog / HandoverEvent / RlfEvent` 每個 PM 視窗由 F1 上報落地,與 RIC 無關。§10.4 的「E2Adapter POST」改為 orchestrator 主動輪詢。
- CU 加 `POST /api/v0.1/CU/Logs/TelemetryExportReader/read`(游標式匯出四張表;`max_only` 回最大 id)。CU 表已累積 937 萬筆量測、1243 萬筆 cell 列,archiver 啟動時用 `max_only` 定游標、只封存本 run 之後的資料。
- orchestrator `run_telemetry_archive/services/optional/cu_archiver.py`:每 run 一條背景執行緒,每 2 s 輪詢 CU(→ `run_kpm_sample` 一窗一列:per_ue 17 UE 的 rsrp/sinr/thp/mcs/prb/delay/volume/neighbors + per_cell PRB%;`run_handover_event` 含 HO 與 RLF)與 E2Adapter ControlAudit(→ `run_control_event`,RIC 不通時為 0)。`LaunchController.start/stop` 起停它,stop 回 stats。orchestrator gunicorn 改單 worker(執行緒狀態在行程內)。
- 踩到:`self._stop = Event()` 蓋掉 `Thread._stop()` 讓 `join()` 炸(`'Event' object is not callable`);`CellMeasurementLog.tick_count` 是窗內 tick 數不是絕對 tick,sim_time 要累計。
- **驗證**:corridor_16_24 三輪。最後一輪 45 s:samples 55、handover 18(attach 的 PREP 事件)、rlf 2、polls 24、errors 0;sim_time_ms 逐窗 +1000;stop 後 registry stopped、DU 停、零模擬端 traceback。
- 未做:`run_kpm_sample.wall_time_ms` 未填;ControlAudit 欄位對映在 RIC 通之前未驗;DU/CU 本身仍不知道 `scene_run_uuid`(P4 per-run 容器時自然解決)。

## P2 完成(2026-09-13)。留給 P4 的:run_instance 健康輪詢、DU/CU 認得 scene_run_uuid、E2Adapter 多 node。下一階段 P3:兩個前端(管理畫布 + 監控)。

## P3 兩個前端(開始 2026-09-13)

### 2026-09-13 — P3-1 管理平台前端骨架 ✅
- 舊 Dashboard(P0 已搬到 `…-scene-editor-frontend`)改名 `ran-scene-management-legacy-dashboard`,compose `dashboard` 指過去照跑(ANR 工作仍用它)。新前端在乾淨的 `ran-scene-management-scene-editor-frontend/`,**照 `frontend_rule` 白名單**(`app/ components/ hooks/ services/` + `config/ types/ styles/ public/`;沒有 `lib/`),eslint 加 services→hooks/components 的 import 邊界規則。
- 資料流:`hooks/feature/*` → `services/api/*`(`listX/getX/createX/updateX/deleteX`,底層全 POST)→ `services/clients/apiClient.ts`;async 形狀 `{data,status,error,refetch}`(`hooks/base/useAsync`)。
- 頁面:`/scenes`(卡片、每 scene 的 run 列、Start/Stop 打 orchestrator、建立/刪除)、`/scenes/[id]`(物件樹 / R3F 畫布 / 屬性面板)、`/presets`(天線 / 材質 / DU 模板表)、`/imports`(劇本 JSON 貼上匯入)。
- 畫布物件模型照計畫 §3:**cell 是可拖節點**(拖離 gNB 位置 = DAS,放開才寫回 registry `position`)、gNB 為群組標記、UE 軌跡折線、建築方塊;`+gNB` 自動建 1 DU / 1 cell / 1 RU;cell 面板含天線 preset 下拉(寫 `ru.f_antenna_preset_uuid`)、pci / 頻率 / 頻寬 / 功率 / 方位 / **tilt**。
- **視覺未定**:先用中性白底、單一強調色;Polycam 式的極簡室內風格等你定方向再刻。
- 踩到:r3f 的 optional expo peer 讓 `npm install` ERESOLVE → `.npmrc legacy-peer-deps`;`@typescript-eslint` 7 + eslint 10 不相容(舊 Dashboard 同樣壞)→ eslint 9 + ts-eslint 8;`no-undef` 要放在 recommended 展開之後。
- 驗證:`tsc --noEmit` 乾淨、`next build` 全路由通過、lint 通過、compose `scene-editor-frontend` :3011 起來(`GET /scenes` 200,dev 模式 hot reload)。**畫布互動與資料寫回尚未在瀏覽器實測**(無瀏覽器環境)—— 請開 http://<host>:3011/scenes 試:點一個 corridor 場景 → 拖 cell → 看 registry 是否更新。
- 未做(P3-2 起):UE 軌跡/流量編輯、建築材質下拉、GLB/OSM 上傳表單、precompute 觸發、監控前端 repo。

## P3-2 監控前端骨架(2026-09-13)

**做了什麼**
- 新系統 `ran-emulation-runtime/ran-emulation-runtime-run-monitor-frontend`(Next.js 15 App Router、TS strict、同 scene-editor 工具鏈與 eslint 邊界規則),compose service `run-monitor-frontend` → **:3012**。
- **零控制**:services 只有 `*Reader/read`,沒有任何 start/stop/update 呼叫(§10.5)。
- 路由:`/runs`(run 清單,3 s 輪詢;DU 達成倍速)、`/runs/[id]`(① Full KPM per-cell + 可展 per-UE、② RIC 命令 + 命令前後 5 窗 PrbTotDl 對照、③ cell 狀態、④ E2 面(SCTP 連線/E2 node/設定→達成倍速)、換手/RLF、設定快照、起停紀錄,後三者預設收合)、`/compare`(最多 4 run,PrbTotDl 依 sim-time 對齊)、`/runs/[id]/playback`(視窗 slider)、`/runs/[id]/events`(run/HO/RLF/RIC 合併事件流)。
- 資料來源:registry `SceneRunReader`/`SceneReader`;orchestrator `RunKpmSampleReader`/`RunHandoverEventReader`/`RunControlEventReader`/`LaunchRequestReader`;DU `Tick/TickController/read`;E2Adapter `Status/AdapterStatusReader/read`。
- 圖表用內建 SVG `Sparkline`,不拉圖表庫(之後套深色工程風時再決定是否換)。
- `apiClient` 同時接受 `{success:true}`(registry/orchestrator)與 `{status:"success"}`(DU/RU 舊信封)。

**驗證**
- typecheck / lint 乾淨;`next build` 成功。
- 容器 `ran-run-monitor-frontend` 起來後 `/runs` `/compare` `/runs/<id>` `/runs/<id>/events` `/runs/<id>/playback` 皆 200(用已封存 run `scene_run-7de7da10…`,55 視窗)。
- 瀏覽器實測(10.3.0.217:3012)尚未做,與 :3011 一起等使用者測。

**未做 / 待辦**
- ② 的「命令前後對照」目前只比 PrbTotDl 平均;RIC 尚未連線所以 control_event 為空,等 P4 再對照真資料調欄位。
- ④ 的 DU/E2 狀態是全域讀(目前一個 DU),P4 多 run 後要改成依 run 的 container 讀。
- `wall_time_ms` 封存仍為 0(orchestrator 待補)。
- 兩個前端的深色工程風(下一步,一起套)。

## P3-3 深色工程風 + archiver 修正(2026-09-13)

**做了什麼**
- 兩個前端(scene-editor :3011、run-monitor :3012)改成深色工程風:深底 `#0b0f14` + 頁面淡格線、青色 `#4fd1ff` 主線 / 橘色 `#ff8a3d` 選取與強調、表頭大寫字距、狀態 pill 深色底亮字。兩個 repo 各留一份 `styles/globals.css`(共用 token 區塊相同,依規則不跨 repo import)。
- 3D 畫布:深色地面、格線 section 亮青色 / cell 暗藍、建築改**線框**(`<Edges>` + 8% 透明體)、cell / gNB / UE 標籤白字加深色描邊、gNB palette 換亮色、marker 常態自發光。
- 用 headless Chromium(playwright 容器)截圖確認兩頁(`scratchpad/editor.png`、`monitor.png`)。
- 順手在監控頁發現並修 `cu_archiver.py` 兩個 bug:
  1. 同一視窗內舊劇本殘留 cell 的 `tick_count=0` 覆蓋真值 → `sim_time_ms` 卡在 1000;改取視窗內最大 tick。
  2. 同一 `scene_run` 再次 start 時 `window_index` 從 0 重算 → 重複;改成從 DB 既有最大值接續。
  驗證:重跑 40 s,視窗 133→179 接續、sim_time 每窗 +1000。

**已知(留 P4)**
- CU 是全域表,`per_cell` 會混到其他劇本殘留 cell(本次看到 `src_c0`);CU per-run 才根治。
- 測試期間同一 run 被 start 多次,舊的重複視窗(window 0–54 三份)仍在 DB;這個 run 是測試資料,不清。

## P3-4 兩個前端依回饋重刻(2026-09-13)

**使用者回饋**:未置中;劇本要 label 分類;沒有可拉東西的畫布;天線 / RAN 參數要有管理頁;要能像舊 Dashboard 從網路拉場景;監控要 Prometheus+Grafana 式圖形化(PRB per cell、一個個 UE),原封數值是最後手段;要美觀。

**監控平台 :3012(commit 9a3ba83)**
- 置中 `shell`(max 1480);Grafana 式 12 欄 panel grid、stat tile 列(附著 UE / 平均 SINR / Σ 吞吐 / 平均 PRB / MCS / 換手+RLF / RIC 命令,含與上一窗差值、狀態色)、時間範圍 chips(1m/5m/15m/全部)、LIVE 徽章。
- 自製 SVG 圖表(不拉圖表庫):`TimeSeriesChart`(多序列、淡格線、hover 十字線 + tooltip、圖例、刻度數隨寬度)、`BarChart`、`ColumnChart`、`Sparkline`、`ServingStrip`。色彩用 dataviz skill 的深色類別色(固定順序、cell 依名稱對應),狀態色 good/warning/serious/critical。
- Panels:PRB DL/UL per cell、當下 cell 負載長條、每 cell UE 數、DL 吞吐 per cell、平均 SINR per cell、**RAN 模擬執行狀況**(UE driver 進度條、達成倍速、DU tick、UE 附著、E2 link、DU cell 表)、換手/RLF 每分鐘直條、SINR 直方圖、**UE 逐一觀測**(每 UE 一張 SINR 迷你圖 + serving cell 色帶 + 當下值;點選展開 6 指標時序)、RIC 命令、設定快照。每個 panel 有「表」切換 = 原始數值退路。
- `/runs` 有 stat 列 + 狀態 chips;`/compare` 每指標一圖、run 為序列;playback / events 沿用新元件。
- 新增 UE driver 狀態讀取 `UE/Scenario/ScenarioController/status`(env `NEXT_PUBLIC_UE_BASE_URL`)。

**管理平台 :3011**
- 置中 `shell`(max 1400);`/scenes` 依 legacy_scenario_id 前綴自動分類 chips(ANR / 走廊室內 / 意圖 CCO-IM-ES / 規模全天 / 手動 / 其他),卡片左邊框依類別上色、run 狀態 pill、啟動/停止/監控↗。
- 編輯器:左欄 **元件庫**(gNB / Cell 拉遠 / UE / 建築盒 → 放置模式 → 點地面建立,Esc 取消)、**地圖(OSM)**(地標 geocode → 選候選 → 抓 Overpass → attach 成 building source=osm)、物件樹;畫布地面接點擊、OSM 建築先畫 footprint 標記環(footprint 渲染留 Omniverse 階段);右欄分頁 **屬性 / 天線 / RAN 參數**:天線 = cell RU preset + 覆寫 JSON、UE preset;RAN 參數 = DU 模板選擇 + config_override、gNB A3(offset/hys/TTT)、Run 設定(mode/倍速/sim_dt/時長,無 run 自動建 draft)、Run knobs(9 種 key,JSON 或字串)。刪除物件。
- 新頁 `/network-elements`:天線陣列 / DU 設定模板 / 建築材質三個分頁,表格內嵌編輯列 CRUD(`/presets` 轉址)。
- 服務層新增:networkElements(updateDu/Building/Ue、create/delete)、presets(update/delete)、runs(runKnob CRUD、updateSceneRun)、geometry(geocode/generate/list/attach)。

**驗證**:兩邊 typecheck / lint 乾淨;headless Chromium 截圖 5 頁;throwaway scene 走 API:UE + waypoint(欄位是 `ord`,已修)、manual_box 建築、OSM attach(既有 ready asset)全部成功並清掉。真的抓 Overpass 未跑(外網、1–3 分鐘),請使用者在瀏覽器試。

## P3-5 gNB 模板 / 天線現場調整 / 監控 gNB→cell 圓環(2026-09-13)

**使用者回饋**:full KPM 是否都在;PRB 用圓環百分比、以 gNB 為單位再展 cell;「並看」難聽 → Runs 後面接模擬名稱分頁;網路元件要能管 gNB 參數(參考對齊 OAI 的設定)、給一組預設、場景現場套用只是快速填、現場可改、改完可存成/更新模板、天線同理;要不要 DB 管。

**Registry(DB 管,答案:要)**
- 新表 `preset_catalog_gnb_config_template`(name、source oai/custom、PLMN、A3 enabled/offset/hys/TTT、cell RF 預設 band/GHz/BW/dBm/tilt、cells_per_gnb、azimuth_step、FK → DU 模板、FK → 天線 preset);actor/serializer/URL 同 DuConfigTemplate 模式(`GnbConfigTemplateController/create|update|delete`、`GnbConfigTemplateReader/read`)。
- `gnb.f_gnb_config_template_uuid`(SET_NULL,記來源模板;現場改值不自動回寫);read_full_tree 帶 `config_template`。
- migrations `preset_catalog 0002`、`radio_access_element 0004`;`manage.py seed_presets`(冪等)建三組預設:DU 模板「OAI 對齊」(DDDDDDDSUU、μ1、106 PRB、min 5、PF 0.05、BLER 0.1、discard 300、HARQ 4)、天線「1×1 iso(OAI rfsim)」、gNB 模板「OAI 對齊預設」(208/95、A3 關 1/0.5/80、n78 3.5 GHz 40 MHz 23 dBm,綁前兩者)。

**管理平台**
- 元件庫放 gNB 時自動套「OAI 對齊預設」(source=oai 的模板):DU 綁模板、依 cells_per_gnb 建 cell(帶 RF 預設、方位步進)、RU 綁天線、gNB 帶 PLMN/A3。
- gNB 屬性頁頂端「gNB 模板」列:下拉套用(確認後覆蓋 PLMN/A3/DU 模板/每 cell RF/天線,之後仍可逐項改)、「現場存成新模板」、「更新模板『X』」(值取現場第一個 DU/cell/RU)。
- cell 天線分頁:preset 下拉 + **現場調整欄位**(pattern/rows/cols/極化/間距/增益)→「套用到此 RU(覆寫 antenna_override)」/「存成新 preset」/「更新『X』」/「清除覆寫」。
- 網路元件頁新增「gNB 模板」分頁(含 DU 模板、天線的參照下拉),預設頁籤。

**監控平台**
- 頂欄改成 Runs + 每個執行中 / 最近結束的 run 一個分頁(模擬名稱,執行中有綠點),「並看」改名「對照」。
- PRB DL/UL 改成 **gNB → cell 圓環板**:每 gNB 一列,列首 gNB 平均圓環,後面每 cell 一個圓環(色跟 cell、>85% 警示);gNB 對應由 registry read_full_tree 的 cell 名稱比對,對不到歸「其他」(舊劇本殘留 cell 會落在這)。走勢折線保留在下方。
- Full KPM 覆蓋:per-cell 新增 UL 吞吐、RLC SDU delay、平均 MCS;UE 細節新增 Thp UL、PDCP volume DL/UL 時序,以及 rank、5QI、PRB、鄰區 RSRP/RSRQ 列。至此 KPM 的每個欄位都有圖或位置。

**驗證**:migrate + seed OK;registry 讀回模板 OK;兩前端 typecheck/lint 乾淨;headless 截圖(dashboard 圓環板、gNB 模板列、天線分頁、網路元件 gNB 模板頁)。gNB 模板「套用 / 存成」按鈕有 confirm/prompt,未在 headless 走完,請使用者實測。

## P4-1 per-run 容器(2026-09-13)

**做了什麼**
- orchestrator 掛 `/var/run/docker.sock` + `docker` SDK;`PER_RUN_ENABLED=on`(compose 預設 on,可關回共用模式)。
- `run_lifecycle/services/optional/per_run_template.json`:由 `docker compose config` 產生的 cu/du/ru/ue 容器規格(image、env、bind mount 絕對路徑),host 名與 DB 名以 `{cu}` `{db_cu}` 佔位。
- `container_spawner.py`:`spawn(run, mode)` 建三個 DB `cu_<rid>/du_<rid>/ru_<rid>`(rid = uuid 後 8 碼)→ 起四個容器 `<role>-<rid>`(同 `ransim-net`,容器內 8000 → host 隨機 port,label `ransim.scene_run_uuid`)→ CU `GNB_ID_HEX` 每 run 不同、RU `RU_CHANNEL_MODE` 依 run.mode、env `SCENE_RUN_UUID`;`wait_healthy`(四個 HTTP 讀端點,最多 300 s);`teardown` 停+刪容器、DROP DB;`live_run_exists` 實作「live 同時最多 1 個」。
- `health_monitor.py`:每 run 一條 thread,每 5 s 看容器狀態 + HTTP → registry `run_instance.status / last_heartbeat`。
- `LaunchController.start`:validate → spawn → 寫 `run_instance`(role/container_id/host_port)→ 等健康 → UE driver(per-run 的 `ue-<rid>`)start → 狀態 running → archiver 指到 `cu-<rid>`;失敗自動 teardown。`stop`:UE stop(容器死了也照清)→ archiver stop → health stop → teardown → run_instance stopped → run stopped。
- UE loader 防呆:`default_serving_cell` 不在場景 cell 裡就退回第一個 cell 並 warning(舊劇本 corridor 寫 `src_c0` 但 cell 叫 `src` → 之前 UE 掛在幽靈 cell 上,CU 出現假 serving cell、DU PRB 永遠 0;監控頁看到的「其他 / src_c0」就是它)。
- 監控前端:讀 registry `run_instance`,有 host_port 就打該 run 的 DU/UE(`NEXT_PUBLIC_RUNTIME_HOST`),沒有就退回共用;RAN 執行狀況面板列出四個容器的 port / 狀態 / 心跳。

**驗證**
- corridor_16_24 per-run 起停:四容器 ~10 s 就緒(DB 新建 + migrate),run_instance 四列 running、心跳每 5 s 更新;stop 後容器移除、DB drop。
- **兩個 run 同時跑**(corridor_16_24 + corridor_00_08,皆 cached):各自 DU tick 獨立、封存各自視窗、cell 集合互不污染;host load ~2.0,每組 8 容器合計 < 500 MB。
- 幽靈 cell 修正後 per_cell 只剩 `src / nbr`;corridor_16_24 的 UE 在 5700 s 前不在場 → 開場 RLF 屬預期(T310,之後由 UE 端 re-camp 回來)。
- 監控頁截圖:per-run 容器列、DU tick、UE driver 進度均來自 `-49117e33` 這組。

**已知 / 待辦(P4-2 起)**
- **E2Adapter 仍指向共用 CU(:8101)**:RIC 看不到 per-run CU;要做多 E2 node 多 SCTP(先驗證 RIC 接受同 IP 多 node;目前 RIC 10.3.0.71 連線被 reset,無法驗)。
- CU `start_anr_fixture` 找 `/app/docs/scenarios/<id>.json` 404(corridor 系列 JSON 不在 docs/scenarios,只在 registry legacy store)→ CU 該改走 registry shim。
- 第二個 run 達成倍速 0.47×(設定 1×)需查(RU 2 個 gunicorn sync worker?)。
- 共用的 cu/du/ru/ue compose 服務仍在(legacy Dashboard 用);之後可拿掉。
- UDS/msgpack 傳輸(§11 決策②)未動。

## P4-1b E2 node 身分槽位(2026-09-13,回 RIC 端的可行性問題)

- RIC 端(e2mgr)以 E2 Setup 的 PLMN + gNB ID 推導 meid(`gnb_208_095_000e00`),同 ID 的 run 會互相覆蓋 → 每 run 必須唯一。
- 我們的身分本來就是 CU env(`PLMN_MCC/PLMN_MNC/GNB_ID_HEX/GNB_ID_LENGTH`)。改成確定性分配:PLMN 固定 208/95,gNB ID 22-bit 基底 `0x000e00`,**低 9 bit 當 run 槽位**(0x001–0x1ff,同時最多 511 run);orchestrator start 時從 registry 執行中 run 的 `gnb_id_hex` 反推已用槽位,取最小空位,寫回 `scene_run.gnb_id_hex / e2_node_id`(新欄位 + migration `simulation_run 0002`)。
- 實測兩個 run:`cu-49117e33` 宣告 `0x00000e01`(3585)、`cu-388e8e0a` 宣告 `0x00000e02`(3586),PLMN 208/095;registry 記 `gnb_208_095_000e01 / 000e02`。
- E2Adapter 多 node(每 run 一條 SCTP)仍待做(P4-2),需 RIC 端可連才能驗。

## P4-2 E2Adapter per-run(2026-09-13)

**決定**:不把 1529 行的單連線 `sctp_loop`(模組級 `_ACTIVE_SUBS` / socket lock / 狀態 singleton / ring)改成多 association,改成 **每 run 一個 adapter 容器** `e2adapter-<rid>`(host network,SCTP 綁 host IP、各自 ephemeral port;HTTP 8400+槽位),`SIM_CU_URL` 指到該 run 的 CU host port。RIC 端效果相同:N 個 run = N 條 association = N 個 E2 node(`gnb_208_095_000e0N`),訂閱/控制天然依 meid 分流。對 RIC 端的問題「adapter 一對一還是一對多」答:**一對一(每場景一個 adapter)**。
- `per_run_template.json` 加 `e2adapter`(佔位 `{cu_port}` `{e2_port}`);spawner 支援 `network_mode: host`、`roles` 子集、`cu_host_port`;`health_url` 對 host-network 容器走 `host.docker.internal:port`。
- **兩階段 spawn**:cu/du/ru/ue → 等健康 → 才起 e2adapter(adapter 起來就抓 CU 的 E2 node id 送 E2 Setup;CU 沒 ready 會抓失敗然後進 5 分鐘 backoff)。
- archiver 的 ControlAudit 改讀該 run 的 adapter;monitor E2 面狀態改依 `run_instance` role=e2adapter 的 port。
- registry `run_instance` 多一列 role=e2adapter。

**驗證**
- 兩個 run 同時:`e2adapter-49117e33`(:8401,CU :32796)送 E2 Setup ranName `gnb_208_095_000e01`;`e2adapter-388e8e0a`(:8402)送 `gnb_208_095_000e02`;各 `pdu_sent_count=1`。
- RIC(10.3.0.71:36422)目前對所有 association 都 `Connection reset by peer`(含原本共用 adapter),所以 E2 Setup Response / 多 node 註冊 **尚未驗證**,要等 RIC 端修好。

**待辦**
- 停 run 時先送 E2 Reset / 關 association 再停容器(現在是容器 SIGTERM 直接斷)。
- 共用 `e2adapter`(gnb_…000e00)仍在 compose 裡,會多註冊一個 node;RIC 可連後決定是否拿掉。
- adapter backoff 5 分鐘(RIC m-release bug 對策)在 per-run 情境下可能太長。

## P4-3 達成倍速 0.47× 的真因:共用 `.mode` 交接檔(2026-09-13)

- 現象:第二個 run(corridor_00_08,設定 1×)在第一個 run 起來後瞬間量到 0.47×。
- 真因:RU 在 `/data/channel_cache/.mode` 寫 `cached:<scenario_id>`、DU 每 tick 讀它決定用哪個 npz;這個目錄是所有 run 共用的 bind mount,所以 run1 的 RU 一寫 `cached:corridor_16_24`,run2 的 DU 就把 cache 切成 corridor_16_24(log 實證 `DuChannelCache loaded: scenario=corridor_16_24` 出現在 du-49117e33),重載 npz 讓 tick 停頓 ~1 s → 該秒的 achieved 掉到 0.47×,**而且之後 run2 一直用錯的通道**。這是跨 run 汙染 bug,不是效能問題。
- 修法:DU / RU 的 `MODE_FILE` 改可由 env `CHANNEL_MODE_FILE` 指定;orchestrator 對同 run 的 du/ru 設 `/data/channel_cache/.mode.<rid>`。舊共用 `.mode` 只剩 legacy 共用容器在用。
- 驗證:兩 run 重起後 `.mode.49117e33 = cached:corridor_00_08`、`.mode.388e8e0a = cached:corridor_16_24`,各 DU 只載入自己的 cache(各一行 loaded);20 s 取樣 run2 ≈ 1.0×(0.89–1.11,量測窗 1 s / 2 tick 的粒度抖動)、run1 ≈ 2.0×。
- 教訓:P4 之前「共用目錄上的狀態檔」都要檢查;目前已知只有這一個。

## P4-4 傳輸層(②)實測後決定不做(2026-09-13)

- DU `TickController/read` 新增 `body_ms {avg,max}`(tick body wall 耗時,近 1 s 視窗),serializer 補欄位。
- 掃 wall_tick 250 → 50 → 15 ms:達成 2.0× / 10.0× / **22×**,body avg 16 ms、max 33 ms。HTTP 已不在關鍵路徑(`dl_tti` 非阻塞),瓶頸是 DU 自身計算 → §11.3 的 63 ms / 7–8× 估計作廢,寫成 §11.8。
- **決定:UDS/msgpack 不做**;要更快是 profile tick body,另開題。

## P4-5 cell 識別碼跨場景唯一(2026-09-13,回 RIC 端 ③)

- RIC 端盤點 dt-anr-xapp:27 個狀態欄位以 (src, dst) 等 cell 字串當鍵、沒有場景維度;registry 裡 53 個 cell 名跨場景重複(`gnbDT_c0` ×24、`src` ×5…),並行必撞(最嚴重 `_guard_cooldown` 會把後者永遠噤聲)。
- 做法:sim 對外 cell_id 一律 **`<tag>:<name>`**,tag = 該 run gNB ID 低 12 bit(`e01`),與 E2 node `gnb_208_095_000e01` 同源。
  - 加標籤只在 UE loader(所有 cell 字串唯一源頭):cells、default_serving、cell_quotas;env `CELL_ID_TAG` 由 orchestrator 設。
  - 剝標籤只在 cell → 物理 tx 名的轉換點:DU `channel_cache_du.cell_id_to_tx`、RU `payload_builder._cells_grouped_by_gnb`、UE `cell_selection.to_cu_cell_id`(用剝掉的名字比對、回完整 id)。
  - helper 在 `ran_sim_protocol/cell_tag.py`;UE image 沒掛 protocol 套件,所以 UE 內有一份同語意的 `ue_lifecycle/services/cell_tag.py`。
  - 監控 gNB 分組比對時剝標籤;封存與 E2 原樣帶標籤。
- 驗證:兩 run 同時 → DU cell `e01:src / e01:nbr` 與 `e02:src / e02:nbr`;UE attach 18/18 到 `e01:src`;cached SINR 43–55 dB(npz 對應沒斷);封存 per_cell / serving 都帶標籤;0 RLF。
- SCTP:host 上 `association_max_retrans` 已掉回 10,需重跑 `RANsim-E2Adapter/shell/host_setup_sctp.sh`(root),已請使用者跑。

## P5-1 天線落地:registry preset / tilt → RU → Physics(2026-09-13)

**做了什麼**
- 協定 `CellSpec` 加 `tilt_deg`(正 = 往下)、`power_dbm`。
- Physics:`SionnaEngine` 吃陣列間距與每 cell tilt、提供 `antenna_signature()`;`SionnaBusinessService.ensure_antenna()` 比對請求的 `tx_config.antenna_array / rx_config.antenna_array / cells[].tilt_deg`,不同就用同一份幾何重建 engine(~1–4 s);`PathSolver/compute` 每次請求都會走這個檢查(env `PHY_ANTENNA_FROM_REQUEST=off` 可關)。陣列是 scene-global(Sionna 限制),tilt 是 per-cell。
- RU:`Cell.tilt_deg`、`AntennaConfig.ue_rows/ue_cols/ue_pattern/ue_polarization`(migration antenna 0005),`update_cells` 收 tilt、`build_tx_config` 帶 tilt/power、`build_rx_config` 用 UE 陣列。
- UE:loader 從 registry 樹取 cell 的 RU preset(第一個 cell 的當整個 run 的 gNB 陣列,不同會 warning)、UE preset、cell tilt;scenario driver 在 scene-apply 前一律 `RU update_antenna`(沒 preset 給 1×1 tr38901 V —— 以前 live mode 沒人設 AntennaConfig,RU 會 raise);Physics push_scene 也帶完整 `scene_antenna_config`。
- **Transmitter orientation 修正(重要)**:自由空間 + `look_at` 實測,本場景 Y-up、Sionna orientation=[α(繞 z),β(繞 y),γ(繞 x)],舊碼把羅盤方位直接塞 α,實際是把扇區「轉成仰角」。改成解析式反推(boresight = Rz(α)Ry(β)x̂,d = (sin az·cos t, −sin t, −cos az·cos t) → β = −asin d_z, α = atan2(d_y, d_x)),β=±90° 奇異點微推。驗證:az 90/180/0/270/135 各自朝東/南/北/西/東南最大;tilt +10/+20/+35 讓下方 35° 的 UE 逐步 +1.8/+3.0/+3.7 dB,−10 反向。env `PHY_ORIENTATION_MODE=legacy` 可切回舊行為(只給對照舊 cache)。

**驗證**
- Physics 直打:1×1 → 2×2 cross → 4×4 V + UE 1×2,H 形狀 (1,1)→(1,8)→(2,16),重建 0.5–4 s;同設定不重建。
- 整條鏈(live per-run run,anr_nrt_capacity):registry 掛 2×2 cross preset + n60_c0 tilt 10 → UE `update_antenna gnb 2×2 cross` → RU cells `e03:n60_c0 tilt 10` → Physics `rebuilding … cross 2×2 … tilts {'n60#191': 10.0}` → `antenna config applied`。測完已還原場景、刪測試 preset。
- 順帶:live 模式 DU body ≈130 ms(Sionna 光追)→ live 上限約 2–3×,cached 才有 20×。

**發現(P5-2 要做)—— 座標系**
- Mitsuba 場景與所有位置都是 **Y-up**(ground cube scale (500, 0.1, 500)),但 Sionna 假設 **z-up**:天線 pattern 的「垂直面」與 **V 極化軸都躺在水平面上**(V = 我們的南向)。方位/仰角靠上面的解析式已對,但極化(cross 的 H/V、V-only 的 null,例如 az=180 時下方 UE −200 dB)與 3GPP pattern 的上下切面仍是錯的。
- 正解:engine 邊界做座標旋轉 —— 位置 (x, y, z)_ours → (x, −z, y)_sionna,幾何載入時對每個 shape 加 `<rotate x=1 angle=90>`(或 builder 直接輸出),H / path_gain 不受影響。做完後 α 就是方位、β 是仰角,polarization 才有意義。**會改變所有 live / precompute 的數值**,既有 npz cache 都是「天線側躺」算出來的,要重算。
- 另:`PHY_PATH_GAIN_PER_PORT` 仍 off(4×4 的 path gain −83.7 dB 比 1×1 −98.7 高 15 dB 是元素相加),MIMO 多層(§5 第 5–7 項)未動。

## P4-6 E2 association 生命週期對時(2026-09-13,回 RIC 端)

- 對時:我方 06:34:29/39/49 UTC 送三個 Setup(000e00/e01/e02),RIC 端 e2mgr 記 06:07:29/39/49(其時鐘慢 27 分),但標 CONNECTED 在 06:12:47/06:13(≈5 分鐘後);我方 adapter 等 Setup Response 只等 30 s 就關 association、5 分鐘後重連 → Response 回到已不存在的 association。
- 改:`E2_SETUP_RESPONSE_TIMEOUT_SEC`(env,per-run 與共用皆 600)、`SCTP_BACKOFF_*` 縮到 20 s;adapter 收 SIGTERM 先送 E2 Reset、shutdown SCTP 再結束(`graceful_shutdown`),對應 RIC 要求的「先 Removal/Reset 再關關聯再停容器」;association 關閉時記 log。
- 06:44:40 / 06:44:41 / 06:45:3x 重連後,**三條 association 同時 ESTABLISHED 持續 >9 分鐘**(`/proc/net/sctp/assocs` state 3,lport 49749/34211/47478 → 36422),Setup 各送一次,但到 06:53:50 仍無 Setup Response(pdu_recv 0)。球在 RIC 端:請他們在這三條活著的關聯上核對 association↔ranName 綁定與 Response 是否送出。

## P4-7 多 E2 node 三方驗證通過(2026-09-13)

- RIC 端根因是他們的 rtmgr 推不到 e2mgr(RMR 路由表空 → Setup Response 建好送不出),07:09 修 rtmgr 後:三個 node 同時 CONNECTED、E2T associatedRanList 三個、對三個 meid 各發 REPORTCGI 控制 state=0 + ACK。
- 我方 07:15:41 / 07:15:41 / 07:16:20 UTC 收到 `E2 Setup outcome=successfulOutcome accepted=[2,3,4,6,5]`(e01 / e02 / 共用 e00);07:16:36 三邊各收一筆 `RICcontrolRequest style=9 (REPORTCGI)`,`RIC_CONTROL_ACK sent`,adapter 稽核記 `result=e01:nbr`(帶 run 標籤的 cell)、rtt 14 ms。三條 SCTP association 持續 ESTABLISHED。
- 修 archiver:E2Adapter `ControlAuditReader` 回 `{commands:[…]}` 不是 list,之前一筆都封存不到;現在對映 command→action_type、result→target、acked→ACK、rttMs→landing_latency_ms。既有 seq=1 那筆在 prime 之前,不回補;下一筆控制起會進 `run_control_event`(監控頁「RIC 命令」面板)。
- orchestrator 啟動時自動接回 status=running 的 run 的 archiver / 健康輪詢(以前重啟 orchestrator 會丟)。
- 結論:P4 的驗收條件「兩個不同場景同時跑、RIC 看到兩個 E2 node、KPM/控制互不干擾」達成。剩:共用 cu/du/ru/ue/e2adapter(000e00)退場時機、E2 Removal(目前用 E2 Reset + 關 SCTP 收尾)。

## P4-8 收尾改送 E2 Removal(2026-09-13)

- Reset 是「連線重來、訂閱清掉、我還在」,Removal(E2AP v2 §8.3.9,本 schema procedureCode 13)才是「我要下線,請移除」;用 Reset 收尾 RIC 端仍會留 DISCONNECTED 殘留,而且槽位重用時會踩到 m-release「stale record → 5 分鐘」路徑。
- 加 `encode_e2_removal_request()`(唯一 IE TransactionID;往返自測 13 bytes);`graceful_shutdown` 先送 Removal、等回應最多 2 s、失敗才退回 Reset(env `E2_SHUTDOWN_PROCEDURE=reset` 可強制舊行為)。
- 實測:`docker stop e2adapter-388e8e0a` → 08:00:15 UTC 送出 Removal Request(13 bytes),2 s 內 RIC 沒回 Response;重新 spawn 後 08:00:40 Setup 再成功。RIC 端是否有處理 Removal(R-NIB 移除 `gnb_208_095_000e02`)待他們確認。
- 共用 cu/du/ru/ue/e2adapter 先不退場(使用者決定)。

## P5-2 Physics 座標系轉 z-up(2026-09-13)

- 新增 `ran_calculation/frame.py`:engine 邊界做 Rx(+90°)—— 位置 ours (x,y,z) → Sionna (x,−z,y)(tx / rx / 速度);Mitsuba XML 載入時對每個 shape 的 `to_world` 補 `<rotate x=1 angle=90>`(相對檔名改絕對)寫暫存檔,既有場景檔不用重產。env `PHY_FRAME=zup`(預設)| `yup`(舊行為)。
- orientation 回到單純定義:α = 90° − 羅盤方位、β = +tilt(正 = 往下),與 z-up 空場景 `look_at` 完全一致(E→0,0;S→α=−90;N→+90;下方 35°→β=+35.5)。
- 自由空間驗證:**極化** V→V −65.6 / V→H −336 / H→H −65.6 dB(以前躺平時 V 極化沿南向,分不出 V/H);**方位** az 90/180/0/270 各朝東/南/北/西最大、135 東南;**下傾** az=90 與 az=180 行為一致、單調(+35 → 下方 UE +3.5 dB),az=180 不再有 −200 dB 假 null;**幾何** 東 20 m 放 10×15×10 建築,正後方 UE −19.5 dB、側邊不變 → 幾何與位置轉的是同一個框架。
- 影響:所有 live / precompute 數值改變。現有 cached run 只有 corridor 四份(方位 0°、1×1 V,誤差幾 dB 級),舊檔改名 `*.legacyframe.npz` 留對照,重算四份;其他 25 份舊 npz 沒 run 在用,歸檔。
- corridor cache 重算:舊四份改名 `*.legacyframe.npz`(容器內 root 才能寫 data 目錄);`corridor_24h` 以 z-up 框架重算中(`run_precompute_segmented.sh corridor_24h 10000`,SCENARIO_STORE_URL 指 registry shim;`update_status` 404 只是警告)。踩到兩個坑:① `--resume` 接到舊框架的 checkpoint、② `pkill -f` 沒殺到 python 行程造成兩個行程同寫 ckpt —— 已全部砍掉、刪 ckpt 從 0 重跑。前 35000 tick UE 不在場所以 ~800 t/s,之後 ~5 t/s,ETA ≈ 7.5 h;完成後用 `carve_window.py` 切 00_08 / 08_16 / 16_24 三份。

## P5-3 多天線:per-port 增益 + rank 真的動起來(2026-09-13)

- Physics `PHY_PATH_GAIN_PER_PORT` 改 env_loader、預設 on(compose 也改 on;注意 `docker compose restart` 不重讀 env,要 `up -d`)。驗證:1×1 / 2×2 / 2×2cross+1×2cross 的 mean|H|² 都是 −74.2 dB,回報 pg −72.6 / −72.6 / −75.3(以前 4×8 會 +12 dB 假增益)。
- 通道本身:z-up 框架下 2×2 cross + 1×2 cross 自由空間 H(4×8) 第二奇異值 −4.7 dB(cross-pol 兩個正交通道),有建築時 4 個奇異值 −11.5 / −27.7 / −34.5 dB。
- 兩個讓 rank 卡在 1 的斷點:① RU 在「已用 DU 目前層數預編碼」的 H_eff 上估 rank → 永遠回 DU 給的層數;改成看未預編碼的 H,上限 min(rx,tx,4)。② DU 收 cqi 只寫 sinr,從沒把 RU 回報的 rank 寫進 UE registry;補 `update_ue_sinr(rank=)`。
- per-run DU env `NR_MIMO_LAYERS_ENABLED=on`(TBS × ν,每層等功率分配 → 每層 SINR −3 dB)。
- 整條鏈驗證(live,anr_nrt_capacity):registry 掛 2×2 cross gNB preset + 1×2 cross UE preset → KPM `mimo_rank=2`(5/5 UE,之前 1×1 基準全是 1)。吞吐沒明顯變:這個場景 UE 幾乎沒流量(thp 0–1 Mb/s)、SINR 2–9 dB 兩層各 −3 dB 也撐不起高 MCS —— 要看多層增益得用高流量、高 SINR 的場景。
- 仍未做(§5 第 7 項):RU 回 per-layer SINR 陣列 → DU 做完整 EESM;目前每層 SINR 是等功率分配的近似。

## P5-4 每層 SINR + EESM(計畫 §5 第 7 項,2026-09-13)

- 協定 `CqiIndication.sinr_per_layer_db`(空 = 舊 RU,DU 退回等功率近似)。
- RU:由未預編碼 H 的奇異值算每層 SINR:第 i 層 = 總 SINR − 10log10(rank) + 20log10(σi/σ1)。
- DU:serializer / actor / registry(`ue["sinr_layers"]`)接下來;`eesm.effective_sinr_for_layers(sinr, n, sinr_layers, mcs)` 有每層值就 `combine_db`(EESM,β 依目前 MCS,無 MCS 用 10)壓成等效 SINR,否則等功率近似;pf_scheduler 與 slot engine(`SlotParams.sinr_layers / mcs_hint`)兩個呼叫點都接上。DU 每 50 筆多層 cqi 印一次 INFO。
- 實測(live,2×2 cross + 1×2 cross):`cp0 rank=2 sinr=6.0 layers=[2.97, −1.83]`、`cp4 sinr=1.7 layers=[−1.34, −4.49]` —— 第二層比第一層弱 ~4.8 dB,與自由空間 cross-pol 的第二奇異值 −4.7 dB 一致;KPM rank=2。

## P5-Q2 場景層級天線(2026-09-13)

- Sionna tx_array / rx_array 是 scene-global → 一個 run 只能一組 gNB 陣列、一組 UE 陣列。registry `scene.f_gnb_antenna_preset_uuid / f_ue_antenna_preset_uuid`(migration scene_layout 0003),read_full_tree 帶 `gnb_antenna_preset / ue_antenna_preset`;UE loader 優先用場景層級,沒設才退回「第一個 cell 的 RU preset / 第一個 UE 的 preset」。
- 編輯器:未選物件時「天線」分頁顯示場景層級兩個下拉。API 往返驗證 OK。

## P6 上行鏈路(2026-09-13)

- RU `dl_tti_pipeline`:整批算完 DL 後第二趟算每 UE 的上行 SINR@serving gNB:TDD 互易 pg(UE→gNB)=pg(gNB→UE)(RU 已有每 UE 對每 cell 的 path gain,零新光追);UE 開迴路功控 P_perPRB = min(P_CMAX − 10log10 M_ref, P0 + α·PL)(env `RU_UL_P0_DBM=-90 / RU_UL_ALPHA=0.8 / RU_UL_PCMAX_DBM=23 / RU_UL_M_REF_PRB=10`);gNB 每 PRB 雜訊 −113.4 dBm(NF 5);干擾 = Σ 其他 cell 的 UE 功率 × 它到我 gNB 的 pg × ρ(`RU_UL_NEIGHBOR_LOAD`,預設 0.5;inter_freq 時只算同頻)。
- 協定 `CqiIndication.ul_sinr_db`(None = 舊 RU);DU registry `ul_sinr_db`;UL 鏈路適應改 `sinr_to_mcs(ul_sinr)`(同一張 OAI BLER 曲線),舊 RU 退回 DL − 20 dB。以前是 `mcs_ul = mcs_dl − 2`、bps 用 DL SINR。
- 實測(live anr_nrt_capacity):`cp0 dl=6.4 ul=6.2 dB`(功控補償後接近 DL,合理);UL 流量 0.31 Mb/s、serving cell `prb_pct_ul` 19.8%,其他 cell 0。
- 近似 / 待做:ρ 是常數(RU 不知各 DU 的 UL 排程),之後可由 DU 把每 cell UL 負載推給 RU;UL rank 固定 1;UE↔UE 直接干擾(動態 TDD 交叉鏈路)不做。
- ⚠ corridor_24h 重算在 P5-3/P6 期間被我幾次 `docker compose restart/up -d physics` 殺掉(precompute 是 `docker exec` 進 physics 容器跑的,容器一重啟就沒了),停在 40000 tick;已用 checkpoint 續跑(0–40000 也是新框架算的)。**重算期間不要重啟 physics**;長期應把 precompute 放獨立容器。
- P6 補完:DU 每 tick 把「上一 tick 每 cell UL PRB 負載」放進 `DlTtiRequest.cell_ul_load` 推給 RU,RU 落 `Cell.ul_load`(migration antenna 0006;多 worker 不能放全域),上行干擾的 ρ 改用真值(沒推才退 env 常數)。實測 RU 收到 `n62_c0 0.189 / n77_c0 0.151`;此場景雜訊受限,UL SINR 不變(6.2 dB)。

## P5-2 續:corridor cache 第一次重算結果與方位修正(2026-09-14)

- corridor_24h 第一次(z-up)重算 09-13 21:42 完成(172800 tick,最後段 433 s)。與舊框架比:mean +10.2 dB、|diff| p50 25 dB、p95 57 dB —— 遠大於預期的「幾 dB」。
- 原因:走廊沿 z 軸(UE z −16…30,src 在 z=−14、nbr 在 z=+28),兩個 cell 方位都是 0。舊框架 az=0 = boresight +x(橫向、對著牆);新框架 az 是羅盤(0=北=−z)→ src 朝 −z **背對整條走廊**、nbr 朝 −z 面向走廊。舊劇本作者沒有用羅盤語意想 azimuth(0 = 沒指定)。
- 修:registry 5 個 corridor 場景的 src cell azimuth 改 180(朝 +z 面向 UE),nbr 保持 0;shim 讀回已反映。第一次算的檔留成 `corridor_24h.az0.npz` 對照;從 0 再跑一次(ETA ~8 h)。
- 教訓:匯入舊劇本時 azimuth 語意要對:羅盤(現行,編輯器也這樣畫)。其他 anr_* 場景 azimuth 是 90/270 等,是有意識設定的,語意應同羅盤(要不要逐一核對留待重算 anr cache 時)。
- `carve_window.py` 需要 `/tmp/<sid>.json`(劇本),切窗時從 registry shim 先存一份。

## P7-1 預算(precompute)獨立容器 + 管理平台按鈕(2026-09-14)

- orchestrator `PrecomputeController/start|stop`、`PrecomputeReader/read`:每個 run 起一次性容器 `precompute-<rid>`(physics image、同 bind mount、GPU device request、`SCENARIO_STORE_URL` 指 registry shim),跑 `run_precompute_segmented.sh <legacy_scenario_id>`;registry `scene_run.status` draft/pending/failed → **precomputing** → 容器 exit 0 且 log 有 `status=ready` → **ready** + `cache_path`,否則 failed(notes 帶最後幾行)。watcher thread 每 15 s 看。
- 進度從 `<sid>.precompute.log` 解析(tick / % / rate / ETA);orchestrator 以唯讀 bind mount `Physics_sim/data/channel_cache → /data/channel_cache` 讀。第一次踩到「讀容器 stdout 只有 NGC 授權 banner」。
- 管理平台 `/scenes`:cached 且未預算 → 「預算」按鈕;precomputing → 進度條(每 10 s)+「停止預算」;cached 未預算時「啟動」灰掉。
- 驗證:dt_2m(1200 tick,UE 靜止 → 1.7 s)走完 start → precomputing → ready,cache_path 寫回;測完還原成 live/draft。
- 限制:precompute 仍經 registry 的舊劇本 shim 讀劇本,**手動建的場景(沒 legacy_scenario_id)還不能預算** → 下一步讓 run_precompute 直接讀 read_full_tree。
- P7-1 補:registry 舊劇本 shim 的 `scenario_id` 也認 `scene_uuid` → 手動建的場景(沒 legacy id)也能預算,cache 檔名用 scene uuid。臨時場景(1 gNB / 1 UE / 60 s)走 start → ready 驗證通過,已清。

## P4-9 RIC 場景閘道對接(2026-09-14)

- RIC 端(ric-scenario-gw 0.3.0)模型:**一 scene_run 一 pod,pod 訂閱該 run 全部 meid;meid→scenario N:1(409 meid-already-bound)**。我方一個 run 只有一個 CU = 一個 meid,所以 nodes[] 永遠一筆(nodeId "cu");他們例子裡把 e01/e02 當同場景兩個 gNB 是誤解(那是兩個不同 run)。已回答他們三題:同 run 內跨 gNB 換手 / 鄰區 / 重建 PCI 都在同一個 meid 的 indication 裡(實證:一個 node 的 servingCells 同時列 e01:src 與 e01:nbr,HO 表 target e01:nbr)。
- orchestrator:`RIC_GATEWAY_URL` 設了就 start 時 `POST /v1/scenarios`(scenarioId=scene_run_uuid、labels.scene_name、profile、nodes[{cu, meid}]、ranFunctions [2,3,4,5,6]、controlPolicy),stop 時 `DELETE /v1/scenarios/{id}`(他們沒列,404 只記 log)→ `POST /v1/rnib/clear`(PLMN TBCD 02F859、gnb_id 22-bit);`GET /v1/nodes/{meid}` 留給監控。沒設 URL 就只記 log(閘道尚未上叢集)。
- 待 RIC 端:pod 部署 API(RBAC)、dt-anr 重連自癒、閘道部署 + URL。
- 順帶:CU ANR indication 裡有一個 `default-cell-0` 幽靈 cell(CU 內部佔位),之後清。
- 閘道上線 `http://10.3.0.71:30990`(叢集內 `ric-scenario-gw.ricplt:8080`)。收尾改為 E2 Reset → 關 SCTP → 停容器 → **DELETE /v1/scenarios/{id}**(一次釋放 meid 綁定 + 清 R-NIB 三樣);只有 DELETE 沒清成(404 / cleared:false)才補 `/v1/rnib/clear`。node 帶 `plmnId` / `nbIdBits`(第二把 R-NIB key 用)。profile 白名單:anr(預設)/ fullkpm / kpm / rc / ccc。
- 實測:run2 stop → 第一次 DELETE 404(從未註冊)→ 補清成功(deletedRanKey/GnbKey true);start → POST 201,閘道 `GET /v1/nodes/e02` 回 scenarioId、`GET /v1/scenarios` 現查 CONNECTED、subscriptionCount 2。run1 已補註冊。dt-anr 0.1.30-v10 重連自癒實測 67 s。
- RIC ②③ 上線後:start 在註冊後加 `POST /v1/scenarios/{id}/xapp`(best effort);orchestrator 新增 `RicObservationReader/read`(閘道 scenario + node 視圖,給監控頁)。實測 xApp 部署回 422 `k8s-create-failed`:Service 名 `service-ricxapp-dt-scn-scene-run-<32hex>-rmr` 超過 k8s 63 字元上限 —— 閘道只做了小寫/連字號正規化沒截短,已回報 RIC 端(建議 hash 截短);他們修好後不用改我方程式。plmnId/nbIdBits 改可省略(閘道自己查 e2mgr),我方帶著也可。
- RIC ②:閘道名稱長度已修(超長接 8 碼雜湊),但 dt-anr xApp 身分寫死(XAPP_NAME 常數、不讀 SCENARIO_MEIDS)→ per-scenario pod 起不來。/xapp 呼叫改成 env `RIC_GATEWAY_DEPLOY_XAPP`(預設 off),他們參數化後改 on 即可;現在共用 dt-anr 實例 + 閘道註冊/控制/清理照常。

## P5-5 azimuth 核對(2026-09-14)

- 新 registry 指令 `manage.py audit_azimuth [--only <prefix>] [--fix-centroid <prefix>]`:每 cell 的羅盤 boresight 與 UE 質心的夾角(≤90 OK / 側向 / ≥135 背對)。
- 164 個 cell 核對結果:
  - **anr_\*(14 場景)**:方位 90/270,羅盤語意下大多正對 UE(0–47°);舊框架下 270 的那些其實一直對著反方向(171–180°)→ 改正後**更對**。少數背對的(s11/f55/f61/h2/s28/tmp/s01)是劇本設計(harmful/stale/unknown/異頻遠端 cell),不動。
  - **corridor(5)**:已改 src=180,現在 3–4°。
  - **cco_1hr / im / es(兩扇區 c0=0, c1=180)**:一個扇區面向 UE、一個背對,是合理的兩扇區站,不動。
  - **dt_\*(12)、cco_20min、full_day_\*、kpm_compare、recover_\*(共 19 場景)**:兩個 cell 都 0°(作者沒做扇區),羅盤下側向/背對 UE(108–180°);舊框架同樣是共指 +x(39–162°)。建議 `--fix-centroid` 把它們指向 UE 質心(維持共指、恢復「無扇區」的意圖)。
- 對 dt_* / cco_20min / full_day_* / kpm_compare / recover_* 共 19 場景執行 `--fix-centroid`:全 0° 的 cell 改成指向 UE 質心(依 cell 自身位置);修後全部 OK(≤90°)。這些場景的 cache 用到時再預算。

## P4-10 訂閱刪除 + xApp pod 開關(2026-09-14)

- RIC 端回報:拆 xApp 後 gNB 仍對已刪訂閱送 indication(RMR_ERR_NOENDPT 14–29/s,四筆孤兒)。查我方 adapter:收到 `RICsubscriptionDeleteRequest`(procedureCode 9)只印 TODO,不停 producer、不回 Response。
- 補 `_handle_sub_delete`:依 RICrequestID + RANfunctionID 停掉所有 producer(含多 action 的 `-a<id>` 變體)、刪 sim CU 訂閱、回 `RICsubscriptionDeleteResponse`(codec 新增 encode/decode,往返自測 22 bytes);找不到也回成功(冪等)。事件記 ring `sub_delete`。
- 三個 adapter 重啟以清掉既有孤兒 producer(RIC 端 xApp ≤90 s 自癒重訂)。
- dt-anr 已參數化(XAPP_NAME / SCENARIO_ID / SCENARIO_MEIDS…),閘道 0.5.7 拆除零殘留 → `RIC_GATEWAY_DEPLOY_XAPP` 翻 on:之後每個 run start 會部署專屬 pod。

## P6-3 監控頁補上行 / 每層 SINR(2026-09-14)

- per-UE KPM 鏈新增四個欄位 `mcs_ul`、`rb_width_ul`、`ul_sinr_db`(gNB 側上行 SINR,可 null)、`sinr_layers_db`(每層 SINR 陣列,rank 1 為空):
  - 協定 `GnbDuMeasurementReport` 加欄位(預設 0 / None / [],舊 DU 不帶也相容)。
  - DU `pm_aggregator` per-UE 視窗累加 ul_sinr 平均、保留最後一筆每層陣列;`tick_runner` 由 registry(`ul_sinr_db` / `sinr_layers`)餵入並填報告。
  - CU `MeasurementLog` 加欄位(migration 0018),serializer / router 寫入 / telemetry export `_TABLES["measurement"]` 同步;orchestrator `cu_archiver` per_ue key 加入。
  - 監控前端:`UeKpm` 型別、`UE_METRICS` 新增 UL SINR / MCS UL / PRB UL 三張時間序列圖(MCS/PRB 標籤改 DL/UL 區分)、UeDetail 顯示 PRB DL/UL、UL SINR、每層 SINR;原始表加 UL 欄。
- 部署:三個 CU(ransim-cu、cu-388e8e0a、cu-49117e33)套 migration 後重啟 CU/DU/orchestrator。migrate→restart 之間舊 CU 程序對新欄位寫 null 出現短暫 IntegrityError,重啟後歸零。
- 驗證:cu_388e8e0a 的 measurement_log 與 orchestrator 歸檔 per_ue 皆帶 `mcs_ul` / `rb_width_ul` / `ul_sinr_db`(例 p06:mcs_ul 8、PRB UL 12、UL SINR 2.44 dB)。`sinr_layers_json` 目前皆空:兩個 run 的 UE 都是單天線 rank 1,屬預期。run 49117e33 的 RU/UE 是 36 小時前起的舊程序,尚無 UL SINR(mcs_ul 0、ul_sinr null),等 corridor 重算完重啟該 run 即會補上。

## 事故:e01/e02 自 14:55 UTC 停送 indication(2026-09-15 修復)

- RIC 端回報 e01/e02 從 2026-09-14 14:55:41 UTC 起對所有 xApp(含 sim 自己的 scene pod)停送 indication,訂閱回 ErrorSource=E2Node。
- 根因:我方為套 CU migration 0018 做了 `docker restart` CU/DU,per-run 容器的 host port 是 `ports={"8000/tcp": None}` 隨機分配,restart 後重配(cu 32917→32922、32845→32923)。adapter 走 host network、`SIM_CU_URL` 在 spawn 時烤進 env,仍指舊 port → producer 打 CU 全部 connection refused,新訂閱在 sim 端建不起來就回拒。RIC 端無誤。
- 修復:(1) 依原 config 重建兩個 adapter,SIM_CU_URL 指向新 port(16:0x UTC 起兩顆恢復送 indication,CU 呼叫失敗 0);(2) registry `run_instance.host_port` 同步 cu/du 新 port(監控前端 per-run DU 讀數用);(3) spawner 改為 `_free_host_port()` 明確綁定 host port,之後 `docker restart` 不再變 port。
- 教訓:per-run 容器要換程式碼一律走 orchestrator 的 stop/start,不要手動 `docker restart`。
- RIC 端確認(2026-09-15):e00/e01/e02 全面恢復,scene pod 只收 e02(隔離正常),NOENDPT 0、自癒觸發 0。
- 待辦(源自此事故):adapter status 端點加 sim CU 可達性 / 最近 CU 呼叫失敗時間,orchestrator health monitor 納入並在監控頁標示 run 異常;否則「SCTP CONNECTED 但資料不來」沒有任何一端會主動發現。
