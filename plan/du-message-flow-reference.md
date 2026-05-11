# DU (gNB-DU) Message Flow Reference

DU 在 4-system split (CU/DU/RU/Physics) 中的角色：F1AP 北向接 CU，FAPI 南向接 RU，內部跑 MAC scheduler / RLC / HARQ / PM aggregator / Tick driver。

對齊 OAI 結構：`openair2/F1AP/`（北向）+ `openair2/LAYER2/MAC/`（排程）+ `openair2/LAYER2/nr_rlc/` + `openair2/RRC/NR/`（部分）。

---

## 1. 總覽：誰跟 DU 講話

```
                                  ┌─────────────────────┐
       CU-CP (port 8101)  ◄──────►│       DU            │◄──────► RU (port 8103)
                          F1AP    │   (port 8102)       │  FAPI
                                  │                     │
   Dashboard / xApp ──────────────│                     │◄── Physics (RU 經手, 不直接跟 DU)
   (port 3010)         HTTP       │                     │
                                  └─────────────────────┘
                                       ▲       │
                                       │       │ (DB)
                                       └───────┘
                                       PostgreSQL
                                       UeMacState / RlcEntity / CellConfig
                                       (本地 in-memory: _ue_registry, RA, HARQ, PM)
```

主要角色：
- **CU-CP**（北向 peer）：發 F1AP 控制訊息給 DU（attach/HO/release/RRC），收 DU 上報的 measurement_report。
- **RU**（南向 peer）：收 DU 的 dl_tti / ul_tti，回 cqi_indication / crc_indication。
- **Dashboard**（管理面）：呼叫 cell 設定 + tick start/stop + UE register。
- **xApp**（透過 CU 經 E2 Control）：間接寫 PRB quota；或透過 CU 觸發 HO（會走 F1AP）。

---

## 2. Inbound — DU 收哪些訊號

### 2.1 從 CU（F1AP 北向控制）— `/api/v0.1/DU/F1AP/F1ApRouter/*`

| Endpoint | 來源 | 內容（payload 主欄位） | DU 做什麼 | 回什麼 |
|:---|:---|:---|:---|:---|
| `ue_context_setup` | CU NGAP `initial_context_setup` 後 | `{ue_id, drbs[{drb_id,qos_5qi,rlc_mode}], rrc_message_b64, serving_cell_id}` | ① 寫 `UeMacState` (DB) ② 同步 `tick_runner._ue_registry` serving_cell ③ RA Msg1 detected → finalize ④ HARQ add_ue ⑤ 對每個 DRB 建 RLC entity + SRB1 預設 AM | `UeContextSetupResponse{ue_id, success, drb_setup_list}` |
| `ue_context_modification` | CU `handover_executor.execute_f1_handover`（A3 / xApp / 手動 HO 都走這） | `{ue_id, target_cell, rrc_message_b64}` | ① 更新 `UeMacState.serving_cell_id` ② 同步 `_ue_registry[ue]['serving_cell']` → 下個 tick 的 PDU.cell_id 跟著切換 | `{ue_id, serving_cell_id}` |
| `ue_context_release` | CU 在 detach / cleanup | `{ue_id, cause}` | 刪 `UeMacState` + `RlcEntity` + RLC factory unregister + HARQ remove + PM remove | `{ue_id}` |
| `dl_rrc_message` | CU 推 DL RRC（如 RRCSetup/Reconfig） | `{ue_id, rrc_msg_b64}` | 把 RRC PDU 注入該 UE SRB1 的 RLC TX queue（size = b64 估算）| `{ue_id, queued_bytes}` |
| `ul_rrc_message` | UE simulator（測試用）注入 UL RRC PDU | `{ue_id, rrc_msg_b64, is_initial}` | RA 推進到 MSG4_SENT（如 is_initial）→ 經 dispatcher 轉送 CU | `{ue_id, ra_state_after}` |
| `f1_setup_response` | CU 對 du_setup 的 async callback | `{transaction_id, accepted}` | 標記 DU bootstrap 成功 | `{transaction_id}` |

### 2.2 從 RU（FAPI 南向 indication）— `/api/v0.1/DU/FAPI/FapiRouter/*`

