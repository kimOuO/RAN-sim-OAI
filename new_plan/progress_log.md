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

## P4-11 依賴鏈健康監控 + precompute 狀態回寫收斂(2026-09-15)

- registry `run_instance.health_detail`(migration 0003):status 新增 `degraded`,detail 記原因。
- orchestrator `health_monitor.dependency_issue(role, data)`:health 端點不再只看「回得來」,改解析回應——e2adapter 看 `sctp_link.connected` 與 `sim_bridge.last_error`(adapter 每次打 sim CU 失敗都會記,60 s 無新錯自動清);UE 看 `attach_failed` / `scene_apply_errors`;DU 看 `last_error`。任一有問題 → `degraded` + 原因;容器非 running → detail 記容器狀態。
- 監控頁 RanRuntimePanel:degraded 顯示黃燈並列出原因。
- 以事故 payload 單測:「sim CU 不可達 http://127.0.0.1:32917: ConnectionError…」會被抓到;live 兩個 run 十個 instance 全 running、detail 空。
- precompute `_patch_status` 打舊 Omniverse update_status 端點 404 一次即永久關閉(不再每 50 tick 刷 404 HTML);`carve_window` 回寫失敗改提示。scene_run 狀態一律由 orchestrator precompute_actor 依容器結束碼決定。

## P6-4 小項清理(2026-09-15 凌晨)

- `run_kpm_sample.wall_time_ms`:archiver 改寫入歸檔時的 epoch ms(之前恆 0);已驗。
- CU 時序表保留期:新增 `services/optional/retention/log_pruner.py`,啟動時開 thread,每 `CU_LOG_PRUNE_INTERVAL_SEC`(600)清 `CU_LOG_RETENTION_HOURS`(24)以前的 measurement_log / cell_measurement_log / rlf_event / handover_event。長期資料以 orchestrator 歸檔為準。shared CU 首輪清掉 58.7 萬 + 46.4 萬列舊資料。per-run CU 於下次 run start 生效(現有兩個 run 的容器不重啟,重啟會換 port)。
- CU ANR fixture:`_load_scenario` 檔案找不到時改向 registry 相容端點 `RAN/Scenario/ScenarioController/read` 取 raw_json(`SCENARIO_STORE_URL`,預設 registry 容器)。
- `default-cell-0` 幽靈:DU F1 Setup 在 cell_state 空時不再塞假 cell,改送空 served_cells(CU serializer 允許空)。run 49117e33 的舊資料(3,778 列、最後 09-13 11:18)由保留期自然清掉;該 run 重啟後不再出現。
- 監控頁「RIC 端觀測」面板:orchestrator `RicObservationReader`(閘道 scenario + node view)接上前端,顯示 profile / isolation / 控制策略、每個 meid 的 E2 連線與訂閱數、觀測中的 xApp pod(phase / ready),30 s 慢輪詢。
- 未做:MIMO 增益驗證場景(需 GPU precompute,等 corridor 重算完)。

## corridor_24h 重算完成、切窗、兩個 run 重啟(2026-09-15 上午)

- corridor_24h(src az=180、z-up)於 05:28 本地完成,172,800 tick 全算。與舊 az0 版比:src cell 平均 path gain −107.0 dB(舊 −110.9),nbr 不變 −67.4;src 仍比 nbr 弱約 40 dB,方位修正只拉回 3.9 dB,待查 src 站位/高度。
- 切出 corridor_00_08 / 08_16 / 16_24(各 57,600 tick,無未算 tick;無路徑比例 29.3 / 16.9 / 19.7%)。
- **事故**:ransim-postgres 於 00:24 UTC 因「No space left on device」在 WAL redo 時退出,直到 02:56 UTC 才發現拉起(期間兩個 run 的 CU/DU 全部 OperationalError、歸檔停擺)。發現時磁碟已有 83G 空間,postgres volume 僅 1.5G,填滿的不是 DB。docker 用 json-file 且無 log-opts 輪替,per-run CU/DU 日誌量極大(docker logs 一個容器要跑一分多鐘),高度懷疑是容器 json log;確認需要 root 看 /var/lib/docker/containers。
- 兩個 run 走 orchestrator stop/start 重啟(第二個第一次 DU 未在時限內就緒,重試即成功)。重啟後:十個 instance running、adapter SCTP/E2 Setup 完成、sim CU 無錯;run 49117e33 現在有 UL 欄位(p06 mcs_ul 14、UL SINR 9.38);cell_config 只剩 e0x:src/nbr,default-cell-0 消失;RU/DU 皆載入新切的 cache;閘道兩個 run 各一個 meid CONNECTED、專屬 xApp pod Running(各看到兩個 pod,應是舊 pod 尚未拆完)。槽位對調:388e8e0a 現為 e01、49117e33 為 e02。
- DU achieved 0.94×(目標 2×,body_ms 平均 498 > 250 目標),既有效能議題。

## P5-5 MIMO 增益驗證(2026-09-15)

- cached 模式的 npz 只有純量 path gain,RU 拿不到 H → rank 永遠 1;MIMO 驗證必須走 live。
- registry 新增天線預設「gNB 2×1 cross tr38901(4-port)」「UE 1×1 cross iso(2-port)」;以 dt_2m(1 UE 定點、2 cell、600 s)為底匯入 `mimo_check`(場景層級綁兩個預設)與 `siso_check`(1×1 對照),流量 60 Mbps 滿載;dt_2m 原場景(2 Mbps)也跑了一輪。三個 scene_run 都留在 registry,可重複跑。
- **live 啟動缺陷(修)**:Physics 每次 engine 重建 ~30 s(warmup + 天線變更再一次),RU 5 s 逾時 → 退成 SINR −100 → DU 1 s 內宣告 RLF → CU DROP → UE IDLE 後量測鏈不再恢復(整場 per_ue 空)。修法:RU `RU_PHYSICS_TIMEOUT_SEC` 預設 60;physics 失敗改為「本 tick 無觀測」(不回 CqiIndication、不快取,不觸發 RLF);UE `PHYSICS_PUSH_TIMEOUT_SEC` 預設 180,push_scene 等 engine 建好才 attach。修後三輪 physics 失敗 0、RLF 0。
- 結果(同一 UE 位置,120 個視窗平均):

| 場景 | 流量 | rank | MCS | SINR | RSRP | PRB | 吞吐 |
|---|---|---|---|---|---|---|---|
| dt_2m 1×1 | 2 Mbps | 1.00 | 10.5 | 15.7 | −82.3 | 6.1 | 1.99 |
| mimo_check 4×2 | 2 Mbps | 1.99 | 13.0 | 19.6 | −78.3 | 4.6 | 1.98 |
| siso_check 1×1 | 60 Mbps | 1.00 | 10.4 | 15.7 | | 106.0 | 34.29 |
| mimo_check 4×2 | 60 Mbps | 1.99 | 12.9 | 19.6 | | 100.2 | 42.38(峰 45.0) |

- 解讀:rank 2 在 119/120 視窗成立,每層 SINR [16.7, 9.0] dB;第二層比第一層低 7.7 dB,EESM 後 MCS 只從 10.4 升到 12.9,滿載吞吐 +24%(34.3 → 42.4 Mbps),不是 2×——符合單 UE、LOS 主導(奇異值差距大)的預期。同流量下 PRB −25%。每層 SINR 有進歸檔(229/231 視窗;先前用 max(text) 查到 '[]' 是字串排序假象)。
- 注意:live 模式 physics engine 是全域單例,同時只能跑一個 live run,否則不同天線/場景互相重建。

## 事故:兩個 per-run CU 同時卡死(2026-09-15 06:30 UTC)

- 06:30:26 UTC 起 cu-388e8e0a / cu-49117e33 的 Daphne 同時停止回應 HTTP(CPU 0%、DB 連線全 idle、無鎖等待),DU→CU measurement_report 逾時、adapter 打 CU 逾時、歸檔停擺;前端 3012 兩個 run 因此沒有數值。前 5 分鐘 CU 有一波 A3 換手(SessionController/handover ×4)且 DU 達成倍速掉到 0.39×。
- 新的依賴鏈健康監控有抓到:e2adapter 標 degraded「sim CU 不可達 … Read timed out」、cu 標 starting;但沒有自動復原。
- 容器內 ptrace 被擋(py-spy 失敗),抓不到堆疊。假設:換手路徑 CU→DU 同步呼叫、DU 再同步回打 CU,把 Daphne 執行緒池佔滿形成環形等待。**待查**:給 CU 容器 CAP_SYS_PTRACE 或加 faulthandler 訊號,下次卡住時 dump。
- orchestrator stop 也卡:ue_stop 等 180 s → gunicorn worker 預設 30 s 逾時被 SIGKILL,start 同樣。修:ue_stop 45 s 上限、gunicorn `--timeout 600`。復原方式:強拆 10 個容器後 start,07:25 UTC 起兩個 run 恢復正常至今。

## P4-12 CU 卡死可觀測 + run 自動復原(2026-09-15)

- CU `apps.ready` 註冊 `faulthandler.register(SIGUSR1, all_threads=True)`:`docker kill --signal=USR1 cu-<rid>` 即把所有執行緒堆疊印進 docker logs,不需 ptrace(已在 ransim-cu 驗證)。per-run 容器另加 `cap_add=SYS_PTRACE`,py-spy 也可用。
- health monitor 自動復原:任一角色連續非 running 超過 `PER_RUN_AUTO_RESTART_SEC`(120)→ 對 CU/DU 送 SIGUSR1 留堆疊 → 經自家 API stop/start 整個 run(沿用 RIC 解除登記、容器重建、UE 起場流程),兩次間隔 ≥ `PER_RUN_AUTO_RESTART_COOLDOWN_SEC`(600);原因寫進 scene_run.notes。
- 實測:`docker pause cu-49117e33` 模擬卡死 → 125 s 判定 → stop 200 / start 201 → 3 分鐘內五個容器重建、歸檔恢復、健康全綠。

## P4-13 DU 達成倍速:量測報告改非同步(2026-09-15)

