# DU 物理層保真度:參數來源清單

> 建立 2026-09-11,2026-09-26 全面核對更新。目的:對每一個影響 KPM 的物理參數,標明
> **它是規範引用、是有標定依據的抽象參數、還是無出處的擬合值**。這份清單是對外交付時
> 「你怎麼證明這個 DT 接近真實系統」的答案。
>
> 原則:**沒有出處的東西不准假裝有出處。** 抽象參數不是問題,誤引規範才是。
>
> 2026-09-26 核對方式:標示「與 OAI 一致」的項目,皆以本機 OAI 原始碼
> (`/home/mitlab/openairinterface5g`,commit `91e7030cf8`,2025-12-04)逐項比對過數值,
> 不是只抄程式註解。比對時發現兩處註解宣稱的 OAI 出處並不存在,已更正(見 D 節)。

---

## A. 規範引用與 OAI 原值(可直接寫進論文)

| 項目 | 值 | 出處 | 核對 |
|---|---|---|---|
| PRB 子載波數 `N_sc^RB` | 12 | TS 38.211 §4.4.4.1 | |
| TBS 資源元素數 `N'_RE` | `12 × N_symb^sh − N_DMRS^PRB − N_oh^PRB`,上限 `min(156, ·)` | TS 38.214 §5.1.3.2 | |
| xOverhead `N_oh^PRB` | 0(未配置時的預設值) | TS 38.214 §5.1.3.2 | OAI `gNB_scheduler_dlsch.c` 呼叫 `nr_compute_tbs` 時傳 0 ✔ |
| TBS 與層數關係 | `N_info ∝ N_RE × R × Q_m × ν` | TS 38.214 §5.1.3.2;OAI `nr_compute_tbs_common.c:68` | |
| TDD 上下行結構 | period 5ms,7 DL + 1 special(6 DL / 4 UL 符號)+ 2 UL | TS 38.213 §11.1 / TS 38.331 `TDD-UL-DL-ConfigCommon` | OAI `gnb-du.sa.band78.106prb.rfsim.pci0.conf:135-139` ✔ |
| 有效 DL / UL 比例 | `(7 + 6/14) / 10 = 0.742857`;`(2 + 4/14) / 10 = 0.228571` | 同上推導 | |
| numerology | μ=1(30 kHz SCS)→ 0.5 ms/slot,2000 slot/s | TS 38.211 §4.3.2 | |
| **MCS 表** | Table 1(64QAM,MCS 0–28)的 `Q_m` 與碼率 | TS 38.214 Table 5.1.3.1-1 | 與 OAI `nr_mac_common.c` `Table_51311` 逐列相同 ✔ |
| **CQI 表** | Table 1(CQI 0–15)的 `Q_m` 與碼率 | TS 38.214 Table 5.2.2.1-2 | 與 OAI `gNB_scheduler_primitives.c` `cqi_table1` 逐列相同 ✔ |
| CQI 定義 | 回報「以該 CQI 的調變碼率傳送單一 TB 時 BLER ≤ 0.1」的最高 CQI | TS 38.214 §5.2.2.1 | OAI UE `csi_rx.c` `nr_csi_rs_cqi_estimation` 同規則 ✔ |
| PRB 最小分配 `MIN_PRB` | 5 | OAI `gNB_scheduler_dlsch.c:753` `const int min_rbSize = 5` | ✔ |
| `RRU.PrbTotDl` 計算式 | `(UE Δtotal_rbs) × 100 / (node Δtotal_prb_aggregate)` | TS 28.552;OAI `ran_func_kpm_subs.c::fill_RRU_PrbTotDl()` | |
| `DRB.RlcSduDelayDl` 定義域 | 到達 → MAC 取走(不含傳輸) | TS 28.552;OAI `nr_rlc_entity_am.c:1762` `waited_time` | |
| RSRP / SINR 量化 | RSRP −156..−31 dBm → 0..125;SINR −23..40 dB → +23 | TS 38.133 | |

以上規範表(MCS 表、CQI 表與其 SINR 切點)放在 DU 與 RU 共用的
`ran-emulation-runtime-interface-protocol/ran_sim_protocol/nr_link_tables.py`,兩端從同一處取值。

### BLER 曲線(DU 唯一的 BLER 模型)

| | |
|---|---|
| 來源 | OAI 官方 NR AWGN link-level 模擬,首傳錯誤率 `err0 / trials0` |
| 來源路徑 | `openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/AWGN_results/mcs{N}_awgn_5G.csv` |
| 產生方法 | EESM + MATLAB link-level simulation(見來源 `README.md`) |
| 覆蓋 | MCS 0–28 全覆蓋,2086 點 |
| 檔案 | `RANsim-DU/main/apps/mac/services/optional/link_adaptation/data/bler_curve.csv` |
| 讀取 | `link_adaptation/bler_curve.py`;檔案不存在或缺 MCS 時**直接拋錯**,不退回任何公式 |
| 匯入工具 | `RANsim-DU/tools/import_oai_bler.py` |
| 核對 | 抽查 MCS 9:SNR 4.5 dB → 853/1500、5.0 dB → 96/1500,與 CSV 完全相同 ✔ |