| Endpoint | 來源 | 內容 | DU 做什麼 | 回什麼 |
|:---|:---|:---|:---|:---|
| `cqi_indication` | RU `dl_tti_pipeline.run()` 算完每個 PDU 後 | `CqiIndication{ue_id, sinr_db, cqi, rank, pmi, rsrp_dbm, serving_cell, neighbors[{cell_id,rsrp_dbm,rsrq_db}]}` | ① `mcs_controller.update(ue_id, sinr_db, ts)` → outer-loop link adaptation 算 `new_mcs + smoothed_bler` ② `tick_runner.update_ue_sinr(ue_id, sinr_db, rsrp_dbm)`（in-memory _ue_registry）③ `tick_runner.update_ue_neighbors(ue_id, neighbors)`（給 A3 用）| `{ue_id, new_mcs, smoothed_bler}` |
| `crc_indication` | RU UL HARQ 結果 | `{ue_id, harq_pid, success}` | `harq_manager.handle_feedback(ue, harq_pid, "UL", success)` 推 HARQ state machine | `{ue_id, harq_pid, state}` |

### 2.3 從 Dashboard / 管理面

| Module | Endpoint | 內容 | DU 做什麼 |
|:---|:---|:---|:---|
| MAC | `MacCellController/create` | `{name, gnb_id, pci, freq, bw, ...}` | 寫 `Cell` 表（in DB） |
| MAC | `MacCellController/update` | 同上 | 更新 |
| MAC | `MacCellController/replace_cells` | `{cells[]}` | 全量替換 + exclude-delete 舊 cell |
| MAC | `MacCellController/disable` / `enable` | `{cell_id}` | 寫 `CellState.is_active` → tick_runner 排程時跳過 |
| MAC | `MacScheduler/set_prb_quota` | `{cell_id, max_prb_pct, ...}` | 寫 `PrbQuotaStore`（in-memory）→ scheduler.allocate 時 cap |
| Tick | `TickController/start` / `stop` | `{}` | 啟/停 500ms tick driver |
| Tick | `TickController/register_ue` | `{ue_id, serving_cell?, sinr_db?, rsrp_dbm?, qos_5qi?}` | 加進 `_ue_registry`（serving_cell 不傳 → fallback 查 UeMacState DB） |
| Tick | `TickController/replace_ues` | `{ues[]}` | 全量替換 _ue_registry + exclude-delete 舊 UE |
| RLC | `RlcDataController/inject_sdu` | `{ue_id, bearer_type, bearer_id, sdu_bytes}` | RLC entity recv_sdu → enqueue → 累積到 BO |

### 2.4 從 xApp（**間接**透過 CU 的 E2 Control）

xApp **不直接**呼 DU。透過 RIC E2 → E2 Adapter → CU `e2_control_actor`：

| RIC E2SM-RC | CU 翻譯後打 DU 的哪 | 內容 |
|:---|:---|:---|
| Style 2 / Action 6 (PRB Quota) | `MacScheduler/set_prb_quota` | `{cell_id, max_prb_pct}` |
| Style 3 / Action 1 (Handover) | **不打 DU**（`/F1AP/F1ApRouter/ue_context_modification`） | `{ue_id, target_cell}` |

---

## 3. Outbound — DU 主動打誰

### 3.1 To CU — `http://cu:8000/api/v0.1/CU/F1AP/F1ApRouter/*`

| 何時 | Endpoint | 內容 | 為什麼 |
|:---|:---|:---|:---|
| Bootstrap（容器啟動） | `du_setup` | `F1SetupRequest{gnb_du_id, served_cells[{cell_id, gnb_id, pci, freq, bw, ...}]}` | 通知 CU 這個 DU + 它的 cells，CU 寫 `DuRegistry` + `CellConfig` |
| 每 5 ticks (~2.5s) | `measurement_report` | `GnbDuMeasurementReport{ue_id, rsrp_dbm, sinr_db, throughput_dl_mbps, throughput_ul_mbps, mcs_dl, rb_width_dl, mimo_rank, pdcp_sdu_volume_dl/ul, rlc_sdu_delay_dl_ms, neighbor_cells[]}` | CU 寫 MeasurementLog + 跑 A3 evaluator → 必要時觸發 HO |
| UE 注入 UL RRC | `ul_rrc_message` | `{ue_id, rrc_msg_b64}` | UE 的 UL RRC PDU 經 DU 轉給 CU |
| Cell 配置變更 | `du_configuration_update` | `{served_cells_updated[]}` | 通知 CU cell 改了（用得少） |

### 3.2 To RU — `http://ru:8000/api/v0.1/RU/FAPI/FapiRouter/*`

| 何時 | Endpoint | 內容 | 為什麼 |
|:---|:---|:---|:---|
| **每 tick (500ms)** | `dl_tti_request` | `DlTtiRequest{sfn, slot, pdus[{ue_id, prb_start, prb_count, mcs, layers, pmi, payload_size_bytes, harq_pid, cell_id}]}` | RU 拿 PDU 對每個 UE 算 channel + SINR + 回 cqi_indication |
| 每 tick (UL) | `ul_tti_request` | `UlTtiRequest{sfn, slot, pdus[]}` | RU 收 UL data，回 crc_indication |