- 在 DU tick body 加五段計時(`body_ms.p_rlc / p_sched / p_dl_tti / p_pm / p_report`,TickController/read 可見)。corridor_16_24 @2×:body 平均 207–283 ms(預算 250),其中 **p_report ≈ 203 ms 固定**——step 5 每 2 tick 對 CU 依序 POST 18 筆 UE + 2 筆 cell 量測報告,每筆新開連線,回應又不被使用。
- 修:`cu_client_operations` 共用 `requests.Session`(keep-alive);tick_runner 量測/cell 報告改丟進背景執行緒佇列依序送(保序,佇列 4000 滿則丟最舊並記 log)。
- 結果:p_report 203 → 3.6 ms;corridor_16_24 @2× 達成 1.89×(修前 0.9–1.5×),body 平均 138 ms;corridor_00_08 @1× 達成 1.0×、body 5.7 ms。歸檔 per_ue 正常、佇列無丟棄。
- 剩餘大頭 `p_pm` ≈ 110 ms(step 4 的 SLOT_SHADOW 逐 UE slot 引擎),尖峰 max 273 ms 偶爾超預算;要再上 3× 以上得動它。postgres 常態 130–145% CPU 值得查(shared CU 的 KPM 查詢 + 三個 CU 寫入)。
- DU 容器單獨 `docker restart` 後 tick 不會自己恢復(F1 Setup 通過但 tick_count 0):health monitor 新增「DU is_running=false → degraded」,由自動復原接手(實測 125 s 判定、重建成功)。DU `mac` 補上 0005 migration(bw_mhz / total_prb 欄位定義漂移)。

## 第 4 項 corridor src 站位查核(2026-09-15)

- 不是站位錯。按 UE 到站台距離分箱看 24h cache:src 與 nbr 在 0–20 m 幾乎一樣(3–6 m 約 −47 dB、12–20 m 約 −60 dB);src 的 −107 dB 平均是被「30–50 m 且被走廊轉角/牆完全遮蔽(−160 dB)」的 100 萬個樣本拉低——UE 大部分時間停在 nbr 那一端。方位修正後兩站都正對走廊。
- 附帶觀察:兩站 0–3 m 內反而只有 −70 dB(3–6 m 是 −47),是 tr38901 天線垂直面在正下方的零點,UE 停在站台正下方時會偏弱;屬模型行為,不改。

## 第 5 項 docker 日誌輪替 + 降 log 量(2026-09-15)

- 量 5 分鐘:CU 約 10,000 行幾乎全是 daphne access log(measurement_report 每秒 30 筆);DU 每 tick 每 UE 印 SLOT_SHADOW / DU_SINR_CMP / UL sinr;RU 每請求印 dl_tti、update_ues。
- 改:CU daphne `--access-log /dev/null`(Dockerfile,已重建 ransim-cu:platform);DU/RU 上述 per-tick info 降為 debug。預估 log 量少一個數量級。
- 主機端輪替:`docker-compose-deployment/host_setup_docker_log_rotation.sh`(sudo):寫 daemon.json log-opts 200m×3、重啟 docker、--force-recreate ransim-platform 服務;per-run 容器由自動復原重建時套用。**待使用者執行**。

## 事故:docker 重啟後兩個 run 同時自動重啟搶到同一 E2 槽位(2026-09-16 00:03 本地)

- 使用者執行日誌輪替腳本 → docker daemon 重啟 → 兩個 run 的容器 exited → 健康監控同時判定並自動重啟 → 兩個 start 併發,`allocate_slot` 都看到對方「不是 running」→ 都拿 slot 1(e01、adapter port 8401):第二個 adapter 起不來(port in use),RIC 登記也互撞。
- 修:start 內配槽位改在進程鎖 `_SLOT_LOCK` 內完成,且配到後立刻把 `gnb_id_hex / e2_node_id / status=starting` 寫回 registry,used 集合含 starting。健康監控隨後把 49117e33 重啟為 e02/8402 並成功登記 RIC;388e8e0a 手動 stop/start 一次清掉殘留登記。
- 日誌輪替生效:新容器 LogConfig json-file max-size 200m × max-file 3。

## postgres 常態 100%+ CPU(2026-09-16)

- 歸因:不是慢查詢,是連線 churn——CU/DU/RU 沒設 CONN_MAX_AGE,Django 每個 HTTP 請求開新 PG 連線,量到每秒 70+ 個新 session、170 個 commit,postgres 忙著 fork backend。`synchronous_commit=off` 無效(CPU 不變),證實非 fsync。
- 修:
  - DU/RU(gunicorn,固定執行緒)`CONN_MAX_AGE=600` 持久連線 → 兩者的新 session 歸零。
  - CU(daphne/ASGI,每請求新執行緒)**不能**用 CONN_MAX_AGE:實測連線跟著死掉的執行緒漏,20 分鐘塞滿池、HTTP 全部逾時。改回 0,前面放 **pgbouncer**(compose 新服務 `ransim-pgbouncer`,session 模式、萬用 db、pool 60+20),CU 的 DB_HOST 指 pgbouncer(compose + per_run_template)。client 端仍每請求連線,但 postgres 不再 fork。
  - RU:P6 加的 cell ul_load 每 tick UPDATE 拿掉,pipeline 直接用 DL TTI 請求帶的 cell_ul_load,DB 只當後備。
- 結果:兩個 run(一個 2×)postgres CPU 106% → 約 28%;per-run CU 每 DB 4–5 條連線;歸檔、健康全綠。
- 順帶:同一 run 的 start/stop 加 run 級鎖(手動 stop/start 撞上自動復原造成 run 變 failed 無容器,已補跑)。RIC 端在我方連續重啟期間回 SCTP `control-processing-overload`,恢復後自癒。

## 端到端回歸 e2e_check(2026-09-16 01:50–02:05 本地)

- 流程:匯入 dt_2m 複本 → scene_run cached → orchestrator PrecomputeController(GPU 容器,1200 tick 1.4 s)→ status ready → LaunchController/start → 驗 12 段 → stop → 收尾。
- 通過:五個容器 running、健康無 detail;UE attach 1/1、scene apply 無錯;DU tick 2× 達成 1.97×(body 24 ms);RU 載入 e2e_check.npz cached;CU measurement_log 持續寫入、UE CONNECTED;歸檔 per_ue 含 UL/每層欄位、wall_time_ms 有值;adapter SCTP 連上、E2 Setup 完成、RAN function 2/3/4/5/6 全接受;RIC 閘道登記成功、專屬 xApp pod 2 個 Running;監控頁用的 registry / orchestrator API 都有資料;stop 後五個容器移除、三個 DB 刪除、run_instance 全 stopped、RIC scenario/node 404、歸檔 241 筆保留。
- **未通過:RIC 沒有下訂閱**。e2e_check 3 分鐘內 subscriptionCount 0、adapter 只收到 E2SetupResponse;兩個 corridor run 自 17:0x UTC 重啟後同樣 0 訂閱、30 分鐘 0 筆 indication。我方 SCTP/E2 Setup 正常,訂閱由 RIC xApp 發起 → RIC 端問題(當時 RIC 曾回 SCTP control-processing-overload;懷疑 submgr/xApp 在我方連續重啟後卡住)。
- 49117e33 上一輪重啟 RIC DELETE 逾時、之後登記未成功(meid-not-registered),再 stop/start 一次補登記。
- 殘留:precompute-<rid> 容器 exited 後未清(小,待清理)。

## 管理平台合併為一個後端 + app 依領域分類(2026-09-16)

- `ran-scene-management-network-element-registry` → **`ran-scene-management-backend`**;`building-geometry-ingest` 兩個 app 併入;`legacy-dashboard`(3010)退場。管理平台現在就是 backend + scene-editor-frontend 兩個目錄。
- app 重新分類(平鋪 + 前綴):場域 `field_scene`(scene/building/material/劇本匯入)、設備 `equipment_ran` / `equipment_ue`(含流量)/ `equipment_preset`、3D `render_scan_mesh` / `render_osm_footprint`、執行 `simulation_run`。
- URL 前綴 `Network_element_registry` → `Scene_management_backend`,app 段同步改名;compose 服務/映像/容器改 `scene-management-backend`(port 8301 不變),ingest 8303 併入 8301;外部呼叫端(orchestrator、UE loader、CU fixture、兩個前端、per_run_template)全部改路徑。
- 資料:18 張表 db_table 明示,資料表不動;django_migrations / content_type 的 app 名以 SQL 改名;Material 從 preset 搬到 field_scene 與 FK 目標 app 變更用 SeparateDatabaseAndState(state-only)遷移。ingest 兩表原本 0 列,直接以新 app 建表。事前 pg_dump 備份在 scratchpad。
- 驗證:後端 8 個 app 讀端點 + 舊劇本相容端點全通(68 場景 / 149 gNB / 282 UE 完整);兩個前端 tsc 通過、3011/3012 回應;e2e_check 經新後端 start/stop 全鏈通過(UE 由 read_full_tree 取場景、五容器健康、歸檔、收尾)。
- 踩到:歷史遷移的小寫 lazy ref(`'preset_catalog.antennapreset'`)要另外改;容器內產生的 root 檔案用 docker chown 處理;orchestrator 在後端換名期間 DNS 失敗導致兩個舊 run 的 health thread 停擺,重啟 orchestrator 恢復。
- RIC 端(2026-09-16 04:xx 本地)確認修好:submgr 與 rtmgr 互鎖 + xApp 重試無退避。我方 8401/8402 pdu_sent 11 萬 / 13 萬、gateway subscriptionCount 各 6。e03(e2e_check 測試 run)在我方已無 adapter、閘道未登記,RIC e2term 仍留其關聯 = m-release 無 E2 Removal、我方關機只送 Reset 的已知限制,請 RIC 端手動移除。主機上三條 SCTP 關聯 = e01、e02 + 共用 e00(依決策保留)。

## P7-A1 三層天線模型:資料模型 + RU 數學核心(2026-09-16)

依 `new_plan/ru_antenna_mimo_plan.md` 階段 A1。把「元件 / TXRU / CSI-RS 埠」從一個 `rows×cols` 拆成三層。

- **registry `antenna_preset` 擴充**(migration 0004,舊欄位語意不變:`rows`/`cols` = 單面板元件排列 M/N):
  新增 `panels_mg/ng`、`panel_v/h_spacing`、`trx_v_group`、`trx_count`、`electrical_tilt_deg`、
  `csi_ports`、`port_n1/n2`、`ru_category`(O-RAN Cat A/B)、`bf_method`、`gob_az/el_beams`。