使用者:外迴路鏈路適應、操作點 MCS 選擇(排程器 PRB 需求、上行)、slot engine 重傳模擬、
PM 的 HARQ 輪次統計、CQI 切點推導。**2026-09-26 前 MCS 控制器另用一套無出處的 erfc 公式**
(見 D 節),與本曲線在中高階 MCS 相差約 10 dB,兩套並存;已統一。

**選 SISO 而非 MIMO 2×2 的理由**:AWGN 曲線是「每一層」的原語。MIMO 增益在本模擬中
顯式建模為 (a) TBS × 層數、(b) 每層 SINR 因等功率分配下降,而非換一張把 2×2 效應
預先吸收的表。用 MIMO 表會讓 rank 1/2 共用同一條曲線 → 看不出天線選擇的差異,且只在
2×2 成立。

**來源資料的已知非單調**:OAI 原始資料中 MCS 1 達 10% BLER 需 −2.3 dB,低於 MCS 0
(−0.3 dB)與 MCS 2(−0.2 dB)。不修改原始資料;程式選 MCS 時逐一檢查每個 MCS 而非假設
單調,CQI 切點則取累計最大值。

### 外迴路鏈路適應(`mcs_controller.py`)

OAI `get_mcs_from_bler()`(`gNB_scheduler_primitives.c`)的等價實作,以下數值皆已核對:

| 參數 | 值 | OAI 出處 |
|---|---|---|
| 更新週期 | 10 frame = 100 ms(模擬時間) | `BLER_UPDATE_FRAME 10` |
| BLER 平滑 | `bler = 0.9 × bler + 0.1 × bler_window` | `BLER_FILTER 0.9f` |
| 上 / 下門檻 | 0.15 / 0.05(`TARGET_BLER` = 0.1 的 1.5× / 0.5×) | `MACRLC_nr_paramdef.h` `dl_bler_target_upper/lower` 預設 |
| MCS 範圍 | 0–28 | `dl_min_mcs` / `dl_max_mcs` 預設 |
| 新 UE 初值 | MCS = 下限;平滑 BLER = (上 + 下) / 2 | `init_bler_stats()` |

與 OAI 的差異:`bler_window` 用 OAI 曲線上「目前 MCS、目前 SINR」的期望首傳 BLER
(本模擬沒有逐 TB 解碼結果);不實作「一期內首傳 ≤ 3 次就降一階」(閒置 UE 的 MCS
仍出現在 KPM,掉到 0 會誤導分析)。

---

## B. 有標定依據的抽象參數(非規範值,但有可追溯的依據)

| 項目 | 值 | 依據 |
|---|---|---|
| `sched_pipeline_slots` | 2 slot(1 ms) | 聚合 gNB 排程處理 + PDCCH 組裝/解碼 + UE N1(TS 38.214 §5.3)。標定自 OAI 實測「乾淨 1~4 ms」。**⚠ 舊名 `k0_slots` 會被誤讀為 TS 38.214 §5.1.2.1 的 K0(NR 常見值為 0),2026-09-11 已正名。** |
| HARQ RTT | 4 slot | NR TDD 下 k1 + k2 + 處理時間的合理量級,未逐項對規範拆解 |
| 操作點首傳 BLER | 0.1 | TS 38.214 §5.2.2.1 的 CQI 定義。**更正**:舊文件寫「對齊 OAI `target_dl_bler`」,OAI 並無此參數;OAI 外迴路用 0.05 / 0.15 的上下門檻,0.1 恰在其間 |
| HARQ 最大輪數 | 4 | OAI `dl_harq_round_max` 預設值 |
| HARQ 重傳合併 | 第 k 次傳送等效 SINR + `10·log10(k)` dB | Chase combining(D. Chase, *"Code Combining"*, IEEE Trans. Commun., 1985)。NR 實際用 incremental redundancy,增益通常略高,故為保守近似 |
| 實際送出量 | 頻譜效率 × (1 − 首傳 BLER) | 每個重傳佔用一次傳輸機會的穩態結果;鏈路適應把 BLER 維持在 5%–15%,約扣 10% |
| CQI 1 切點 | MCS 0 切點 − `10·log10(0.2344 / 0.1523)` dB | CQI 1(QPSK 78/1024)在 MCS 表 1 沒有同碼率的 MCS,以頻譜效率比外插 |
| EESM β | per-MCS 表 | Lagén et al., *"New Radio Physical Layer Abstraction for System-Level Simulations of 5G Networks"*, IEEE ICC 2020, **arXiv:2001.10309** Table II。ns-3 **5G-LENA** 的依據實作。以 NR-compliant LLS 對 TDL-A/TDL-D(TR 38.901)校正。論文 Remark 1:β 對 SCS 與載波頻率不敏感 → 適用 band78。 |
| 等功率分配 | 每層 −10log10(ν) | TS 38.214 §5.1.6.2 無其他指示時各層等分;一階近似 |
| `RLC_TX_MAXSIZE_BYTES` | 10 MB | 對齊 OAI `nr_rlc_entity_am.c:1842-1847` 的 `tx_maxsize` 行為(依 DT 的低 MCS 環境下調) |
| `discardTimer` | 300 ms | 3GPP `discardTimer` 機制;值取遠高於已對齊的 12–22 ms |

