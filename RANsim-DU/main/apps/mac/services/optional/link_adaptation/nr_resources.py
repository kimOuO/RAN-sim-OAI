"""NR 資源計算 —— PRB/slot 的 RE 數、TDD 下行比例、TBS 容量。全 DU 唯一真值來源。

★ 存在理由:過去 scheduler 與 slot engine 各自算「一個 PRB 一秒能送多少 bit」,
  兩邊常數不同(scheduler 有 0.80 overhead + 0.72 TDD;slot engine 兩者都沒有,
  TDD 遮罩還把 special slot 當整格),結果 slot engine 的排空速度比 scheduler
  的預算高約 35%。本模組把三個因子(RE 數、TDD 權重、層數)集中,讓兩個引擎
  不可能再分岔。

規範依據
--------
* **N_RE(每 PRB 的可用 RE 數)** — 3GPP TS 38.214 §5.1.3.2:
      N'_RE = N_sc^RB × N_symb^sh − N_DMRS^PRB − N_oh^PRB
      N_RE  = min(156, N'_RE) × n_PRB
  其中 N_sc^RB = 12(§4.4.4.1)。

* **N_oh^PRB(xOverhead)** — 由 `pdsch-ServingCellConfig` 的 xOverhead 配置,
  取值 {0, 6, 12, 18};**未配置時為 0**。OAI 亦以 0 呼叫:
      openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c:730
      `0 /* N_PRB_oh, 0 for initialBWP */`

* **層數 ν** — TS 38.214 §5.1.3.2 的 N_info = N_RE × R × Q_m × ν,
  故 TBS 與層數成正比。OAI 對應實作:
      openair2/LAYER2/NR_MAC_COMMON/nr_compute_tbs_common.c:68
      `Ninfo = ((nb_re * R_5 * Qm * Nl) >> 11) >> tb_scaling`
  呼叫端層數來自 `get_dl_nrOfLayers()`(gNB_scheduler_dlsch.c:722)。

* **TDD 上下行結構** — TS 38.213 §11.1 / TS 38.331 `TDD-UL-DL-ConfigCommon`。
  本模擬對齊 OAI band78 參考設定:
      targets/PROJECTS/GENERIC-NR-5GC/CONF/gnb-du.sa.band78.106prb.rfsim.pci0.conf:135-139
      dl_UL_TransmissionPeriodicity = 6 (5ms) / nrofDownlinkSlots = 7
      nrofDownlinkSymbols = 6 / nrofUplinkSlots = 2 / nrofUplinkSymbols = 4
  → 每 10 個 slot:7 個全 DL + 1 個 special(14 symbol 中 6 個 DL)+ 2 個全 UL。
  special slot **不是**整格 DL,故以 6/14 加權,而非布林遮罩的 1.0。
      有效 DL 比例 = (7 + 6/14) / 10 = 0.742857

已知簡化
--------
* `N_symb^sh` 固定 12(PDSCH 佔用符號數),未依 PDSCH mapping type / 起始符號動態變化。
* `N_DMRS^PRB` 固定 12(DMRS type 1、單符號、2 個 CDM group without data),
  未依 `dmrs-AdditionalPosition` 變化。OAI conf 為 `dmrs_TypeA_Position = 0`。
* 未做 TBS 量化(38.214 的 Ninfo → 查 Tbstable_nr / LDPC 分段對齊)。本模擬在
  byte-level 預算層工作,量化對聚合吞吐/延遲統計影響可忽略。
"""
from __future__ import annotations

from main.utils.env_loader import get_bool, get_int

# ── 38.214 §5.1.3.2 / §4.4.4.1 ────────────────────────────────────────────
N_SC_PER_RB = 12                      # N_sc^RB
N_SYMB_PDSCH = get_int("NR_N_SYMB_PDSCH", 12)      # N_symb^sh
N_DMRS_PER_PRB = get_int("NR_N_DMRS_PRB", 12)      # N_DMRS^PRB
N_OH_PER_PRB = get_int("NR_N_OH_PRB", 0)           # N_oh^PRB(xOverhead,預設 0)
RE_CAP_PER_PRB = 156                  # min(156, N'_RE) 的上限

# ── TDD(OAI band78 DDDDDDDSUU)────────────────────────────────────────────
# 每 slot 的 DL 容量權重。special slot = 6/14 個符號可用於 DL。
TDD_DL_WEIGHTS: tuple[float, ...] = (1.0,) * 7 + (6.0 / 14.0,) + (0.0, 0.0)
TDD_UL_WEIGHTS: tuple[float, ...] = (0.0,) * 7 + (4.0 / 14.0,) + (1.0, 1.0)

SLOTS_PER_SEC = get_int("NR_SLOTS_PER_SEC", 2000)  # μ=1(30 kHz SCS)→ 0.5ms/slot

