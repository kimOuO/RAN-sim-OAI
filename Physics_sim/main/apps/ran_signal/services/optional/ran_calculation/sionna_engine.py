"""Sionna RT PathSolver 封裝。

載入場景一次，per-tick 更新 Receivers 位置後重跑 PathSolver。
輸出每個 (UE, gNB) 對的 path gain（linear）。

鐵則 14-5：Service 不處理 HTTP，不做業務決策——只輸出數字。
"""
import math
from typing import Any

from main.utils.env_loader import get_float, get_int
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
        self._scene = rt.load_scene(mitsuba_scene_path)

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
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern=gnb_antenna_pattern,
            polarization=gnb_polarization,
        )
        # UE 天線：cross 會把每 element 拆成 H+V 兩 ports（手機典型 2T4R）；
        # 增加 num_rx_ant 會線性增加 path solver 計算量
        self._scene.rx_array = rt.PlanarArray(
            num_rows=self.ue_array_rows,
            num_cols=self.ue_array_cols,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
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
                    tx = rt.Transmitter(
                        name=tx_name,
                        position=tx_position,
                        orientation=[azimuth_rad, 0.0, 0.0],
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
                tx = rt.Transmitter(
                    name=g["name"],
                    position=g["position"],
                    orientation=[azimuth_rad, 0.0, 0.0],
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

    def _warmup(self) -> None:
        """啟動時跑一次 dummy compute 觸發 OptiX kernel JIT 編譯。"""
        import time

        rt = self._rt
        dummy_pos = [0.0, 1.5, 0.0]
        dummy = rt.Receiver(name="__warmup__", position=dummy_pos)
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
            rx = rt.Receiver(name=u["id"], position=u["position"])
            rx.velocity = u.get("velocity", [0.0, 0.0, 0.0])
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
