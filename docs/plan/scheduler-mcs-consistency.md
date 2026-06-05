# 修正計畫:scheduler / TBS / throughput 統一用操作點 MCS(消除內部不一致)

> 產出:2026-06-04
> 起因:es_1hr@3x shadow 顯示 slot_loop delay ~4.4x OAI(96ms vs 21.8),根因是
> **scheduler 用樂觀 `sinr_to_mcs` 算 PRB 需求 → 只給 ~8 PRB(真實要 ~20)**。
> 前置:`docs/plan/in-process-slot-engine.md`、memory `phase0_es1hr_result`。

---

## 0. 一頁版

**病根**:DT 內部對「一個 PRB 能塞多少 bytes」有兩套互相矛盾的 MCS:
- `mcs_controller`(BLER 閉環 AMC)= **操作點 MCS**(~10% BLER),是對的源頭,RIC 報的 MCS 也是它。
- 但 `pf_scheduler`(算 PRB)、`tick_runner` TBS budget(bps_re)、`phy_high` throughput 都還用**樂觀 `sinr_to_mcs`**(無視 BLER,SINR10→mcs16 vs 操作點 mcs7,每 PRB 容量差 2.65x)。

**後果**:scheduler 以為 8 PRB 夠 → 實際真實鏈路要 ~20 → honest slot_loop 報排隊 96ms。`/30` calib 把 delay 硬湊回 18ms 遮住病。OAI 自洽(scheduler+PHY 同用真實 MCS)→ 給足 PRB → 21.8ms。

**修法**:讓 PRB 需求 / TBS / throughput **全部改用操作點 MCS + 對應 bps_re**(單一來源),不再用樂觀表。= 修不一致,非把模型改悲觀。

**這會動到現役 KPM**(PRB% 升 ~2.7x、throughput/delay 重算),所以全程 flag-gate + 對 OAI 重新校。

---

## 1. 鐵律

1. **flag-gate**:`SCHED_MCS_CONSISTENT`(預設 off),off 維持現狀,驗證過才切。
2. **單一 MCS 來源**:per-UE-per-tick 的 `(mcs, bps_re)` 只能有一個源頭(operating-point),所有消費端共用。
3. **先量後改**:Phase 1 先用 shadow 預測影響(PRB%/throughput 會變多少),再動現役。
4. **KPM 不退化才算過**:PRB%/throughput/delay 三者對 OAI 同時不變差,且排序/趨勢正確。

---

## 2. 統一的 MCS 真相來源(先建)

三張 BLER/required 表目前分散:`ldpc_abstract._MCS_SINR_REQUIRED_DB`(slot_loop 經 bler_table 用)、`mcs_controller._MCS_SINR_REQUIRED_DB`(自己一份)、`mcs_table`(樂觀,要退場)。

| 動作 | 內容 |
|---|---|
| 確認 controller 與 ldpc_abstract 的 required 表一致 | 兩份應相同(copy);若有差先合一,否則 scheduler 用的 mcs 跟 slot_loop 不同步 |
| 建 `(mcs)→bps_re` 單一 helper | slot_loop 已有 `_eff_for_mcs`(由 mcs_table 的 mcs↔bps_re 插值);抽成共用,給 scheduler/tick_runner 共用 |
| 定義 per-UE 取數 API | `mcs = mcs_controller.get_mcs(uid)`;`bps_re = eff_for_mcs(mcs)` → 這對就是全系統唯一真相 |

---

## 3. 分階段

### Phase 1 — 影響預測(shadow,不動現役)
在 tick_runner(已有 shadow hook)旁,**額外 log「若用操作點 MCS 算的 prb_needed」**對照現役 rb_alloc。跑 es_1hr/im_1hr,量:
- 操作點 prb_needed vs 現役 rb_alloc 差幾倍(預期 ~2.7x)
- 換算 PRB% 會從 ~3% 升到多少
- **決策 gate**:升幅是否合理(對 OAI es/im PRB% 參考;OAI 參考需先撈)。離譜就先查表/SINR 來源,不硬切。

