"""Sionna RT PathSolver 封裝。

載入場景一次，per-tick 更新 Receivers 位置後重跑 PathSolver。
輸出每個 (UE, gNB) 對的 path gain（linear）。

鐵則 14-5：Service 不處理 HTTP，不做業務決策——只輸出數字。
"""

import os

# TS 38.215 §5.1.1:RSRP 為 per-port 量(功率線性平均,接收分集下不取各分支之和)。
# off = 舊行為:對 (rx_ant, tx_ant) 元素對加總,僅在 1x1 陣列下與 per-port 等價。
# 啟用多天線陣列前必須打開,否則 path_gain 會被元素數污染。詳見 compute_paths 內註解。
import math
from typing import Any

from main.utils.env_loader import get_bool, get_float, get_int, get_str

# per-port 正規化(TS 38.215 §5.1.1 RSRP 是「每個資源元素、每個天線埠」的功率):預設 on(2026-09-13 P5-3)。
# off = 舊行為,path gain 隨 (rx_ant × tx_ant) 元素對數線性膨脹(4×4 比 1×1 高 ~15 dB 的假增益)。
_PATH_GAIN_PER_PORT = get_bool("PHY_PATH_GAIN_PER_PORT", default=True)
from main.utils.logger import get_logger


logger = get_logger(__name__)


