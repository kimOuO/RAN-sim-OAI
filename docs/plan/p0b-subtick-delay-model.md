# P0b 實作計畫:RLC delay 改「解析建模 sub-tick 排空」(B 方案)

> 產出日期：2026-06-01
> 目標：delay 從「跨 tick wall 量測 + `/30` 擬合」改成「粗 tick 內 FIFO 排隊解析計算」,
>       生出 ms 級、有物理依據、無 fudge 的 RlcSduDelayDl。
> 前置理解：`docs/plan/granularity-bottleneck-and-fixes.md`

---

## 0. 鐵律(設計約束,不可違反)

1. **觀測-only**:model 不改真實 buffer/排空狀態(byte 何時離開 buffer 仍是 tick 邊界)。
2. **byte 守恆**:model 算的排空總量 = 真實 budget(throughput/buffer 不受影響)。
3. **delay 是葉指標**:sim 內部無人消費它,只往上報 → 改它不影響 scheduler/HARQ/RC 落地。
4. **feature flag 隔離**:`RLC_DELAY_MODEL = calib(現狀) | subtick(新)`,default `calib`,
   驗證通過前絕不動現有 OAI 對齊路徑。

---

## 1. 模型:單伺服器 FIFO 排隊(G/D/1)

每個 tick,排空速率固定 `rate = budget_bytes / sim_dt_ms`(bytes/sim-ms)。
SDU 帶 sim-time 到達時戳 `arrival_sim_ms`。維護一個 per-entity 跨 tick 的伺服器游標
`_server_free_sim_ms`。FIFO 遞迴:

```
for sdu in queue (FIFO):
    drained = 這 tick 從這顆排掉的 bytes(= 現有 segment() 的 take 邏輯)
    service_start  = max(sdu.arrival_sim_ms, _server_free_sim_ms)
    service_finish = service_start + drained / rate
    _server_free_sim_ms = service_finish
    if sdu 完全排空 (bytes_remaining == 0):
        delay_ms = service_finish - sdu.arrival_sim_ms     # ← sim-time,ms 級
        emit delay_ms
    # 部分排空:不 emit,游標已前進,下個 tick 用新 rate 接續
```

**為什麼這給 ms 級**:
- 不塞車:`service_start ≈ arrival`,delay ≈ `drained/rate` = 傳輸時間(小,ms 級,像 OAI 14ms)
- 塞車:`service_start` 被前一顆的 `finish` 主導 → delay 自然長(buffer 堆積)
- 兩種情況都物理正確,**不需要 `/30`**。

---

## 2. 命門:到達時戳必須在 tick 內「散開」

若所有 SDU 都記成 tick 起點到達 → FIFO 下尾包 `finish ≈ tick_start + sim_dt` → delay≈500ms,
粗 tick 問題復發。**必須用 batch 的 `ts_offset_us` 把到達散在 tick 的 sim-time 軸上。**

料現成:`rlc_data_actor.inject_sdu_batch` 已經有 per-packet `ts_offset_us`(rlc_data_actor.py:90-93)。

**做法**:`recv_sdu` 時用 DU sim-clock + offset 比例算 sim-time 到達:
```
arrival_sim_ms = now_sim_ms - (1 - ts_offset_us/window_us) × sim_dt_ms
```
即「這顆在過去一個 sim_dt 內、位置 offset_fraction 處到達」。offset_fraction 保留 batch 內
相對間距 → 散開 → 各包快速排空 → ms 級。

> 注意:此「到達分布映射」是**物理輸入模型**(非輸出 fudge),是 B 的主要待校 tunable —
> 對 OAI 驗證時調的是這個,而非在輸出端乘係數。

---

## 3. 具體改點

| # | 檔案 | 改動 |
|---|---|---|
| 1 | `rlc/services/optional/segmentation/segmenter.py` `SduItem` | 加欄位 `arrival_sim_ms: float = 0.0`(沿用既有 `enqueue_ts_ms` 不動,新增 sim-time 欄) |
| 2 | `rlc/.../entities/am_entity.py` `recv_sdu` | 簽名加 `arrival_sim_ms`;建 SduItem 時帶入。加 per-entity 游標 `self._server_free_sim_ms`(start/reset 清 0) |
| 3 | `rlc/actors/rlc_data_actor.py` `inject_sdu_batch` | 從 runner 拿 `now_sim_ms` + `sim_dt_ms`,用 §2 公式算 `arrival_sim_ms` 傳給 `recv_sdu`。`inject_sdu`(非 batch)退化:`arrival_sim_ms = now_sim_ms` |
| 4 | `segmenter.py` `segment()` | 加參數 `rate_bytes_per_sim_ms`、`server_free_sim_ms`(in/out)、`now_sim_ms`。`RLC_DELAY_MODEL=subtick` 時走 §1 FIFO 遞迴算 sim-time delay;`calib` 時走原 `now_ms - enqueue_ts`(完全不動) |
| 5 | `am_entity.generate_pdu` | 把 entity 的游標 + rate + now_sim_ms 傳進 segment;接回更新後游標 |
| 6 | `tick/.../runner/tick_runner.py` | (a) 算 `rate = budget/sim_dt` 傳進 generate_pdu;(b) 暴露 `now_sim_ms = tick_count × sim_dt`;(c) `RLC_DELAY_MODEL=subtick` 時**跳過** `_DELAY_CALIB`(:308-327)——delay 已是 sim-time 原生,不再乘 `/30` |