- **內建 preset 15 筆**(`seed_antenna_presets` 指令,冪等,`--update` 可覆寫):1×1 iso(OAI)、
  TR 38.901 §7.8.1 大尺度校準(10×1)、§7.8.2 完整校準 Config 1(雙面板 4×4 雙極化)、
  2T2R / 4T4R / 8T8R(Cat A)、16T16R / 32T32R / 64T64R(Cat B, predefined beam)、UE 1/2/4 埠。
  64T64R = 192 元件(12×8 雙極化)→ 每 TXRU 垂直帶 3 片 → 64 TRX → 再虛擬化成 32 埠 (N1,N2)=(8,2)。
- **RU `virtualization.py`**(元件 → TXRU):權重直接用 **TR 38.901 式 (7.3-1)**
  `w_m = (1/√M)·exp(−j2π/λ·(m−1)·d_V·cos θ_etilt)`,θ_etilt = 90° + 電子下傾。
  元件索引順序對齊 Sionna RT(查 `paths.py:818` 的張量維度確認:**極化慢、位置快;位置又是 col 慢、row 快**)。
  另有 `port_mapping()` 做 TRX → 埠的第二層合併(64 TRX → 32 埠)。
- **RU `codebook_type1.py`**(TXRU/埠 → 層):**TS 38.214 §5.2.2.2.1 Type I 單面板參數化產生器**,
  涵蓋 2–32 埠、rank 1–4。原 `codebook.py` 其實是 **TS 38.211 §6.3.1.5 的 PUSCH 表**(照抄 OAI,只有 2/4 埠),
  用在下行是權宜;新模組才是 PMI/RI 回報講的那一個,舊表保留作 UL 與回歸對照。
- 驗證:窮舉 **12,246 個 PMI**,形狀 (ports×layers)、總功率 = 1、層間正交全數通過。
  2 埠 rank 1 的 4 個 W 與 OAI 表的非退化 4 項逐項相符。
  64T64R 的 W_virt (192×64):每欄功率 1、每片元件只屬於一個 TRX;電子下傾 6°、d_V 0.8λ 時相位遞增 30.1°(理論 2π·0.8·sin6° = 30.1°)。
- 踩到:照 Table 5.2.2.2.1-3 字面取 (2O1,0)…(4O1,0) 當第二道波束偏移,在 N1=2 時 2·O1 ≡ 0 (mod N1·O1),
  第二道波束退化成第一道 → rank 3/4 層間不正交。改成由 (N1,N2) 推出不繞回的組合。
- 附帶修:pgbouncer pool 是「每個 database」算的,60+20 在三個 run(4 個 cu_* DB)時要 320 條 server 連線,
  撞爆 postgres 預設 max_connections=100。pool 改 15+5,postgres `max_connections=300`。
- **三層貫通 RU 訊號鏈**(同日稍晚):
  - RU `AntennaConfig` 加同一組三層欄位(migration 0007),write serializer 全可選(舊呼叫端 = 一片元件一個埠)。
  - 新 `array_chain.py`:把 `virtualization.build()`(元件→TRX)與 `port_mapping()`(TRX→埠)乘好並依設定簽章快取;
    `to_ports(H_elem, cfg)` 把物理回來的元件層 H 壓到埠層。元件數對不上時原樣回傳(相容舊 cache)。
  - `precoder.apply_pmi(..., layout=(N1,N2))` 走 TS 38.214 Type I;不給 layout 沿用舊 OAI 表;單埠直接跳過預編碼。
  - `dl_tti_pipeline` 先 `to_ports` 再預編碼,rank / 每層 SINR 改看埠層通道。
  - registry preset 三層欄位經 `read_full_tree` → UE loader `_preset_to_array` → `ru_client.update_antenna` 一路帶到 RU。
- **前端**:網路元件管理的天線分頁改三層顯示(圖樣 / M×N / 極化 / 面板 Mg,Ng / dV,dH / 增益 / **元件數(推導)** /
  每TRX垂直 / TRX / 電子下傾 / CSI 埠 / **(N1,N2)(推導)** / O-RU Cat / BF 方法 / GoB 方位,仰角)。
- **實測(mimo_check 場景,單 UE 定點 LOS,UE 2 埠)**:

| gNB preset | 元件 | TRX | 埠 | (N1,N2) | Cat | rank | MCS | SINR | 吞吐 Mbps |
|---|---|---|---|---|---|---|---|---|---|
| 4T4R(舊測) | 4 | 4 | 4 | (2,1) | A | 1.99 | 13.0 | 19.6 | 42.4 |
| 8T8R | 8 | 8 | 8 | (2,2) | A | 1.98 | 12.9 | 19.5 | 40.5 |
| 32T32R | 128 | 32 | 32 | (8,2) | B | 2.00 | 13.0 | 19.7 | 41.2 |

  8 埠與 32 埠在舊 OAI 表下會直接丟 CodebookError 退回 rank 1,現在 codebook 錯誤 0、RLF 0、physics 失敗 0。
  32T32R 的 chain 實測為 (128×32) 非單位矩陣,每埠由 4 片元件合成、每埠功率 1。rank 停在 2 是因為 UE 只有 2 埠(rank ≤ min(rx,tx)),符合預期。
- **已知落差(列入 A2)**:SINR 目前仍由純量 path_gain 算,沒有把陣列的相干合成增益算進去,所以 4/8/32 埠的 SINR 幾乎一樣。
  正確做法是 SINR 改由預編碼後的有效通道 H_eff 推導。這是 A2(RU 端 RI/PMI 選擇)要一起處理的。

## P7-A2 RI / PMI 選擇 + 有效通道 SINR(2026-09-16)

### ★ 先修一個從 P5-3 就存在的重大 bug:H 的形狀一直是錯的
physics(`path_solver_actor._serialize_h`)把複數矩陣序列化成**最後一軸 [re, im]**,
所以 (num_rx, num_tx) 的 H 在 JSON 裡是 (num_rx, num_tx, 2) 的實數陣列。
RU 的 `_to_complex_matrix` 用 `np.vectorize` 逐**純量**coerce,`len(x)==2` 那條分支永遠不命中,
3D 結果又被下面的 polarization 分支 reshape 成 `(num_rx × num_tx, 2)` ——
**H 變成「num_rx×num_tx 根接收天線 × 2 個發射埠」**。
實測 8×8 cross 的 gNB + 2 埠 UE:H 應該是 (2, 128),實際拿到 (256, 2)。
rank / PMI / 每層 SINR 從 P5-3(2026-09-13)起都是拿這個錯形狀算的,
先前「rank 2、+24% 吞吐」的結論要以本次之後的數字為準。修法:先攔截標準 [re,im] 格式再轉。

### A2 本體
- 新 `csi_selection.py`:RU 代 UE 做 CSI 回報(TS 38.214 §5.2.2)。
  - 每層 SINR 用 **MMSE 接收機**公式 `γ_i = 1/[(I + γ_ref·H_effᴴH_eff)⁻¹]_ii − 1`。
    ★ 一開始用 `γ_i = γ_ref·‖H_eff[:,i]‖²`(假設層間不干擾),純 LOS(真 rank 1)會被選成 rank 2
    且兩層都「很好」;MMSE 公式會自動把落在同一空間特徵上的層壓下去。
  - 兩階段搜尋:先在 DFT 波束網格(≤ 256 個)挑最佳波束,再窮舉 i1_3 / i2 / rank(≲ 30 個候選)精算容量。
  - 結果依通道指紋快取(UE 沒動就不重算,等效 CSI 回報週期)。
- 寬頻 SINR 改由**最佳單層預編碼的陣列增益**推導:`sinr_db += 10log10(rank1_gain)`,
  天線變大 SINR 才會真的變好(RLF / CQI 都吃這個值)。
- **DU 以前從來沒把 RI / PMI 帶進 PDU**:`build_dl_tti` 的 `rank_map` / `pmi_map` 兩個參數
  從來沒人傳,所以 layers 永遠 1、pmi 永遠 0,預編碼形同虛設(rank 只影響 slot 引擎的吞吐估算)。
  現在 tick_runner 從 registry 帶入,`update_ue_sinr` 也存 RU 選的 PMI。

### 實測(mimo_check,單 UE 定點,UE 2 埠;直接打 RU 的 dl_tti 端點,不經歸檔)
| gNB | 埠 | SINR | rank | 每層 SINR(dB) | 相對 4 埠 |
|---|---|---|---|---|---|
| 4T4R | 4 | 27.2 | 2 | 24.2 / 2.6 | — |
| 8T8R | 8 | 30.3 | 2 | 27.2 / 5.7 | +3.1 dB(理論 +3.0) |
| 32T32R | 32 | 35.6 | 1 | 35.6 | +8.4 dB(理論 +9.0,差額為 codebook 量化) |

- 三組的 per-port path_gain 完全相同(−81.28 dB),證實 `PHY_PATH_GAIN_PER_PORT` 的正規化正確、
  陣列增益只由 codebook 算一次,沒有雙重計算。
- 32T32R 選 rank 1(波束太集中,第二層不划算);4/8 埠選 rank 2 但第二層很弱 —— 符合單 UE LOS 的預期。
- codebook 錯誤 0、RLF 0。
- 教訓:比較不同設定時不要直接查歸檔(會混到前一輪的樣本),改打 RU 端點拿當下值。

## P7-B1 GoB 與 O-RAN Cat B predefined-beam(2026-09-16)

- 新 `gob.py`:O-RU 手上的波束表。波束本體就是 TS 38.214 的 DFT 波束 v_{l,m},
  差別在 codebook 是 UE 回報 PMI 去選、GoB 是 O-RU 存一份固定子集由 `beamId` 指定(O-RAN WG4 predefined-beam)。
  - 指向角:`sin(方位) = −l'/(O1·N1·d_h_eff)`、`sin(仰角) = −m'/(O2·N2·d_v_eff)`。
    **負號來自匹配濾波**:通道 h_c = exp(+j2π·d·c·sin a) 的最佳權重是 conj(h_c),而 v_{l,m} 的相位是 +。
    ★ 一開始漏了負號,實測把 UE 放 −60° 會選到標示 +61° 的波束,加負號後 7 個測試角全對上。
  - `d_*_eff` 是**埠間**等效間距(= 元件間距 × trx_v_group × 埠合併數),不是元件間距。
    32T32R 的 d_v_eff = 0.8 × 4 = 3.2λ → 可視區內有柵瓣,標 `grating=True`;
    理想 steering vector 測試裡 −8° 會選到標示 +8.99° 的波束(柵瓣剛好落在 −8.99°),
    實際通道有子陣列自己的元件方向圖壓著,這個歧義不會顯現。超出 ±90° 標 `steerable=False`。