---

## 4. Tick Loop — DU 的核心引擎（每 500ms 跑一次）

`tick_runner._tick_body()` 是整個 DU MAC 的調度心臟。一個 tick 完整流程：

```
┌─ 每 500ms ────────────────────────────────────────────────────────────┐
│                                                                       │
│ 1. 收集 RLC buffer status + SDU delay samples                         │
│      bo_by_ue       = {ue_id: total_BO_bytes}                         │
│      delay_by_ue    = {ue_id: [delay_ms_sample, ...]}                 │
│      來源: rlc_factory.all_entities() 內每個 RLC entity 的             │
│              buffer_status() + take_delay_samples()                    │
│                                                                       │
│ 2. 決定誰要 measurement / 誰要 PDSCH 排程                              │
│      ues_for_measurement = list(_ue_registry.values())   # 所有 UE     │
│      ues_with_bo = [u for u in registry if bo_by_ue[u] > 0]            │
│      → measurement 跟 PDSCH 解耦 (對齊 OAI CSI-RS 獨立於 PDSCH)        │
│                                                                       │
│ 3. Per-cell 排程                                                      │
│    inactive_cells = CellState.is_active=False 的 cell（跳過）          │
│    per_cell_alloc = group ues_with_bo by serving_cell                  │
│                                                                       │
│    for each cell:                                                     │
│      cap = PrbQuotaStore.cap_factor(cell)   ← xApp E2 寫的              │
│      capped_prb = max(1, prb_per_cell * cap)                           │
│      alloc = scheduler.allocate(cell, ues_on_cell, capped_prb)         │
│      rb_alloc_global.update(alloc)                                     │
│                                                                       │
│    # 沒 traffic 的 UE 也要送 dl_tti 給 RU 算 measurement               │
│    for ue in ues_for_measurement:                                     │
│        rb_alloc_global.setdefault(ue, 0)                               │
│                                                                       │
│ 4. MCS / TBS 計算                                                     │
│    for ue in ues_for_measurement:                                     │
│        mcs_ctl.update(ue, sinr_db, now_ms)   ← outer-loop LA          │
│        mcs = mcs_ctl.get_mcs(ue)                                       │
│        mbps = mcs_to_throughput(mcs, n_rb=rb_alloc[ue])                │
│        tbs_map[ue] = int(mbps * 1e6 * 0.5 / 8)                         │
│                                                                       │
│ 5. Drain RLC queue (給 PDSCH 對應的 SDU 出 queue)                     │
│    for ue in ues_with_bo:                                             │
│        budget = tbs_map[ue]                                           │
│        分配給 RLC entity → entity.generate_pdu(budget)                 │
│                                                                       │
│ 6. Build & dispatch DL TTI                                            │
│    cell_id_map = {ue: ue['serving_cell'] for ue in ues_for_measurement}│
│    dl_msg = build_dl_tti(sfn, slot, rb_alloc, mcs_map, tbs_map,        │
│                            cell_id_map=cell_id_map)                    │
│    RuClientBusinessService.post_dl_tti_request(dl_msg) ──► RU         │
│                                                                       │
│ 7. PM aggregator accumulate (per UE per tick)                         │
│    for ue in ues_for_measurement:                                     │
│        pm.accumulate_ue(                                              │
│            gnb=ue.serving_cell, mcs_dl=mcs_map[ue],                    │
│            sinr_db=ue.sinr_db, rsrp_dbm=ue.rsrp_dbm,                  │
│            prb_dl=rb_alloc[ue], dl_bytes=tbs_map[ue],                 │
│            qos_5qi=ue.qos_5qi, rank=ue.rank)                          │
│    pm.accumulate_rlc_delay(ue, delays)                                 │
│                                                                       │
│ 8. Periodic measurement report (每 5 ticks = 2.5s)                    │
│    if tick_count % 5 == 0:                                            │
│      for ue in pm.active_ue_ids():                                    │
│        w = pm.flush_ue_report(ue)  → 視窗 avg/sum                      │
│        report = GnbDuMeasurementReport(ue, rsrp/sinr/.../neighbors)    │
│        CuClientBusinessService.post_measurement_report(report) ──► CU  │
│                                                                       │
│ 9. Advance sfn/slot                                                   │
│      slot+=1; if slot>=SLOTS_PER_FRAME: slot=0; sfn+=1                 │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 5. 關鍵欄位 — 從哪裡來

### 5.1 `DlTtiRequest.pdus[].cell_id` (DU → RU)
- **Source**: `_ue_registry[ue]['serving_cell']`
- **更上游**: 由 F1AP `ue_context_setup` / `ue_context_modification` 從 CU 帶下來
- **再上游**: CU 的 `UeContext.serving_cell`（NGAP attach 初設 + A3/xApp/手動 HO 更新）

### 5.2 `DlTtiRequest.pdus[].prb_count` (DU → RU)
- **Source**: `rb_alloc_global[ue]`
- **怎麼算**: `scheduler.allocate(cell, ues_on_cell, capped_prb)`
- **`capped_prb`**: `prb_per_cell * cap_factor` — `cap_factor` 由 `PrbQuotaStore`（xApp 透過 E2 Style 2/Action 6 寫的）給；無 quota 時 = 1.0
- **`ues_on_cell`**: BO > 0 的 UE 才進這個 list；measurement-only UE 補 0 PRB

### 5.3 `DlTtiRequest.pdus[].mcs` (DU → RU)
- **Source**: `mcs_controller.get_mcs(ue)`
- **怎麼算**: outer-loop link adaptation — 用 RU 上一個 tick 回的 SINR + 內部累積的 BLER history → 反查 3GPP TS 38.214 MCS table

### 5.4 `DlTtiRequest.pdus[].pmi` 和 `layers`（**目前 hardcoded**）
- pmi = 0 (codebook[0])
- layers = 1 (rank-1 SISO)
- **TODO**: RU 端做 PMI search + rank selection（見 traffic-and-pmi-improvement.md Phase B）

### 5.5 `GnbDuMeasurementReport.*` (DU → CU)
所有欄位由 `pm_aggregator` 累計每 tick 的值，flush 時取視窗平均/總和：

| 欄位 | 累積方式 | 原始 source |
|:---|:---|:---|
| `rsrp_dbm` | 視窗平均 | RU `cqi_indication.rsrp_dbm` → `_ue_registry[ue]['rsrp_dbm']` |
| `sinr_db` | 視窗平均 | RU `cqi_indication.sinr_db` |
| `throughput_dl_mbps` | 視窗總和 / window_seconds | DU `tbs_map` (經 mcs+prb 算出的理論值) |
| `mcs_dl` | 視窗平均 | DU `mcs_controller.get_mcs(ue)` |
| `rb_width_dl` | 視窗平均 | DU `rb_alloc_global[ue]` |
| `mimo_rank` | 視窗平均 | RU `cqi_indication.rank`（目前永遠 1） |
| `pdcp_sdu_volume_dl` | 視窗總和 | DU `tbs_map` 視同 PDCP byte（簡化）|
| `rlc_sdu_delay_dl_ms` | 視窗平均 | RLC entity `take_delay_samples()` (enqueue→dequeue 時間差) |
| `neighbor_cells[]` | 最後一筆覆蓋 | RU `cqi_indication.neighbors[]` → `_ue_registry[ue]['neighbors']` |

### 5.6 `_ue_registry`（in-memory，per-UE state）

| Key | 寫入時機 | 來源 |
|:---|:---|:---|
| `serving_cell` | F1AP setup/modification | CU `UeContext.serving_cell` |
| `sinr_db` | RU cqi_indication 來時覆蓋 | RU `dl_tti_pipeline` |
| `rsrp_dbm` | 同上 | 同上 |
| `qos_5qi` | register_ue 時設 | Dashboard payload，預設 9 |
| `neighbors` | RU cqi_indication 來時覆蓋 | RU 算 non-serving cells RSRP |
| `rank` | 不寫（PM accumulate 時取，預設 1） | hardcoded |

---

## 6. 端到端訊息走向（典型場景）

### 6.1 UE Attach (NGAP → F1AP UeContextSetup)

```
Dashboard → CU /NGAP/initial_ue_message
              ↓