def probe_gpu() -> dict[str, Any]:
    """查 GPU 狀態。失敗時回傳 {available: False}。"""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"available": False}
        idx = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(idx)
        return {
            "available": True,
            "name": props.name,
            "total_memory_mb": props.total_memory // (1024 * 1024),
            "capability": f"{props.major}.{props.minor}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}


class SionnaEngine:
    """Stateful：啟動時載 scene + 建 Transmitters；per-tick 更新 Receivers。"""

    def __init__(
        self,
        *,
        mitsuba_scene_path: str,
        gnbs: list[dict[str, Any]],
        gnb_antenna_pattern: str = "tr38901",
        gnb_polarization: str = "V",
        ue_antenna_pattern: str = "dipole",
        ue_polarization: str = "V",
        gnb_array_rows: int = 1,
        gnb_array_cols: int = 1,
        ue_array_rows: int = 1,
        ue_array_cols: int = 1,
        gnb_v_spacing: float = 0.5,
        gnb_h_spacing: float = 0.5,
        ue_v_spacing: float = 0.5,
        ue_h_spacing: float = 0.5,
    ):
        self.mitsuba_scene_path = mitsuba_scene_path
        self.gnbs = gnbs
        self.frequency_ghz = float(gnbs[0]["frequency_ghz"]) if gnbs else get_float(
            "SIM_DEFAULT_FREQ_GHZ", default=3.5
        )
        self.max_depth = get_int("SIM_MAX_DEPTH", default=5)
        self.gnb_antenna_pattern = gnb_antenna_pattern
        self.gnb_polarization = gnb_polarization
        self.ue_antenna_pattern = ue_antenna_pattern
        self.ue_polarization = ue_polarization
        self.gnb_array_rows = max(1, int(gnb_array_rows))
        self.gnb_array_cols = max(1, int(gnb_array_cols))
        self.ue_array_rows = max(1, int(ue_array_rows))
        self.ue_array_cols = max(1, int(ue_array_cols))
        self.gnb_v_spacing = float(gnb_v_spacing); self.gnb_h_spacing = float(gnb_h_spacing)
        self.ue_v_spacing = float(ue_v_spacing); self.ue_h_spacing = float(ue_h_spacing)
        # Transmitter orientation 的軸對應(2026-09-13 P5 自由空間實測,見 progress_log P5-1):
        #   本場景 Y-up(x 東、y 高、z 南)、boresight +x;Sionna orientation=[α(繞 z), β(繞 y), γ(繞 x)]
        #   → α 是「仰角」(α=-35° 讓下方 UE +3.7 dB)、β 是「方位」(β=-35° 讓 +z 方向 UE +3.6 dB)、γ 是 roll。
        #   yup   :azimuth(羅盤,0=北=-z,90=東=+x)→ β = 90°-az;tilt(正=往下)→ α = -tilt。
        #   legacy:舊行為 azimuth → α(把扇區轉成仰角,物理上錯;只留給對照舊 cache 用)。
        self._orientation_mode = get_str("PHY_ORIENTATION_MODE", default="yup").lower()
        self._cell_tilts: dict[str, float] = {}

        # 延遲 import Sionna——避免 Django management command 也拖 GPU kernel
        try:
            import sionna.rt as rt  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "sionna-rt not installed inside container (pip install sionna-rt)"
            ) from exc

        self._rt = rt
        self._solver = rt.PathSolver()

        # 載場景
        # P5-2:z-up 框架 —— 幾何補 Rx(+90°)、位置進 Sionna 前轉(見 frame.py)
        from .frame import adapt_scene_xml, to_sionna, is_zup
        self._to_sionna = to_sionna
        self._zup = is_zup()
        self._scene = rt.load_scene(adapt_scene_xml(mitsuba_scene_path))

        # 主動檢查:這個場景的材質是否支援使用者要求的頻率?
        # 不支援就 raise SceneFrequencyMismatch（會帶詳細訊息),不再偷偷 fallback。
        from .scene_frequency import assert_frequency_for_scene
        assert_frequency_for_scene(self.frequency_ghz, self._scene)

        self._scene.frequency = self.frequency_ghz * 1e9

        # 配天線陣列（scene-global，所有 gNB 共用一組 tx_array、所有 UE 共用一組 rx_array）。
        # 0.5λ 是 5G NR PlanarArray 慣例間距。
        self._scene.tx_array = rt.PlanarArray(
            num_rows=self.gnb_array_rows,
            num_cols=self.gnb_array_cols,
            vertical_spacing=self.gnb_v_spacing,
            horizontal_spacing=self.gnb_h_spacing,
            pattern=gnb_antenna_pattern,
            polarization=gnb_polarization,
        )
        # UE 天線：cross 會把每 element 拆成 H+V 兩 ports（手機典型 2T4R）；
        # 增加 num_rx_ant 會線性增加 path solver 計算量
        self._scene.rx_array = rt.PlanarArray(
            num_rows=self.ue_array_rows,
            num_cols=self.ue_array_cols,
            vertical_spacing=self.ue_v_spacing,
            horizontal_spacing=self.ue_h_spacing,
            pattern=ue_antenna_pattern,
            polarization=ue_polarization,
        )

        # 裝 Transmitters：每個 cell 建一個 TX（帶正確 azimuth）
        # _cell_entries: [{tx_name, gnb_name, pci}] — 用於 compute_paths 聚合
        # DAS / multi-TRP 支援:cell.position 給的話用 cell 位置(物理分離 antenna),
        # 沒給就 fallback 到 gnb.position(傳統 co-sited sector)。
        self._cell_entries: list[dict[str, Any]] = []
        for g in gnbs:
            cells = g.get("cells") or []
            if cells:
                for cell in cells:
                    tx_name = f"{g['name']}#{cell['pci']}"
                    azimuth_rad = math.radians(float(cell.get("azimuth_deg", 0)))
                    # AL5.2: 試 α 正號. γ 經實驗繞 beam 軸自身 → c1/c3 沒方向性.
                    # 改成 α 正號 (預設 Sionna world Z = our scene Y = 高度).
                    tx_position = cell.get("position") or g["position"]
                    tilt_deg = float(cell.get("tilt_deg", 0) or 0)
                    self._cell_tilts[tx_name] = tilt_deg
                    tx = rt.Transmitter(
                        name=tx_name,
                        position=self._to_sionna(tx_position),
                        orientation=self._orientation(azimuth_rad, tilt_deg),
                    )
                    self._scene.add(tx)
                    self._cell_entries.append({
                        "tx_name": tx_name,
                        "gnb_name": g["name"],
                        "pci": int(cell["pci"]),
                    })
            else:
                # 向後相容：無 cells 時當單 TX 處理
                azimuth_rad = math.radians(float(g.get("azimuth_deg", 0)))
                tilt_deg = float(g.get("tilt_deg", 0) or 0)
                self._cell_tilts[g["name"]] = tilt_deg
                tx = rt.Transmitter(
                    name=g["name"],
                    position=self._to_sionna(g["position"]),
                    orientation=self._orientation(azimuth_rad, tilt_deg),
                )
                self._scene.add(tx)
                self._cell_entries.append({
                    "tx_name": g["name"],
                    "gnb_name": g["name"],
                    "pci": int(g.get("pci", 0)),
                })

        total_tx = len(self._cell_entries)
        logger.info(
            "SionnaEngine init: scene=%s freq=%.2f GHz max_depth=%d gnbs=%d tx=%d "
            "gnb_array=%dx%d %s/%s ue_array=%dx%d %s/%s",
            mitsuba_scene_path, self.frequency_ghz, self.max_depth, len(gnbs), total_tx,
            self.gnb_array_rows, self.gnb_array_cols, gnb_antenna_pattern, gnb_polarization,
            self.ue_array_rows, self.ue_array_cols, ue_antenna_pattern, ue_polarization,
        )

        # Warmup：跑一個 dummy compute 預編譯 CUDA kernel，避免第一個真實請求多 100~150ms
        self._warmup()

        logger.info("SionnaEngine ready (warmed up)")


    def _orientation(self, azimuth_rad: float, tilt_deg: float) -> list[float]:
        """Sionna orientation [α, β, γ](ZYX Euler,boresight = Rz(α)·Ry(β)·x̂ = (cosα cosβ, sinα cosβ, -sinβ))。
        本場景 Y-up、羅盤方位 az(0=北=-z, 90=東=+x)、tilt 正=往下(-y):
          目標方向 d = (sin az·cos t, -sin t, -cos az·cos t) → β = -asin(d_z), α = atan2(d_y, d_x), γ = 0。
        與 rt.Transmitter.look_at 實測一致(E→0,0;S→β=-90;E 下 35°→α=-35.5;S 下 35°→α=-90,β=-54.5)。
        legacy 模式保留舊行為(azimuth 直接進 α,物理上是仰角;只給對照舊 cache)。"""
        if self._orientation_mode == "legacy":
            return [azimuth_rad, 0.0, 0.0]
        if self._zup:
            # z-up 世界:α = 繞 z 的方位(羅盤 0=北=+y_s, 90=東=+x),β = 繞 y 的俯仰(正 = 往下,-z)
            return [math.radians(90.0) - azimuth_rad, math.radians(tilt_deg), 0.0]
        t = math.radians(tilt_deg)
        dx, dy, dz = math.sin(azimuth_rad) * math.cos(t), -math.sin(t), -math.cos(azimuth_rad) * math.cos(t)
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            dx = 1e-4   # β=±90° 的 Euler 奇異點(實測給 -200 dB 的假 null),微推一點避開
        beta = -math.asin(max(-1.0, min(1.0, dz)))
        alpha = math.atan2(dy, dx)
        return [alpha, beta, 0.0]

    def antenna_signature(self) -> dict[str, Any]:
        """目前 scene 的天線設定(陣列 + 每 tx 的 tilt),給 path_solver 判斷請求帶的設定有沒有變。"""
        return {
            "gnb": [self.gnb_antenna_pattern, self.gnb_polarization, self.gnb_array_rows, self.gnb_array_cols, self.gnb_v_spacing, self.gnb_h_spacing],
            "ue": [self.ue_antenna_pattern, self.ue_polarization, self.ue_array_rows, self.ue_array_cols, self.ue_v_spacing, self.ue_h_spacing],
            "tilts": dict(sorted(self._cell_tilts.items())),
            "orientation_mode": self._orientation_mode,
            "frame": "zup" if self._zup else "yup",
        }

    def close(self) -> None:
        """釋放 Sionna/DrJit 持有的資源。

        每次換場景都會新建一個 SionnaEngine 再換掉舊的,但舊的只是解除 Python
        參照 —— Mitsuba 場景與 PathSolver 背後是 DrJit 配置的 GPU/host 緩衝,
        不 flush 就不會還。2026-08-25 連跑十二題切換十二次場景後,physics
        漲到 **31.8 GiB** 被 global OOM killer 殺掉(anon-rss 33306552 kB)。
        """
        import gc
        for attr in ("_solver", "_scene", "_cell_entries", "_rt"):
            try:
                setattr(self, attr, None)
            except Exception:  # noqa: BLE001
                pass
        gc.collect()
        try:
            import drjit  # type: ignore
            drjit.flush_malloc_cache()
        except Exception:  # noqa: BLE001 — 沒有 drjit 或版本無此 API 就算了
            pass

    def _warmup(self) -> None:
        """啟動時跑一次 dummy compute 觸發 OptiX kernel JIT 編譯。"""
        import time

        rt = self._rt
        dummy_pos = [0.0, 1.5, 0.0]
        dummy = rt.Receiver(name="__warmup__", position=self._to_sionna(dummy_pos))
        self._scene.add(dummy)

        t0 = time.time()
        try:
            _ = self._solver(
                scene=self._scene,
                max_depth=self.max_depth,
                los=True,
                specular_reflection=True,
                diffuse_reflection=True,
                refraction=True,
                diffraction=True,
            )
            logger.info("warmup done in %.0f ms", (time.time() - t0) * 1000)
        finally:
            self._scene.remove("__warmup__")

    def compute_paths(self, *, ue_positions: list[dict[str, Any]]) -> dict[str, Any]:
        """per-tick 光追。

        Returns:
          {
            "path_gain_linear": {
                "<ue_id>": {"<gnb_name>": float, ...},  # 線性 path gain
                ...
            }
          }
        """
        rt = self._rt
        scene = self._scene

        # 清掉上 tick 的 Receivers（gNB 保留）
        for name in list(scene.receivers.keys()):
            scene.remove(name)

        # 放新 Receivers
        for u in ue_positions:
            rx = rt.Receiver(name=u["id"], position=self._to_sionna(u["position"]))
            rx.velocity = self._to_sionna(u.get("velocity", [0.0, 0.0, 0.0]))
            scene.add(rx)

        # 跑光追
        paths = self._solver(
            scene=scene,
            max_depth=self.max_depth,
            los=True,
            specular_reflection=True,
            diffuse_reflection=True,
            refraction=True,
            diffraction=True,
        )

        # 取 CIR 做 path gain
        a, _tau = paths.cir(normalize_delays=True, out_type="numpy")
        # Sionna RT v2.x shape: (num_rx, num_rx_ant, num_tx, num_tx_ant, num_paths, num_time)
        # （v1.x 有 batch_size 維在最前；v2 已拿掉。cross polarization 時 rx_ant=2）

        import numpy as np

        logger.debug("CIR shape=%s", a.shape)

        # v1.x 兼容：若 ndim==7 把 batch 維拿掉
        if a.ndim == 7:
            a = a[0]

        if a.ndim != 6:
            raise RuntimeError(f"Unexpected CIR shape {a.shape}; expected 6 dims")

        num_rx = a.shape[0]
        num_rx_ant = a.shape[1]
        num_tx = a.shape[2]
        num_tx_ant = a.shape[3]

        tx_names = [c["tx_name"] for c in self._cell_entries]
        rx_names = [u["id"] for u in ue_positions]

        if num_rx != len(rx_names) or num_tx != len(tx_names):
            logger.warning(
                "shape mismatch: num_rx=%d (expected %d), num_tx=%d (expected %d)",
                num_rx, len(rx_names), num_tx, len(tx_names),
            )

        # Fast Fading：每 tick 給每 path 加獨立隨機相位（模擬 ms 級微小動作造成的
        # 相位擾動）。多徑向量相加後自然產生 Rayleigh/Rician fading：
        #   - 單一主導路徑（LoS 強）：相干加成，fading 小（Rician-like）
        #   - 多路徑相近強度：向量和有很大變異，fading 大（Rayleigh-like）
        # ENABLE_FAST_FADING=false 可關閉（回退成舊的 incoherent 能量和）
        from main.utils.env_loader import get_bool
        enable_fast_fading = get_bool("ENABLE_FAST_FADING", default=True)

        # AK7: 取消 per-gnb_name aggregation, 直接 emit per-tx_name path_gain.
        # 同 gNB 多 sectored cell 之間 (各自 azimuth 不同) 的 path_gain 在 cell 邊緣 / 不同方向
        # 會差很多, 聚合 max 會抹掉 cell-level differentiation. 下游 RU 端用 cell name (= tx_name)
        # 查 path_gain 才能算對 RSRP / 觸發 CCO 真實 cell PRB imbalance.
        path_gain: dict[str, dict[str, float]] = {}
        # channel_matrix[ue_id][tx_name] = H (rx_ant, tx_ant) complex — per cell
        channel_matrix: dict[str, dict[str, np.ndarray]] = {}
        serving_cells: dict[str, str] = {}  # ue_id -> tx_name (best cell across all)

        for rx_i in range(num_rx):
            per_ue: dict[str, float] = {}
            per_ue_H: dict[str, np.ndarray] = {}
            best_tx = None
            best_pg = -1.0

            for tx_j in range(num_tx):
                # (rx_ant, tx_ant, num_paths) — Sionna 給的複數 coefficients
                coeffs = a[rx_i, :, tx_j, :, :, 0]

                if enable_fast_fading:
                    # 每 path 獨立隨機相位旋轉
                    num_paths = coeffs.shape[-1]
                    rand_phase = np.exp(
                        1j * np.random.uniform(0.0, 2.0 * np.pi, num_paths)
                    ).astype(coeffs.dtype)
                    # broadcast 到每 path 方向
                    faded = coeffs * rand_phase   # 相位擾動，振幅不變
                    # 複數向量相加 → narrowband channel matrix H
                    combined = np.sum(faded, axis=-1)   # (rx_ant, tx_ant)
                    pg = float(np.sum(np.abs(combined) ** 2))
                else:
                    # 舊行為：incoherent 能量和（無 fast fading，靜態 RSRP）
                    combined = np.sum(coeffs, axis=-1)
                    pg = float(np.sum(np.abs(coeffs) ** 2))

                # ── per-port 正規化(PHY_PATH_GAIN_PER_PORT)────────────────
                # 問題:上面的 pg 是對整個 (rx_ant, tx_ant) 矩陣的元素對「加總」。
                #   1x1 陣列時剛好 = 單一元素,看不出問題;一旦陣列變大,pg 會隨
                #   元素對數目線性膨脹(2x2 gNB + 1x2 UE → 8 對 → 約 +9 dB),
                #   RSRP/SINR 整體上移 —— 但那不是波束成形增益,只是把「元素數量」
                #   當成了「接收功率」。這就是 docs 早期記載的 antenna gain 雙重計算。
                #
                # 規範:3GPP TS 38.215 §5.1.1 定義 SS-RSRP 為承載參考訊號之 RE 的
                #   功率「線性平均」,且明訂在接收分集下回報值以個別接收分支為準,
                #   並非各分支功率之和 → RSRP 是 per-port 量,不隨陣列元素數放大。
                #
                # 正確的增益分工:
                #   * path_gain / RSRP  → per-port 平均(本正規化)
                #   * 波束成形陣列增益  → 由 RU 的 codebook precoder W 作用在 H 上產生,
                #                        只計一次(main/apps/beamforming/)
                #   * 空間多工增益      → 由 H 的 SVD rank 產生(TBS × ν)
                #
                # 預設 off,維持現有 1x1 數值與既有 npz cache/校正結果完全一致;
                # 要啟用多天線陣列前必須先打開,否則 path_gain 會被元素數污染。
                if _PATH_GAIN_PER_PORT:
                    n_pairs = int(combined.size) if hasattr(combined, "size") else 1
                    if n_pairs > 1:
                        pg /= float(n_pairs)

                tx_name = tx_names[tx_j]   # e.g. "gnb4#0", "gnb4#1"
                per_ue[tx_name] = pg       # per-cell — 不再聚合到 gnb_name
                per_ue_H[tx_name] = combined

                if pg > best_pg:
                    best_pg = pg
                    best_tx = tx_name

            path_gain[rx_names[rx_i]] = per_ue
            channel_matrix[rx_names[rx_i]] = per_ue_H
            if best_tx:
                serving_cells[rx_names[rx_i]] = best_tx

        return {
            "path_gain_linear": path_gain,
            "channel_matrix": channel_matrix,
            "serving_cells": serving_cells,
        }