---

## C. 無出處的擬合值與建模簡化(仍需處理)

| 項目 | 值 | 問題 |
|---|---|---|
| `fading_std_db` | 2.0 dB | slot engine 的 per-slot 快衰落標準差,無出處。**未來應改為由 TDL 通道模型(TR 38.901)或 Physics 的實際通道變異推導** |
| TB 計數粒度 | 每 UE 每 tick 算一個 TB | PM 的 `du_TB.*` 計數以「樣本」為單位,不是逐 slot 的實際 TB 數;比例(錯誤率、重傳率)可用,絕對數量不可用 |
| `SLOT_CADENCE_PERIOD` | 40 | 僅用於反事實對照組 `res_op`,不影響 KPM |
| `LEGACY_OVERHEAD` / `LEGACY_TDD_DL_RATIO` / `LEGACY_TDD_UL_RATIO` | 0.80 / 0.72 / 0.22 | 僅 `NR_TBS_SPEC_MODE=off` 時使用。per-run 與 compose 自 2026-09-26 起皆為 on,保留僅供 A/B 回溯 |

---

## D. 曾經是 fudge 或誤標出處、已清除

| 項目 | 狀態 |
|---|---|
| RLC delay `/30` | slot engine takeover 後輸出被丟棄,不進 KPM(2026-06) |
| load-adaptive K0(3→44 slot) | compose 釘死 MIN=MAX=2,內插失效(2026-06-17) |
| `SLOT_OP_PRB_FLOOR = 10` | 降為 2(物理最小 grant)(2026-06-17) |
| BLER「亂猜 sigmoid」 | 早期版本,已棄用 |
| 4-MCS 手工 BLER 錨表 | 換成 OAI 官方 28-MCS 曲線(2026-09-11);`bler_curve.legacy.csv` 於 2026-09-26 刪除 |
| slot engine 與 scheduler 容量分歧 1.389× | `nr_resources` 集中常數後收斂為 1.000(2026-09-11);per-run 於 2026-09-26 開啟 `NR_TBS_SPEC_MODE` 才真正生效 |
| **MCS 控制器的 erfc BLER 公式**(`_MCS_SINR_REQUIRED_DB`、`SIGMA_DB`) | 2026-09-26 刪除。舊文件稱其「已降為 fallback,正常路徑不再命中」,**實為錯誤**:MCS 控制器一直在主路徑使用它,比 OAI 曲線悲觀約 10 dB,使回報的 MCS 與吞吐量偏低。另外公式在其「10% 門檻」處實際算出 50% |
| **無出處的 SINR→(MCS, bit/RE) 表**(`mcs_table._SINR_TO_MCS`) | 2026-09-26 刪除。註解稱 Table 5.1.3.1-2(256QAM 表),數值與兩張表都對不上;MCS 28 給到 7.41 bit/RE,超過 64QAM 上限 5.55。吞吐量用它的頻譜效率,與實際使用的 MCS 無關 |
| **兩張不同的 SINR→CQI 表** | 2026-09-26 刪除。DU 的表註明「對齊 OAI cqi_table2」,**OAI 並無此表**,數值也與 OAI UE 端切點不符;RU 另有一張每 2 dB 一格的表。改為依 TS 38.214 §5.2.2.1 由 OAI 曲線推導的單一共用表 |
| **固定 SINR 分箱的 HARQ 輪次**(≥12 dB 首傳成功…) | 2026-09-26 改為依 MCS 與 SINR 由 OAI 曲線計算。舊分箱與 MCS 無關,但鏈路適應會把首傳 BLER 維持在 10% 附近 |
| **MCS 控制器用牆鐘、每 tick 動兩次** | 2026-09-26 改為模擬時間,每 100 ms 一期。舊行為下收斂速度隨倍速改變(10 倍速時慢 10 倍) |
| DU `phy_high` 模組 | 2026-09-26 刪除。除 BLER 曲線外皆為死碼(precoding、MIMO、layer mapping、調變表、兩個無呼叫者的 HTTP 端點);BLER 曲線移入 `mac/link_adaptation`。MIMO 由 RU codebook 與 mac `mu_mimo` 負責 |