- **Cat B 路徑**:`ru_category == 'B'` 時預編碼直接用 beamId 對應的權重(O-DU 只送 beamId),
  rank 1 = 兩極化同相送一道波束,rank 2 = 同一道波束用雙極化送兩層。Cat A 仍走 A2 的 Type I 搜尋,
  但兩者都會算 GoB 當 KPI(O-RAN WG1 §4.6.4.1 要每波束 RSRP)。
- **beam_id 進 KPM 全鏈**:CqiIndication → DU serializer / registry / PM 視窗 → GnbDuMeasurementReport →
  CU MeasurementLog(migration 0019)→ telemetry export → orchestrator 歸檔 → 監控頁 UE 詳情。
  另帶 `beam_rsrp_top`(前 K 道波束相對最佳的 dB 差)。
- 實測(32T32R Cat B predefined,GoB 16 方位 × 4 仰角 = 64 道):
  方位候選 −61.0° … +61.0°(16 個)、仰角 −4.5 / 0 / +4.5 / +9.0°;
  選到 beamId 8,次佳低 1.65 dB、第三低 3.82 dB;歸檔與 CU 表都看得到 `beam=8 rank=2 sinr=32.6 每層=[29.55, 27.51]`。
- 踩到:DU 的 `CqiIndicationSerializer` 是明確欄位白名單,新欄位沒加就會被吃掉 —— beam_id 一開始整條鏈都是 null。

## P7-B2 波束的 RIC 控制 + 監控頁波束分佈(2026-09-16)

- **per-cell 波束狀態**(RU `Cell` 模型,migration 0009):`electrical_tilt_deg`、`active_beam_ids`(GoB 子集,空 = 全部)、
  `max_layers`(0 = 用全域)。語意對齊 O-RAN WG1 §4.6:前兩者屬 O1 / OFH M-plane 慢迴路,
  `max_layers` 屬 E2 快迴路;我方目前只有 E2 通道,三者先都走 E2,程式內已註記之後接 O1 時分流。
- **控制鏈**:xApp → adapter → CU `E2/Control/request` **RC (style 2, action 8) = Antenna/Beam Control**
  → `DuClientBusinessService.post_beam_control` → DU `MacCellController/set_beam_control`(純轉送,DU 不存狀態)
  → RU `BeamController/set`(部分更新)。另有 `BeamController/read` 讀回目前設定。
- **RU 套用**:`array_chain.to_ports(..., etilt=)` 讓電子下傾 per-cell 生效(疊在 preset 預設值之上);
  `gob.active_subset()` 篩 GoB;`max_layers` 同時作用在 Cat A 的 Type I 搜尋與 Cat B 的 `_cat_b_select`。
- **實測(32T32R Cat B,單 UE 定點)**:

| 步驟 | 控制 | SINR | rank | beam |
|---|---|---|---|---|
| 基準 | — | 32.56 dB | 2 | 8 |
| 1 | 電子下傾 +10° | 33.14 dB | 2 | 8 |
| 2 | 最大層數 = 1 | 33.14 dB | **1** | 8 |
| 3 | GoB 只留 beam 0/1/2 | **15.25 dB** | 1 | **1** |
| 4 | 回滾(下傾 0、層數 4、全波束) | 32.56 dB | 2 | 8 |

  第 4 步逐項回到基準值,證明控制可回滾、無殘留。
- **監控頁**:新增「波束使用分佈」面板,每 cell 列出用過的波束(色深 = 使用比例,數字 = 該波束平均 SINR),
  對應 O-RAN WG1 §4.6.4.1 的每波束統計需求。
- 踩到:(1) 用 heredoc 把方法附加到檔案尾端會掉到 class 外面 → DU URL 反射不到、整個 DU 起不來,
  run start 因健康檢查失敗回滾;(2) CU 判成功時看 `success` 欄,但 DU 的 wrapper 用的是 `status: "success"`,
  控制其實生效卻回報失敗;(3) `active_subset` 篩過的清單不能再用 beam_id 當索引。

## 事故:VM 記憶體耗盡整台卡死、需重開機(2026-09-16 18:19–18:48 本地)

### 時間線
- 17:25 最後一次提交(B2)。之後留著 4 個 run 在跑:corridor_16_24 @2×、corridor_00_08 @1×、e2e_check(皆 cached)、mimo_check 32T32R(live)。
- 18:14 起 postgres checkpoint 從 < 1 s 變成 100–127 s(I/O 被記憶體壓力拖垮);18:17 出現 `canceling authentication due to timeout`。
- 18:19 `snapd` 被 SIGKILL;之後 containerd 連續 31 次 `context deadline exceeded`,系統卡死,18:48 使用者重開機。
- **這次沒有 OOM kill 記錄**:只有 2 GB swap,核心在換頁中卡住而不是乾淨地殺掉行程。

### 上一次開機期間(09-12 ~ 09-16)的 OOM kill(核心有留行程表)
| 時間 | 被殺 | RSS | 容器 |
|---|---|---|---|
| 09-14 22:18 | python | 30.1 GB | **omniver_kit**(Omniverse 平台,非模擬器) |
| 09-15 14:31 | python | 17.5 GB | **omniver_kit** |
| 09-15 20:51 | gunicorn | **19.9 GB** | **du-388e8e0a**(corridor_16_24 @2× 的 per-run DU) |
09-15 20:51 當下其他大戶:python 13.1 GB(omniver_kit)、daphne 6.7 GB(physics 或 CU)。
容器 ID 對應:a3c988f 於 09-14 14:40 UTC 啟動、14:56 UTC 被 `docker restart`(當時為套 CU migration 重啟 CU/DU),對到 du-388e8e0a。

### 根因(已重現驗證)
1. **DU slot 引擎佇列無上限**:`SlotParams.discard_timer_ms` 預設 0(關閉),而 `tick_runner` 建 `SlotParams` 時**從來沒傳**這個值。
   UE 在沒有訊號的區域(corridor 的 src cell 有 20.8% 無路徑、大量 −160 dB)容量 ≈ 0,但流量持續進來,
   `SlotEngineState.carry_queue` 就無限增長;每個 UE 有兩份 state(`_slot_states` / `_slot_states_op`)。
   重現:無訊號、0.6 Mbps、2000 tick → carry_queue 28,134 筆;開 discard 300 ms → 穩定在 15 筆。
   佇列越長 `queue.pop(0)` 越慢 —— 這也是之前量到 DU `p_pm`(SLOT_SHADOW 階段)高達 110 ms 的原因之一。
2. **RU 通道快取不會清過期項**:`physics_client/.../channel_cache.py` 的 `ChannelCache` 只在「同一個 key 再被查」時刪過期項。
   移動中的 UE 每個 tick 都是新 key,舊 key 永遠不會再被查。重現:寫 36,000 筆全部過期,仍留 36,000 筆。
   實測每筆 744 bytes(cached)/ 42 KB(live 32T32R)。corridor 兩個 run 合計約 0.3 GB/小時。
3. **omniver_kit(非模擬器)** 自己就吃到 17–30 GB,被殺兩次。
4. **所有容器都沒有記憶體上限**,加上 swap 只有 2 GB → 單一失控行程拖垮整台 VM;今天直接卡死而非 OOM kill。

兩個洩漏都是**既有 bug**(不是今天的天線改動引入),但今天留著 4 個 run 連跑數小時讓它們持續累積。
今天的 32T32R live run 使用者為定點(快取 key 不變),不是洩漏來源;但 physics 在今天多次以 128 元件陣列重建 Sionna engine,
其記憶體成長**未能驗證**(重開後已無該行程)。

### postgres
- **沒有壞**。它的 restart policy 是 `no`,硬重開後沒被拉起來,依賴它的 physics 因此不斷重啟,其他服務都停著。
- 手動啟動後自動回復正常:`not properly shut down; automatic recovery in progress` → redo 0.02 s → ready。
  `invalid record length ... got 0` 是 WAL 結尾的正常標記,不是損毀。資料完整:72 萬筆 KPM 歸檔、68 個場景。
- 當機前的 100 秒 checkpoint 是記憶體壓力的**症狀**,不是原因。
- 另外抓到**我今天造成的錯誤洪流**:`column ru_antenna_config.panels_mg does not exist` 每 2 秒一次。
  共用 `ransim-ru` 的 `ru_db` 從沒套 migration;長時間運行的 per-run RU 在 gunicorn worker 回收後載入了新 model 卻沒有新欄位。
  屬錯誤訊息洪流,不是記憶體來源。

### 目前狀態
只啟動了 postgres(診斷用),其餘模擬器容器都停著,沒有 run 在跑。修正待使用者同意。

### 修正(2026-09-16 19:xx,使用者同意 1 / 2 / 4 / 5)
1. **DU slot 引擎佇列**:`tick_runner` 兩處 `SlotParams` 都改為照 `_SLOT_DISCARD_TIMER_MS`(預設 300 ms)套用。
   以前第一處只在 takeover 時套、影子模式一律 0;第二處(`res_op` 反事實)完全沒傳。
   另在 `simulate_sdu_delays` 結尾加 `_trim_to_buffer_cap`:佇列總位元組超過 `RLC_TX_MAXSIZE_BYTES`(與 am_entity 同值,10 MB)
   就從最舊的丟、計入 dropped —— CCO 劇本刻意 `set_discard_timer_ms(0)` 時記憶體仍有界。
   驗證:無訊號 + discard 關 10,000 tick → 佇列封頂 6,666 筆 / 10.00 MB、記憶體 1.16 MB(以前無限);
   discard 300 ms → 15 筆;訊號好 → 丟 0 筆(無副作用)。
2. **RU 通道快取**:每 256 次 set 掃一次過期項;總筆數超過 `RU_CHANNEL_CACHE_MAX`(預設 5000)從最早到期的淘汰到 90%。
   驗證:移動 UE 寫 36,000 筆 → 留 1,638 筆(以前 36,000);長 TTL + 上限 5000 → 留 4,938;正常命中不受影響。
