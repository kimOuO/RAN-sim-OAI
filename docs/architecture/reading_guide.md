# XAPP_DT 導讀:從哪裡開始看這套數位孿生

寫給第一次接手這個 repo 的人。照順序看,每一步都給「看哪個檔案、看完應該知道什麼」。
全部看完約 3–5 天;只想能改東西的話,第 0–4 步(約 1 天)就夠開始動手。

---

## 這套系統在做什麼

用真實的 3D 場景(OSM 地圖或掃描模型)算出無線電波傳播,驅動一套 O-RAN 網路模擬
(CU / DU / RU / UE),把量測結果以 O-RAN E2 介面送給外部的 RIC,讓 RIC 的 xApp 可以
對這個「數位孿生網路」下控制命令(換手、節能、波束),並在監控頁看到結果。

```
使用者在編輯器畫場景 ──> 管理平台(registry)存設定
                              │
                       編排器(orchestrator)啟動一個 run
                              │
        ┌─────────────────────┼─────────────────────────┐
        │                     │                         │
   UE driver             CU / DU / RU              E2 Adapter ──> RIC / xApp
  (推時間、人流)        (協定與無線模擬)            (E2 訊息)
        │                     │
        └──── Physics(Sionna 光線追蹤 / GPU)────┘
                              │
                     orchestrator 歸檔 ──> 監控前端
```

---

## 第 0 步:全貌(半天)

| 看什麼 | 為什麼 |
|---|---|
| `new_plan/platform_restructure_plan.md` | 平台為什麼拆成這些模組、每個 run 長什麼樣、資料表 ER 圖。特別看 §1(資料夾)、§2.2(ER)、§4(per-run 設計) |
| `docker-compose.yml` | 有哪些服務、連接埠、掛載、記憶體上限。看懂系統邊界最快的地方 |
| `new_plan/progress_log.md` | 事件簿,不用一次讀完。日後查「為什麼這樣寫」時用關鍵字搜 |

**服務一覽(host 連接埠)**

| 服務 | 連接埠 | 角色 |
|---|---|---|
| `scene-management-backend` | 8301 | 管理平台(registry):場景與網元設定的唯一真相 |
| `scene-editor-frontend` | 3011 | 場景建置(四步驟精靈) |
| `run-orchestrator` | 8302 | 編排器:起停 run、健康監控、遙測歸檔 |
| `run-monitor-frontend` | 3012 | 監控頁(唯讀) |
| `physics` | 8104 | Sionna 光線追蹤(GPU) |
| `cu` / `du` / `ru` / `ue` | 8101–8103, 8105 | 共用的舊實例(per-run 才是主線,見下) |
| `kpm-calib` | 8200 | KPM 對 OAI 實機數據的校準 |
| `postgres` / `pgbouncer` | 5433 | 資料庫 |

**關鍵觀念:一個 run = 5 個容器 + 3 個資料庫。**
啟動一個 run,編排器會用 docker SDK 起 `cu-<rid>`、`du-<rid>`、`ru-<rid>`、`ue-<rid>`、
`e2adapter-<rid>`(rid = scene_run_uuid 後 8 碼),並建 `cu_<rid>`、`du_<rid>`、`ru_<rid>` 三個 DB;
停止時容器移除、DB drop。Physics 是共用的(cached 模式 run 期間不打它)。

---

## 第 1 步:管理平台 —— 場景怎麼被定義

`ran-scene-management/ran-scene-management-backend/main/apps/`

| 檔案 | 看什麼 |
|---|---|
| `field_scene/models/{scene,building,material}.py` | 場景、建築、材質 |
| `equipment_ran/models/{gnb,du,cell,ru}.py` | gNB → DU → cell → RU 四層;A3 換手參數在 gnb |
| `equipment_ue/models/` | UE、waypoint(路徑點)、traffic、active_window(在場時段) |
| `equipment_preset/models/` | 天線 preset、DU / gNB 設定模板 |
| `field_scene/services/optional/scenario_import/scenario_v1.py` | 劇本 JSON ↔ DB 的轉換,`docs/scenarios/*.json` 是範例 |
| `render_osm_footprint/` | 地圖:地標搜尋、Overpass 抓建築、轉 Mitsuba 場景 |
| `render_scan_mesh/` | 掃描檔:GLB 上傳、材質分類、轉 Mitsuba |

**看完應該知道:** 一個場景由哪些資料組成、gNB/DU/cell/RU 的層級關係、
場景幾何(`scene.geometry_source`)是一個指向 Mitsuba XML 的路徑。

