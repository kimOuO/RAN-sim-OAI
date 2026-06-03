# 粒度瓶頸(granularity bottleneck)— 根因、影響、解法探討

> 產出日期：2026-06-01
> 起點：P0a/P1/P1-out 修完速度/throughput/buffer/KPM 頻率的「誠實度」後,delay 仍要靠
>       `/30` 擬合校正。追問「瓶頸在哪、OAI 為何做得到」逼出這份分析。

---

## 1. 根因:跨容器 HTTP 成本鎖死了「粒度 × 速度」

```
wall_tick 物理底限 ≈ 跨容器 HTTP RTT 串接 ≈ 50ms(DU→RU→DU→Omniverse,壓不下去)
sim_speed = sim_dt_ms / wall_tick_ms
  → 要有用的速度(10x):sim_dt ≥ 50ms × 10 = 500ms  ← 被迫粗 tick
  → 要細 tick(sim_dt=0.5ms,對齊 OAI slot):speed = 0.5/50 = 0.01x  ← 慢 100×,沒意義
```

**結論**:細 tick 不是不可能,是「細 tick 跟有用的速度不能同時要」。DT 選了速度(任務是快轉
驗證 xApp)→ 被迫 sim_dt=500ms 粗 tick。**總根 = 同步 HTTP per tick。** 這也是 ①速度上限、
②RC 閉環遲到、③delay 失真 的共同根 —— 三者都是「tick 太貴 → 被迫粗顆粒」的不同出口。

## 2. 為什麼 OAI 沒這問題

| | DT | OAI |
|---|---|---|
| 架構 | 5 容器,每 tick 跨容器 HTTP | 單體 C,in-process |
| 一 tick wall 成本 | ~50ms | <<0.5ms(函式呼叫) |
| 排程粒度 | 被迫 500ms | 真的每 0.5ms slot |
| delay 怎麼來 | 粗 tick 生不出 → 校正捏 | 每 slot 真排程+排空 → ms 級自然湧現 |

OAI 是「真的做」;DT 是「近似 + 校正」。這是**設計取捨**,不是 bug:DT 換到可加速/可視化/
可插 xApp 閉環,代價是時間型指標要校正;OAI 換到 slot 級保真,代價是不能快轉。

## 3. 粗 tick 對三個 KPM 的影響(程度差很多 — 關鍵)

| 指標 | 受傷 | 機制 | v7 實際對齊 |
|---|---|---|---|
| **throughput / volume** | 🟢 最輕 | 「窗內平均」型,平均對粗取樣耐受;只要窗內總排空 byte 對就對 | ⭐ 5/6 phase ±25% |
| **PRB%** | 🟡 中 | 「每決策」型,OAI 每 slot 決策(min_rbSize=5),DT 每 500ms 一次 → 顆粒差,靠 MIN_PRB 校正,低流量仍結構偏高 | 🟡 高流量~50%、低流量過高 |
| **delay** | 🔴 最重 | 「時間」型,直接被 tick 量子化(0/500/1000ms…),物理生不出 ms 級 → 靠 `/30` 硬捏,最脆弱 | 🟡 normal-1 重捏才 117%,其他 18-310% |

**洞察**:平均型指標幾乎不受傷(所以早就對齊好),時間型指標(delay)最直接暴露粗 tick 這個根。

---

## 4. ★ 解法探討 ★

### 關鍵突破:HTTP 成本只逼粗了「channel 那一段」,沒逼粗「queue 延遲」

重新拆解 DU tick 在做的事:
- **跨容器、貴(HTTP-bound)**:DU→RU 拿 channel/SINR(必須粗,每 ~50ms 一次)
- **本地、便宜(純 DU 內計算)**:RLC buffer 排空、SDU 延遲累計 —— **這段是純本地 Python,跟
  HTTP 無關,可以在每個粗 tick 內部用任意細的粒度去「算」,近乎零成本**

