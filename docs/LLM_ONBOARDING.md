# XAPP_DT — LLM 快速理解文件

> 產出日期：2026-06-01
> 對象：之後接手這個 repo 的 LLM / 工程師
> 目的：30 秒抓到「這是什麼、怎麼跑、瓶頸在哪、改哪裡」。細節指到既有文件,不重抄。

---

## 0. 一句話

XAPP_DT 是一個**分裂式 5G NR RAN 數位孿生 (Digital Twin)**,把 OAI/O-RAN 的 **CU/DU/RU/UE** 拆成 4 個獨立 Django HTTP 服務,加 **Sionna RT 光追物理層 (Physics_sim)**、**Omniverse 3D 視覺化**、以及一個 **HTTP↔ASN.1/SCTP 翻譯器 (E2Adapter)** 對接外部真實 RIC。目的是讓 **xApp 先在 DT 上跑過、確認 handover / PRB 控制決策合理,再部署到實體 RAN**。

---

## 1. 服務拓樸 (記住這張圖就夠開工)

```
                        外部 RIC (10.3.0.71:36422)
                              ▲ SCTP PPID=70 (ASN.1)
                              │
                    ┌─────────┴─────────┐
                    │  RANsim-E2Adapter │  host net :8201
                    │  HTTP ↔ ASN.1     │
                    └─────────┬─────────┘
              拉 KPM / 落地 RC │ HTTP
                    ┌─────────▼─────────┐
   ┌────────────────┤   RANsim-CU :8101 │  RRC / F1AP / NGAP / A3 HO決策 / E2 sub
   │                └─────────┬─────────┘
   │ Dashboard 控制           │ F1AP HTTP
   │ (Physics_sim/            │
   │  Dashboard :3010)  ┌─────▼─────────┐
   │                    │ RANsim-DU :8102│  ★模擬真實來源★ MAC/RLC/PF排程/PM/Tick loop
   │                    └─────┬─────────┘
   │              FAPI dl_tti │  ▲ cqi_indication
   │                    ┌─────▼─────────┐
   │                    │ RANsim-RU :8103│  天線/Beamform/SINR estimate/channel cache
   │                    └─────┬─────────┘
   │           PathSolver HTTP│ (cache miss 才打)
   │                    ┌─────▼─────────┐
   │                    │ Physics :8104  │  Sionna RT 光追 (GPU) ~200ms/call
   │                    └───────────────┘
   │
   ├─→ RANsim-UE :8105  每 100ms 推 UE 位置(→RU) + traffic inject(→DU RLC)
   └─→ Omniverse :8001 / Kit :8080  3D 場景 + 訊號/位置歷史 ingest + playback
```

共用 1 個 Postgres (host :5433, 內含 cu_db/du_db/ru_db/physics_db)。全部由 repo 根的 `docker-compose.yml` 拉起。

---

## 2. 一個 tick 的資料流 (心智模型)

`DU tick_runner` 是整個 sim 的心跳 (預設 `SIM_TICK_MS`,1x = 500ms/tick)。每 tick:

1. RLC 收 buffer status (UE 注入的 SDU) + 取 SDU delay 樣本
2. RU 回的 SINR → MCS (mcs_controller IIR)
3. PF scheduler 分 PRB (受 xApp E2 PRB quota cap)→ 算 TBS budget
4. RLC `generate_pdu(budget)` → 真實 drained bytes
5. 累加 PM (per-UE window)
6. 每 N tick (PM_WINDOW_SEC=1s ⇒ 20 tick) flush KPM → F1AP `measurement_report` 給 CU
7. CU 組 `ue_status[]` → E2Adapter 拉走 → 編 E2SM-KPM → SCTP 給 RIC

KPM 欄位怎麼算 + 哪些因子驅動跳動：見 `test_records/kpm_field_notes.md`(很完整,別重算)。

---

## 3. 三條 xApp 閉環 (平台對外承諾)

| Case | KPM 輸入 | RC 動作 (E2SM-RC) | 落地點 |
|---|---|---|---|
| **IM** 干擾管理 | PrbTotDl + UEThpDl + RlcSduDelayDl | Style2/Action6 PRB quota | DU `MacScheduler/set_prb_quota` |
| **CCO** 覆蓋容量 | PrbTotDl 跨 gNB 差距 | Style3/Action1 handover | CU `nr_HO_F1_trigger` → DU `ue_context_modification` |
| **ES** 節能 | PrbTotDl + PdcpSduVolumeDL (5min窗) | HO + PRB quota 組合 | 兩段:先 CU HO 再 DU set_prb_quota |

介面合約:`intents-interface.md`。測試紀錄:`test_records/case{1_im,2_cco,3_es}_2026-05-11.md`。

---

## 4. 加速機制 (這是專案目前主戰場)

