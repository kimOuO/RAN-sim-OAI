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