4. **自動重啟**:compose 的 postgres / cu / du / ru / ue / e2adapter / physics / scene-management-backend /
   run-orchestrator / 兩個前端全部 `restart: unless-stopped`(physics 原為 on-failure)。
   per-run 容器不加:VM 重開後由 orchestrator 恢復的健康監控判定不健康 → 自動 stop/start 重建,
   若容器自己先起來,DU tick 不會恢復,反而會多一次重啟。
5. **`ransim-ru` 的 `ru_db` 補 migration**:容器啟動時自動套上 antenna 0007 / 0008 / 0009,
   `panels_mg` 等欄位已存在,`panels_mg does not exist` 錯誤歸零。

### 重啟與 RIC 連線
- `docker compose up -d` 核心服務全部起來、無錯誤。orchestrator 恢復 4 個 run;兩個測試 run(mimo_check 32T32R live、e2e_check)
  經 API 停止並向 RIC 解除登記;兩個 corridor run 由健康監控自動復原重建(124 s 判定 → stop/start),
  各拿到獨立 E2 身分(388e8e0a = e02、49117e33 = e01)——證實 VM 重開後的復原路徑可行。
- **RIC 連不上**:三個 adapter 都是「SCTP connected → 送出 E2 Setup → 2 秒後關聯被關 → 20 秒重試」循環,主機 0 條 SCTP 關聯。
  原因是 `host_setup_sctp.sh` 設的東西**重開機後失效**:
  - `net.sctp.path_max_retrans` / `association_max_retrans` 退回預設 5 / 10(應為 99999)。
    `/etc/sysctl.d/99-ransim-sctp.conf` 其實在,但開機時 systemd-sysctl 早於 sctp 模組載入,參數不存在被默默跳過。
  - iptables 阻擋 SCTP 往 docker / k8s 內網的規則不會保存。主機有 7 個 docker 橋接網段,
    SCTP 多重歸屬會宣告這些位址,RIC 連不到就斷。
- 腳本加上第 4 段「開機自動套用」:寫 `/etc/modules-load.d/ransim-sctp.conf`(開機即載入 sctp),
  並安裝 `ransim-sctp.service`(oneshot,網路與 docker 起來後重跑本腳本)。**需使用者以 sudo 執行一次**。

## 本地模擬回歸(不含 RIC):單場景 → 4 場景並行(2026-09-16 19:20–20:10 本地)

驗證腳本逐項檢查:容器 5/5、健康(RIC SCTP 造成的 degraded 不算失敗)、UE driver、DU tick 前進與達成倍速、
RU channel cache、physics 失敗數、CU CONNECTED 與量測寫入、CU/DU 錯誤、歸檔筆數與 UE 涵蓋、
**cell 隔離**(歸檔裡每個 cell 都帶本 run 標籤)、SINR 有限值、監控 API、記憶體。

| 階段 | 場景(cell 標籤) | 結果 |
|---|---|---|
| 單場景 | corridor_16_24 @1×(e01) | 14/14(先以 corridor_00_08 測,夜間時段前 7.8 小時無流量,吞吐驗不到,改用有流量的時段) |
| 2 場景 | + corridor_08_16(e02) | 各 14/14 |
| 3 場景 | + corridor_00_08(e03) | 各 14/14 |
| 4 場景 | + e2e_check(e04) | 各 14/14;e2e_check 下行 1.97 Mbps ≈ 設定 2 Mbps |
| 跑 20 分鐘後 | 4 場景 | 各 14/14 |

- 隔離:4 個 run 各拿獨立 E2 身分 e01–e04,歸檔裡沒有任何外來 cell。
- 換手與 RLF 都有發生(corridor_08_16 3 分鐘內 RLF 6–8 次、換手 19 次),流程正常。

### 測試中發現並修掉的
1. **RIC SCTP 斷線時健康監控每 10 分鐘把 run 整個重啟**:adapter 被標 degraded → 列入自動重啟。
   重啟修不好外部 RIC,只會打斷模擬。改成 `SCTP 未連線` 屬外部問題:照樣標 degraded,但不觸發重啟;
   `sim CU 不可達`、`DU tick 未運行`、容器掛掉仍會重啟。
2. **KPM API 一次回傳全部**:corridor_00_08 累積 309,805 筆,請求 > 30 s 逾時;監控頁每 3 秒輪詢一次,
   等於讓 orchestrator 反覆組數百 MB 的回應。改成預設最近 3600 筆(依主鍵),回應 1.1 s。前端範圍「全部」改為「1h」。

### 20 分鐘持續監測(4 場景,每 2 分鐘取樣)
| 容器 | 20 分鐘變化 | 判斷 |
|---|---|---|
| omniver_kit | **+813 MB**(前後半各約 +400) | **仍在線性洩漏,約 2.4 GB/小時**,佔總增長 83% |
| orchestrator | +34 MB(前後半各 +17) | 線性,約 100 MB/小時,待觀察 |
| 3 個 corridor CU | +21 ~ +28 MB,幾乎都在後 10 分鐘 | 階梯狀;不是保留期清理(新 DB 無可清資料),原因未明,待觀察 |
| postgres | +31 MB | shared buffers 填充,正常 |
| DU × 4 | +2.6 ~ +5.4 MB,遞減 | **洩漏已修**(先前單一 DU 長到 20 GB) |
| RU × 4 | +0.0 ~ +5.4 MB,多數已平 | **洩漏已修** |
| UE × 4、physics | ≈ 0 | 穩定 |
主機可用記憶體 34.8 → 33.9 GB。以目前速度約 12 小時耗盡,**幾乎全部來自 omniver_kit**。

### 觀察到但未處理(既有行為)
- SINR 最高到 79 dB、corridor 有 58–80% 的樣本 > 40 dB。corridor 牆面把另一個 cell 的干擾完全擋掉,
  靠近基站的 UE 只剩熱雜訊,模型上說得通;但 TS 38.133 規定 SS-SINR 可回報範圍只到 40 dB。9/13 起就是如此。
- KPM API 單次回應仍有 18 MB,監控頁每 3 秒拉一次,可再改成增量拉取。

## 2026-09-16 RIC 連線回歸(SCTP 主機設定修好之後)

- 前提:使用者用 sudo 跑過 `host_setup_sctp.sh`;`ransim-sctp.service` 已啟用,5 個 adapter 都 SCTP 連線、E2 Setup 完成。
- 狀況:adapter 自己回報已連線,但 RIC 閘道把 corridor_16_24(e01)記成 `DISCONNECTED`、訂閱 0;那份註冊是重開機前留下的(`addedAt` 比 adapter 最後一次連上還早約 27 分鐘)。
  RIC 對外入口沒開 e2mgr 查詢,只能從閘道看。處理方式:把這個場景停掉再啟動 → 閘道 gen 12→13,狀態變 CONNECTED,訂閱 5。
- 逐步加場景(每加一個就等閘道狀態穩定):e01 → e02 → e03 → e04,每個場景都有自己的一組 xApp(a6/k5),訂閱數會從 1–2 慢慢長到 5。
- 四個場景同時跑:閘道 4/4 CONNECTED、訂閱都是 5;每個 adapter 在驗證期間持續送出 PDU(約 +41~48);本地檢查 4/4 都 14/14 PASS,cell 隔離也正確。
- 注意:場景剛啟動時 UE driver 會短暫停在 `phase=preparing`,屬正常,暖機完就轉成 running。
- 已知問題:重開機或 RIC 斷線後,閘道可能留著舊的 DISCONNECTED 註冊,目前要手動 stop/start 那個場景。
- 還沒處理:omniver_kit 記憶體洩漏;第 3、6 項(容器記憶體上限、health monitor 記憶體檢查)。

## 2026-09-16 SINR 失真上限 + 記憶體第 3 / 6 項 + orchestrator 洩漏

**SINR 偏高(最高 79 dB)**
- 原因:近距離直視路徑的物理 SNR 本來就很高(RSRP 約 −35 dBm、雜訊底 −98 dBm);場景額外損耗設 0;又加上陣列增益;而且模型裡沒有收發機失真。
- 修法:加 EVM 失真上限 `1/SINR_eff = 1/SINR + 1/SNR_evm`,SNR_evm = 29.1 dB(TS 38.104 §6.5.2 / TS 38.101-1 §6.4.2.1:256QAM EVM ≤ 3.5%)。環境變數 `RU_EVM_SNR_DB`,設 0 可關閉。
  - RU:下行寬頻 SINR、選 rank/PMI 用的參考 SINR、每層 SINR、上行 SINR。
  - DU cached 路徑(`channel_cache_du.compute_sinr_db`):corridor 場景的 SINR 其實是 DU 自己算的,只改 RU 沒有效果。
- 結果:四個場景的 SINR 最高 29.1 dB,超過 40 dB 的 0 筆,MCS 最高仍能到 25;本地檢查 4/4 都 14/14。
- 另外看到:部分樣本 SINR 低到 −35 ~ −55 dB,這是改動前就有的,還沒查。

**記憶體**
- 第 3 項:
  - 每個場景的容器都設 `mem_limit = memswap_limit`(cu/du 1g、ru 2g、ue/e2adapter 512m,可用 `RUN_MEM_LIMIT_<ROLE>` 覆寫),另外補上 `restart_policy unless-stopped`,之前這些容器沒有設。
  - compose 的核心服務也加上限:postgres 4g、orchestrator 2g、ru 2g,其餘 256m–1g;physics 維持原本的 12g。
  - 正在跑的容器已用 `docker update` 套上。
- 第 6 項:health monitor 每 60 秒讀一次容器記憶體,超過上限 85% 就標 degraded,持續下去走既有的自動重啟;主機可用記憶體低於 10% 只記 warning,不重啟 run。
- orchestrator 每小時 +100 MB 的原因:`local.py` 把 DEBUG 寫死成開啟,每條 DB 連線保留最近 9000 筆 SQL 原文,歸檔執行緒寫的是大 JSON。
  - 修法:改成讀 `DJANGO_DEBUG`,compose 對 orchestrator 與 scene-management-backend 設 False。
  - 效果:orchestrator 從 351 MB 降到約 123 MB,重啟四個 run 之後持平。
- CU:重啟後前 10 分鐘從 82 MB 漲到約 135 MB 後持平,看起來是暖機,不是洩漏。
- omniver_kit:12.1 → 12.7 GiB / 16 分鐘,仍在漲,沒有動它(不是我們的服務)。

**RIC 觀察(之後驗證時處理)**:重啟四個 run 後,64efe95f 已連線,但約 20 分鐘訂閱數仍是 0,其他三個都是 5。

