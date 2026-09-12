# 天線陣列:Schema 定義與使用方式(知識背景)

> 建立 2026-09-12。為「天線陣列作為可調屬性」蒐集的背景資料。
> 三個來源:3GPP TR 38.901 §7.3(規範)、Sionna RT `PlanarArray`(我們的實作)、
> 商用部署慣例(8T8R / 64T64R 等)。
> 相關:[`ne_and_parameters.md`](ne_and_parameters.md)、[`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md)

---

## §1 先分清三層,否則參數會混在一起

| 層 | 問的問題 | 典型參數 |
|---|---|---|
| **① 元件 (Element)** | 單一輻射體長什麼樣? | 輻射圖 pattern、最大增益、3dB 波束寬、極化傾角 |
| **② 陣列 (Array)** | 元件怎麼排? | 列數 M、行數 N、間距 dV/dH、面板數 Mg/Ng |
| **③ 埠對映 (TXRU mapping)** | 幾個元件接到一個收發單元? | 子陣列 (sub-array) 虛擬化、T/R 數 |

**大多數混淆來自第 ③ 層。** 「64T64R」的 64 指的是 **TXRU(收發單元)數**,不是元件數。
真實 64T64R 常是 192 個輻射體(8 列 × 8 行 × 2 極化 × …)透過子陣列映射到 64 個 TXRU。

> ⚠️ **Sionna RT 沒有第 ③ 層。** `PlanarArray` 的每個元件就是一個獨立的天線埠,
> 等同「全數位陣列」。所以在我們的 DT 裡,`num_rows × num_cols × 極化數` 直接
> 就是 channel matrix 的維度,沒有子陣列虛擬化。做天線研究時這是必須說明的簡化。

---

## §2 3GPP TR 38.901 §7.3 的正式定義

### 2.1 陣列結構標記

基站天線建模為**均勻矩形面板陣列**,標記為:

```
(Mg, Ng, M, N, P)    間距 (dg,V, dg,H, dV, dH)
```

| 符號 | 意義 |
|---|---|
| `Mg` | 一「列」有幾個面板(panel) |
| `Ng` | 一「行」有幾個面板 |
| `M` | 每個面板中,**同極化**的元件在垂直方向的個數 |
| `N` | 每個面板中,元件在水平方向的行數 |
| `P` | 極化數:`1` = 單極化,`2` = 雙極化(±45° 斜極化) |
| `dV`, `dH` | 面板**內**元件的垂直/水平間距(λ 的倍數) |
| `dg,V`, `dg,H` | 面板**間**的間距 |

元件總數 = `Mg × Ng × M × N × P`

### 2.2 元件輻射圖(Table 7.3-1)

**垂直切面:**
```
A_EV(θ') = −min[ 12 · ((θ' − 90°) / θ_3dB)² ,  SLA_V ]
```

**水平切面:**
```
A_EH(φ') = −min[ 12 · (φ' / φ_3dB)² ,  A_max ]
```

**合成:**
```
A''(θ', φ') = G_E,max − min{ −[A_EV(θ') + A_EH(φ')] ,  A_max }
```

**標準數值(TR 38.901 Table 7.3-1):**

| 參數 | 值 | 意義 |
|---|---|---|
| `θ_3dB` | **65°** | 垂直 3dB 波束寬 |
| `φ_3dB` | **65°** | 水平 3dB 波束寬 |
| `SLA_V` | **30 dB** | 垂直旁瓣衰減上限 |
| `A_max` | **30 dB** | 前後比 / 最大衰減 |
| `G_E,max` | **8 dBi** | 元件最大方向性增益 |

> 65°/65° 的水平波束寬正是為 **三扇區(120°/扇區)** 設計的 —— 這是為什麼
> 三扇區是最常見的巨集站配置。

---

## §3 Sionna RT 的實作(我們實際能設的)

### 3.1 `PlanarArray` 真實 API

```python
sionna.rt.PlanarArray(
    *,
    num_rows: int,              # ≥ 1
    num_cols: int,              # ≥ 1
    vertical_spacing:   float = 0.5,   # λ 的倍數
    horizontal_spacing: float = 0.5,   # λ 的倍數
    pattern: str,                       # 見 3.2
    polarization: str = ...,            # 見 3.3
    polarization_model: str = "tr38901_2",
)
```

**注意 Sionna 只有 `num_rows` / `num_cols`,沒有面板層(Mg/Ng)。**
對應 TR 38.901 就是 `Mg = Ng = 1` 的單面板情形。多面板要自己建多個 array 或多個 Transmitter。

### 3.2 四種元件輻射圖

| `pattern` | 公式 | 最大增益 | 用途 |
|---|---|---|---|
| `iso` | `c_θ = 1` | **0 dBi** | 全向,除錯/基準用。**我們的 `cco_20min` 劇本用這個** |
| `dipole` | `c_θ = √1.5 · |sin θ|` | **≈2.15 dBi** | 短偶極,UE 端常用 |
| `hw_dipole` | `c_θ = √1.643 · |cos(π/2·cos θ) / sin θ|` | **≈2.15 dBi** | 半波偶極,較真實的 UE 天線 |
| `tr38901` | 見 §2.2 | **8 dBi** | **基站扇區天線的標準模型** |

### 3.3 極化選項 —— 這裡最容易選錯

Sionna 的 `polarization` 是**斜角(slant angle)列表**:

| `polarization` | 斜角 | 每元件的埠數 | 對應 3GPP |
|---|---|---|---|
| `V` | `[0]` | 1 | P=1,垂直極化 |
| `H` | `[π/2]` = 90° | 1 | P=1,水平極化 |
| `VH` | `[0, π/2]` = 0°/90° | 2 | 雙極化,但是 **0°/90°** |
| `cross` | `[−π/4, π/4]` = **±45°** | 2 | ✅ **P=2,3GPP 標準的雙斜極化** |

> 🔴 **常見錯誤:以為 `VH` 就是 3GPP 的 dual-polarized。**
> TR 38.901 的 `P=2` 明確是 **±45° 斜極化** → 對應 Sionna 的 **`cross`**,不是 `VH`。
> 我們的 `AntennaConfig` model 四個選項都列了(`V`/`H`/`VH`/`cross`),要選 `cross`。

**天線埠總數 = `num_rows × num_cols × len(slant_angles)`**
例:`num_rows=8, num_cols=8, polarization="cross"` → 128 個埠(全數位)。

### 3.4 兩種極化模型

| `polarization_model` | 行為 |
|---|---|
| `tr38901_1` | 方向相依的旋轉:`C_θ = cos(ψ)·C̃_θ`、`C_φ = sin(ψ)·C̃_θ`,ψ 隨 (θ, φ, ζ) 變 |
| `tr38901_2` | 簡化旋轉:`C_θ = cos(ζ)·C̃_θ`、`C_φ = sin(ζ)·C̃_θ`(**Sionna 預設**) |

---

## §4 RAN-SIM 現有 schema 對照

### 4.1 三處定義(目前互不相通)

| 位置 | 欄位 | 生效嗎 |
|---|---|---|
| **RU DB** `AntennaConfig` | `rows`、`cols`、`polarization`、`pattern`、`vertical_spacing`、`horizontal_spacing` | ❌ 組進請求後被 Physics 忽略 |
| **前端型別** `SceneAntennaConfig` | `gnb_array_rows/cols`、`ue_array_rows/cols`、`gnb_antenna_pattern`、`gnb_polarization`、`ue_antenna_pattern`、`ue_polarization` | ⚠️ 型別已完整,只有 pattern 有接後端 |
| **Physics** `scene_config.json` | 同上 key | 🔴 **檔案裡根本沒這個 key → 全部 fallback 到 1** |

`AntennaConfig` model 的合法值(已對齊 Sionna):

```python
POLARIZATION_CHOICES = ("V", "H", "VH", "cross")
PATTERN_CHOICES = ("tr38901", "dipole", "iso", "hw_dipole", "vh_dipole")
```

> ⚠️ `vh_dipole` 不在 Sionna 的四種 pattern 裡,傳下去會失敗。

### 4.2 目前實際生效的值

| | 值 | 來源 |
|---|---|---|
| gNB 陣列 | **1 × 1** | `sionna_operations.py:135-138` 的 `.get(..., 1)` fallback |
| UE 陣列 | **1 × 1** | 同上 |
| 間距 | **0.5λ** | `sionna_engine.py:94-95` **硬編,不讀傳入值** |
| gNB pattern | 劇本 `antenna_pattern`(`cco_20min` = `iso`) | ✅ 唯一真的生效的 |
| 極化 | `V` | 預設 |

---

## §5 天線的不同使用方式

### 5.1 固定扇區化 (Sectorization)

最基本、也是 RAN-SIM 目前唯一在做的。每個 cell 一個固定 azimuth 的 Transmitter。

| 配置 | 每扇區波束寬 | 說明 |
|---|---|---|
| 全向(1 扇區) | 360° | 小型基站、室內 |
| **三扇區** | 120° | **最常見**;65° 元件波束寬就是為此設計 |
| 六扇區 | 60° | 高密度都會區,容量換複雜度 |

**RAN-SIM 現況**:`Cell.azimuth_deg` 支援,劇本可設。**但沒有 `tilt`(下傾角)** ——
而下傾角是實務上調覆蓋最常用的旋鈕(機械下傾 / 電子下傾)。

### 5.2 波束成形 (Beamforming)

| 類型 | 怎麼做 | 元件↔TXRU |
|---|---|---|
| **類比** | RF 端移相器,一次只有一個波束 | 多對一 |
| **數位** | 基頻端每個埠獨立加權,可同時多波束 | 一對一 |
| **混合** | 子陣列類比 + 跨子陣列數位 | 分組 |

**Sionna 是全數位模型**(每元件一埠),所以 DT 天生只能模擬數位波束成形。
要模擬類比/混合,得自己在 RU 加一層子陣列加權。

### 5.3 空間多工 (Spatial Multiplexing)

| | 說明 | 靠什麼 |
|---|---|---|
| **SU-MIMO** | 對單一 UE 送多層(rank > 1) | H 的 SVD rank;需要豐富散射 |
| **MU-MIMO** | 同時對多個 UE 送,空間分離 | UE 間通道正交性;需要 CSI |

**RAN-SIM 現況**:SU-MIMO 的**程式都在**(RU `estimate_rank` SVD、DU `mimo_processor`
等功率分配、`TBS × ν`),但因為陣列是 1×1 → rank 恆為 1 → 全部空轉。
**MU-MIMO 完全沒有**(排程器是 per-UE 分 PRB,沒有空間維度)。

### 5.4 碼本 (Codebook)

| 類型 | 用途 | RAN-SIM |
|---|---|---|
| **Type I** | 單使用者,粗量化,回授量小 | ✅ **`codebook.py` 已完整實作** 38.211 §6.3.1.5 六張表 |
| **Type II** | MU-MIMO,細量化,回授量大 | ❌ 沒有 |

`codebook.py` 支援的 `(layers, ports)`:`(1,2) (1,4) (2,2) (2,4) (3,4) (4,4)`
→ **沒有 1-port 條目**,所以 1×1 陣列查表必定 `CodebookError`。

### 5.5 波束管理 (Beam Management)

SSB 波束掃描、CSI-RS 波束精化、波束失敗恢復。
**RAN-SIM 完全沒有** —— 沒有 SSB、沒有波束掃描的時間結構。

### 5.6 分散式 (DAS / Distributed MIMO / Cell-free)

多個地理分離的輻射點服務同一 cell。

**RAN-SIM 現況**:`sionna_engine` 註解已註明支援 ——
「DAS / multi-TRP 支援:cell.position 給的話用 cell 位置(物理分離 antenna)」,
且 `Cell` model 有獨立的 `position_x/y/z`。**底層已通,只差前端把 cell 從 gNB 解放。**

### 5.7 商用配置對照

| 稱呼 | TXRU 數 | 典型元件排列 | 用途 |
|---|---|---|---|
| 2T2R / 4T4R | 2 / 4 | 少數行,雙極化 | 傳統巨集站 |
| **8T8R** | 8 | 約 4 行 × 多列 × 雙極化 | Sub-6 主流升級路徑 |
| 32T32R | 32 | 約 4×4×2 子陣列映射 | 中密度都會 |
| **64T64R** | 64 | 約 8×8×2 = 128 輻射體映射到 64 TXRU | Massive MIMO 旗艦 |

> 若要在 Sionna 裡「近似」64T64R,設 `num_rows=8, num_cols=8, polarization="cross"`
> 會得到 **128 個全數位埠** —— 比真實的 64 TXRU 更理想化。這個差異必須在論文裡說明。

---

## §6 對 RAN-SIM 的映射:能做 / 不能做

| 使用方式 | 現在能做嗎 | 缺什麼 |
|---|---|---|
| 固定扇區(azimuth) | ✅ | — |
| 下傾角 (tilt) | ❌ | `Cell` 沒有 tilt 欄位;Sionna Transmitter 的 orientation 要接出來 |
| 元件輻射圖選擇 | ✅ | 唯一真的生效的天線參數 |
| 陣列大小 (M×N) | ❌ | Physics 忽略傳入值 + `scene_config` 沒設 |
| 極化 (P=2, ±45°) | ❌ | 同上;且要記得選 `cross` 不是 `VH` |
| 元件間距 | ❌ | Sionna 呼叫端硬編 0.5λ |
| 數位波束成形 | ⚠️ | codebook 已就緒,但 1-port 無表可查 |
| 類比/混合波束成形 | ❌ | Sionna 無子陣列層,要自建 |
| SU-MIMO (rank>1) | ⚠️ | 程式全在,rank 恆 1 |
| MU-MIMO | ❌ | 排程器無空間維度 |
| Type II codebook | ❌ | — |
| 波束管理 / SSB 掃描 | ❌ | 無 SSB 時間結構 |
| DAS / multi-TRP | ⚠️ | 後端已通,前端未暴露 |

---

## §7 建議的 schema(若要把天線做成可調屬性)

```jsonc
"antenna": {
  // ── 元件層 ──
  "pattern": "tr38901",        // iso | dipole | hw_dipole | tr38901
                                // ⚠ 不要用 vh_dipole,Sionna 沒有
  // ── 陣列層 ──
  "num_rows": 8,               // M(垂直)
  "num_cols": 8,               // N(水平)
  "vertical_spacing": 0.5,     // dV,λ 倍數
  "horizontal_spacing": 0.5,   // dH,λ 倍數
  // ── 極化 ──
  "polarization": "cross",     // V | H | VH | cross;3GPP P=2 → cross(±45°)
  "polarization_model": "tr38901_2",
  // ── 指向(目前缺)──
  "azimuth_deg": 0.0,          // ✅ Cell 已有
  "tilt_deg": 0.0              // ❌ 待補
}
```

**掛在哪一層?** 建議掛在 **Cell / TRP**,不是 gNB ——
因為同一個 gNB 的不同扇區本來就可能用不同天線,而且 DAS 的每個輻射點各自獨立。

⚠️ 但 Sionna 目前是 **scene-global** 一組 `tx_array`(所有 Transmitter 共用)。
要做 per-cell 天線,得改成每個 Transmitter 綁自己的 array,或拆成多個 scene 分批算。
**這是 per-cell 天線配置的真正技術門檻**,比改 schema 難得多。

---

## §8 參考來源

- **3GPP TR 38.901** §7.3 "Antenna modelling",Table 7.3-1 —
  [ETSI TR 138 901 V16.1.0 (PDF)](https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/16.01.00_60/tr_138901v160100p.pdf)
- **3GPP TS 38.211** §6.3.1.5 — Type I codebook(我們的 `codebook.py` 來源)
- **Sionna RT `PlanarArray`** — [API 文件](https://nvlabs.github.io/sionna/rt/api/antenna_array.html)
- **Sionna RT 輻射圖與極化模型原始碼** — [antenna_pattern.py](https://nvlabs.github.io/sionna/_modules/sionna/rt/antenna_pattern.html)
- **MATLAB `phased.NRAntennaElement`** — 確認 TR 38.901 預設值 65°/30 dB/8 dBi:
  [MathWorks 文件](https://www.mathworks.com/help/phased/ref/phased.nrantennaelement-system-object.html)
- **MATLAB `phased.NRRectangularPanelArray`** — (Mg,Ng,M,N,P) 面板陣列:
  [MathWorks 文件](https://www.mathworks.com/help/phased/ref/phased.nrrectangularpanelarray-system-object.html)
- **商用配置對照** — [8T8R vs 64T64R](https://www.rfwireless-world.com/Terminology/Difference-between-conventional-8T8R-and-64T64R-Massive-MIMO-Antenna.html)、
  [CommScope 8T8R 白皮書](https://www.andrew.com/globalassets/digizuite/1009035-8t8r-config-in-5g-networks-wp-119671-en.pdf)
- **波束成形分類** — [Ericsson Technology Review: Broad beamforming in Massive MIMO](https://www.ericsson.com/en/reports-and-papers/ericsson-technology-review/articles/beamforming-in-massive-mimo)
- **Massive MIMO 碼本與回授** — [arXiv:2301.13390](https://arxiv.org/abs/2301.13390)
