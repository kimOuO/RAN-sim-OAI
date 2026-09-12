# DU 物理層保真度:參數來源清單

> 建立 2026-09-11。目的:對每一個影響 KPM 的物理參數,標明**它是規範引用、是有標定
> 依據的抽象參數、還是無出處的擬合值**。這份清單是對外交付時「你怎麼證明這個 DT 接近
> 真實系統」的答案。
>
> 原則:**沒有出處的東西不准假裝有出處。** 抽象參數不是問題,誤引規範才是。

---

## A. 規範引用(可直接寫進論文)

| 項目 | 值 | 出處 |
|---|---|---|
| PRB 子載波數 `N_sc^RB` | 12 | TS 38.211 §4.4.4.1 |
| TBS 資源元素數 `N'_RE` | `12 × N_symb^sh − N_DMRS^PRB − N_oh^PRB`,上限 `min(156, ·)` | TS 38.214 §5.1.3.2 |
| xOverhead `N_oh^PRB` | 0(未配置時的預設值) | TS 38.214 §5.1.3.2;OAI `gNB_scheduler_dlsch.c:730` 亦以 0 呼叫 |
| TBS 與層數關係 | `N_info ∝ N_RE × R × Q_m × ν` | TS 38.214 §5.1.3.2;OAI `nr_compute_tbs_common.c:68` |
| TDD 上下行結構 | period 5ms,7 DL + 1 special(6/14 DL 符號)+ 2 UL | TS 38.213 §11.1 / TS 38.331 `TDD-UL-DL-ConfigCommon`;實際值取自 OAI `gnb-du.sa.band78.106prb.rfsim.pci0.conf:135-139` |
| 有效 DL 比例 | `(7 + 6/14) / 10 = 0.742857` | 同上推導 |
| numerology | μ=1(30 kHz SCS)→ 0.5 ms/slot,2000 slot/s | TS 38.211 §4.3.2 |
| MCS 表 | Table 1(64QAM,MCS 0–28) | TS 38.214 Table 5.1.3.1-1 |
| CQI 表 | 16 級 | TS 38.214 Table 5.2.2.1-2(簡化) |
| PRB 最小分配 `MIN_PRB` | 5 | OAI `gNB_scheduler_dlsch.c:753` `const int min_rbSize = 5` |
| `RRU.PrbTotDl` 計算式 | `(UE Δtotal_rbs) × 100 / (node Δtotal_prb_aggregate)` | TS 28.552;OAI `ran_func_kpm_subs.c::fill_RRU_PrbTotDl()` |
| `DRB.RlcSduDelayDl` 定義域 | 到達 → MAC 取走(不含傳輸) | TS 28.552;OAI `nr_rlc_entity_am.c:1762` `waited_time` |
| RSRP / SINR 量化 | RSRP −156..−31 dBm → 0..125;SINR −23..40 dB → +23 | TS 38.133 |

### BLER 曲線(2026-09-11 更新)

| | 舊 | 新 |
|---|---|---|
| 來源 | 手工 4 點錨表 + `erfc` 公式,**無出處** | OAI 官方 NR AWGN link-level 模擬 |
| 覆蓋 | MCS 0/9/20/27,12 列 | MCS 0–28 全覆蓋,2086 列 |
| 產生方法 | 不明 | EESM + MATLAB link-level simulation(見來源 `README.md`) |
| 檔案 | `bler_curve.legacy.csv`(保留供回退) | `bler_curve.csv` |

來源路徑:`openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/AWGN_results/mcs{N}_awgn_5G.csv`
匯入工具:`RANsim-DU/tools/import_oai_bler.py`

**選 SISO 而非 MIMO 2×2 的理由**:AWGN 曲線是「每一層」的原語。MIMO 增益在本模擬中
顯式建模為 (a) TBS × 層數、(b) 每層 SINR 因等功率分配下降,而非換一張把 2×2 效應
預先吸收的表。用 MIMO 表會讓 rank 1/2 共用同一條曲線 → 看不出天線選擇的差異,且只在
2×2 成立。

**換表的量化影響**(10% BLER 所需 SINR,新 − 舊):

| MCS 區間 | 差值 | 意義 |
|---|---|---|
| 0–3 | −0.6 ~ +4.8 dB | 低階接近 |
| 4–9 | −2.6 ~ −8.0 dB | 舊表逐漸偏悲觀 |
| 13–27 | **−10.7 ~ −11.7 dB** | 舊表嚴重高估所需 SINR |
| 28 | −23.1 dB | 舊表在此已超出定義域 |

→ 舊公式在中高階 MCS 要求的 SINR 比實際高約 11 dB,導致 `_mcs_at_op_point()` 長期
選了過低的 MCS。換表後同一 SINR 可用的 MCS 明顯提高。

---

## B. 有標定依據的抽象參數(非規範值,但有可追溯的標定過程)