## 2026-09-17 多場景 RIC 控制測試(第 1~5 步,走閘道)

時間為 UTC 2026-09-16 16:07–16:08。四個場景的 NGAP ID 相同,正好用來驗證隔離。

| 場景 | ReportCGI | 換手(p17 / cco_ue_01) | PRB 配額 | CCC cell 開關 |
|---|---|---|---|---|
| e01 | ACK ×2 | ACK 438 ms,src→nbr 成功 | ACK 192 ms,DU 兩 cell 都設 10/60/30 | 不送 |
| e02 | ACK ×2 | ACK 117 ms,src→nbr 成功 | 不送,DU 配額為空 ✔ | 不送 |
| e03 | ACK ×2 | ACK 289 ms,src→nbr 成功 | ACK 102 ms,DU 兩 cell 都設 10/60/30 | 不送 |
| e04 | ACK ×2 | ACK 45 ms,gnbDT_c0→c1 成功 | 不送,DU 配額為空 ✔ | 鎖 `e04:gnbDT_c0` ACK,30 秒後解鎖 ACK,DU log 有 disable / enable |

- 四個換手在 CU 的觸發來源都是 `E2_RIC_CONTROL`,時間間隔約 10 秒,與各自送出指令的時間一致,沒有串到別的場景。
- 修正:CCC cell 開關以前一律回 ACK,現在找不到 cell 或 DU 拒絕時會回 ControlFailure。CU 回 409,避免 adapter 把這種情況記成「CU 不可達」(commit 95d3b9e)。
- 另外:e02 的訂閱數是 0,原因在 RIC 閘道舊版的清理規則(0.8.3 已修);重啟 e02 的 adapter、重送 E2 Setup 後恢復成 5。
- 監控腳本的兩個誤報已修正:ACK 還沒寫回就讀到的紀錄;CCC 分成「收到請求」和「送出 ACK」兩筆紀錄。
- 尚未做:天線/波束控制(RC 2/8)的 E2 解碼;閘道的場景 `active` 狀態由 RIC 端處理。

## 2026-09-17 天線收尾 1:RC 2/8 天線 / 波束控制可從 E2 下

- adapter:
  - `to_sim_control_payload` 支援 (2,8),ranP:1 = 目標 cell(NR-CGI,格式同 3-1)、2 = 電子下傾(valueInt,0.1°;也接受 valueReal 度)、3 = 可用波束 ID(valuePrintableString "0,3,5",空字串 = 全部)、4 = 最大層數(0 = 不限)。
  - RAN Function Description 的 style 2 加上 action 8,並加進 `_SUPPORTED_RC_STYLES`;必要參數為 {1},另外允許 {2,3,4}。
- adapter 行為修改:RC 控制在 sim CU 拒絕時改回 RICcontrolFailure(以前一律 ACK),與 CCC 一致。
- CU (2,8):
  - 沒有 cell_id 時改用 target_cgi 反查 cell;以前會把 header.node(gNB MEID)誤當成 cell。
  - 錯誤改回 409,避免 adapter 把它記成「CU 不可達」,讓 health monitor 誤判。
- 測試:
  - 新增 `test_rc_beam_control.py`(7 項);`test_rfd_round_trip` 原本就壞(v10 模組編碼、舊模組解碼 → bitlen overflow),改用 `_rc_ies()` 解碼。adapter 全部 22 項通過。
  - 端到端(e01,用 adapter 會送出的 payload 打 CU):`e01:nbr` 設成下傾 6.5° / 波束 [0,1] / 層數 1,RU 讀回一致,`e01:src` 沒變;不存在的 cell、沒帶參數都回 409;還原後回到預設。

## 2026-09-17 天線收尾 2:階段 C(cached 模式也有 MIMO / 波束)

**做法**:不存整個 H,改存每 (tick, UE, cell) 前 K 條路徑的參數,RU 依當下天線設定重建元件層 H。
- 預算時陣列改成 1×1、雙極化 VH,每條路徑存 A_k(2×2 極化耦合係數,已含元件方向圖)、k_t、k_r(離開 / 到達方向),以及每個 tx 的 orientation。
- RU `path_synth.synthesize` 用 Sionna synthetic array 同一公式重建:H = Σ c(ζ_r)ᵀ A_k c(ζ_t) · e^{j2π(R·p)·k} · 隨機相位;±45° 斜極化由 V/H 線性組合(tr38901_2)。多面板依 TR 38.901 擺位(RU 沒有面板間距欄位,暫用緊鄰)。
- 換天線設定不必重算 cache。

**驗證**
- 重建 vs Sionna 直接用整個陣列(`experiment_c_path_synth.py`,3 種陣列 × 3 個 UE,含 cross / VH / 非零 orientation):最大相對誤差 1.8e-5。
- corridor 場景截斷誤差(`experiment_c_topk.py`,tick 150000,33 組 UE×cell,8×8 cross):K=8 時捕捉功率最差 97.7%、H 誤差 90% 分位 3.6%、最差 14% → 取 K=8。
- RU 單元測試 `test_path_synth.py` 6 項通過(元件順序、正面 / 端射相位、斜極化、旋轉、fading 保功率)。
- e2e_check 重新預算(K=8)後,在 e04 執行期換天線:
  - 1×1:SINR 15.5 dB,rank 1。
  - 8T8R + UE 2 埠:SINR 約 22.4 dB,rank 2 佔 30/44,beam 3,MCS 16。
  - 32T32R Cat B:rank 2 佔 45/45,兩層各約 21–22 dB,寬頻 23–25 dB,beam 8,MCS 17–19。
  - 測完已還原成 1×1。

**其他修改**
- 預算:`PRECOMPUTE_PATHS_K`(預設 6,corridor 用 8),寫入 `<scenario>.paths/`(a / kt / kr 用 memmap,另有 meta.json),checkpoint 前先 flush;`carve_window.py` 會一起切路徑檔。
- RU:ChannelCache 以 mmap 讀路徑檔(未完成的不用);cached 分支用 `_synth_cached_h` 產生每個 cell 的 H,之後走和 live 相同的流程。
- DU cached 模式自己重算寬頻 SINR 時,以前會蓋掉陣列增益 → CqiIndication 新增 `array_gain_db`,DU 在失真上限之前加回。
- physics 的 CUDA 再次靜默失效(對其他容器下 `docker update` 後),已重啟 physics 恢復。
- 進行中:corridor_24h 以 K=8 重算(約 1.4 GB,預計 8 小時以上),完成後切三段並重啟三個 corridor run。舊檔備份為 `corridor_24h.pre_paths.npz`。

## 2026-09-17 天線收尾 3:其餘 O1 天線控制 + 每波束統計

- RU Cell 新增三個 per-cell 控制(migration 0010),BeamController set / read 已支援:
  - `trx_active_ratio`:節能關 TXRU。每片面板每個極化只留中間幾欄,不重新正規化,所以總功率和陣列增益一起降。
  - `beam_taper`:none / hamming / taylor。Taylor 窗自己實作(與 scipy 同算法),正規化成總功率不變,效果是主瓣變寬。
  - `beam_power_offsets_db`:Cat B 每道波束的功率偏移;選到該波束時,寬頻 SINR、各層 SINR 和 array_gain_db 都一起調整。
- 實作位置:`virtualization.element_weights` 產生元件層權重,pipeline 在虛擬化之前乘到 H_elem 上。
- E2:RC 2/8 新增 ranP 5(TRX 比例,百分比)、6(taper 字串)、7(每波束功率,`"beamId:dB,…"`,只接受 ≤ 0);RFD 已宣告,adapter 允許這三個參數,CU 會轉送。adapter 測試 24 項通過。
- 歸檔:per_cell 新增 `beams`,內容為 {beam_id: ue_count, rsrp_avg_dbm, sinr_avg_db, sinr_min_db, prb_dl, thp_dl_mbps},另有 `beam_switches`(同一 cell 內換波束的次數,換 cell 不算)。
- e04 驗證(32T32R Cat B,UE 2 埠,經 CU RC 2/8):
  - 基準:23.9 dB,rank 2,beam 8。
  - TRX 50%:21.7 dB。原始值約少 6 dB,被 29 dB 失真上限壓縮。
  - taylor:23.4 dB。
  - beam 8 −6 dB:18.9 dB。
  - 測完全部還原,天線改回 1×1。
- 尚未做:E2SM-KPM 對 RIC 的每波束量測;目前 RIC 只能從 per-UE 的 beam_id 自己統計。

## 2026-09-17 RIC 回覆處理

- 閘道 0.8.4 場景啟用:orchestrator 在宣告 + 部署 xApp 後,每 5 秒呼叫一次 `activate`(最多 180 秒,409 時繼續等)。重啟四個 run 後都自動變成 active。啟用時的 warnings(還沒有訂閱)屬正常,訂閱隨後建立。
- `controlPolicy.allowedStyles` 改用 env `RIC_GATEWAY_ALLOWED_STYLES`,compose 設為 RIC 端提供的名稱:rc-reportcgi, anr-add, 3-1, 2-6, ccc-lock, ccc-unlock。RC 2/8 在 RIC 端還沒有編碼,預定名稱 `2-8`。
- platform_clients 原本的 meid 佔用重試引用了未定義的 `logger`(NameError),已補上。
- **func2 假流量(e03)**:CU 的 KPM 校正 hook 會把數值換成 kpm-calib 的輸出,但 kpm-calib 對全 0 的輸入仍回 ~320 kbps / PRB ~1%。corridor_00_08 在 7.3 h 前本來就沒有流量,RIC 卻在 func2 看到 DRB.UEThpDl 約 54 萬 bps。修正:原始值為 0 的指標不做校正。修正後 e03 的 func2 回 0 / 0 / 0。
- e00(共用 stack)沒有 CONNECTED UE,所以 func2 沒有指示可送,不是故障;RIC 端會把它排除在 mobiflow 的自動重訂之外。
- e00 在 12:16 前重連 173 次、e04 每 22 秒重連:都是主機 SCTP 設定開機後沒生效造成,已修(922fe59),RIC 端已結案。

## 2026-09-17 RIC 經閘道下 2-8(天線 / 波束控制)實測 — e04,全部成功

e04 在執行期改成 32T32R Cat B(GoB 16×4)、UE 2 埠;UE 1056001738 在 e04:gnbDT_c0,使用 beam 8。RIC 經閘道送 7 步,間隔 30 秒(UTC 17:26:34–17:29:35)。adapter 紀錄的 instId 17–23 與 RIC 端一一對上。