CU mock AMF self-respond → CU /NGAP/initial_context_setup
              ↓
            CU 挑 first active CellConfig 為 initial serving cell
            CU 寫 UeContext.serving_cell=gnb4_c0
              ↓
CU → DU /F1AP/ue_context_setup {ue_id, drbs, rrc_message_b64, serving_cell_id="gnb4_c0"}
              ↓
            DU 寫 UeMacState.serving_cell_id="gnb4_c0"
            DU tick_runner.update_ue_serving_cell()
            DU 建 RLC entities for DRBs
              ↓
DU → CU 回 UeContextSetupResponse{ue_id, success, drb_setup_list}
```

### 6.2 一個 Tick 的 DL 流程（500ms）

```
Tick fires (DU internal threading)
  ↓
DU tick_runner._tick_body():
  - 收 RLC BO + delay samples
  - scheduler.allocate(...) → rb_alloc
  - mcs_controller.get_mcs(ue) → mcs
  - build_dl_tti(...) → DlTtiRequest
  ↓
DU → RU /FAPI/dl_tti_request {sfn, slot, pdus[{ue, prb, mcs, cell_id}]}
  ↓
RU dl_tti_pipeline.run(req):
  - Sionna ray trace → channel, path_gain
  - apply_pmi(H, pdu.pmi, pdu.layers) → H_eff
  - estimate_sinr / rank / cqi
  - 對每個 PDU 算出 CqiIndication
  ↓
