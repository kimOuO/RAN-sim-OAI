# test 劇本問題診斷（2026-10-15）

本輪依使用者要求，先梳理系統並定位問題。已讀取本機原始碼、registry 設定、run API、容器日誌及通道快取，並以 Chromium 實測頁面。本輪沒有修改應用程式、資料庫設定，也沒有起停現有 Run；以下是診斷結果與待修項目，不代表已修復。

查核的場景為 `test`：

- scene：`scene-ee25dca8b82949b5b0e264942648057f`
- run：`scene_run-05773c085d2f44c68b5c98c2b75b3514`
- 拓樸：2 gNB、2 DU、5 cell、11 UE。
- 查核時 Run 為 `live`、設定 1×、600 秒、`sim_dt_ms=600`。
- 10 個隨機 UE 名稱為 `use00`–`use09`，另有手動 UE `ue11`。
- 臺灣時間 12:01:40 啟動 Run，12:02:05 啟動 UE 劇本，12:03:08 RU worker 被 OOM killer 終止。

## 1. 系統資料流與本輪閱讀範圍

```text
場景編輯器 :3011
  → registry :8301：場景幾何、gNB/DU/cell/RU、UE 路徑/流量/時段、Run knobs
  → orchestrator :8302：每場容器、拓樸、起停、健康監控、KPM/事件歸檔
  → UE driver：載入 registry、接入 UE、推進位置與流量
  → RU 鎖步時鐘：依序收集各 DU 的 tick，統一模擬時間與全場量測
  → Physics：live 即時計算；cached 讀取預算通道與路徑參數
  → RU：天線、波束與 SINR；DU：排程、流量、RLF；CU：A3/NRT/換手/重建
  → E2 adapter：接 RIC；O1 facade + adapters：接 SMO
  → 監控 :3012：即時儀表板、3D、事件、回放、RIC
```

已對照 `README.md`、`docs/architecture/reading_guide.md`、`workflow.md`、compose，並追讀編輯器狀態、UE 產生器、registry tree/import/export、啟動編排、快取檢查、UE driver/生命週期、RU 鎖步與快取、CU A3/自主 ANR/跨 gNB 換手及監控輪詢。

文件中的「一場 5 容器、3 DB」是較早的單 gNB 描述；目前多 gNB 版本會依 gNB/DU 數量擴展，不能直接以舊文件判斷目前執行架構。

## 2. 手動 UE 無法設定路徑：缺少編輯介面

已確認：手動放置只建立一個 `t=0` 的 waypoint；畫布拖曳只會對既有 waypoint 全部加上位移。UE 頁只有屬性、天線、流量與在場時段，沒有新增/修改/刪除路徑點的介面。

後端已有 `UeWaypointController/create/update/delete` 與 Reader，因此這是前端功能缺口，並非 UE 模型不支援移動。

`ue11` 實際只有一個 waypoint，屬於靜止 UE；修改 `speed_mps` 不會憑空產生目的地。

主要位置：

- `ran-scene-management/ran-scene-management-scene-editor-frontend/hooks/feature/useSceneEditorPage.ts`：`placeAt`、`moveUe`。
- `ran-scene-management/ran-scene-management-scene-editor-frontend/app/scenes/[id]/ue/page.tsx`。
- `ran-scene-management/ran-scene-management-backend/main/apps/equipment_ue/models/ue_waypoint.py`。

修正方向：加入可驗證時間順序的路徑點編輯器，支援手動與隨機建立的 UE；儲存後重新載入場景並更新選取物件。

## 3. 跨 gNB 的 A3：已開啟，但缺少鄰區關係

實際兩台 gNB 都是 `a3_enabled=true`，offset=1 dB、hysteresis=0.5 dB、TTT=80 ms。

CU 日誌明確記錄：

```text
A3 無法換手:NRT 沒有 e50:gnb1_c0 → e51:gnb2_c1 的鄰區關係
A3 無法換手:NRT 沒有 e50:gnb1_c0 → e51:gnb2_c0 的鄰區關係
```

A3 開關控制「是否評估/觸發換手」，自主 ANR 控制「是否自動建立鄰區關係」。兩者是分開的設定。A3 的 NRT gate 預設啟用；缺少允許的關係就會跳過目標。

