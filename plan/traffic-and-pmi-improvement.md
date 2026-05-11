# 計畫：補 Traffic Injector + 修 PMI/Layers Hardcoding

## 背景

### 現況
1. **PMI/layers hardcoded**：DU `tti_builder` 對所有 PDU 寫死 `pmi=0, layers=1` → RU `dl_tti_pipeline` 用 codebook[0] 投影 H → SINR/CQI/rank 系統性失真（永遠 rank=1，throughput 損失 ~75%）。
2. **沒有 traffic injector**：sim 無自動 SDU 注入機制，所有 UE 的 RLC BO=0 → `DRB.UEThpDl / RRU.PrbTotDl / DRB.PdcpSduVolumeDL / DRB.RlcSduDelayDl` 都永遠是 0。

### 對應到專案目標
參考 `intents-interface.md` 的劇本（IM/CCO/ES 三 case 的 KPM 觀察欄位）：

| KPM Field | IM 用 | CCO 用 | ES 用 | 沒 traffic 時 |
|:---|:---:|:---:|:---:|:---|
| `RRU.PrbTotDl` | 主 | 主 | 主 | 永遠 0 |
| `DRB.UEThpDl` | 主 | 副 | 副 | 永遠 0 |
| `DRB.RlcSduDelayDl` | 主 | — | — | 永遠 0 |
| `DRB.PdcpSduVolumeDL` | — | — | 主 | 永遠 0 |

xApp **不看** SINR / CQI / RSRP（拒絕清單）→ PMI 失真 *對 xApp decision logic 完全無感*。

但 PMI/layers 失真會**間接**讓 throughput 偏低 ~75% → KPI 觸發點偏 false positive。

### 結論
**P0 (must-do)**：補 traffic injector — 沒這個 xApp 看到的 KPM 永遠 0，IM/CCO/ES 都跑不了。
**P2 (defer)**：修 PMI/layers — 等 traffic injector 上後實測 KPI 是否合理再決定。

---

## Phase 1: Traffic Injector (P0)

### 1.1 設計選項對比

| 方案 | 實作位置 | 優點 | 缺點 | 對齊真實 OAI |
|:---|:---|:---|:---|:---|
| **A. DU 內建 service** | DU container 內背景 thread | 不需新 container；隨 DU 啟停；統計易整合 | DU code 變大 | ⚠️ 真實 OAI 沒這個（traffic 由 UE app / iperf 產） |
| **B. Sidecar container** | docker-compose 新增 traffic-gen container | 隔離；可獨立配置；換 traffic pattern 容易 | 多一個 container | ✅ 對齊 iperf-style 外部 traffic |
| **C. Dashboard 按鈕** | 前端按鈕觸發單次 inject | UI 直觀；按需 | 不持續；demo 需 user 一直按 | ❌ 不對齊真實 |

**推薦：方案 A + 部分 C**
- A：DU 內建 `TrafficInjectorService`，可從 Dashboard 啟停，對選定 UE 持續注 SDU（背景 thread）。
- C：Dashboard 加「Traffic Generator」面板，可開/關 + 設定 rate（Mbps）+ 選 UE。
- 不採 B：對 sim 來說 sidecar 過度複雜，且 inject_sdu endpoint 已存在，內部 thread 直接呼比較簡單。

### 1.2 改動清單

#### 1.2.1 DU 端：新建 `TrafficInjectorService`

**新增**：`/home/mitlab/XAPP_DT/RANsim-DU/main/apps/rlc/services/optional/traffic_generator/`

```
traffic_generator/
├── __init__.py
└── injector.py        # TrafficInjectorService（背景 thread）
```

