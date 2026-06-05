# 大改造計畫:in-process 引擎 + slot-level MAC 模擬(branch: experiment/oai-fine-tick)

> 產出日期:2026-06-04
> 目標:讓 DT 的 KPM(尤其 delay)**物理忠實對齊 OAI、零 fudge**,同時**保住壓縮速度**。
> 路線:in-process 抽 HTTP(速度槓桿)+ slot-level MAC/HARQ 模擬(忠實度)+ Cython 熱迴圈。
> 前置理解:`docs/plan/granularity-bottleneck-and-fixes.md`、`p0b-subtick-delay-model.md`(B1 發現)。

---

## 0. 為什麼這樣改(一頁版)

**根因**:DT 一個 tick=500ms 一次帶過 1000 個 OAI slot → HARQ/slot 對齊/AM ACK 這些 slot 級延遲生不出來 → delay 比 OAI 低 → 只能用 `/30` + bug 偷偷補(load-bearing,一碰就垮)。

**修法兩刀**:
1. **in-process 抽 HTTP**:per-tick 63ms(~58ms HTTP)→ ~5ms。解速度天花板 + 騰出 slot loop 的 wall 預算。
2. **slot-level MAC 模擬**:tick 內跑本地 slot 迴圈,逐 0.5ms 模擬 MAC/RLC/HARQ → delay 自然湧現,不用 fudge。

**GPU 不用在這**:slot loop 是順序狀態機(slot N+1 依賴 N),不是 data-parallel → 用 **Cython/C**,不是 GPU。GPU 留給 channel(Sionna,已在)+ 未來 Monte-Carlo 掃參數。

**省多少**(估):per-tick 63ms → ~5-10ms(in-process + Cython slot loop)→ sustained ~8x → **~30-50x**,24h 場景從 ~3hr → **~30-50 分鐘**,且 delay slot-accurate。

---

## 1. 鐵律 / 設計約束

1. **不大爆炸**:分階段,每階段獨立可測、可 rollback。
2. **fidelity 先於架構**:Phase 0 先用純 Python 證明 slot-loop 能對齊 OAI,再投入架構工。對不上就不做架構。
3. **feature flag**:每階段藏 flag 後,default 維持現狀,驗證通過才切。
4. **保留現有資產**:subtick FIFO 排隊模型(= slot loop 的「排隊」那塊)、P0a/P1(漂移修,在 main)。

---

## 2. 分階段計畫

### ★ Phase 0 — slot-loop 忠實度(純 Python,shadow,**零架構改動**)← 最先做、最關鍵

**這是整個專案的 de-risk 關卡。** 先證明「slot 模擬能對齊 OAI delay」,再談架構。純 Python 慢沒關係(只驗忠實度,不驗速度)。

| 新檔 | 內容 |
|---|---|
| `RANsim-DU/main/apps/mac/services/optional/slot_engine/slot_loop.py`(新) | 獨立 slot 模擬器。輸入:per-UE(buffer SDU 帶 enqueue-slot、mean SINR)、TDD pattern、HARQ 參數、BLER 曲線、MCS。輸出:per-SDU sim-time delay |
| `slot_engine/bler_table.py`(新) | per-MCS 的 SINR→BLER(AWGN 查表 or sigmoid 近似,對 OAI 校) |

slot_loop 要模的(逐 DL slot):
- TDD:`is_dl_slot(slot)`(band78 DDDDDDDSUU,DL ratio 0.72)
- per-slot fast-fading:`inst_sinr = mean_sinr + fading_draw(slot)`
- HARQ:K1(PDSCH→ACK ~1-2 slot)、retx RTT ~4 slot、16 process;NACK→排 retx
- 排程:PF 分 PRB(retx 優先),SINR→MCS→TBS
- RLC drain:取 TBS bytes 組 PDU
- BLER:`P(fail)=bler(mcs,inst_sinr)` → 成功排 `slot+K1` deliver、失敗排 `slot+K_RTT` retx
- delay = `(deliver_slot - enqueue_slot) × 0.5ms`

**Hook(shadow)**:`tick_runner._tick_body` 在現有 calib 路徑**旁邊**也跑一次 slot_loop,**只 log 對照、不接管**(flag `SLOT_ENGINE_SHADOW=on`)。

**驗證 + 決策 gate**:跑 es/im,比 slot_loop delay vs OAI(normal-1 14.4 / im 17.5 / es 21.8ms)。校 **BLER 曲線 + K-offset**(物理參數,非 fudge)。
- 對得上(±20%,跨 phase,不靠 threshold 開關)→ **進 Phase 1**
- 對不上 → 留在 Phase 0 修模型(架構工先不投)

---

### Phase 1 — in-process DU↔RU(抽掉 FAPI HTTP,~30ms/tick)

現況:`tick_runner → build_dl_tti → RuClientBusinessService.post_dl_tti_request`(HTTP)→ RU `dl_tti_pipeline` 算 SINR → `du_callback` POST `cqi_indication` 回 DU(HTTP)。

