# RANsim-RU 詳細筆記:做了什麼 / 與現實的差距 / 天線模擬怎麼做

> 建立 2026-09-11。逐檔讀過原始碼後整理,結論皆附行號證據。
> 相關:[`phy_fidelity_sources.md`](phy_fidelity_sources.md)(參數來源分類)、
> [`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md)(多天線改造方案)。

---

## §0 一句話

**RU 的工作是把「幾何」變成「一個數字」** —— UE 在哪、基站在哪、牆在哪 → `sinr_db`。
DU 裡所有東西(MCS、PRB、TBS、BLER、delay、KPM)都從這個數字長出來。

RU 全部 **3,156 行**,約 DU 的三分之一。

| 模組 | 行數 | 做什麼 |
|---|---|---|
| `fapi_south` | 1,311 | DL/UL TTI pipeline —— **主幹** |
| `antenna` | 801 | 陣列/cell/UE 位置的 DB 與配置 API |
| `beamforming` | 445 | 38.211 codebook、precoder、SINR/rank/CQI 估計 |
| `phy_low` | 306 | numerology/FFT/OFDM 的**描述**(不算 IQ) |
| `physics_client` | 281 | 打 Physics、L2 cache |

---

## §1 逐模組:實際在算什麼

### 1.1 `beamforming/codebook.py`(157 行)—— 品質最高的一份

5G NR **Type I codebook,38.211 §6.3.1.5**,直接對拍 OAI
`openair1/PHY/MODULATION/nr_modulation.c:33-118`。沿用 OAI 的 ASCII 編碼:
`'1'→1, '0'→0, 'n'→-1, 'j'→1j, 'o'→-1j`。

實作的表:

| 表 | layers × ports | PMI 範圍 |
|---|---|---|
| 6.3.1.5-1 | 1 × 2 | 0–5 |
| 6.3.1.5-3 | 1 × 4 | 0–27 |
| 6.3.1.5-4 | 2 × 2 | 0–2 |
| 6.3.1.5-5 | 2 × 4 | 0–21 |
| 6.3.1.5-6 | 3 × 4 | 0–6 |
| 6.3.1.5-7 | 4 × 4 | 0–4 |

**這是規範層級的忠實實作,可以直接引用。**

> ⚠ **但表裡沒有 1-port 條目。** 目前系統跑在 1×1 陣列 → `lookup()` 必然
> `raise CodebookError` → 見 §2 的後果。

### 1.2 `beamforming/precoder.py`(37 行)

```python
H_eff = (H @ W) * 1/sqrt(num_ports)      # 38.211 §6.3.1.5 正規化
```
`H: (num_rx, num_ports)` → `H_eff: (num_rx, num_layers)`。
對應 OAI `nr_ru_procedures.c::nr_feptx_prec()`。正規化只在這裡做一次
(codebook 回傳未正規化的 W),避免重複乘 —— 這個分工是對的。

### 1.3 `beamforming/sinr_estimator.py`(64 行)—— RU 的心臟,但只有一半在跳

三個函式:

| 函式 | 算法 | 現況 |
|---|---|---|
| `estimate_sinr(H_eff, noise)` | per-layer 功率的**線性域算術平均** / noise | **DL 沒在用**,只有 UL 用 |
| `estimate_rank(H_eff)` | SVD,`σ/σ_max > 0.1` 的個數 | 有用,但輸入恆 1×1 → 恆回 1 |
| `sinr_to_cqi(sinr_db)` | 16 級門檻(−6 → 22 dB,每 2 dB 一階) | 有算,**但沒人用**(見 §2) |

### 1.4 `fapi_south/dl_tti_pipeline.py`(528 行)—— 主幹

一次 DL TTI 的完整流程:

```
DlTtiRequest (from DU)
   ↓
取 path_gain:  live → 打 Physics PathSolver
               cached → 讀 npz 查表
   ↓
path_gain_dict = {tx_name: path_gain_linear}   ← 純量,每個 cell 一個
   ↓
   ├─ RSRP ── _path_gain_to_rsrp_dbm() ── ran_sim_protocol.rsrp_model
   │            RSRP = 10log10(pg) + tx_power_dbm − scene_loss_db
   │
   ├─ SINR ── _compute_sinr_db_with_real_interference()
   │            SINR = serving_mW / (Σ 其他同頻 cell mW + noise_mW)
   │            noise floor = −98 dBm
   │            ★ 全程只用純量 path_gain,不碰 H、不碰 precoder ★
   │
   ├─ rank ── H → apply_pmi(H, pmi, layers) → estimate_rank(H_eff)
   │            ★ 唯一用到 H 與 codebook 的地方 ★
   │
   └─ CQI ─── sinr_to_cqi(sinr_db)
   ↓
CqiIndication{sinr_db, cqi, rank, pmi, rsrp_dbm, serving_cell, neighbors}
```

**干擾判定**(`_overlaps()`):兩 cell 頻段中心距 < 平均頻寬 → 視為同頻互擾。
`inter_freq=True` 則強制全部不互擾(舊劇本相容)。

### 1.5 `physics_client/`(281 行)

`payload_builder.py` 組 `PathSolverRequest`(gNB 位置、azimuth、頻率、陣列設定)。
`channel_cache.py` 是 L2 快取,key = `(ue_id, 量化後位置, antenna_signature)`,
同位置同配置不重打 Physics。

### 1.6 `phy_low/`(306 行)

**只做描述,不做運算。** numerology μ → SCS/symbols/slot/FFT size 查表
(38.211 §5.3.1, §5.3.2),以及把 PDU 拼成 grid 描述。沒有真的 IQ、沒有 FFT。

---

## §2 四個「算了但沒人用」的發現

這是讀 RU 最重要的收穫 —— **有些看起來很完整的東西,實際上是斷的。**

### 發現 1:DL 的 SINR 完全不經過波束成形

`dl_tti_pipeline.py:483`:
```python
sinr_db = _compute_sinr_db_with_real_interference(path_gain_dict=..., ...)
```

輸入只有**純量 path_gain**。`estimate_sinr()`(那個吃 `H_eff` 的函式)
在 DL 路徑上**從未被呼叫** —— grep 全 repo,只有 `ul_tti_pipeline.py:88` 用它。

**所以:codebook → precoder → H_eff 這條鏈,對 DL 的 SINR 沒有任何影響。**
它唯一的產物是 `rank`。

> UL 用 H、DL 不用 —— 這個不對稱沒有物理理由,是演進的殘留。

### 發現 2:codebook 在目前配置下必定失敗

1×1 陣列 → `H.shape = (1, 1)` → `num_ports = 1` → `_TABLES.get((layers, 1))` = `None`
→ `CodebookError` → 被 `dl_tti_pipeline.py:504` 接住 → `rank = 1`。

```python
except codebook.CodebookError as exc:
    logger.warning("codebook lookup failed for ue=%s: %s", pdu.ue_id, exc)
    rank = 1
```

**live 模式下這行 warning 每個 UE 每個 tick 都會印。** 157 行的忠實 codebook
實作目前是純裝飾。

### 發現 3:RU 算的 CQI 沒有人用

DU 只在一行 log 裡碰過 `cqi`(`fapi_router_actor.py:57`)。
真正決定 MCS 的是 `mcs_ctl.update(uid, ue["sinr_db"], ...)` —— **DU 直接吃 SINR**。

所以 RU 的 `sinr_to_cqi()`(38.214 Table 5.2.2.1-2 簡化版)只影響 log 可讀性。

> 副作用:RU 的 CQI 門檻表與 DU 的 `_SINR_TO_MCS` 是**兩張獨立的表**。
> 它們目前碰巧都以 2 dB 為階、起點都在 −6 dB,但沒有任何機制保證兩者同步。

### 發現 4:cached 模式連 H 都沒有

npz 只存 `path_gain_db (tick, ue, cell) float32`。所以 cached 模式下
`H_raw is None` → 直接 `rank = 1`,連 codebook 都不會被呼叫。

---

## §3 與現實的差距

### A. 對齊得好的部分

| 項目 | 依據 |
|---|---|
| Type I codebook 六張表 | 38.211 §6.3.1.5,對拍 OAI `nr_modulation.c` |
| precoder 正規化 `1/√N_ports` | 38.211 §6.3.1.5 |
| numerology / FFT / OFDM 描述 | 38.211 §5.3.1, §5.3.2 |
| 多 cell 干擾用真實 path_gain 合成 | 取代了早期「固定 −20 dB 一刀切」的 hack |
| RSRP 單一事實源 | `ran_sim_protocol.rsrp_model`,Coverage 與 KPM 共用同一函式 |
| path_gain 已含天線 pattern | Sionna `PlanarArray` 內建,**不可再外加 antenna gain** |

`rsrp_model.py` 的 docstring 誠實記錄了歷史上的 **+14 dBi 天線增益雙重計算**
與那個「剛好抵銷」的 −50 dB magic constant,以及為何改成 −36 dB。這段值得完整讀。

### B. 結構性簡化(有意識的取捨)

| 簡化 | 後果 |
|---|---|
| **SINR 是全頻段單一純量** | 沒有頻率選擇性衰落。真實系統 SINR 逐 RB 變化,排程器可做 frequency-selective scheduling;DT 做不到,也因此**用不到 EESM**(沒有多個分量可壓縮) |
| 不做 IQ / FFT / 真 LDPC | `phy_low` 只描述不運算;BLER 由查表抽象 |
| 快衰落在 RU 端沒有 | fading 在 DU 的 slot engine 用 `gauss(0, 2.0 dB)` 加(見 `phy_fidelity_sources.md` C 類) |
| L2 cache 以量化位置為 key | 位置微動不重算,TTL 0.5s |

### C. 斷掉 / 不一致的部分

| 問題 | 嚴重度 |
|---|---|
| DL SINR 不走 H(發現 1) | 中 —— 波束成形對 KPM 零影響 |
| 1×1 陣列讓 codebook 必失敗(發現 2) | 中 —— 每 tick warning,且 rank 恆 1 |
| CQI 無人消費(發現 3) | 低 —— 但兩張表可能靜默分歧 |
| UL 用 H、DL 不用 | 低 —— 演進殘留 |
| `RU_SCENE_CALIBRATION_LOSS_DB = 0.0` | ⚠ 模組預設是 **36.0**,compose 設 **0.0**。等於「Sionna 沒模到的損耗(穿透/人體/遮蔽)一律不計」。室外空曠場景可接受,室內掃描場景要重新檢視 |
| `path_gain` 對天線元素對加總 | **高** —— 見 §4 |

---

## §4 天線模擬:目前實際怎麼做

### 現在的做法

```
scene_config.json  →  Physics SionnaEngine  →  rt.PlanarArray(num_rows, num_cols, ...)
                                                  ↓
                                       tx_array(所有 gNB 共用一組)
                                       rx_array(所有 UE 共用一組)
                                                  ↓
                                       PathSolver 光追 → a[rx, rx_ant, tx, tx_ant, path]
                                                  ↓
                                       combined = Σ_path  →  H (rx_ant, tx_ant)
                                       pg = Σ_{rx_ant, tx_ant} |combined|²
```

**兩個關鍵事實:**

1. **陣列是 scene-global 的** —— 所有 gNB 共用一組 `tx_array`,所有 UE 共用一組
   `rx_array`。不能 per-gNB 設不同天線。
2. **`rt.PlanarArray` 已內建天線 pattern**(`tr38901` / `dipole` / `iso` …),
   所以 `path_gain` 裡已經含了方向性增益 —— 這就是為何不可再外加 antenna gain。

### 目前實際生效的值:全部 1×1

| 環節 | 值 | 為什麼 |
|---|---|---|
| `deploy/scene_config.json` | **沒有 `scene_antenna_config` 這個 key** | → 全部 fallback 到預設 `1` |
| 全 repo 唯一設 `scene_antenna_config` 的地方 | 只設 `gnb_antenna_pattern` | rows/cols 從未被設過 |
| RU `build_rx_config()` | 曾硬編 `rows=1, cols=1` | 2026-09-11 改為 `UE_ARRAY_ROWS/COLS`,預設仍 1 |
| Physics `path_solver_actor.py:88` | **明確忽略請求的 tx_config/rx_config** | 註解自承是 TODO |

**結論:H 恆為 1×1,rank 恆為 1,整條多天線鏈路是惰性的。**

### 阻擋放大陣列的 bug

`sionna_engine.py::compute_paths()`:
```python
pg = float(np.sum(np.abs(combined) ** 2))   # 對所有 (rx_ant, tx_ant) 元素對加總
```

`path_gain` 隨天線元素對數線性膨脹:

| 陣列 | 元素對 | path_gain 偏移 |
|---|---|---|
| 1×1 / 1×1 | 1 | 基準 |
| gNB 2×2 / UE 1×2 | 8 | **≈ +9 dB** |
| gNB 4×4 / UE 2×2 | 64 | **≈ +18 dB** |

這不是波束成形增益,是把「元素數量」當成了「接收功率」。

**規範**:TS 38.215 §5.1.1 定義 RSRP 為功率**線性平均**,接收分集下以個別分支為準,
非各分支之和 → RSRP 不隨陣列元素數放大。

已加 `PHY_PATH_GAIN_PER_PORT`(預設 `off`,1×1 下除以 1 完全等價)。

---

## §5 最終該長什麼樣

三種增益各有出處、**各只計一次**:

| 增益 | 物理來源 | 該由誰產生 | 目前狀態 |
|---|---|---|---|
| 路徑損耗 / RSRP | 距離、遮蔽、反射 | Sionna path_gain(per-port 平均) | ⚠ 目前是元素對加總 |
| **波束成形陣列增益** | 相干合成,`W` 作用在 `H` | RU `beamforming/`(codebook 已就緒) | ❌ 對 DL SINR 無影響 |
| **空間多工增益** | `H` 的 SVD rank | DU `TBS × ν` | ✅ 已實作,但 rank 恆 1 |

要讓天線選擇有意義,目標資料流應該是:

```
Physics: H (n_rx, n_tx) 複數矩陣  ← 隨天線配置真的改變
   ↓
RU: 掃 PMI → W → H_eff = H·W/√N
    per-layer SINR = |H_eff[:,k]|² / (干擾 + noise)
    rank = SVD(H_eff)
    effective SINR = EESM(per-layer SINRs, β[mcs])    ← DU 的 eesm.py 已備妥
   ↓
DU: TBS = f(MCS(eff SINR)) × rank                     ← nr_resources 已備妥
    每層功率 = 總功率/rank                             ← eesm.equal_power_split_db 已備妥
```

**DU 側的三塊(EESM、TBS×ν、等功率分配)已經在 2026-09-11 做好並以旗標關著。
缺的全部在 RU 與 Physics 這一段。**

改造順序見 [`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md) §5。
分水嶺是「讓 Physics 讀請求裡的 `tx_config`」—— 那決定天線設定能不能在 runtime 改,
而那是「選擇」這個題目的前提。