後端已實作跨 gNB 換手與自主學習鄰區。自主 ANR 預設關閉，Run knob 為 `anr_auto_add`；`test` 目前只有 `inter_freq=1`，沒有設定 `anr_auto_add`。介面在第四步的 Run knobs 提供此鍵，缺少與 A3 放在一起的清楚說明與狀態。

若要讓 DT 自己補鄰區，可在 Run knobs 設 `anr_auto_add=true`，重新啟動 Run 才會寫進各 CU 環境；若要測 RIC 的 ANR，應由 xApp 建關係並確認控制實際落地。不能只把 A3 打開就預期跨 gNB 鄰區會自動出現。

主要位置：

- `RANsim-CU/main/apps/cu_cp/services/optional/mobility/a3_handover_calculation.py`：`_nrt_allowed_targets`。
- `RANsim-CU/main/apps/cu_cp/services/business/anr_auto.py`。
- `RANsim-CU/main/apps/cu_cp/services/business/handover_executor.py`：遠端 cell 分派到 `execute_inter_gnb_handover`。
- `ran-emulation-runtime-run-orchestrator/main/apps/run_lifecycle/actors/launch_request_actor.py`：`ANR_AUTO_ADD` 注入。

以上相對路徑中的執行服務皆位於 `ran-emulation-runtime/`。

## 4. 操作後畫面沒有刷新：場景樹更新，選取物件仍是舊資料

`selection` 直接保存整個 gNB/cell/UE 物件；`withSave` 成功後只呼叫 `tree.refetch()`，沒有依 UUID 從新樹重新取出 selection。屬性面板又直接使用 `selection`，所以 API 已成功、場景樹也更新，但右側開關、天線、屬性仍可能顯示舊值。重新選取物件或重整頁面才會看到新值。

另外，`withSave` 沒有等待 refetch 完成，就解除 saving 狀態並顯示「已儲存」。Run 狀態僅在 precomputing 時持續輪詢，啟動後的狀態不一定自動追蹤。這些都是使用者難以確認操作結果的來源。

監控端也有輪詢穩定性問題：`usePolling` 依賴 callback 的物件身分，而部分 callback 又依賴每次 render 新建的 async state 物件，會反覆重建 interval。本輪實測仍有輪詢，不能宣稱它完全停止；但更新節奏會被其他 render 延後。

主要位置：

- 編輯器 `hooks/feature/useSceneEditorPage.ts:42`、`:47`。
- 編輯器 `hooks/feature/useEditorStep.ts:19`。
- 監控 `hooks/base/usePolling.ts:5`、`hooks/feature/useRunLive3dPage.ts:27`。

修正方向：selection 只存 UUID/類型並從新樹解析；成功狀態涵蓋讀回；輪詢使用穩定 callback 或 ref；執行中的 Run 持續追蹤狀態。

## 5. cached 只有一分鐘：快取確實只有 60 秒

直接讀取 `Physics_sim/data/channel_cache/scene-ee25dca8b82949b5b0e264942648057f.npz`：

```text
path_gain_db.shape = (120, 11, 5)
tick_ms = 500
duration_sec = 60.0
total_ticks = 120
```

`.paths/meta.json` 同樣是 120 ticks、500 ms，並非完整的 600 秒。

目前 Run 已設定 600 秒，UE 路徑最終時間也都是 600 秒。啟動端的 `channel_cache.available()` 只用 `isfile` 判斷快取可用，沒有驗證快取時長、UE 路徑、場景幾何或內容版本。

RU/DU 快取讀取超出 tick 範圍時都會固定取最後一個 tick。因此 60 秒後可能仍持續讀取 59.5 秒附近的通道，卻拿來搭配往後繼續移動的 UE；不能把這種結果解釋成合理的無線品質。

注意：快取超時本身採用 clamp，沒有把 UE 路徑循環回原點。畫面跳回去另有時鐘問題，見下一節。

修正方向：以最後確定的場景與時長重算完整 600 秒；啟動前驗證快取覆蓋範圍，並以場景/路徑/必要天線與幾何資訊的簽章判斷是否過期。只看檔案存在不夠。

## 6. UE 移動後回原位、live 也有：RU OOM 與前端時鐘外推疊加

目前 live Run 的實際狀態：

