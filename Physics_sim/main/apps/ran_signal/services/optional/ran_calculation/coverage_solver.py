"""Coverage Map Solver — 用 Sionna RadioMapSolver 產 per-gNB 2D RSRP 網格。

輸出格式對齊外部平台 spec：
  - 第一維 = z（北到南），第二維 = x（西到東）
  - 單位 dBm，null = 遮蔽/無訊號
"""
import math
from typing import Any

import numpy as np

from main.utils.env_loader import get_float
from main.utils.logger import get_logger


logger = get_logger(__name__)

# Sionna radio map plane 水平放置所需的 orientation（XZ 平面，法線 +Y）
_HORIZONTAL_PLANE_ORIENTATION = [0.0, 0.0, math.pi / 2]


THERMAL_NOISE_DBM_PER_HZ = -174.0


def _db_to_lin(db: float) -> float:
    return 10.0 ** (db / 10.0)


def _lin_to_db(lin: float) -> float:
    if lin <= 0:
        return -999.0
    return 10.0 * math.log10(lin)


def compute_coverage_map(
    *,
    scene: Any,
    gnbs: list[dict[str, Any]],
    cell_entries: list[dict[str, Any]] | None = None,
    x_range: tuple[float, float],
    z_range: tuple[float, float],
    x_step: float,
    z_step: float,
    sample_height_m: float = 1.5,
    max_depth: int = 3,
    null_threshold_dbm: float = -120.0,
    include_sinr: bool = True,
) -> dict[str, Any]:
    """以 Sionna RadioMapSolver 算 coverage map，輸出對齊外部 spec。

    Args:
        scene: 已載入的 Sionna Scene（需已 add Transmitters）
        gnbs: list of gNB config dict，每個含 name, pci, cell_id, frequency_ghz, power_dbm
        x_range / z_range: (min, max) 公尺
        x_step / z_step: 取樣間距 公尺
        sample_height_m: UE 高度
        max_depth: 光追 bounce 次數（coverage 建議 <= 3 節省 VRAM）
        null_threshold_dbm: RSRP 低於此值改回 None
        include_sinr: 是否一併算每格 SINR（對 serving cell 而言）

    Returns:
        {
            "grid": {n_rows, n_cols, ...},
            "gnbs": [{gnb_name, rsrp_dbm[[...]], sinr_db[[...]]}, ...],
        }
    """
    import sionna.rt as rt

    # 為缺少 pci / cell_id 的 gNBs 分配預設值
    for idx, gnb in enumerate(gnbs):
        if "pci" not in gnb:
            gnb["pci"] = idx
        if "cell_id" not in gnb:
            gnb["cell_id"] = f"cell_{gnb.get('pci', idx)}"

    x_min, x_max = x_range
    z_min, z_max = z_range
    x_size = x_max - x_min
    z_size = z_max - z_min
    x_center = (x_min + x_max) / 2
    z_center = (z_min + z_max) / 2

    # Debug: print grid info
    logger.info(f"[Coverage] Grid: x_range={x_range} z_range={z_range} x_step={x_step} z_step={z_step}")
    logger.info(f"[Coverage] Center: ({x_center}, {z_center}) Size: {x_size}×{z_size}")

    # Sionna size 是 (x_size, z_size) 對應水平 orientation；cell_size 同序
    solver = rt.RadioMapSolver()
    rm = solver(
        scene=scene,
        center=[x_center, sample_height_m, z_center],
        orientation=_HORIZONTAL_PLANE_ORIENTATION,
        size=[x_size, z_size],
        cell_size=[x_step, z_step],
        max_depth=max_depth,
        los=True,
        specular_reflection=True,
        diffuse_reflection=False,    # coverage 用，不跑 diffuse 省 VRAM
        refraction=True,
        diffraction=False,            # coverage 用，不跑 diffraction 省 VRAM
    )

    # path_gain shape = (num_tx, H, W)
    # 實測：cell_centers[0,0]=(x_min,z_min)，H = z 軸方向（h=0 是 z_min=南），W = x 軸方向
    path_gain = np.array(rm.path_gain)   # linear
    num_tx, H, W = path_gain.shape

    # 決定用哪種 TX→gNB 映射：若有 cell_entries 且與 num_tx 匹配，用多 cell 聚合；否則 1-to-1
    use_cell_entries = cell_entries is not None and len(cell_entries) == num_tx
    if not use_cell_entries and num_tx != len(gnbs):
        raise RuntimeError(
            f"Sionna num_tx={num_tx} 與 gnbs 輸入 {len(gnbs)} 不一致，且未傳入 cell_entries"
        )

    # 若 cell_entries：把 per-TX path_gain 聚合為 per-gNB（取 max）
    if use_cell_entries:
        gnb_names_ordered = [g["name"] for g in gnbs]
        gnb_pg = {name: None for name in gnb_names_ordered}
        for tx_i, ce in enumerate(cell_entries):
            gname = ce["gnb_name"]
            if gnb_pg[gname] is None:
                gnb_pg[gname] = path_gain[tx_i].copy()
            else:
                np.maximum(gnb_pg[gname], path_gain[tx_i], out=gnb_pg[gname])
        path_gain = np.stack([gnb_pg[n] for n in gnb_names_ordered], axis=0)
        num_tx = len(gnbs)

    # 轉成 RSRP dBm per (tx, H, W)
    with np.errstate(divide="ignore"):
        rsrp_dbm_all = 10.0 * np.log10(np.maximum(path_gain, 1e-30))
    for tx_i, gnb in enumerate(gnbs):
        rsrp_dbm_all[tx_i] += float(gnb["power_dbm"])

    # 若要 SINR：算每格 serving cell（argmax RSRP）+ 干擾 + 雜訊
    noise_figure_db = get_float("SIM_NOISE_FIGURE_DB", default=7.0)
    if include_sinr:
        # 每格雜訊依 serving gNB 的 bandwidth 決定；這裡取平均 bandwidth 當通用
        avg_bw_hz = np.mean([float(g["bandwidth_mhz"]) * 1e6 for g in gnbs])
        noise_dbm = THERMAL_NOISE_DBM_PER_HZ + 10 * math.log10(avg_bw_hz) + noise_figure_db
        noise_lin = _db_to_lin(noise_dbm)

        rsrp_lin_all = 10.0 ** (rsrp_dbm_all / 10.0)                # (num_tx, H, W)
        serving_tx_idx = np.argmax(rsrp_lin_all, axis=0)             # (H, W)
        total_rx_lin = np.sum(rsrp_lin_all, axis=0)                  # (H, W)

        H_idx, W_idx = np.indices((H, W))
        serving_signal_lin = rsrp_lin_all[serving_tx_idx, H_idx, W_idx]
        interf_lin = total_rx_lin - serving_signal_lin
        sinr_lin = serving_signal_lin / np.maximum(interf_lin + noise_lin, 1e-30)
        sinr_db_serving = 10.0 * np.log10(np.maximum(sinr_lin, 1e-20))    # (H, W)
    else:
        sinr_db_serving = None

    # 轉成外部 spec 要的格式：第一維 = z（北到南），第二維 = x（西到東）
    # Sionna path_gain[tx] shape 是 (H=z_axis, W=x_axis)
    # h=0 是 z_min（南），h=-1 是 z_max（北）；只需反轉 h 讓 index 0 = 北
    def _reshape_to_zx(arr_hw: np.ndarray) -> np.ndarray:
        """Sionna (z_idx_south_to_north, x_idx_west_to_east) → client (z_idx_north_to_south, x_idx_west_to_east)."""
        return arr_hw[::-1, :]

    gnb_out: list[dict[str, Any]] = []
    for tx_i, gnb in enumerate(gnbs):
        rsrp_grid = _reshape_to_zx(rsrp_dbm_all[tx_i])    # (Z, X)
        # null 遮蔽處理
        rsrp_rows = []
        for row in rsrp_grid:
            rsrp_rows.append([
                None if v < null_threshold_dbm else round(float(v), 1)
                for v in row
            ])

        gnb_entry: dict[str, Any] = {
            "gnb_name": gnb["name"],
            "pci": int(gnb["pci"]),
            "cell_id": str(gnb["cell_id"]),
            "frequency_ghz": float(gnb["frequency_ghz"]),
            "power_dbm": float(gnb["power_dbm"]),
            "rsrp_dbm": rsrp_rows,
        }

        if include_sinr and sinr_db_serving is not None:
            # 只對 serving_tx_idx == tx_i 的 cell 填 SINR 值，其他 cell 填 None
            serving_mask = (serving_tx_idx == tx_i)                  # (H, W)
            sinr_masked = np.where(serving_mask, sinr_db_serving, np.nan)
            # Clip SINR 到合理範圍 [-30, +30] dB，避免遮蔽/死角出 -170 等無意義數字
            sinr_masked = np.clip(sinr_masked, -30.0, 30.0)
            sinr_grid = _reshape_to_zx(sinr_masked)
            sinr_rows = []
            for row in sinr_grid:
                sinr_rows.append([
                    None if not np.isfinite(v) else round(float(v), 1)
                    for v in row
                ])
            gnb_entry["sinr_db"] = sinr_rows

        gnb_out.append(gnb_entry)

    # Z dim 對應的 rows：( z_max - z_min )/z_step + 1 近似值
    n_rows, n_cols = gnb_out[0]["rsrp_dbm"].__len__(), len(gnb_out[0]["rsrp_dbm"][0])

    return {
        "grid": {
            "x_range": list(x_range),
            "x_step": x_step,
            "z_range": list(z_range),
            "z_step": z_step,
            "sample_height_m": sample_height_m,
            "n_rows": n_rows,
            "n_cols": n_cols,
        },
        "gnbs": gnb_out,
    }