→ **delay 的精度不需要細 tick,也不需要砍 HTTP。它需要的是:把 delay 從「跨 tick 量測」
改成「在粗 tick 內部解析地建模 sub-tick 排空」。** 這把「channel 更新粒度(被迫粗)」跟
「queue 延遲粒度(可以細)」解耦 —— 這是整個解法的支點。

### 三條路線

| 路線 | 做法 | 能對齊到 | 工作量 | 風險 | 砍 HTTP? |
|---|---|---|---|---|---|
| **A. P0b-淺** | segmenter delay 改 sim-time(tick 數×sim_dt)量測,`/30`/`_OAI_SLOT_MS` 退役,改用真實比 sim_dt/slot 校正 | 誠實 + 校正有物理依據,但**仍粗顆粒**(底層還是 500ms 量子) | 小-中 | 中(要重跑 OAI 對齊) | 否 |
| **B. P0b-深** ⭐ | delay 改「算」不「量」:每個粗 tick 內,用 SDU 到達時戳(batch mode 的 `ts_offset_us` 已有)+ 排空預算,**解析地模擬 sub-tick(slot 級)排空**,算出每包真實排隊延遲 | **ms 級、有物理依據、無 fudge** —— 粗 tick 也能生出對齊 OAI 的 delay | 中-高 | 中-高(要建模+對 OAI 驗證) | 否 |
| **C. 架構根治 ①** | DU↔RU 改 async/in-process、Kit ingest 移出 tick 路徑 → wall_tick 底限降低 → 可跑細 tick at speed → delay 自然湧現 | 真·OAI 級(①②③ 全改善) | 大 | 高(動核心架構) | 是 |

### 推薦:D = B(只對 delay)+ 維持其他不動

- throughput/PRB 已對齊得好(平均/決策型對粗 tick 耐受)→ **不要動**
- 只有 delay(時間型)需要修 → 用 **B 解析建模**,因為:
  1. 不必砍 HTTP 架構(C 的大改可長期再說)
  2. 不必細 tick(避開速度代價)
  3. 比 A 好:A 還是粗顆粒只是校正有依據;B 是真的生出 ms 級
  4. **料已備好**:batch mode 的 per-packet `ts_offset_us`(`traffic_gen` 已送)就是 sub-tick
     到達時戳,B 的輸入現成

### B 的具體構想(待細化)

在 `segmenter.segment()` 或 `pm_aggregator` delay 計算處:
- 每個 tick 的排空預算 budget_bytes 視為「這 500ms sim 內、分散在 ~1000 個虛擬 slot 上」
- SDU 帶 enqueue 的 sub-tick offset(來自 `ts_offset_us`)
- 用 FIFO + 每虛擬 slot 排空速率,算每包「從 enqueue offset 到被排空的 slot」的 sim-time 差
- → 得到 ms 級 delay 分布,平均即 RlcSduDelayDl
- 校正:理論上**不需要 fudge**;若殘差,用真實 slot=0.5ms 為單位(非 `/30`)

驗證:對 v7 的 OAI delay(normal-1 14.4ms / im 17.5ms / es 21.8ms…)比對,目標 ±20% 且
**不靠 phase-aware threshold 那種脆弱開關**。

---

## 5. 待決定

1. 做 B(深)還是先 A(淺)?B 工程量大但治本、退役 fudge;A 快但治標。
2. C(砍 HTTP)是否排入長期路線?它同時解 ①②③,但風險最高。

## 關聯
- `docs/debug_records/2026-06-01_p0a_p1_drift_fix.md` — 已修的速度/吞吐誠實度(P0a/P1/P1-out)
- `docs/debug_records/2026-06-01_oai_slot_delay_calib_dont_touch.md` — 為何 `/30` 不能單獨改
- `docs/test_records/full_day_24hr_3x_kpm_v7_2026-05-25.md` — 三指標對齊 OAI 的實測(throughput好/PRB中/delay脆)
- `docs/test_records/sim_speed_ceiling_2026-05-23.md` — HTTP RTT ~50ms/tick 的實測拆解