**慣例:** 所有 API 都是 POST,路徑是 `/api/v0.1/{System}/{Module}/{Controller}/{action}`。
沒有 GET/PUT/DELETE。

---

## 第 2 步:編排器 —— 一個 run 怎麼被啟動

`ran-emulation-runtime/ran-emulation-runtime-run-orchestrator/main/apps/run_lifecycle/`

| 檔案 | 看什麼 |
|---|---|
| `actors/launch_request_actor.py` | start / stop 的進入點 |
| `services/optional/container_spawner.py` | 容器怎麼起、port 怎麼配、per-run DB、E2 node ID 槽位 |
| `services/optional/per_run_template.json` | 每個角色的映像檔、環境變數、掛載(由 compose 產生) |
| `services/optional/health_monitor.py` | 健康輪詢、自動重啟、劇本跑完自動停 |
| `services/optional/platform_clients.py` | 對 registry 與 RIC gateway 的呼叫 |

**看完應該知道:** 啟動順序(先起 DU tick,再起 UE 劇本 —— 順序反了 UE 會被當殘留清掉)、
per-run 隔離怎麼做、run 的狀態怎麼寫回 registry。

---

## 第 3 步:介面協定 —— 各元件之間講什麼話

`ran-emulation-runtime/ran-emulation-runtime-interface-protocol/ran_sim_protocol/fapi.py`

**先看這個再看 RU / DU,會省很多時間。** 重點兩個 dataclass:

- `DlTtiRequest`(DU → RU):這個 tick 要對哪些 UE 發多少 PRB、每個 UE 的服務 cell、
  劇本時鐘 `scene_sim_ms`、每個 cell 的上下行負載
- `CqiIndication`(RU → DU):SINR、RSRP、CQI、rank、PMI、beam、上行 SINR、鄰區量測

---

## 第 4 步:UE driver —— 時間和人流是誰在推

`ran-emulation-runtime/RANsim-UE/main/apps/`

| 檔案 | 看什麼 |
|---|---|
| `scenario/services/scenario_loader.py` | 劇本怎麼載入、位置怎麼正規化成時間軸 |
| `scenario/services/scenario_driver.py` | 啟動流程、模擬時鐘(wall time × 倍速)、劇本跑完的判定 |
| `scenario/services/sim_orchestrator.py` | 場景推送、UE 附著的順序 |
| `ue_lifecycle/services/manager.py` | UE 狀態、位置內插、流量產生 |

**看完應該知道:** 模擬時間 = 實際經過時間 × 倍速;UE 位置是路徑點之間的線性內插;
UE 的「在場時段」決定它何時進場離場。

---

## 第 5 步:物理模擬 —— 電波怎麼算

`ran-emulation-runtime/Physics_sim/`

| 檔案 | 看什麼 |
|---|---|
| `main/apps/ran_signal/services/business/sionna_operations.py` | 場景載入、算路徑的進入點 |
| `main/apps/ran_signal/services/optional/ran_calculation/sionna_engine.py` | Sionna 引擎、天線設定、路徑參數輸出 |
| `main/apps/ran_signal/services/optional/ran_calculation/frame.py` | 座標系:平台是 Y 軸朝上,Sionna 是 Z 軸朝上,轉換在這裡 |
| `precompute/run_precompute.py` | 快取怎麼產生(cached 模式的來源) |
| `precompute/carve_window.py` | 從 24 小時快取切出時段 |

**看完應該知道:** live 模式每個 tick 即時算;cached 模式事先算好整段存成 npz
(`Physics_sim/data/channel_cache/*.npz`),外加一個存前 K 條路徑參數的 `.paths` 目錄,
RU 用它重建多天線通道矩陣。

---

## 第 6 步:RU → DU → CU → E2 Adapter

**RU** `RANsim-RU/main/apps/fapi_south/services/optional/dl_tti_pipeline.py` 是主流程:
查通道(cached 查表 / live 打 physics)→ 依天線與波束重建通道 → 算 RSRP / SINR / rank / PMI
→ 算上行 SINR → 回 `CqiIndication`。
其他:`channel_cache_loader.py`(快取載入、缺值內插、平滑)、`live_smoothing.py`、
`beamforming/`(波束、codebook)、`antenna/`(陣列、極化、面板)。

**DU** `RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py` 是心跳:
每個 tick 做 RLC 緩衝、排程、算吞吐、量測回報、斷線偵測(`rlf_detector.py`)。
`fapi_north/services/optional/channel_cache_du.py` 是 cached 模式下 DU 自己算 SINR 的那條路。

