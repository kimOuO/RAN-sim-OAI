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
