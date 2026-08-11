"""Host telemetry → bbu_status entries for E2KPM.

Adapted from XAPP_DT/Physics_sim/_legacy/cu_candidates/bbu_telemetry.py:
removed Django-utils dependency, swapped to our env_loader / logger.
psutil and pynvml are imported softly — both may be absent in tests.
"""
from __future__ import annotations

from main.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import psutil  # type: ignore[import-not-found]
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    logger.warning("psutil not installed — bbu_status will be all zeros")

try:
    import pynvml  # type: ignore[import-not-found]

    pynvml.nvmlInit()
    _NVML_READY = True
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
except Exception:  # noqa: BLE001
    _NVML_READY = False
    _GPU_HANDLE = None


def _read_cpu_temp() -> float:
    if not _HAS_PSUTIL:
        return 0.0
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return 0.0
        for key in ("coretemp", "k10temp", "cpu_thermal"):
            if key in temps and temps[key]:
                return float(temps[key][0].current)
        first = next(iter(temps.keys()))
        if temps[first]:
            return float(temps[first][0].current)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _read_cpu_power_estimate() -> float:
    if not _HAS_PSUTIL:
        return 0.0
    cpu_pct = psutil.cpu_percent(interval=None)
    return cpu_pct / 100.0 * 65.0  # assume 65 W TDP


def _read_gpu_power() -> float:
    if not _NVML_READY:
        return 0.0
    try:
        return pynvml.nvmlDeviceGetPowerUsage(_GPU_HANDLE) / 1000.0
    except Exception:  # noqa: BLE001
        return 0.0


class BbuTelemetryService:
    @staticmethod
    def snapshot_host() -> dict[str, float]:
        if not _HAS_PSUTIL:
            return {
                "cpu": 0.0, "cpu_power": 0.0, "cpu_temp": 0.0,
                "load_average": 0.0, "mem": 0.0, "tot_power": 0.0,
            }
        # cpu_percent(interval=None) 量的是「距上次呼叫」的區間;一個 snapshot 內
        # 只能量一次然後共用 — 連續呼叫第二次區間趨近 0 恆回 0.0(bbu 全 0 實踩)。
        # 首次呼叫(基線未建立)也回 0 → 補一次 0.1s 阻塞量測。
        cpu = psutil.cpu_percent(interval=None)
        if cpu <= 0.0:
            cpu = psutil.cpu_percent(interval=0.1)
        cpu_power = cpu / 100.0 * 65.0  # assume 65 W TDP
        mem = psutil.virtual_memory().percent
        try:
            load1, _, _ = psutil.getloadavg()
        except (AttributeError, OSError):
            load1 = 0.0
        return {
            "cpu": round(cpu, 2),
            "cpu_power": round(cpu_power, 2),
            "cpu_temp": round(_read_cpu_temp(), 2),
            "load_average": round(load1, 2),
            "mem": round(mem, 2),
            "tot_power": round(cpu_power + _read_gpu_power(), 2),
        }

    @staticmethod
    def per_gnb_snapshot(gnb_names: list[str]) -> dict[str, dict[str, float]]:
        host = BbuTelemetryService.snapshot_host()
        n = max(1, len(gnb_names))
        shared = {
            "cpu": round(host["cpu"] / n, 2),
            "cpu_power": round(host["cpu_power"] / n, 2),
            "cpu_temp": host["cpu_temp"],
            "load_average": round(host["load_average"] / n, 2),
            "mem": host["mem"],
            "tot_power": round(host["tot_power"] / n, 2),
        }
        return {name: dict(shared) for name in gnb_names}