**CU** `RANsim-CU/main/apps/cu_cp/`:
`actors/f1ap_router_actor.py`(UE 狀態、量測報告進來的地方)、
`services/optional/mobility/a3_handover_calculation.py`(A3 換手判斷 + L3 濾波)、
`services/business/{handover_executor,reestablishment}.py`、`actors/anr_*`(鄰區關係)、
`services/business/anr_kpm*.py`(KPM 產生)。

**E2 Adapter** `RANsim-E2Adapter/main/apps/e2_adapter/`:
`services/optional/sctp_link/sctp_loop.py`(和 RIC 的連線、訂閱、上報)、
`services/optional/codec/`(E2AP / E2SM-KPM / E2SM-RC 編解碼)。

---

## 第 7 步:監控與歸檔

- orchestrator 的 `run_telemetry_archive`:KPM 樣本、換手事件、控制事件的歸檔
- `ran-emulation-runtime-run-monitor-frontend`:dashboard、事件流、3D 即時與回放

---

## 最有效的一招:追一個 tick

```
UE driver 推進模擬時間、更新 UE 位置
  → DU tick:RLC 緩衝 → 排程(誰拿多少 PRB)
  → DU 送 DlTtiRequest 給 RU(服務 cell、劇本時鐘、各 cell 負載)
  → RU 查通道:cached 查 npz / live 打 Physics(Sionna)
  → RU 算 RSRP、SINR(含鄰區干擾)、rank、PMI、鄰區量測
  → RU 回 CqiIndication 給 DU
  → DU 依 SINR 查 BLER 曲線決定 MCS、算吞吐、餵斷線偵測
  → DU 每秒送量測報告給 CU
  → CU 判 A3 換手 / 處理斷線重建 / 產生 KPM
  → E2 Adapter 經 SCTP 送 RIC;RIC 的 xApp 可回送控制命令
  → orchestrator 歸檔 → 監控前端顯示
```

---

## 名詞對照

| 名詞 | 意思 |
|---|---|
| run / scene_run | 一次模擬執行;一個場景可以有多個 run(不同模式、倍速) |
| cached / live | 通道用事先算好的快取 / 每個 tick 即時光線追蹤 |
| tick | 模擬的最小步進,預設 500 ms 模擬時間 |
| 劇本時鐘 scene_sim_ms | 從 UE 劇本開始算起的模擬時間,查快取用它(不是 DU 的 tick 數) |
| path gain | 路徑增益,不含發射功率的通道衰減 |
| PRB | 實體資源區塊,排程的最小單位 |
| A3 | 3GPP 的換手事件:鄰區比服務 cell 強某個門檻並持續一段時間 |
| RLF | 無線鏈路失敗(斷線) |
| KPM / RC | E2 的量測服務模型 / 控制服務模型 |

---

## 讀的時候要知道的坑(都踩過)

1. **兩個時鐘**:DU 的 tick 計數會早於 UE 劇本開始,兩者差距曾讓通道比 UE 位置超前 2 分鐘。
   查快取一律用劇本時鐘 `scene_sim_ms`。
2. **座標系**:平台(含編輯器、registry、Mitsuba 檔)是 Y 軸朝上;Sionna 是 Z 軸朝上,
   轉換只在 `Physics_sim/.../frame.py` 這個邊界做。
3. **光線追蹤有雜訊**:同一位置相鄰兩筆可能差十幾 dB。cached 在載入時平滑,live 在 RU 平滑。
4. **快取缺值不等於沒訊號**:某 tick 沒追到路徑是取樣問題,短缺口要內插,長缺口才當沒訊號。
5. **A3 預設是關的**:劇本 JSON 沒寫 A3 欄位 → 匯入後不會自動換手,只能等斷線重連。
6. **設定在 run 啟動時凍結**:容器啟動時把 registry 的設定拉進記憶體,run 期間改 registry 不會生效,要重啟 run。
7. **路徑要兩邊一致**:registry 與 physics 都把場景檔掛在 `/app/scenes`,`geometry_source.path` 才能共用。

---

## 想改東西時的最短路徑

| 想改什麼 | 去哪裡 |
|---|---|
| 場景有什麼欄位 | registry 的 models + serializers |
| 場景建置介面 | `scene-editor-frontend/app/scenes/[id]/*` + `hooks/feature/*` |
| 電波怎麼算 | `Physics_sim`(傳播)、`RANsim-RU`(天線、SINR) |
| 排程、吞吐、斷線 | `RANsim-DU/main/apps/tick`、`mac` |
| 換手、鄰區、KPM | `RANsim-CU/main/apps/cu_cp` |
| 和 RIC 的往來 | `RANsim-E2Adapter` |
| 起停 run、健康檢查 | `run-orchestrator/main/apps/run_lifecycle` |