| 步驟 | 參數 | 回覆 | 我方 KPM(平均) |
|---|---|---|---|
| 基準 | — | — | SINR 23.83,rank 2,beam 8 |
| 1 | max_layers=1 | ACK | rank 1 佔 27/31(其餘 4 筆在切換過渡期),SINR 23.66 |
| 2 | max_layers=0, txru 50% | ACK | rank 2,SINR 21.83(−2.0 dB) |
| 3 | txru 100%, taylor | ACK | SINR 22.59(−1.2 dB;RIC 量到 −0.98) |
| 4 | none, beam 8 −6 dB | ACK | SINR 17.67(−5.3 dB),每層 SINR 也下降 |
| 5 | beams 0,1 | ACK | beam 換成 1,SINR 9.48(RIC 量到 7.5,約 5–15 秒後到最低) |
| 6 | tilt 0, beams 全部, 8:0 | ACK | 恢復:SINR 23.87,beam 8 |
| 7 | nci=123(負面測試) | ControlFailure(ricRequest/control-message-invalid) | 設定不變 |

- 第 3 步比原本預估多掉約 0.5 dB:原本 −0.5 dB 的預估來自先前單次的量測。以 Taylor(8) 的加窗效率計算,單一方向損失 −0.69 dB,水平、垂直兩個方向合計 −1.38 dB,再經 29 dB 失真上限壓縮後約為 −1 dB,與實測相符。TXRU 確實已回到 100%:若仍是 50%,SINR 應約 20.8 dB,實測是 22.6 dB。
- 監控(ric_ctrl_watch,1 小時)在 RIC 回報確認後提前結束。它標記的 FAIL 只有第 7 步,是預期的負面結果。
- e04 的天線是在執行期改的,run 重啟後會回到 1×1。

## 2026-09-17 RIC 群組換手 / 節能測試(UTC 01:17–01:20)— 全部符合預期

- G1 e01:matched=15、executed=15,CU 紀錄 15 筆 E2_RIC_CONTROL e01:src→nbr。
- G2(e02 帶 e01 的 cell 名)、G3(e02 帶不存在的 ARFCN):都是 NO_MATCH,e02 沒有 RIC 觸發的換手。e02 分布的變動來自同時段 18 次 RLF 後重新接入,與控制無關。
- E1 e04:UE 換到 c1,DU 在 01:18:59 disable c0(isEnergySaving);E2 在 01:19:29 enable c0(isNotEnergySaving),UE 留在 c1;E3(不存在的 cell)回 ControlFailure。
- e03 閘道世代號 129 的原因:health monitor 的重啟冷卻時間存在監控實例上,每次重啟都建新實例 → 冷卻從未生效,形成重啟迴圈。已改為模組層紀錄,並限制 1 小時最多自動重啟 3 次,超過就停止並記錄 error。

## 2026-09-17 前端流程端到端測試(走廊、1 gNB × 3 cell、8 UE,兩個相同場景同時跑)

- 依 scene-editor 的 API 順序建 `ui_corridor_live`(live)與 `ui_corridor_cached`(cached),兩者內容雜湊相同。
  - gNB 位於走廊中段,3 個 cell 方位 0/120/240°,cell 參數用 OAI 範本(n78、3.5 GHz、40 MHz、23 dBm,A3 關)。
  - 天線:gNB 用 2T2R 小站(tr38901 雙極化);UE 用 1 埠 iso。
  - UE:固定亂數種子產生隨機路徑(0.8–1.5 m/s)與隨機上下行流量(每 30 秒換一次),劇本長 10 分鐘。
- 過程中發現並修正:
  1. **live 模式其實在自由空間算**:UE 推給 physics 的場景只有 buildings,沒帶掃描模型 → 已改成推送 `geometry_source`。
  2. **預算沒套用場景的天線 preset**(一律 tr38901/dipole):registry 匯出補上 tx/ue_antenna,預算時改用與 live 相同的欄位。
  3. scene-editor 前端在 dev 編譯 3D 頁面時記憶體峰值約 906 MiB,撞到 1g 上限後被砍 → 兩個前端改為 3g。
  4. 監控頁:UE 狀態缺 `attach_failed` 時整頁當掉;直條圖與圓環沒處理 NaN。
  5. 最初用 OAI 的 1×1 iso 天線時,同站 3 cell 沒有方向性,SINR 固定 −3 dB → 改用 2T2R 定向天線。
- 結果:兩個 run 本地檢查分別 13/13、14/14;RIC 閘道 e05 / e06 皆 active、CONNECTED、訂閱 5;前端 3D 畫面(CDP 截圖)與兩個監控頁都正常顯示。
  - live 與 cached 數值接近:SINR 中位數 4.6 / 6.0 dB,下行平均 1.34 / 1.49 Mbps。
  - RLF 頻繁(3 分鐘 70–80 次)、沒有換手:原因是同頻同站 3 cell 在窄走廊互相干擾,且 OAI 範本的 A3 關閉,UE 只能靠 RLF 後重新駐留換 cell。
  - `omniver_backend` 的 ingest_signals 回 500(OperationalError)不在我方範圍,也不影響模擬。
  - 監控頁載入初期會出現一次 NaN 的 React 警告,畫面上沒有 NaN。
- corridor_24h 的路徑預算(K=8)目前到 65%,約還要 5.5 小時。

## 2026-09-17 第二次 VM 卡死(11:3x–11:56)

- 截圖中的兩次 OOM(10:10、10:11)是 scene-editor 前端在自己的 1g 上限內被砍,只影響該容器,之後上限已調為 3g。
- 真正的卡死:11:02 起系統服務陸續逾時,11:39 journald / snapd 看門狗逾時,11:46 出現 balloon workqueue 訊息,連 poweroff 都送不出去,11:56 重開機。核心沒有全域 OOM,屬於記憶體接近耗盡時不斷回收造成的停頓。沒有歷史記憶體紀錄,無法定案。
  - 最大嫌疑是 omniver_kit:沒有上限,9/16 量到每小時 +2.4 GB。
  - 其他同時在跑的:6 個 run、corridor 預算,以及各服務上限加總已超過 48 GB。
- 處理:
  1. omniver_kit 在 Omnivers_platform/docker-compose.yml 加上 `mem_limit: 8g`,已重建(原檔備份為 .bak-20260917);它使用 nvidia runtime,不能用 docker update,重建後 GPU 正常。
  2. 使用者 crontab 每 5 分鐘執行 `/home/mitlab/memlog/memlog.sh`,記錄主機與各容器記憶體,一天一檔、保留 14 天,每天約 0.5 MB、每次約 2 秒。
  3. 重開機後 run 容器無限重啟:約 20 個容器同時在共用的 protocol 掛載目錄 pip install,在 build/ 互相衝突。已改成先複製到私有目錄再安裝(517b575)。
- 待處理:6 個 run 尚未重新 start;corridor_24h 預算的 checkpoint 在 120000 tick,尚未續跑。

## 2026-09-17 前端:場景建置四步驟、3D 即時、3D 回放

- 場景編輯器 `/scenes/[id]` 改成四個步驟頁(舊網址會轉到步驟 1),上方有步驟列,每一步都有檢查清單;有錯誤時要確認才能前往下一步。
  1. environment:場景資料、幾何來源切換(可沿用其他場景的掃描模型)、複製場景、建築盒 / OSM、材質。
  2. network:放置時要套用的 gNB 模板、gNB / cell / 天線 / A3 / DU 模板;檢查同站同頻、同頻 PCI 重複、沒開 A3、沒設天線。
  3. ue:情境範本(一般 / 通勤 / 會議室 / 尖峰)+ 隨機種子產生 UE(路徑、分段流量、在場時段,同種子結果相同)、路徑播放預覽(1–60×)、單一 UE 的流量(cbr / piecewise)與在場時段編輯。
  4. launch:啟動前檢查(live 限 1 個、cached 需 cache、同時 run 數、倍速 × UE 數)、Precompute 進度、啟動 / 停止、開監控、run 設定與 knobs。
- registry 新增 `SceneController/duplicate`:深複製整個場景(以前用 export / import 會遺失天線 preset)。
- 監控平台:
  - 新增「3D 即時」分頁:UE 用 InstancedMesh 一次畫完,依 UE driver 的 elapsed_sim_sec 加倍速外插移動;顏色 = 服務 cell,亮度 / 大小 = SINR;換手閃白、RLF 閃紅;UE→cell 連線;標籤只在滑鼠指到或選取時顯示(可切換全部)。
  - 回放頁加上 3D 與自動播放。
  - 歸檔新增 `scene_t_sec`(劇本時間,migration 0002):sim_time_ms 會跨重啟累加,不能拿來對應劇本路徑。
- 驗證(CDP 無頭截圖):四個步驟頁都沒有 console 錯誤;在測試場景 `ui_wizard_test` 產生通勤情境 8 個 UE,資料正確,播放時 UE 會移動;3D 即時頁上 corridor_08_16 的 UE 會隨時間移動並換到 nbr;回放 3D 顯示劇本時間與 UE 位置。
- 尚未做:畫布顯示掃描模型(glb)、覆蓋熱圖預覽。

## 2026-09-17 畫布顯示掃描模型 + 覆蓋熱圖預覽

- registry `SceneGeometryReader`:
  - `meshes`:解析場景的 Mitsuba XML(scene.geometry_source,以及建築的 .xml geometry_ref),列出 ply / obj 網格、材質、to_world 轉換。
  - `mesh_file`:只能依 shape_id 取「該場景有引用」的檔案,不接受任意路徑;單檔上限 60 MB。
  - compose 以相同絕對路徑唯讀掛載 `Omnivers_platform/assets/maps`。
