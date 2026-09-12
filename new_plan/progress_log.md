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