RU → DU /FAPI/cqi_indication {ue, sinr, cqi, rank, pmi, rsrp, serving_cell, neighbors}
  ↓
DU FapiRouterController.cqi_indication():
  - mcs_controller.update(ue, sinr) → 學新 MCS
  - tick_runner.update_ue_sinr / update_ue_neighbors
  ↓
DU 回 RU {ue_id, new_mcs, smoothed_bler}
```

### 6.3 每 5 ticks 上報 CU

```
DU tick_runner._tick_body() (tick % 5 == 0):
  pm.flush_ue_report(ue) → 視窗 avg/sum
  build GnbDuMeasurementReport
  ↓
DU → CU /F1AP/measurement_report {ue, rsrp/sinr/throughput/.../neighbors}
  ↓
CU FapiRouterController.measurement_report():
  - 寫 MeasurementLog
  - A3 evaluator: serving_rsrp + neighbor_rsrp 比較
  - 若 A3 條件達 → execute_f1_handover → 後續流程見 6.4
```

### 6.4 Handover (A3 / xApp / 手動)

```
任意觸發點:
  A. CU A3 evaluator (在 measurement_report handler 內)
  B. xApp E2 Control Style 3/Action 1 → CU /E2/Control/request → e2_control_actor
  C. Dashboard → CU /Session/SessionController/handover
  ↓
CU handover_executor.execute_f1_handover(ue, target_cell, trigger):
  - 寫 HandoverEvent
  - 更新 UeContext.serving_cell = target_cell
  - 呼叫 ↓
  ↓
CU → DU /F1AP/ue_context_modification {ue_id, target_cell, rrc_message_b64}
  ↓
DU F1ApRouterController.ue_context_modification():
  - 更新 UeMacState.serving_cell_id
  - tick_runner.update_ue_serving_cell()
  ↓
下個 tick 的 PDU.cell_id 變成 target_cell
RU 收到後算 channel for target_cell
CqiIndication.serving_cell = target_cell
```

---

## 7. DU 內部資料倉

| 名稱 | 型態 | 內容 | 何時寫 / 讀 |
|:---|:---|:---|:---|
| `UeMacState` (DB) | persistent | UE 的 MAC 層狀態 (ue_id, serving_cell_id, ...) | F1AP setup/modification 寫；查詢用 |
| `RlcEntity` (DB) | persistent | RLC entity 配置 | F1AP setup 建；F1AP release 刪 |
| `Cell` (DB) | persistent | DU 提供的 cells | MacCellController create/update |
| `CellState` (DB) | persistent | cell on/off 狀態 | MacCellController disable/enable |
| `PrbQuotaStore` | in-memory | xApp 設的 PRB cap | E2 Control set/clear/list |
| `_ue_registry` | in-memory | UE 即時狀態 (sinr/rsrp/cell/neighbors) | F1AP setup 同步；cqi_indication 更新；tick 讀 |
| RLC factory entities | in-memory | RLC TX queue + delay samples | F1AP setup 建；inject_sdu 寫；tick drain 讀 |
| `RA Manager` | in-memory | Random Access state machine | F1AP setup 觸發 msg1/finalize |
| `HARQ Manager` | in-memory | HARQ process state | crc_indication 更新 |
| `mcs_controller` | in-memory | per-UE outer-loop LA history | cqi_indication 更新 |
| `pm_aggregator` | in-memory | per-UE / per-gNB measurement window | tick accumulate；flush 後重置 |

---

## 8. 一句話：DU 核心職責

> 收 RU 的 SINR/RSRP → 決定下個 tick 給每 UE 多少 PRB / 哪個 MCS → 通知 RU 在這個 cell 發 PDSCH → 把窗口內的 KPI（rsrp/sinr/throughput/delay/volume + neighbor RSRPs）每 2.5s 上報 CU → 接 CU 的 setup/HO/release 命令調整 UE 狀態。

對應 OAI：是 `nr_schedule_ue_spec_dlsch()` + `nr_mac_rrc_data_ind()` + F1AP message dispatcher 三者合體。