- 兩個前端的 3D 都會畫出場景模型:PLYLoader / OBJLoader 解析,依 ITU 材質上色、半透明,可調「剖面高度」(預設 2.2 m,切掉天花板才看得到室內)。場景檔與平台同為 Y-up,不用轉換;走廊模型與 UE 路徑 / gNB 位置吻合。
- 覆蓋熱圖:
  - physics `CoverageRunner/compute_scene` 另建暫時 engine 算,不動 live engine,但計算期間拿 engine 鎖;回傳每格最佳 RSRP、serving SINR、最佳 cell。
  - coverage_solver 修正 z-up:P5-2 之後取樣平面仍用 y-up 參數;現在改依 cell_centers 反推軸向。
  - registry `SceneGeometryReader/coverage` 由場景匯出設定(含天線 preset)並自動決定網格(外框外擴 5 m、≤ 40000 格)。
  - 編輯器步驟 2 加上「覆蓋熱圖」面板:高度、格距、SINR / RSRP / 最佳 cell、不透明度、色階、統計。
  - 驗證:ui_wizard_test 49×219 格(0.25 m)約 4 秒;最佳 cell 的三個扇區方向與方位角 0 / 120 / 240° 相符;扇區交界 SINR 低。
- 事故:我用「等 log 出現 checkpoint @ tick 130000」來決定何時重啟 physics,但 precompute log 是累加的,9/14 那次完整重算就有這一行 → 條件立刻成立,physics 在 14:06 就被重啟,當時進度 127600 還沒存,從 120000 重跑,損失約 7600 tick(約 1 小時)。之後判斷條件要限定在本次執行之後的 log(或看 checkpoint 檔的 mtime)。

## 場景建置第一層:地圖多邊形 / 上傳掃描檔(2026-09-18)
- 步驟 1 分兩層:第一層選來源(從地圖建立 / 上傳掃描檔 / 匯入劇本連結),第二層才是 3D(元件庫拖 gNB、UE)。已有幾何的場景直接進 3D,可按「更換場景來源」。
- 地圖:Leaflet(深色 CARTO / OSM 底圖切換),台灣起始;搜尋地標 → 飛過去並自動框正方形(半邊 100–300 m,依地標外框夾值);多邊形拖頂點、拖邊中點插入、雙擊刪除、逐點重畫;面積上限 1 km²(前後端一致)。
- registry `OsmMapEditor/preview`(多邊形 → 範圍內建築,重心在多邊形內才算)與 `build_scene`(逐棟材質 / 高度 / 排除 → Mitsuba,設 `geometry_source`、`origin_lat/lon`、`bounds`)。台科大 0.1 km² 實測 115 棟、3 s;產生的 Mitsuba physics 可載入、畫布網格 4 組(依材質分組、顯示色依材質)。
- 上傳掃描檔:沿用 `ScanMeshImporter/import_glb`,新增 `ScanAssetController/use_for_scene` 設成場景幾何;不經地圖。
- registry 的 scanned-building-assets 掛載改到 `/app/scenes`(與 physics / precompute 相同),`geometry_source.path` 兩邊通用;畫布網格讀取的允許根目錄同步改。
- 材質表原本是空的:預載 13 種 ITU 材質(concrete / brick / plasterboard / wood / glass / ceiling_board / chipboard / floorboard / metal / marble / 三種地面);前端材質 API 路徑修正(`Equipment_preset` → `Field_scene`)。
- 移除舊 MapFetchPanel 流程(只掛一筆 building,沒設場景幾何,模擬用不到)。
- 未做:瀏覽器端互動實測;地圖產生的場景尚未跑過 precompute / live 驗證傳播。

## 地圖場景端到端實測 + 下行干擾依負載加權(2026-09-19)
- 台科大 0.07 km² OSM 場景:80 棟、2 gNB 於 51 / 42 m 屋頂(各 3 扇區 tr38901)、6 UE 街道移動。precompute 4 分鐘(確認用 OSM 幾何,缺值 1%);cached 2× 6 UE 全附著、HO 21 / RLF 7、零錯誤;RIC 有 indication。
- live 1× 起初 3 分鐘 RLF 11、HO 2。兩個原因:(1) live 每 tick 重新光追,SINR 瞬間掉到 −20~−37 dB → RU `live_smoothing`(每 UE×tx dB 域 EMA,τ 5 s 模擬時間,漏追 10 s 內沿用);(2) 下行干擾把所有鄰 cell 當滿載 → 6 同頻 cell / 260 m 輕載也 SINR < −6 dB,且沒有單一鄰區強 4 dB,A3 不觸發只能 RLF。
- 下行干擾加權:DU 每 tick 算每 cell DL PRB 佔用率(1 s EMA)→ `DlTtiRequest.cell_dl_load` → RU 干擾 × 鄰 cell 負載(下限 0.1:SSB / CSI-RS / PDCCH);DU in-process(cached)同式。舊 DU 沒送 → 滿載(`RU_DL_NEIGHBOR_LOAD`)。
- 結果(live 1×,4 分鐘):RLF 14 → 5、HO 1 → 10,SINR 5.9–23.5 dB,cell PRB 0–20%,零錯誤。**所有場景的下行 SINR 都會變(輕載變好)**,走廊等既有劇本的 KPM 數值會不同。
- registry gunicorn 改 gthread 4 threads + 600 s 逾時(Overpass 讀建築實測超過 30 s 被 WORKER TIMEOUT 砍掉)。
- 匯入的劇本 JSON 沒寫 A3 → A3 關;這次手動開。編輯器放 gNB 會套模板(含 A3)。

## 待辦:下行雜訊底沒有依據(2026-09-19 記錄,與提高射線取樣數一起處理)
- `RU_NOISE_FLOOR_DBM` 預設 −98 dBm,查不到出處:RU README 寫 −95(與程式不一致),架構文件只把 −98 當既定值抄下來,progress_log 只在討論「近距離 SINR 過高」時提到。
- 依公式反推:40 MHz + UE NF 7 dB → −174 + 76 + 7 ≈ −91 dBm,現值樂觀約 7 dB。對照上行 `RU_UL_NOISE_PER_PRB_DBM` = −113.4 是嚴格推導的(−174 + 10log10(360 kHz) + NF 5)。
- 建議改法:依 cell 頻寬動態算 `−174 + 10log10(BW) + NF`,NF 用 RU 表已有但未使用的 `noise_figure_db`;下行也改成 per-PRB 與上行一致。
- 影響:所有場景下行 SINR 降約 7 dB(高 SINR 區受 EVM 上限壓著影響小,cell 邊緣會明顯變差、RLF 變多)→ 改完要重跑 OAI 校準對照。
- 一起處理的還有:precompute 提高射線取樣數(現在相鄰 tick path gain 跳 ~14 dB,靠載入平滑壓住)。

## 待辦:多埠天線 / 波束成形實際上從未在場景跑過(2026-09-19 發現)
- 現況:codebook(TS 38.214 Type I,4–32 埠)、GoB(含柵瓣標記、可用子集)、RIC 波束控制(RC 2-8 七個參數)都實作完成,但**跑過的場景全是 1 埠天線**:
  - corridor_08_16:cell 的 RU 沒有 antenna_preset(退回 1×1)
  - osm_ntust_test:`legacy-tr38901-1x1-V`,csi_ports=0、gob 0×0
- 後果:陣列增益恆為 0 dB、rank 恆為 1、beam_id 恆為 None;RIC 下 RC 2-8 會回 ACK 但不改變任何訊號(1 埠沒有波束可切,電子下傾在單片元件上無意義)。
- 待做:把測試場景的 RU 指到 `32T32R mMIMO`(8×8 cross、32 埠、GoB 16×4)、UE 改 2 埠,驗證四件事:
  1. SINR 出現陣列增益(預期 +15 dB 量級)  2. rank 2 真的被選到且 sinr_per_layer_db 有值
  3. beam_id 有值、beam_rsrp_top 合理      4. RIC RC 2-8 改電子下傾 / 限制波束子集後訊號確實改變
- 附帶確認:cached 場景改陣列大小照理不用重算快取(路徑參數是 1×1 VH 存的),要實測驗證。

## 待辦:編輯器缺三個常用設定入口(2026-09-19 記錄)
1. **A3 只能停用、不能開啟**:屬性面板只有「停用 A3」按鈕,要開只能套含 A3 的 gNB 模板或直接打 API(2026-09-17/18 幫 corridor 與 osm_ntust_test 開 A3 都是走 API)。應補成 checkbox。
2. **DU 重要欄位藏在 JSON 覆寫裡**:`tdd_pattern` / `numerology` / `n_prb` / `min_prb` / `qos_gbr_first` / `gbr_max_share` 只能從「DU 覆寫 JSON」填,面板只開了 PF α / BLER 目標 / discard / HARQ。前四個常調,值得開成正式欄位。
3. **排程器不能從介面選**:PF / max_throughput / round_robin 目前只能改環境變數,而且是全域、非 per-run。應放進 du_config_template 並在面板開下拉。

## 多埠天線 / 波束成形實際驗證通過(2026-09-19)
場景 `osm_ntust_test`(台科大 OSM,2 gNB × 3 cell,6 UE 街道移動),6 個 RU 全改 `32T32R mMIMO`
(8×8 cross 128 元件、trx_v_group 4 → 32 TXRU、32 CSI 埠、GoB 16×4、Cat B),UE 改 `UE 2 埠 cross iso`。

- **要重算快取的原因是 UE 元件場型改變**(dipole → iso),不是從 1 埠變 32 埠 —— 印證「陣列大小改變不用重算」。precompute 3.5 分鐘。
- 結果(cached 2×,scene_t 150):

  | | 1 埠(先前) | 32T32R + 2 埠 UE |
  |---|---|---|
  | SINR | 5.9–23.5 dB | 17.6–28.5 dB |
  | rank | 恆 1 | 全數 2 |
  | 每層 SINR | 空 | 有值,兩層差 0.1–2 dB |
  | beam_id | None | 20/37/42/54/55/62 |
  | MCS | 1–10 | 11–24 |

  SINR 只提升 ~10 dB(理論 15 dB):EVM 上限 29 dB 壓著 + 部分 UE 本來就高。DU/RU 零錯誤。
- **RIC 波束控制(RC 2-8)實測有效**:對 `e01:g1_c0` 下 `active_beam_ids=[20,21,22]` + `electrical_tilt_deg=10`
  → RU log `set_beam_control` → m02 SINR 17.6 → −5.7 dB 並起 T310、m00 24.5 → 18.8、m01 被 A3 換到隔壁 cell。
  解除限制(空清單 + tilt 0)後全部恢復:6 UE 附著、SINR 17.6–28.0、rank 2、beam 3–58。
- 這個場景的天線設定保留,當作日後多埠 / 波束的回歸基準。
- 仍存在:CU 開場 `dl_rrc_message` 404(斷線 UE 的 SRB1 已清,競態),與天線無關。
