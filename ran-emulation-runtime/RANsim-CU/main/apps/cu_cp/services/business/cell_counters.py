"""per-cell 累計計數 helpers(A/B/C 修復,2026-08-12)。"""
from __future__ import annotations

from django.db.models import F

from main.apps.cu_cp.models.cell_cum_counter import CellCumCounter
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger

logger = get_logger(__name__)


def _get(cell_id: str) -> CellCumCounter:
    obj, _ = CellCumCounter.objects.get_or_create(
        cell_id=cell_id, defaults={"updated_at": TimestampService.now()})
    return obj


def add_session_time(cell_id: str, seconds: float) -> None:
    """A:UE 釋放/掉話時,把該 session 存活秒數落帳到其 serving cell。"""
    if not cell_id or seconds <= 0:
        return
    try:
        _get(cell_id)
        CellCumCounter.objects.filter(cell_id=cell_id).update(
            session_time_sec=F("session_time_sec") + int(seconds),
            updated_at=TimestampService.now())
    except Exception:
        logger.exception("add_session_time failed for %s", cell_id)


def sample_conn(cell_id: str, conn_now: int) -> tuple[int, float]:
    """B+C:取樣連線數 → 更新高水位 + 平均樣本。回 (conn_max, conn_mean)。"""
    try:
        obj = _get(cell_id)
        new_max = max(obj.conn_max, int(conn_now))
        CellCumCounter.objects.filter(cell_id=cell_id).update(
            conn_max=new_max,
            conn_sum=F("conn_sum") + int(conn_now),
            conn_n=F("conn_n") + 1,
            updated_at=TimestampService.now())
        n = obj.conn_n + 1
        mean = (obj.conn_sum + conn_now) / max(n, 1)
        return new_max, mean
    except Exception:
        logger.exception("sample_conn failed for %s", cell_id)
        return int(conn_now), float(conn_now)


def get_session_time(cell_id: str) -> int:
    try:
        obj = CellCumCounter.objects.filter(cell_id=cell_id).first()
        return int(obj.session_time_sec) if obj else 0
    except Exception:
        return 0