> `_OAI_SLOT_MS`、`/30`、`HIGH_TRAFFIC_BO_BYTES` 等只在 `calib` 路徑用;`subtick` 完全繞過。
> 驗證通過後才考慮刪除(見 [[oai_slot_delay_calib_dont_touch]],別在驗證前刪)。

---

## 4. 分階段交付

| 階段 | 內容 | 驗證 |
|---|---|---|
| **B1** | 改點 1-6,flag `subtick`,FIFO model + 到達散開上線(default 仍 `calib`) | sanity:跑 es_1hr `subtick`,delay 應 ms 級、隨負載升降、不爆 500ms |
| **B2** | 對 OAI 校正:跑 full_day_24hr `subtick`,對 v7 的 OAI delay(normal-1 14.4 / im 17.5 / es 21.8ms)比對 | 目標 ±20%,**只調 §2 到達分布模型**,不准加輸出 fudge |
| **B3** | 確認 6 phase 對齊 ≥ calib 後,default 翻 `subtick`,標記 `/30` 系列為 legacy | A/B:subtick vs calib 對 OAI 對齊度 |

> B2 完整跑 full_day_24hr 3x ≈ 8hr wall。B1 sanity 用 es_1hr 短跑即可(分鐘級)。

---

## 5. 風險

| 風險 | 緩解 |
|---|---|
| 破壞現有 OAI delay 對齊 | flag 隔離,default `calib`,B3 驗證通過才翻 |
| 到達分布映射(§2)需調 | 它是物理 tunable,對 OAI 調;比 `/30` 有依據、可解釋 |
| 跨 tick 游標漏清(HO/stop 殘留) | start()/HO RLC 重建時 reset `_server_free_sim_ms`(跟 buffer 清空同步) |
| rate=0(idle tick)除零 | rate≤0 時跳過 delay 計算(本來就沒排空) |

---

## ★ B1 驗證結果(2026-06-01)— 重要發現,推翻原假設 ★

B1 全改點落地、編譯通過、subtick flag 上線跑 es_fast/es_1hr,**機制正常**:
不崩、observational-only(buffer 不受影響)、delay sim-time 原生、隨負載起降、idle=0。

**但 magnitude 不是 ms 級,而是穩態 ~430ms**(es_1hr@4x,sim720-1020 穩態):

| | throughput | delay | buffer |
|---|---|---|---|
| subtick 穩態 | 2.04 Mbps | **429ms** | 140KB |

`delay ≈ buffer/rate = 140KB / 2Mbps ≈ 560ms`(Little's law)→ **模型算得完全正確**。

### 發現:delay 大是「真實佇列」,不是量測假象

原假設(本文件 §1、granularity 文件)認為「delay 大是粗 tick 量子化 → B 重算即可 ms 級」。
**B1 證明這只在「佇列空」時成立。** 實際 DT 在持續流量下有**真實的 ~140KB 常駐 backlog**,
新封包 FIFO 排在後面就是得等 ~430ms。模型誠實報出 → 沒錯。

backlog 來源:
1. **注入是大塊 burst**(UE 每 ~100ms wall 灌 ~100KB,HTTP 成本逼出的 batch)
2. **排空 tick 粒度 + 容量邊際**(drain ≈ inject ≈ 2Mbps,清不掉 standing queue)

OAI 沒此 backlog,因每 0.5ms slot 連續排空 → 佇列近空 → 14ms。**calib 的 `/30` 是把真實的
430ms 硬壓成虛構 14ms。**

### 結論:B 單獨無法達 OAI ms 級

delay 不是 metric bug,是**真實佇列** → 重算 metric 解不掉。要消 430ms 得攻 backlog 本身:
- 注入改細水(違反 HTTP-batch 設計)
- 或排空改細粒度(= ① 架構根:DU↔RU async/in-process,降 wall_tick → 細 tick → 連續排空)

→ **又繞回 ① HTTP-per-tick 架構根。** B1 的價值是**把被 `/30` 蓋住的真相照出來**:DT delay 大
是物理真實。default 已還原 `calib`(subtick 現比 calib 離 OAI 更遠),程式留 flag 後待 ① 解了再用。

### 待決定(更新)
1. 接受「DT delay 是結構性大、calib 用 fudge 對齊 OAI、xApp 驗證時知道這是近似」?(務實)
2. 還是投入 ① 架構根(DU↔RU async),讓排空細粒度 → backlog 自然消 → subtick 才生 ms 級?(治本大改)
3. 或 B 加「sub-tick 連續排空 backlog」的進階建模,試圖在不改架構下逼近(中等,但 §B1 顯示 backlog 是真實狀態,建模能壓多少存疑)

## 關聯
- `docs/plan/granularity-bottleneck-and-fixes.md` — 為何選 B(注:B1 發現修正了其樂觀預期)
- `docs/debug_records/2026-06-01_oai_slot_delay_calib_dont_touch.md` — `/30` 別在驗證前刪
- `docs/test_records/full_day_24hr_3x_kpm_v7_2026-05-25.md` — B2 對齊目標數據
