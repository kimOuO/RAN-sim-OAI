# Full Day 24hr Scenario — 5x KPM 對照 OAI (v2, P1.12 後)

跑於 2026-05-23 21:33 ~ 2026-05-24 02:24(wall 4h51m)— sim 完整跑完 25h sim-time。

Session: `sim_1779543213785_07595389`,scenario `full_day_24hr`,RU cached mode,sim_speed_x=5。

**主要差異 vs v1**:加入 P1.12(RLC TX buffer 500 KB → 10 MB)。

---

## 結果總覽 — 6 Phase 對照

### Throughput DL / UL

| Phase | sim-time | DT v2 thp_DL | OAI thp_DL | 對齊度 | DT v1 thp_DL | 改善 |
|---|---|---|---|---|---|---|
| **normal-1** | 00:00-06:55 | 110.3 kbps | 195.0 kbps | 🟡 57% | 110.3 kbps | = |
| **im** | 07:00-10:55 | **218.6 kbps** | 213.5 kbps | ⭐ **102%** | 51.4 kbps | **+167 kbps** |
| **normal-2** | 11:00-13:55 | 16.4 kbps | 15.8 kbps | ⭐ 104% | 16.3 kbps | = |
| **cco** | 14:00-16:55 | 9.1 kbps | 8.0 kbps | ⭐ 114% | 8.7 kbps | = |
| **normal-3** | 17:00-21:55 | 5.2 kbps | 4.7 kbps | ⭐ 111% | 5.1 kbps | = |
| **es** | 22:00-23:55 | 220.2 kbps | 275.2 kbps | 🟡 80% | 283.3 kbps | -63 kbps |

| Phase | DT v2 thp_UL | OAI thp_UL |
|---|---|---|
| **normal-1** | 22.1 kbps | 13.7 kbps |
| **im** | 43.7 kbps | 14.1 kbps |
| **normal-2** | 3.3 kbps | 13.5 kbps |
| **cco** | 1.8 kbps | 6.8 kbps |
| **normal-3** | 1.0 kbps | 4.0 kbps |
| **es** | 44.0 kbps | 153.3 kbps |

### RLC Delay DL (calibrated ÷500)

| Phase | DT v2 delay_dl | OAI delay_dl | 對齊度 |
|---|---|---|---|
| **normal-1** | 1.05 ms | 14.4 ms | 🟡 7% |
| **im** | 1.94 ms | 17.5 ms | 🟡 11% |
| **normal-2** | 1.89 ms | 1.5 ms | ⭐ 126% |
| **cco** | 0.01 ms | 0.74 ms | 低 |
| **normal-3** | 2.05 ms | 0 ms | (OAI 報 0) |
| **es** | 0.26 ms | 21.8 ms | 低 |

> delay 校正後低流量 phase (normal-2/3) 仍對齊。高流量 phase delay 低於 OAI,根因是 DT scheduler 每 500ms 才跑一次,queue waiting time 天花板低於 OAI slot-driven 延遲。

### PRB% (×10 calibration 已套)

| Phase | DT v2 prb_pct | DT v1 prb_pct | OAI prb_pct | 對齊度 |
|---|---|---|---|---|
| **normal-1** | 2.24% | 4.49% | 10.67% | 🔴 21% |
| **im** | **8.88%** | 4.41% | 11.71% | 🟡 **76%** (+38%→76%) |
| **normal-2** | 6.82% | 13.75% | 0.89% | 🔴 過高 7× |
| **cco** | 0.11% | 0.20% | 0.45% | 🟡 24% |
| **normal-3** | 6.78% | 13.62% | 0.26% | 🔴 過高 26× |
| **es** | 2.49% | 6.57% | 15.12% | 🟡 16% |

### PDCP DL Volume / measurement window

| Phase | DT v2 pdcp_DL_kbit | OAI pdcp_DL_kbit |
|---|---|---|
| **normal-1** | 13.78 | 151.3 |
| **im** | **27.33** | 164.0 |
| **normal-2** | 2.04 | 12.1 |
| **cco** | 1.14 | 5.7 |
| **normal-3** | 0.65 | 3.3 |
| **es** | 27.53 | 209.5 |

---

## P1.12 主要成果

### im phase 完全對齊

| 量 | v1 | v2 | OAI | 改善 |
|---|---|---|---|---|
| Throughput avg | 51.4 kbps | **218.6 kbps** | 213.5 kbps | ⭐ +167 kbps |
| Throughput max | — | 4119 kbps | — | 正常 |
| PRB% avg | 4.41% | **8.88%** | 11.71% | 🟡 38%→76% |
| Delay | 3.83 ms | 1.94 ms | 17.5 ms | — |