---

## §6 建議讀法

| 順序 | 檔案 | 行數 | 讀完要能回答 |
|---|---|---|---|
| 1 | `beamforming/sinr_estimator.py` | 64 | 三個函式各自有沒有人用?`sv_ratio_threshold=0.1` 是什麼意思? |
| 2 | `beamforming/precoder.py` | 37 | 正規化為什麼是 `1/√N_ports` 而不是 `1/√N_layers`? |
| 3 | `beamforming/codebook.py` | 157 | 為什麼沒有 1-port 的表?那對現在的系統有什麼後果? |
| 4 | `fapi_south/dl_tti_pipeline.py` §`_compute_sinr_db_with_real_interference` | ~80 | SINR 為什麼不套 `scene_loss` 而 RSRP 要套? |
| 5 | `fapi_south/dl_tti_pipeline.py::run()` | ~200 | H 在哪裡被用到?除了 rank 還影響什麼? |
| 6 | `ran_sim_protocol/rsrp_model.py` docstring | ~40 | +14 dBi 雙重計算的歷史;為什麼 −50 改成 −36? |
| 7 | `physics_client/payload_builder.py` | 102 | RU 送了什麼給 Physics?哪些被忽略? |

**第 6 項的 docstring 是整個 repo 裡把「一個參數怎麼從錯誤走到正確」寫得最清楚的一段,
值得當範本讀。**
