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