| 來源 | 查核值 |
|---|---|
| registry | `status=running`，`progress_sec=14.5` |
| 兩個 DU | `tick_count=30`，`scene_sim_ms=14500`，`is_running=true` |
| RU LockstepClock | `running=false`，`tick=0`，`scene_sim_ms=0` |
| UE driver | `running=true`，`elapsed_sim_sec=0` |
| RU cgroup | `oom=1`、`oom_kill=1`，記憶體上限 2 GiB |
| RU 日誌 | 12:03:08 worker SIGKILL，之後新 worker 啟動 |

RU worker 被殺後，process-local 的鎖步時鐘遺失。Gunicorn 補起 HTTP worker，不會自動恢復原本時鐘；DU 留在等待外部 step 的狀態。因此「容器 Up、HTTP 200」不等於模擬仍在推進。

健康監控目前查 RU 的一般狀態，沒有查鎖步時鐘與持續進度；DU 的 `is_running` 也不會因為沒收到 step 自動變 false。這解釋了整場停住但畫面仍然顯示 running。

3D 前端在每次 status 回來後，以 `elapsed_sim_sec + 牆鐘經過時間 × sim_speed_x` 推算位置。它使用設定倍速，沒有使用實際達成倍速，也沒有在模擬時鐘停止時停止外推或限制外推長度。當後端一直回 0 或同一個時間，畫面仍向前移動，下次輪詢又拉回錨點。這正是「走兩步又回去」可由目前程式與實際狀態直接解釋的原因。

原始 UE driver 將軌跡設成 `mode="once"`；`test` 的 UE 也都是 `loop=false`，沒有證據顯示是刻意設定了短週期循環。

另確認設定/實際步長不同：Run 是 600 ms，RU 鎖步程式將值限制在最大 500 ms，DU 實際回報 500 ms。介面應顯示實際採用值或在輸入時限制，不應靜默不一致。

### OOM 原因的證據邊界

已確定發生 OOM。找到可重現的快取延遲清理問題：`ChannelCache` 每累積 256 次 set 才清除過期項目；移動 UE 持續產生新 key，舊 key 的 get 不會被再次觸發。

在獨立 Python process 中用模擬 monotonic clock 驗證：寫入 200 個先後過期的不同 key，得到 `entries=200, expired_entries=200, expected_live_entries=0`。測試只使用很小的樣本，不影響現有 worker。

此次 Physics 每批回應約 24–28 MB，場景的 gNB 與 UE 都套用 8×8 cross 陣列。保留過期通道矩陣會放大記憶體尖峰，是與現象吻合的重要原因；本輪尚未做 heap profile，不能聲稱已證明它是唯一的記憶體來源。

修正方向：降低過期清理延遲、限制快取實際記憶體而非僅筆數；檢查 UE 陣列選型；健康檢查偵測時鐘停止/進度不動；3D 使用有界、依實際進度的時間插值。

主要位置：

- `RANsim-RU/main/apps/physics_client/services/optional/channel_cache.py:23`、`:56`。
- `RANsim-RU/main/apps/phy_low/services/optional/lockstep_clock.py`。
- `ran-emulation-runtime-run-orchestrator/main/apps/run_lifecycle/services/optional/health_monitor.py:61`、`:219`。
- 監控前端 `hooks/feature/useRunLive3dPage.ts:31`。

## 7. 移動一點就斷線：已有真 RLF，也混有顯示問題

最新場次歸檔中有 9 筆 RLF、0 筆成功換手。多筆 RLF 發生在模擬第 2 秒，原因為 `T310_EXPIRY`，並不是單純看起來連線消失。

已查到兩個重要機制：

1. 未指定 serving cell 時，loader 退回場景第一個 cell。開場 attach 的 10 個 UE 都先接 `e50:gnb1_c0`，不是依各 UE 起始位置挑訊號合適的 cell。部分 UE 本來就在其他 gNB 的範圍，開場就可能連到很弱的服務 cell。
2. A3 缺跨 gNB 鄰區關係而被擋，因此即使量測到較強目標，也無法正常換手，只能等 RLF 後重建。日誌可見 `use01`、`use08` 等先斷線再到 gnb2 重建。

因此「靠近另一個 cell 卻斷線」至少有真實的程式原因，不能僅以距離或移動速度解釋。另一方面，3D 的附著狀態只從最新 KPM 與 SINR 哨兵值推導，不是當下 CU RRC 狀態；通道沒有更新、KPM 停留舊值及前端時間倒退都會進一步混淆觀察。

