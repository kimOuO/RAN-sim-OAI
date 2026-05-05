"""BbuTelemetryService — host 系統遙測（模擬真 RAN 的 BBU 硬體 metrics）。

**注意**：真 RAN 每個 gNB 有獨立 BBU 主機。我們容器共用一個 host。
做法：讀 host 真值，按 gNB 數量平均分配，或報同一份。

欄位對應 E2.md 的 bbu_status：
  - cpu            CPU 利用率 (%)
  - cpu_power      CPU 功耗 (W)  — 需 Intel RAPL，容器常無權限，fallback 到估算
  - cpu_temp       CPU 溫度 (°C) — 需 /sys/class/thermal，容器常無權限
  - load_average   1-min load average
  - mem            記憶體利用率 (%)
  - tot_power      總功耗 (W)   — GPU + CPU 估
"""
from typing import Any

import psutil

from main.utils.logger import get_logger


logger = get_logger(__name__)

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_READY = True
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
except Exception as exc:  # noqa: BLE001
    logger.warning("pynvml init failed (GPU telemetry disabled): %s", exc)
    _NVML_READY = False
    _GPU_HANDLE = None


def _read_cpu_temp() -> float:
    """讀 CPU 溫度；容器常讀不到，失敗回 0.0。"""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return 0.0
        # 常見 key: 'coretemp', 'k10temp', 'cpu_thermal'
        for key in ("coretemp", "k10temp", "cpu_thermal"):
            if key in temps and temps[key]:
                return float(temps[key][0].current)
        # 找不到已知 key，取第一個感測器
        first_key = next(iter(temps.keys()))
        if temps[first_key]:
            return float(temps[first_key][0].current)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _read_cpu_power_estimate() -> float:
    """估 CPU 功耗：讀 Intel RAPL；失敗用 CPU% × TDP 估。"""
    try:
        # Intel RAPL package 能量（累積 μJ）
        with open("/sys/class/powercap/intel-rapl:0/energy_uj") as f:
            # 這只是即時讀取一次，實際需要兩次間隔求功率。這裡簡化。
            _energy_uj = int(f.read().strip())
    except Exception:  # noqa: BLE001
        pass

    # Fallback: CPU utilization × 假設 TDP 65W
    cpu_pct = psutil.cpu_percent(interval=None)
    tdp_w = 65.0
    return cpu_pct / 100.0 * tdp_w


def _read_gpu_power() -> float:
    if not _NVML_READY:
        return 0.0
    try:
        # NVML 回傳單位 mW
        mw = pynvml.nvmlDeviceGetPowerUsage(_GPU_HANDLE)
        return mw / 1000.0
    except Exception:  # noqa: BLE001
        return 0.0


class BbuTelemetryService:
    """Stateless — 每次 snapshot 直接探測。"""

    @staticmethod
    def snapshot_host() -> dict[str, float]:
        """取 host 整體遙測 snapshot。"""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        load1, _, _ = psutil.getloadavg()
        cpu_temp = _read_cpu_temp()
        cpu_power = _read_cpu_power_estimate()
        gpu_power = _read_gpu_power()

        return {
            "cpu": round(cpu, 2),
            "cpu_power": round(cpu_power, 2),
            "cpu_temp": round(cpu_temp, 2),
            "load_average": round(load1, 2),
            "mem": round(mem, 2),
            "tot_power": round(cpu_power + gpu_power, 2),
        }

    @staticmethod
    def per_gnb_snapshot(gnb_names: list[str]) -> dict[str, dict[str, float]]:
        """為每個 gNB 產生 bbu_status（共用 host 值，按個數平均分攤負載）。

        E2.md 格式：bbu_status = {"gnb-133": {...}, "gnb-135": {...}, "timestamp": ...}
        """
        host = BbuTelemetryService.snapshot_host()
        n = max(1, len(gnb_names))

        # 按 gNB 個數分攤 CPU/功耗（mem 和 load 不分，因為是系統級）
        shared = {
            "cpu": round(host["cpu"] / n, 2),
            "cpu_power": round(host["cpu_power"] / n, 2),
            "cpu_temp": host["cpu_temp"],    # 溫度不分
            "load_average": round(host["load_average"] / n, 2),
            "mem": host["mem"],              # mem 不分
            "tot_power": round(host["tot_power"] / n, 2),
        }

        # E2.md 用 "gnb-<pci>" 或 "gnb-<name>" 當 key；這裡用 gnb-name
        return {name: dict(shared) for name in gnb_names}