### Phase 2 — scheduler PRB 需求改操作點(flag-gate)
`pf_scheduler.allocate` line 69:`sinr_to_mcs(sinr)` → 改用 `(get_mcs(uid), eff_for_mcs(...))`。
- `prb_needed`、`inst_rate`(PF weight)都用這對。
- flag `SCHED_MCS_CONSISTENT=on` 時生效,off 走舊。
- 注意:scheduler 拿不到 mcs_controller 時(caller 沒帶)要 fallback。
- 測:PRB 配置升到 ~20,PRB% 升;**slot_loop shadow delay 應同步往 OAI 掉**(這是主要驗證點)。

### Phase 3 — TBS budget / throughput 的 bps_re 修對
- `tick_runner:509`:`_, bps_re = sinr_to_mcs(sinr)` → `bps_re = eff_for_mcs(mcs_ctl.get_mcs(uid))`(跟它 line 507 已取的 mcs 配對,修掉 mcs/bps_re 錯配)。
- `phy_high_actor:40`:同樣改 bps_re 來源。
- 測:throughput KPM 不應暴跌(PRB 升 × 每PRB 降,淨值穩);drain budget 自洽。

### Phase 4 — KPM 重新校(這步最危險,動 load-bearing)
PRB 升 + drain 自洽後,delay/PRB%/throughput 全位移,要重校:
- **PRB%**:`PRB_OAI_CALIB`(現 1.0)對 OAI es/im PRB% 重設。
- **Delay**:PRB 給足後底層 delay 下降 → `/30`(`_DELAY_CALIB`/`HIGH_TRAFFIC_BO_BYTES`)會把 calib 壓更低 → 需重估;**理想是讓 slot_engine 接管 delay(in-process-slot-engine Phase 3),退掉 /30**,而不是再湊 /30。
- **throughput**:確認 actual_drained 對 OAI。

### Phase 5 — 對 OAI 驗證 + 收尾
- 跑 es_1hr + im_1hr(必要時 full_day_24hr),flag on:
  - calib KPM:PRB%/throughput/delay 對 OAI ±20%,且不比 flag-off 差。
  - shadow slot_loop delay:應從 ~96ms 掉向 OAI ~22ms(證明 PRB 修對)。
- 過 → flag 轉預設 on;`sinr_to_mcs` 標記僅供粗估 / 逐步退場。
- 更新 memory:解除「scheduler PRB 樂觀」病,記新基準。

---

## 4. 風險 / 緩解

| 風險 | 緩解 |
|---|---|
| PRB% 暴升觸發 xApp 誤判(IM/CCO 門檻) | flag-gate;Phase 1 先量升幅;Phase 4 重校 PRB_OAI_CALIB |
| throughput 因 bps_re 改而失真 | Phase 3 mcs/bps_re 配對自洽;比對 actual_drained |
| 動到 /30 連鎖崩(memory 警告) | 不單獨碰 /30;走 slot_engine 接管 delay 的正路(in-process Phase 3) |
| 三張 BLER 表不同步 → scheduler mcs ≠ slot_loop mcs | Phase 2 前先合一 required 表 |
| 漏改某個 MCS 消費端 → 新不一致 | 已盤點 4 處(pf_scheduler / tick_runner TBS / phy_high / 經 controller 的 fapi);逐一改 |

## 5. 盤點:現役所有 MCS 消費端(改動清單)
- `pf_scheduler.py:69` — PRB 需求 + PF weight ❌→改
- `tick_runner.py:507-510` — TBS drain budget(mcs 對、bps_re 錯)❌→改 bps_re
- `phy_high_actor.py:40-41` — throughput 報告 ❌→改 bps_re
- `mcs_controller.get_mcs` / `fapi_router_actor:38` — 已操作點 ✅ 不動(當真相源)
- `slot_engine/slot_loop.py` — 已操作點(改動一三刀)✅

## 關聯
- `docs/plan/in-process-slot-engine.md`(slot_engine 接管 delay 是退 /30 的正路)
- memory:`phase0_es1hr_result`、`cached_sinr_bug`、`oai_alignment_params`