尚不能根據本輪資料斷言每一個移動斷線都由同一原因造成。應先排除初始選網、NRT、時鐘與過期快取，再用固定 UE、固定天線、單一移動路徑做 live/cached 對照，才能評估近場/遮蔽/波束模型。

## 8. ue11 不附著：在場時段語意衝突已確認

實際資料：`ue11.active_windows=[]`；其他 10 UE 都是 `[[0,600]]`。

前端提示「空白＝全程」，3D 也會把沒有時段的 UE 畫成全程在場；runtime loader 卻在場景有人帶時段時，將每個 UE 的空陣列解釋成「一次都不出現」。`_setup_rlc_entities` 因而排除 ue11，日誌直接寫出 `開場 attach 10/11 個 UE`，也沒有將它列為 attach_failed，因為根本沒有嘗試。

這是 `ue11` 本次未附著的直接原因，早於天線計算。單一 waypoint 不會阻止靜止 UE 連線。

暫時可在編輯器把 ue11 在場時段明確填成 `0-600`，重啟後重新觀察。但完整修正需要區分「未設定時段」與「明確設定為完全不在場」，不能直接把所有空陣列都當全程，否則會破壞既有切片劇本。

天線另有選型問題：場景層級的 gNB、UE 都選了 `32T32R mMIMO`（8×8 cross、128 個元件），ue11 自己也選了同一 preset；不是一般手機 UE 的設定。這會大幅增加通道矩陣與傳輸量，應獨立檢查，但不能將本次 ue11 不附著歸因於此。場景層級天線已設定時，個別 UE preset 也不會各自獨立形成 Physics 場景的接收陣列。

主要位置：`RANsim-UE/main/apps/scenario/services/scenario_loader.py:472`、`scenario_driver.py:564`、`ue_lifecycle/services/manager.py:329`。

## 9. O1 404 與「24 個 bug」

O1 404 已由日誌及瀏覽器重現。`RunSubNav.tsx` 有 `/o1` 連結，但 `app/runs/[id]/o1/page.tsx` 不存在。orchestrator 也還沒有給此頁用的 O1 observation reader。這是監控頁尚未實作完成。

查核時本場 O1 兩個 facade、四個 adapter 容器都在執行；404 不能用來判斷 O1 服務或 SMO 連線是否正常，兩者需分別觀測。

「24 個 bug」本輪未能逐項對應，不能把數字直接當成 24 個獨立根因。已實測的範圍：

- 兩套前端 `npm run typecheck` 均通過。
- 兩套 `npm run lint` 均無 error；場景編輯器有 1 個 `useMemo` dependency warning。
- Chromium 開啟 dashboard、live3d、UE editor、O1；前三頁 HTTP 200，O1 HTTP 404。
- 這段觀測未捕獲 JavaScript `pageerror`；有 THREE.Clock deprecation、headless WebGL performance warning 與少數資源 404，不能當成使用者看到的 24 項。
- 瀏覽器直接看見儀表板約 15 秒、3D 約 0 秒，同場「附著 UE」計數也因資料來源不同而不一致。

仍需要使用者看到的錯誤文字或錯誤清單，才能對應那個計數。編譯與 lint 通過不代表上述行為問題不存在。

## 10. 建議修復與驗收順序

1. 修 RU 過期快取、時鐘停止偵測與監控時間來源；驗收超過原本約一分鐘的失效時間，確認各 DU/RU/UE/前端時間持續一致、無 OOM。
2. 修初始 serving cell 選擇、UE 時段語意與 NRT/A3 操作；驗收 ue11 確實嘗試附著、跨 gNB 以正常換手完成，並保留刻意缺鄰區的 ANR 測試能力。
3. 驗證快取長度/內容版本，依最後場景重算 600 秒；驗收 60 秒後通道仍按正確劇本位置變化。
4. 修 selection 與操作後讀回、Run 輪詢，再新增 UE 路徑編輯；驗收不重整頁面就能看到讀回的新設定與新增路徑。
5. 實作 O1 觀測 API 與頁面；驗收頁面 HTTP 200，並以真實資料呈現各 ME、端點、容器與可取得的 SMO 狀態。
6. 依原始前端錯誤逐項回歸，才宣告「24 項」是否已全數解決。

本輪診斷與瀏覽器原始輸出暫存於 `/tmp/xapp-dt-audit/`（含 API JSON、頁面截圖與 console 紀錄）；此目錄可能隨系統清理而消失，主要結論已保存在本文件。