| 改動 | 內容 |
|---|---|
| 抽 RU SINR 邏輯成共用模組 | `RANsim-RU/.../fapi_south/services/optional/dl_tti_pipeline.py` + `channel_cache_loader.py` 的 SINR 計算 → 抽進共用 lib(放 `ran-sim-protocol` 或新 `ran_phy/`),DU 可 import |
| DU 熱路徑改 in-process | `tick_runner` 第 561-569 行:`RuClientBusinessService.post_dl_tti_request`(HTTP)→ 改直接呼叫 in-process SINR 函式,CQI 變回傳值(不再等 `cqi_indication` HTTP callback) |
| channel cache 本地化 | cached mode 下 DU 直接 mmap 讀 npz(免 RU 中介) |
| RU 容器保留 | live mode / editor 仍走 RU(分開的 caller),DU 熱路徑 in-process |

flag:`DU_RU_INPROCESS=on`。省 ~30ms/tick。測:KPM 不變、tick 變快。

---

### Phase 2 — 熱路徑外 I/O 全 async(~20-30ms/tick)

| 改動 | 內容 |
|---|---|
| Omniverse ingest 移出 tick | DU per-tick 訊號/位置 push → 改 `queue.Queue` + 背景 thread 批次寫,**不擋 tick loop** |
| KPM/F1AP report 確認非阻塞 | measurement_report 已是 per-PM-window(非 per-tick),確認不阻塞 |

flag:`INGEST_ASYNC=on`。省 ~20-30ms/tick。測:viz/KPM 照常(只是 async),tick 更快。

→ Phase 1+2 後:per-tick ~63ms → ~5ms(純算),sustained ~8x → 理論 ~50-100x。

---

### Phase 3 — 把 Phase 0 的 slot-loop 接進 in-process 引擎(接管 delay)

- 現有粗 delay 路徑(calib `/30`)→ 換成 slot_loop 的輸出
- delay 變 slot-accurate **且** 架構已快
- flag `SLOT_ENGINE=on`(取代 shadow);此時純 Python slot loop 可能變新瓶頸 → Phase 4 解

---

### Phase 4 — Cython 化 slot-loop 內迴圈

- 1000-slot 順序 hot loop(MAC/RLC/HARQ 狀態機)→ 編成原生碼
- `slot_loop.py` 的內迴圈抽成 `slot_loop_core.pyx`(Cython),`setup.py` 加 build
- ~10-50ms → ~1-5ms/tick
- 測:KPM 不變,tick 大幅變快 → ~30-50x 可行

---

### Phase 5 — 完整驗證 + 清掉 fudge + 修回 budget

1. full_day_24hr 高壓縮跑,6-phase 對 OAI(PRB%/thp/delay),目標 ±20% **不靠 threshold 開關**
2. **重新引入 budget fix**(even-split → greedy)—— 此時 delay 是真的,budget 修對不會破壞對齊(這次失敗的根源解除)
3. **退役** `/30`、`_OAI_SLOT_MS`、`_DELAY_CALIB`、phase-aware threshold(`HIGH_TRAFFIC_BO_BYTES`)
4. 文件更新 + memory 護欄移除「別碰 even-split」(因為已可碰)

---

## 3. 省時間估算

| 階段 | per-tick wall | sustained | 24h 跑完 |
|---|---|---|---|
| 現況 | ~63ms | ~8x | ~3 hr |
| Phase 1+2(in-process) | ~5ms(+slot loop 10-50ms 純Py) | ~10-30x | ~1-2 hr |
| + Phase 4(Cython) | ~5-10ms | **~30-50x** | **~30-50 min** |

**且全程 delay slot-accurate 對齊 OAI,零 fudge。**

---

## 4. 風險 / rollback

| 風險 | 緩解 |
|---|---|
| slot-loop 對不上 OAI | **Phase 0 先擋**:純 Python 驗忠實度,對不上就不做架構工(沉沒成本最小) |
| in-process 合併破壞現有 RU/live mode | RU 容器保留;DU 熱路徑 flag 切換,default 走舊 HTTP 路徑 |
| Cython build 複雜度 | 只 Cython 內迴圈一個檔;純 Python 版保留當 fallback |
| 大改動引入回歸 | 每階段 flag + KPM 對照測;Phase 5 才退 fudge |

## 5. 保留 / 復用

- **subtick FIFO 模型** = slot loop 的「排隊」那塊,直接演進成 slot 級
- **P0a/P1/P1-out**(漂移修)= 在 main,不動
- **budget fix** = Phase 5 才回來(delay 變真後才安全)

## 關聯
- `docs/plan/granularity-bottleneck-and-fixes.md`、`p0b-subtick-delay-model.md`
- OAI 對照:`docs/test_records/full_day_24hr_3x_kpm_v7_2026-05-25.md`、`/home/mitlab/openairinterface5g`(MAC/HARQ 對照源碼)