**核心邏輯** (`injector.py`):
```python
class TrafficInjectorService:
    """背景 thread，週期對選定 UE 注 SDU。對齊 iperf-style constant-bitrate UDP。"""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._config: dict[str, dict] = {}  # ue_id -> {bearer_id, rate_mbps, sdu_size_bytes}

    def configure(self, ue_id: str, *, rate_mbps: float, sdu_size_bytes: int = 1500, bearer_id: int = 1):
        """設定 / 更新某個 UE 的 traffic profile。rate_mbps=0 → 停這個 UE 的 traffic."""
        if rate_mbps <= 0:
            self._config.pop(ue_id, None)
        else:
            self._config[ue_id] = {
                "bearer_id": bearer_id,
                "rate_mbps": rate_mbps,
                "sdu_size_bytes": sdu_size_bytes,
                "next_inject_at_ms": int(time.time() * 1000),
            }

    def list_active(self) -> list[dict]:
        return [{"ue_id": uid, **cfg} for uid, cfg in self._config.items()]

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="traffic-gen")
        self._thread.start()
        return True

    def stop(self) -> bool:
        self._stop.set()
        return True

    def _loop(self):
        # Tick 100ms — 對每個 configured UE 看是否該注新 SDU
        while not self._stop.is_set():
            now_ms = int(time.time() * 1000)
            for ue_id, cfg in list(self._config.items()):
                if now_ms < cfg["next_inject_at_ms"]:
                    continue
                # 計算下一次注入時間 (constant-bitrate)
                bytes_per_sdu = cfg["sdu_size_bytes"]
                bits_per_sdu = bytes_per_sdu * 8
                interval_ms = max(1, int(bits_per_sdu / cfg["rate_mbps"] / 1000))
                cfg["next_inject_at_ms"] = now_ms + interval_ms

                # 注入 — 經由 RLC entity_factory.lookup
                ent = entity_factory.lookup(ue_id, "DRB", cfg["bearer_id"])
                if ent is not None:
                    ent.recv_sdu(bytes_per_sdu)
            self._stop.wait(0.1)


_singleton = None
def get_traffic_injector() -> TrafficInjectorService:
    global _singleton
    if _singleton is None:
        _singleton = TrafficInjectorService()
    return _singleton
```

**Endpoint**（新建 `rlc_data_actor.py` 的 controller 或單獨）:
- `POST /api/v0.1/DU/RLC/TrafficGenerator/start` — 啟動服務
- `POST /api/v0.1/DU/RLC/TrafficGenerator/stop` — 停止
- `POST /api/v0.1/DU/RLC/TrafficGenerator/configure` — body `{ue_id, rate_mbps, sdu_size_bytes?, bearer_id?}`
- `POST /api/v0.1/DU/RLC/TrafficGenerator/list` — 看當前 active 的 traffic profiles

#### 1.2.2 Dashboard 端：Traffic Generator 面板

**修改**：
- `/home/mitlab/XAPP_DT/Physics_sim/Dashboard/components/...`

加一個面板（典型放在 /sim 頁的 sidebar 或 /logs 頁）：
```
┌─ Traffic Generator ─────────────────────┐
│ [Start] [Stop]                          │
│                                         │
│ UE 設定:                                │
│  ▼ UE2  | Rate: 5  Mbps | SDU: 1500 B  │
│  ▼ UE3  | Rate: 0  Mbps | SDU: 1500 B  │
│  [Apply]                                │
│                                         │
│ Active:                                 │
│  UE2 → 5.0 Mbps                         │
└─────────────────────────────────────────┘
```

呼叫 DU `/RLC/TrafficGenerator/configure` + `start/stop`。

#### 1.2.3 Service lifecycle

- DU 容器啟動時：**不**自動啟 traffic injector（避免 demo 時搞混）。
- Dashboard Start Sim 時：**不**自動啟（user 明確按按鈕才啟）。
- DU 容器停時：thread daemon=True 會自動結束。

### 1.3 驗證

1. Dashboard 開 Traffic Generator → 設 UE2 = 5 Mbps → Start
2. 觀察 DU log：每 ~2.4ms 一次 RLC inject (5 Mbps / 1500 B SDU = 416 SDU/s = ~2.4ms interval)
3. 等 5 ticks (~2.5s) 後查 KPM:
   ```bash
   curl POST /CU/E2/E2KpmReporter/read | jq '.data.ue_status[] | {ue_id, throughput_dl_mbps}'
   ```
   應看到 UE2 throughput > 0
4. 觀察 RIC 端 Indication 內 `DRB.UEThpDl` 不再是 0