# 舊行為開關:on = 用本模組的規範值;off = 保留舊常數(0.80 overhead + 0.72 TDD,
# slot engine 布林遮罩)。預設 off,確保既有校正結果不被這次改動推翻。
TBS_SPEC_MODE = get_bool("NR_TBS_SPEC_MODE", False)

# 層數開關:on = TBS 乘 MIMO 層數(38.214 §5.1.3.2 的 ν);off = 一律當 1 層(舊行為)。
# 與 TBS_SPEC_MODE 分開,因為兩者的影響方向相反,要能各自 A/B。
# ⚠ 開啟前務必同時啟用 NR_EESM_ENABLED 的等功率分配(eesm.equal_power_split_db),
#    否則層數提高等於免費多送資料 → 天線選擇結論會系統性偏向高 rank。
MIMO_LAYERS_ENABLED = get_bool("NR_MIMO_LAYERS_ENABLED", False)

# 舊常數(TBS_SPEC_MODE=off 時使用),保留供 A/B 對照
LEGACY_RE_PER_PRB_SLOT = 144          # 12 × 12,未扣 DMRS/overhead
LEGACY_OVERHEAD = 0.80                # PDCCH/DMRS/SSB 的整體折扣(擬合值,無規範出處)
LEGACY_TDD_DL_RATIO = 0.72


def n_re_per_prb_slot() -> int:
    """一個 PRB、一個 slot 的可用 RE 數 —— 38.214 §5.1.3.2 的 min(156, N'_RE)。"""
    if not TBS_SPEC_MODE:
        return LEGACY_RE_PER_PRB_SLOT
    n_re_prime = N_SC_PER_RB * N_SYMB_PDSCH - N_DMRS_PER_PRB - N_OH_PER_PRB
    return max(1, min(RE_CAP_PER_PRB, n_re_prime))


def tdd_dl_ratio() -> float:
    """有效下行 slot 比例(special slot 按符號數加權)。"""
    if not TBS_SPEC_MODE:
        return LEGACY_TDD_DL_RATIO
    return sum(TDD_DL_WEIGHTS) / len(TDD_DL_WEIGHTS)


def dl_slot_weight(abs_slot: int) -> float:
    """該 slot 可用於 DL 的容量比例(0 = UL slot,1 = 全 DL,6/14 = special)。"""
    if not TBS_SPEC_MODE:
        # 舊行為:布林遮罩,special slot 當整格 DL
        return 1.0 if (abs_slot % 10) < 8 else 0.0
    return TDD_DL_WEIGHTS[abs_slot % len(TDD_DL_WEIGHTS)]


def bits_per_prb_slot(bps_re: float, n_layers: int = 1, *,
                      legacy_overhead: bool = True) -> float:
    """一個 PRB、一個(全 DL)slot、此頻譜效率與層數 → bit 數。

    38.214 §5.1.3.2:N_info ∝ N_RE × R × Q_m × ν;此處 bps_re = R × Q_m。

    `legacy_overhead` 只在 TBS_SPEC_MODE=off 時有意義,用來重現兩個呼叫端**不同的**
    舊行為 —— 這個不對稱正是本模組要修的 bug:
      * scheduler 舊式有乘 0.80 overhead  → legacy_overhead=True
      * slot engine 舊式沒有乘            → legacy_overhead=False
    spec 模式下 overhead 由 N_oh^PRB / N_DMRS^PRB 在 RE 數層級扣除,兩端一致。
    """
    n_layers = max(1, int(n_layers)) if MIMO_LAYERS_ENABLED else 1
    bits = n_re_per_prb_slot() * bps_re * n_layers
    if not TBS_SPEC_MODE and legacy_overhead:
        bits *= LEGACY_OVERHEAD
    return bits


def bits_per_prb_sec(bps_re: float, n_layers: int = 1) -> float:
    """一個 PRB 一秒能送多少 bit(已含 TDD 下行比例與層數)。"""
    return bits_per_prb_slot(bps_re, n_layers) * SLOTS_PER_SEC * tdd_dl_ratio()


def bytes_per_prb_tick(bps_re: float, tick_s: float, n_layers: int = 1) -> float:
    """一個 PRB 在一個 tick(tick_s 秒 sim-time)能送多少 byte。"""
    return bits_per_prb_sec(bps_re, n_layers) * tick_s / 8.0


def describe() -> dict:
    """給 log / API 顯示目前生效的資源參數。"""
    return {
        "spec_mode": TBS_SPEC_MODE,
        "mimo_layers": MIMO_LAYERS_ENABLED,
        "n_re_per_prb_slot": n_re_per_prb_slot(),
        "tdd_dl_ratio": round(tdd_dl_ratio(), 6),
        "slots_per_sec": SLOTS_PER_SEC,
        "n_symb_pdsch": N_SYMB_PDSCH,
        "n_dmrs_per_prb": N_DMRS_PER_PRB,
        "n_oh_per_prb": N_OH_PER_PRB,
    }