| 項目 | 值 | 標定依據 |
|---|---|---|
| `sched_pipeline_slots` | 2 slot(1 ms) | 聚合 gNB 排程處理 + PDCCH 組裝/解碼 + UE N1(TS 38.214 §5.3)。標定自 OAI 實測「乾淨 1~4 ms」。**⚠ 舊名 `k0_slots` 會被誤讀為 TS 38.214 §5.1.2.1 的 K0(NR 常見值為 0),2026-09-11 已正名。** |
| HARQ RTT | 4 slot | NR TDD 下 k1 + k2 + 處理時間的合理量級,未逐項對規範拆解 |
| link adaptation 目標 BLER | 0.1 | 對齊 OAI `target_dl_bler` |
| EESM β | per-MCS 表 | Lagén et al., *"New Radio Physical Layer Abstraction for System-Level Simulations of 5G Networks"*, IEEE ICC 2020, **arXiv:2001.10309** Table II。ns-3 **5G-LENA** 的依據實作。以 NR-compliant LLS 對 TDL-A/TDL-D(TR 38.901)校正。論文 Remark 1:β 對 SCS 與載波頻率不敏感 → 適用 band78。 |
| 等功率分配 | 每層 −10log10(ν) | TS 38.214 §5.1.6.2 無其他指示時各層等分;一階近似 |
| `RLC_TX_MAXSIZE_BYTES` | 10 MB | 對齊 OAI `nr_rlc_entity_am.c:1842-1847` 的 `tx_maxsize` 行為(OAI 預設 50 MB,依 DT 的低 MCS 環境下調) |
| `discardTimer` | 300 ms | 3GPP `discardTimer` 機制;值取遠高於已對齊的 12–22 ms |

---

## C. 無出處的擬合值(仍需處理)

| 項目 | 值 | 問題 |
|---|---|---|
| `_MCS_SINR_REQUIRED_DB` | 28 個值 | 無出處。**B 項換表後已降為防呆 fallback**,正常路徑不再命中(CSV 覆蓋 MCS 0–28) |
| `SIGMA_DB` | 1.5 | 同上,僅 fallback 用 |
| `fading_std_db` | 2.0 dB | slot engine 的 per-slot 快衰落標準差,無出處。**未來應改為由 TDL 通道模型(TR 38.901)或 Physics 的實際通道變異推導** |
| `SLOT_CADENCE_PERIOD` | 40 | 僅用於反事實對照組 `res_op`,不影響 KPM |
| `LEGACY_OVERHEAD` | 0.80 | 舊的整體 overhead 折扣。**spec 模式下已被 `N_DMRS^PRB` / `N_oh^PRB` 取代** |
| `LEGACY_TDD_DL_RATIO` | 0.72 | 舊的手動保守值。**spec 模式下已被 0.742857 取代** |

---

## D. 曾經是 fudge、已清除

| 項目 | 狀態 |
|---|---|
| RLC delay `/30` | slot engine takeover 後輸出被丟棄,不進 KPM(2026-06) |
| load-adaptive K0(3→44 slot) | compose 釘死 MIN=MAX=2,內插失效(2026-06-17) |
| `SLOT_OP_PRB_FLOOR = 10` | 降為 2(物理最小 grant)(2026-06-17) |
| BLER「亂猜 sigmoid」 | 早期版本,已棄用 |
| 4-MCS 手工 BLER 錨表 | 換成 OAI 官方 28-MCS 曲線(2026-09-11) |
| slot engine 與 scheduler 容量分歧 1.389× | `nr_resources` 集中常數後收斂為 1.000(2026-09-11,需開 `NR_TBS_SPEC_MODE`) |

---

## E. 開關與預設值

| 環境變數 | 預設 | 作用 |
|---|---|---|
| `NR_TBS_SPEC_MODE` | `off` | 資源/TBS 走 38.214 規範式;off 保留舊常數,兩端各自重現原本(不同的)舊行為 |
| `NR_MIMO_LAYERS_ENABLED` | `off` | TBS 乘層數 ν + 等功率分配 |
| `NR_EESM_ENABLED` | `off` | 多分量 SINR 用 EESM 壓縮;off = 線性域算術平均 |
| `SIM_BLER_CURVE_PATH` | 新曲線 | 指向 `bler_curve.legacy.csv` 可回退舊表 |
| `PHY_PATH_GAIN_PER_PORT`(Physics) | `off` | path_gain 改 per-port 平均(TS 38.215 §5.1.1);1×1 下等價,啟用多天線前必開 |
| `UE_ARRAY_ROWS/COLS`(RU) | `1` | UE 端陣列(原為硬編);Physics 目前仍忽略 rx_config |

**A/B 驗證結果**(每 PRB 每秒 bit 數,per bps_re):

| 模式 | scheduler | slot engine | 比值 |
|---|---|---|---|
| legacy(現況) | 165,888 | 230,400 | **1.389** |
| spec | 196,114 | 196,114 | **1.000** |
| spec + MIMO rank 2 | 392,229 | 392,229 | 1.000 |

---

## F. 待辦

1. **`fading_std_db` 要有出處** — 目前是 C 類唯一還在主路徑上的擬合值。
2. **RU 回 per-layer SINR** — 現在 RU 只回純量,DU 端只能做等功率分配的一階近似。
   要做完整 EESM(`eesm.combine_db()`)需要改 `CqiIndication` 介面帶 per-layer 陣列。
3. ~~確認天線配置真的改變 H~~ — **已驗證(2026-09-11):不會。** 整條多天線鏈路
   目前是惰性的,H 恆為 1×1、rank 恆為 1。且 `path_gain` 對天線元素對加總,放大
   陣列會讓它膨脹(2×2+1×2 ≈ +9 dB)= antenna gain 雙重計算。已加
   `PHY_PATH_GAIN_PER_PORT`(TS 38.215 §5.1.1,預設 off,1×1 下等價)。
   完整盤點與改造方案見 [`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md)。
4. **β 表 bit-exact 驗證** — 目前由 arXiv PDF 的雙欄 Table II 轉錄,已通過單調性與
   調變邊界(MCS 10 / 17 跳階)一致性檢查;要 bit-exact 請對照 5G-LENA `model/nr-eesm-t1.cc`。
5. **重跑 OAI 對照** — 開啟 spec 模式前,B/C 兩類參數的既有標定都是在舊容量常數下做的。