---

## Phase 2: PMI / Layers 修正（P2，traffic 上後評估）

### 2.1 評估準則

跑完 Phase 1 後，用以下條件決定要不要做 Phase 2：

| 條件 | 結論 |
|:---|:---|
| traffic on，throughput KPI 數值「合理」（不偏太離譜） + IM/CCO/ES 觸發點不需要造假 | **不做 Phase 2**，調 threshold 即可 |
| traffic on，throughput 永遠 < 5 Mbps 但需要 demo 高負載場景 | **做 Phase 2 A+B**（PMI search + rank selection） |
| 需要研究 MIMO-aware xApp（非本期目標） | 整套做 A→D |

### 2.2 修法（如果要做）

#### A. PMI codebook search at RU

**改 `RU/dl_tti_pipeline.py`**：每 N tick（例：N=5）對每個 UE 做 PMI search。

```python
# RU 算 channel 後，loop 過 codebook 找 SINR 最大的 PMI
def _select_best_pmi(H, layers, codebook_size, noise_floor_dbm):
    best_pmi = 0
    best_sinr = -float("inf")
    for pmi in range(codebook_size):
        try:
            H_eff = precoder.apply_pmi(H, pmi=pmi, layers=layers)
            sinr = sinr_estimator.estimate_sinr(H_eff, noise_floor_dbm)
            if sinr > best_sinr:
                best_sinr = sinr
                best_pmi = pmi
        except codebook.CodebookError:
            continue
    return best_pmi, best_sinr
```

把選出的 PMI 寫進 `CqiIndication.pmi` 回給 DU。DU 下個 tick 用這個 PMI 寫進 `pdu.pmi`（取代 hardcode 0）。

成本：每 N tick 多算 codebook_size 次 SVD。對 4-port codebook 大約 16-32 個候選；每 5 ticks 算一次 → 平均每 tick 多 ~6 次 SVD。

#### B. Rank selection (3GPP TS 38.214)

```python
def estimate_rank_from_sinr(sinr_db: float) -> int:
    """3GPP TS 38.214 Table 5.2.2.1-2 對應的 rank threshold（簡化版）。"""
    if sinr_db < 5:    return 1
    if sinr_db < 15:   return 2
    if sinr_db < 25:   return 3
    return 4
```

把這個取代現在的 `estimate_rank(H_eff)`（後者是 SVD 條件數，永遠 ≤ ports）。

#### C. Per-layer SINR (進階)

當 rank > 1，要對每 layer 算 effective SINR，再 average 或取 min：
```python
sinr_per_layer = sinr_estimator.estimate_sinr_mmse(H, layers=rank)
sinr_eff = exp_eff_sinr(sinr_per_layer)  # mutual-info-based effective SINR
```

需要：實作 MMSE receiver 模型 + EESM/MIESM 公式。工作量中等。

#### D. CSI feedback loop

DU 把 RU 回的 PMI 存進 `_ue_registry[ue]['pmi']`，下個 tick `tti_builder` 用它 emit 進 PDU。
→ 對齊真實 OAI 的 CSI feedback：UE 報 PMI/RI/CQI → DU 用於下 tick scheduling。

### 2.3 不做的事

- ❌ 真實 channel coding（LDPC/Polar）— 太複雜，throughput 用解析公式夠了
- ❌ 真實 HARQ retransmission throughput penalty — 簡化用 `bler` × 因子
- ❌ Beam tracking with movement prediction — 過度 engineering

---

## 時程

| Phase | 預估 | 是否阻塞 demo |
|:---|:---|:---|
| Phase 1 (Traffic) | 1-2 天 | **是** — 沒這個 IM/CCO/ES 都跑不了 |
| Phase 2 A+B | 2-3 天 | 否 — Phase 1 完評估再決定 |
| Phase 2 C+D | 5+ 天 | 否 — 只在「需要 MIMO-aware xApp」時才做 |

## 立即決策點

- ✅ **要做** Phase 1 Traffic Injector（必要）
- ⏸️ **暫緩** Phase 2 PMI fix（Phase 1 完評估再說）