DT 要把 1 小時 scenario 壓縮成幾分鐘跑完給 xApp 驗證。加速靠**縮短 wall_tick** (`sim_speed_x = sim_dt_ms / wall_tick_ms`),DU 是真實來源,CU + E2Adapter 自動 pull 跟上。

**兩種 channel mode (務必分清)**:
- **live**:RU 每 tick 打 Sionna 即時算 (~200ms/call) → wall 撐不住 → 上限約 **2x**
- **cached**:precompute 好的 `.npz` 查表 (<0.1ms) → 跳過 Sionna → 解鎖高倍速

入口:`/editor` 速度下拉 (live) / `/scenarios` Run 按鈕 (cached)。
完整加速分層、配方、各倍率瓶頸:`sim_speedup.md` + `plan/fast-replay-mode.md`。

---

## 5. ★ 目前最大瓶頸 (使用者要討論的核心) ★

**實測 (`test_records/sim_speed_ceiling_2026-05-23.md`):cached mode 拔掉 Sionna 後,sustained 上限仍只有 ~7-8x,不是「崩」是「跑不到」。**

DU per-tick body wall ≈ 63ms 是物理底限,設 10x/30x/50x 都只跑到 7-8x。拆解這 63ms:

| 來源 | wall 成本 | 性質 |
|---|---|---|
| DU → RU `dl_tti_request` HTTP RTT | ~15 ms | 跨容器 HTTP |
| RU → DU `cqi_indication` callback HTTP | ~15 ms | 跨容器 HTTP |
| DU → Omniverse Kit ingest HTTP (+Postgres write) | ~20-30 ms | 跨容器 HTTP + DB |
| DU 內 scheduler + PM aggregate | ~5 ms | 純 CPU |

→ **瓶頸 = 同步 HTTP round-trip 串接 (~45ms/tick 純 HTTP)**,不是 Sionna、不是 CPU 算力。

連帶兩個衍生問題:
1. **設定漂移**:設 10x 實跑 7.2x → wall-clock duration 跟 sim-time 估算對不上,做 KPM 對照容易誤判 (所以前端速度選項已被砍到只留 5x)。
2. **RC 閉環延遲在 sim-time 上爆大**:xApp 下 RC → adapter → CU → DU 套用,wall 上固定 ~30-50ms;倍速越高,換算成 sim-time 的反應延遲越大,handover 命令會「遲到」。

另外注意一個**獨立**的 delay 問題 (容易跟上面混淆):
- **DRB.RlcSduDelayDl 是秒級不是毫秒級**,這是**結構性**的 — UE container 為省 HTTP 開銷把整個 tick 的 byte 包成 1 個 MB 級「邏輯 SDU」,buffer 累積到 GB 級 → head SDU 等數十秒。語意對 (對齊 spec) 但數值不真實。詳見 `kpm_field_notes.md §5`。

**未實作的提速方向 (sim_speed_ceiling 結論段)**:
- DU↔RU 改 async / in-process channel (消除 HTTP RTT) ← 最大塊
- Kit ingest 改 batch + 後台 thread 寫,不擋 tick loop
- gunicorn sync worker → uvicorn async worker
- `UE_TRAJECTORY_PERIOD_MS` 跟 speed_x 連動 (目前固定 100ms wall)

---

## 6. 已知陷阱 / 設計怪癖 (踩過的雷)

- **RU RSRP pipeline 硬 code TX power 43dBm**,完全不讀 per-gNB `power_dbm`;還雙重套 antenna gain (Sionna 已含) 再用 -50dB 校正硬湊回真機範圍。改 power 在 KPM 端沒反應就是這原因。詳見 `sionna_compute_and_params.md §4`。
- **Coverage 計算與 DU tick 互斥** (GPU 爭用),CoverageRunner.compute() 期間 DU tick 暫停。
- **SCTP 跨主機脆弱**:host reboot 清掉 iptables + sysctl,要重跑 `host_setup_sctp.sh` 否則 e2adapter self-ABORT (記憶 `sctp_host_reboot_wipe.md`)。
- **3 個前端 container 並存** (3001/3002/3010),只有 `Physics_sim/Dashboard:3010` 在維護。
- 座標系:scene_config 是 Y-up;Dashboard SVG 故意鏡射 X 軸 (azimuth 0° 視覺指向螢幕左)。

---

## 7. 推薦閱讀順序

1. 本文件 → 抓全貌
2. `xapp_dt_architecture.md` → 完整服務/端點/分工矩陣
3. `sim_speedup.md` + `test_records/sim_speed_ceiling_2026-05-23.md` → 加速與瓶頸 (現在主戰場)
4. `kpm_field_notes.md` → KPM 每個欄位的公式與因果
5. `sionna_compute_and_params.md` → 物理層參數與已知 bug
6. `intents-interface.md` → xApp 三 case 合約
7. 跨機/SCTP/場景等運維雷:看 memory (`MEMORY.md` index)

> 各服務 commit 後若與本文件出現差異,**以原始程式碼為準**。