---

## E. 開關與設定值

| 環境變數 | 程式預設 | per-run / compose | 作用 |
|---|---|---|---|
| `NR_TBS_SPEC_MODE` | `off` | **`on`** | 資源/TBS 走 38.214 規範式;off 用 C 節的舊常數 |
| `NR_MIMO_LAYERS_ENABLED` | `off` | **`on`** | TBS 乘層數 ν + 等功率分配 |
| `NR_EESM_ENABLED` | `off` | **`on`** | 多分量 SINR 用 EESM 壓縮;off = 線性域算術平均 |
| `SIM_BLER_CURVE_PATH` | 不設 | 不設 | 不設時讀 `link_adaptation/data/bler_curve.csv`;設了僅供實驗,檔案須涵蓋 MCS 0–28 |
| `TARGET_BLER` | 0.1 | 0.1(registry「OAI 對齊」模板的 `target_bler`) | 外迴路**目標值**;上下門檻 = 1.5× / 0.5× = 0.15 / 0.05(OAI 預設)。2026-09-26 前被當成上門檻、下門檻取 1/3,該模板實際跑 0.1 / 0.033。可用 `TARGET_BLER_UPPER` / `_LOWER` 直接指定 |
| `TDD_PATTERN` | `DDDDDDDSUU` | 取自 registry DU 模板 `tdd_pattern` | 逐 slot DL/UL 權重;S = 6 DL / 4 UL 符號(`NR_SPECIAL_DL_SYMB` / `NR_SPECIAL_UL_SYMB`)。2026-09-26 前樣式寫死,模板只影響舊模式的上行比例 |
| `DL_MIN_MCS` / `DL_MAX_MCS` | 0 / 28 | 同 | MCS 範圍(OAI 預設) |
| `PHY_PATH_GAIN_PER_PORT`(Physics) | `off` | `on` | path_gain 改 per-port 平均(TS 38.215 §5.1.1);1×1 下等價,啟用多天線前必開 |
| `UE_ARRAY_ROWS/COLS`(RU) | `1` | `1` | UE 端陣列(原為硬編);Physics 目前仍忽略 rx_config |
| `PYTHONPATH`(DU、RU) | — | `/opt/ran-sim-protocol` | 共用套件讀掛載的原始碼,改了不必重建映像 |

**A/B 驗證結果**(每 PRB 每秒 bit 數,per bps_re):

| 模式 | scheduler | slot engine | 比值 |
|---|---|---|---|
| legacy | 165,888 | 230,400 | **1.389** |
| spec(2026-09-26 起 per-run 使用) | 196,114 | 196,114 | **1.000** |
| spec + MIMO rank 2 | 392,229 | 392,229 | 1.000 |

---

## F. 待辦

1. **`fading_std_db` 要有出處** — 目前是 C 類唯一還在主路徑上的擬合值。
2. ~~RU 回 per-layer SINR~~ — **已完成(2026-09-26 核對)**:RU `dl_tti_pipeline` 在
   `CqiIndication.sinr_per_layer_db` 回傳每層 SINR,DU `eesm.effective_sinr_for_layers`
   有該陣列時以 `combine_db()` 做 EESM,沒有才退回等功率分配。
3. ~~確認天線配置真的改變 H~~ — **已驗證(2026-09-11):不會。** 整條多天線鏈路
   目前是惰性的,H 恆為 1×1、rank 恆為 1。且 `path_gain` 對天線元素對加總,放大
   陣列會讓它膨脹(2×2+1×2 ≈ +9 dB)= antenna gain 雙重計算。已加
   `PHY_PATH_GAIN_PER_PORT`(TS 38.215 §5.1.1,預設 off,1×1 下等價)。
   完整盤點與改造方案見 [`mimo_antenna_selection_plan.md`](mimo_antenna_selection_plan.md)。
4. **β 表 bit-exact 驗證** — 目前由 arXiv PDF 的雙欄 Table II 轉錄,已通過單調性與
   調變邊界(MCS 10 / 17 跳階)一致性檢查;要 bit-exact 請對照 5G-LENA `model/nr-eesm-t1.cc`。
5. **重跑 OAI 對照** — 2026-09-26 起 per-run 開啟 spec 模式並統一 BLER 模型,
   B/C 兩類參數(如 `sched_pipeline_slots`)的既有標定是在舊常數下做的,需重新比對。
6. **HARQ 重傳改 incremental redundancy** — 目前以 Chase combining 保守近似。