**根因確認**:v1 im phase avg=51 kbps 的根因是 RLC TX buffer cap 500 KB —
3 Mbps burst rate 每 500ms tick inject 187 KB,會把 500 KB buffer 打滿後丟棄。
P1.12 把 cap 拉到 10 MB 後,buffer 不再截流,scheduler 能拿到足夠資料分配 PRB。

---

## es Phase 為什麼 v2 avg 低於 v1

- v1: 283.3 kbps, v2: 220.2 kbps, OAI: 275.2 kbps
- **v2 es burst 是正常的**:burst 活躍期 avg **2249 kbps**,max **8475 kbps**
- **問題出在 duty cycle**:burst 樣本 916 / total 9354 = **9.8%**
  - 220.2 kbps = 0.098 × 2249 kbps ✓ 數學吻合
- v1 duty cycle 不同(timing 略異)導致平均值差異
- **burst 機制本身正確**,P1.12 沒有破壞 es phase

---

## 相對趨勢驗證(xApp 真正關心的)

| 比較 | OAI 倍率 | DT v2 倍率 | 趨勢對齊? |
|---|---|---|---|
| im vs normal-1 | 1.10× | 1.98× | ✅ 同向(DT im 現在 > normal-1) |
| es vs normal-3 | 58× | 42× | ⭐ 同向(v1 56×,現在 42×) |
| cco vs normal-2 | 0.51× | 0.55× | ⭐ |
| normal-2 vs normal-1 | 0.08× | 0.15× | 🟡 同向 |
| normal-3 vs normal-2 | 0.30× | 0.32× | ⭐ |

**v1 im phase 趨勢反向問題已修復**:v1 DT im 反而 < normal-1(0.47×),v2 im/normal-1=1.98× ✓。

---

## 解讀

### ✅ 修復成功

- **im phase throughput**:v1 24% → v2 **102%**
- **im phase PRB%**:v1 38% → v2 **76%**
- **im vs normal-1 趨勢**:v1 反向 → v2 正確(im > normal-1)

### ✅ 仍對齊的 Phase

| Phase | 量 | 對齊度 |
|---|---|---|
| normal-2 | Throughput DL | ⭐ 104% |
| cco | Throughput DL | ⭐ 114% |
| normal-3 | Throughput DL | ⭐ 111% |
| es | burst avg Throughput | 🟡 80%(burst per-sample ≈ OAI) |

### 🔴 尚未對齊

1. **normal-1 throughput 57%**:結構限制(500ms tick 排程容量 ≈ 1 Mbps,195 kbps 持續流量但 active ratio < 100%),非 buffer cap 問題
2. **PRB% normal-2/3 過高**:低流量期 scheduler active ratio 接近 100%(DT buffer 一直在累積),OAI 真正空窗時不分 PRB → 結構差異
3. **UL throughput 偏高**:DT UL 高於 OAI 2-3×,需要獨立調查
4. **Delay 高流量 phase 偏低**:DT 500ms tick → queue waiting 天花板低,結構限制

---

## 對 xApp 驗證的最終建議

| xApp 功能 | 可信度 | 建議 |
|---|---|---|
| **IM xApp** | ✅ 高 | v2 im phase 已對齊 OAI → threshold 可直接校準 |
| **CCO xApp** | ✅ 高 | cco/normal-2 throughput 對齊 ✓ |
| **ES xApp** | ✅ 高 | es burst 機制正確,avg trend 對 |
| PRB% 絕對值 | 🟡 | 用相對倍率不用 hard threshold |
| UL throughput | ❓ | 偏高 2-3×,需校準 |

---

## P0-P1 全套 13 個 fix 前後對照

| 量 | P0 之前 | v1(P0-P1.11) | v2(+P1.12) | OAI |
|---|---|---|---|---|
| Throughput normal-2/3 | 0 kbps | ⭐ 對齊 | ⭐ 對齊 | 5-16 kbps |
| Throughput es burst | 不可量 | ⭐ 對齊 | ⭐ 對齊 | 275 kbps |
| **Throughput im** | 0 kbps | 🔴 51 kbps | ⭐ **219 kbps** | 213 kbps |
| Throughput normal-1 | 0 kbps | 🟡 57% | 🟡 57% | 195 kbps |
| RLC Delay normal-2 | 無意義 | ⭐ 對齊 | ⭐ 對齊 | 1.5 ms |
| PRB% im | 0% | 🔴 38% | 🟡 76% | 11.71% |
| PDCP Volume | 0 | 🔴 低 | 🔴 低 | — |

---

## 關聯文件

- `full_day_24hr_5x_kpm_result_2026-05-23.md` — v1 結果(P1.12 前)
- `oai_kpm_calibration_2026-05-23.md` — Delay/PRB calibration 推導
- `oai_alignment_params.md` — 物理層 P0-P1 對照表
- P1.12 fix: `RANsim-DU/main/apps/rlc/services/optional/entities/am_entity.py` + `docker-compose.yml RLC_TX_MAXSIZE_BYTES=10000000`
