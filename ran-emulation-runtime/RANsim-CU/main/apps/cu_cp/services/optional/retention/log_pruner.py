"""CU 時序表保留期(2026-09-15)。

CU 只是熱資料;長期歸檔由 orchestrator run_telemetry_archive 每秒拉走。
不清會無限長(cu_388e8e0a 一天半 cell_measurement_log 就 21 萬列),per-run DB 隨 run 拆除,
但 shared CU 與長 run 需要 rolling window。

env:CU_LOG_RETENTION_HOURS(預設 24;0 = 不清)、CU_LOG_PRUNE_INTERVAL_SEC(預設 600)。
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import timedelta

logger = logging.getLogger(__name__)
_started = False
_lock = threading.Lock()


def _prune_once(hours: float) -> dict[str, int]:
    from django.utils import timezone

    from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
    from main.apps.cu_cp.models.handover_event import HandoverEvent
    from main.apps.cu_cp.models.measurement_log import MeasurementLog
    from main.apps.cu_cp.models.rlf_event import RlfEvent

    cutoff = timezone.now() - timedelta(hours=hours)
    out = {
        "measurement_log": MeasurementLog.objects.filter(recorded_at__lt=cutoff).delete()[0],
        "cell_measurement_log": CellMeasurementLog.objects.filter(recorded_at__lt=cutoff).delete()[0],
        "rlf_event": RlfEvent.objects.filter(detected_at__lt=cutoff).delete()[0],
        "handover_event": HandoverEvent.objects.filter(started_at__lt=cutoff).delete()[0],
    }
    return out


def _loop(hours: float, interval: float) -> None:
    import time
    time.sleep(30)   # 等 migrate / 服務起完
    while True:
        try:
            n = _prune_once(hours)
            if any(n.values()):
                logger.info("[retention] pruned >%sh: %s", hours, n)
        except Exception:  # noqa: BLE001
            logger.exception("[retention] prune failed")
        time.sleep(interval)


def start() -> None:
    global _started
    hours = float(os.environ.get("CU_LOG_RETENTION_HOURS", "24") or 0)
    if hours <= 0:
        return
    interval = float(os.environ.get("CU_LOG_PRUNE_INTERVAL_SEC", "600") or 600)
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, args=(hours, interval), name="cu-log-retention", daemon=True).start()
    logger.info("[retention] started: keep %sh, every %ss", hours, interval)
