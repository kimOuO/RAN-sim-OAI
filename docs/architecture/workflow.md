# XAPP_DT 運作流程

> 這是「怎麼跑、資料怎麼流、xApp 怎麼閉環」的運作流程文件。
> 平台/模組架構見 [`architecture/dt_ran_architecture.md`](architecture/dt_ran_architecture.md);劇本見 [`scenarios/`](scenarios/)。

---

## 0. 一句話
XAPP_DT 是**分裂式 5G NR RAN 數位孿生**:把 OAI/O-RAN 的 CU/DU/RU/UE 拆成獨立 Django HTTP 服務,加 Sionna RT 光追物理層、Omniverse 3D、以及 HTTP↔SCTP/ASN.1 翻譯器(E2Adapter)對接真實 RIC。目的:讓 **xApp 先在 DT 驗證 handover / PRB 控制決策,再上實體 RAN**。

## 1. 服務拓樸(記住這張就能開工)
```
                外部 RIC (SCTP PPID=70)
                        ▲
              RANsim-E2Adapter :8201  (HTTP ↔ ASN.1/SCTP)
                        ▲ 拉 KPM / 落地 RC
                RANsim-CU :8101   RRC/F1AP/NGAP/A3 HO/E2
                        │ F1AP
                RANsim-DU :8102   ★真實來源★ MAC/RLC/PF/PM/Tick
                        │ FAPI dl_tti ▲ cqi
                RANsim-RU :8103   天線/Beamform/SINR/channel cache
                        │ PathSolver(cache miss 才打)
                Physics :8104     Sionna RT 光追 (GPU)

  RANsim-UE :8105  每~100ms 推 UE 位置(→RU)+ traffic(→DU)
  Omniverse :8001 / Kit :8080  3D 場景 + 歷史;劇本/場景倉庫
  Dashboard :3010  控制 + 監控前端     Postgres :5433
```

## 2. 一個 tick 的資料流(心智模型)
`DU tick_runner` 是心跳(每 tick 固定推進 `sim_dt=500ms` sim-time;wall 時間可縮短加速)。每 tick:
1. RLC 收 buffer status(UE 注入的 SDU)+ 取 SDU delay 樣本。
2. RU 回的 SINR → MCS(mcs_controller IIR)。
3. PF scheduler 分 PRB(受 xApp PRB quota cap)→ 算 TBS budget。
4. RLC `generate_pdu(budget)` → 真實 drained bytes。
5. 累加 PM(per-UE window)。
6. 每 N tick(PM_WINDOW=1s)flush KPM → F1AP `measurement_report` 給 CU。
7. CU 組 `ue_status[]` → E2Adapter 拉走 → 編 E2SM-KPM → SCTP 給 RIC。

tick 內部再由 slot engine 以 **0.5ms slot** 建模 delay(TDD、K0 pipeline、BLER/HARQ、FIFO drain)。

## 3. 三條 xApp 閉環(平台對外承諾)
| Case | KPM 輸入 | RC 動作(E2SM-RC) | 落地點 |
|---|---|---|---|
| **IM** 干擾管理 | PrbTotDl + UEThpDl + RlcSduDelayDl | Style2/Action6 PRB quota | DU `set_prb_quota` |
| **CCO** 覆蓋容量 | PrbTotDl 跨 gNB 差距 | Style3/Action1 handover | CU HO → DU `ue_context_modification` |
| **ES** 節能 | PrbTotDl + PdcpSduVolumeDL(5min 窗) | HO + PRB quota / Cell On-Off | 兩段組合 |

xApp 下的 RC 觀察可經 [`api/rc_observation_api.md`](api/rc_observation_api.md) 查詢。

## 4. 怎麼跑一場模擬
1. **上傳劇本**到倉庫(Dashboard 或 API `ScenarioController/upload`;劇本欄位見 `scenarios/`)。
2.(cached 模式)**precompute**:`Physics/Precompute/run` 把通道算成 `.npz`。
3. **起 sim**:`UE :8105 /api/v0.1/UE/Sim/SimController/start`,body `{source:"scenario", scenario_id, speed_x, sim_dt_ms}` —— 自動 scene-apply → UE attach → DU tick → lifecycle。
4. **監控**:Dashboard `/logs`(KPM/RC/PRB quota)、`/scenarios`(觸發評估)。
5. **停**:`SimController/stop`(清 UE / reset PM/KPM/quota)。

## 5. 兩種 channel 模式(務必分清)
- **live**:RU 每 tick 打 Sionna 即時算(~200ms/call)→ wall 撐不住 → 上限約 **2x**。
- **cached**:precompute 好的 `.npz` 查表(<0.1ms)→ 跳過 Sionna → 解鎖高倍速。

## 6. 速度與瓶頸
加速靠縮短 wall_tick(`sim_speed_x = sim_dt_ms / wall_tick_ms`),DU 是真實來源、CU+E2Adapter 自動 pull 跟上。實測 cached sustained 上限約 **7–8x**,瓶頸是**跨容器同步 HTTP RTT**(DU↔RU↔Omniverse ~45ms/tick),不是 Sionna 也不是 CPU。建議 baseline 用 **≤2x**(3x 以上會掉封包/KPM 失真)。

## 7. 已知落差 / 限制
- RU RSRP pipeline 歷史上硬編 TX power(已改成 runtime 旋鈕 tx_power/inter_freq)。
- `DRB.RlcSduDelayDl` 為秒級(結構性:UE 打包整 tick 成大 SDU;calib ÷30 壓平壅塞)。
- Coverage(熱圖)與 RU(KPM)兩條 RSRP pipeline 可能靜默不一致。
- SCTP 跨 host reboot 脆弱(要重跑 `host_setup_sctp.sh`)。

## 8. 脫離 Omniverse
劇本/場景可存進 `physics_db`(Physics 的 `scenario_store`),消費端設 `SCENARIO_STORE_URL` 即可讓 sim 脫離 Omniverse。詳見 `Physics_sim/doc/README.md`。
