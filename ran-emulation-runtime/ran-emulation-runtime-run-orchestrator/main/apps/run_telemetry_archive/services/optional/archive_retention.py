"""歸檔保存策略 —— 在 run 啟動時清掉過期資料。

為什麼需要:外部 Agent 是 pull 模式,資料要留到他來取,所以不能跑完就刪。
但也不能無限長 —— 實測 run_kpm_sample 已累積 163 萬列 / 2.2 GB,
其中單一 scene_run 因為反覆重跑而有 46 萬筆視窗(8 小時劇本應該只有 28800)。

兩條規則(都可用 env 關掉):
    ARCHIVE_KEEP_RUN_SEQ    每個 scene_run 只保留最近 N 輪(含剛啟動的這輪);舊的重跑清掉
    ARCHIVE_RETENTION_DAYS  超過 N 天的歸檔一律清掉

在「啟動時」清而不是「跑完時」清:跑完立刻刪會讓對方來不及取。
啟動一場新的表示上一輪已經用完了,這時候清最安全。

只刪自己(run_seq 較舊)與逾期的,**不會動到別的 scene_run 的最新資料**。
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.apps.run_telemetry_archive.models.run_pm_snapshot import RunPmSnapshot
from main.utils.logger import get_logger

logger = get_logger(__name__)

_MODELS = (
    (RunKpmSample, "run_kpm_sample_created_at"),
    (RunHandoverEvent, "run_handover_event_created_at"),
    (RunControlEvent, "run_control_event_created_at"),
    (RunPmSnapshot, "run_pm_snapshot_created_at"),
)


def _purge_old_seq(scene_run_uuid: str, keep: int) -> dict[str, int]:
    """同一個 scene_run 只留最近 keep 輪(keep = 0 → 全清)。"""
    out: dict[str, int] = {}
    if keep < 0:
        return out
    seqs = sorted({s for s in RunKpmSample.objects
                   .filter(f_scene_run_uuid=scene_run_uuid)
                   .values_list("run_seq", flat=True).distinct()}, reverse=True)
    if len(seqs) <= keep:
        return out
    drop = seqs[keep:]
    for model, _ in _MODELS:
        n, _d = model.objects.filter(f_scene_run_uuid=scene_run_uuid, run_seq__in=drop).delete()
        if n:
            out[model.__name__] = out.get(model.__name__, 0) + n
    if out:
        logger.info("歸檔清理 %s:刪掉舊的 run_seq %s → %s", scene_run_uuid[-8:], drop, out)
    return out


def _purge_expired(days: int) -> dict[str, int]:
    """超過 days 天的歸檔全部清掉(跨 scene_run)。"""
    out: dict[str, int] = {}
    if days <= 0:
        return out
    cutoff = timezone.now() - timedelta(days=days)
    for model, ts_field in _MODELS:
        n, _d = model.objects.filter(**{f"{ts_field}__lt": cutoff}).delete()
        if n:
            out[model.__name__] = out.get(model.__name__, 0) + n
    if out:
        logger.info("歸檔清理:刪掉 %d 天前的資料 → %s", days, out)
    return out


def apply_on_start(scene_run_uuid: str) -> dict[str, int]:
    """run 啟動時呼叫。失敗只記 log —— 清不掉不該擋住啟動。"""
    total: dict[str, int] = {}
    try:
        # 在新一輪寫入前清:舊的只留 N-1 輪,加上即將開始的這輪剛好 N 輪(N ≤ 0 = 不清)
        keep = int(getattr(settings, "ARCHIVE_KEEP_RUN_SEQ", 3))
        for part in (_purge_old_seq(scene_run_uuid, keep - 1) if keep > 0 else {},
                     _purge_expired(int(getattr(settings, "ARCHIVE_RETENTION_DAYS", 30)))):
            for k, v in part.items():
                total[k] = total.get(k, 0) + v
    except Exception:  # noqa: BLE001
        logger.exception("歸檔清理失敗 %s", scene_run_uuid)
    return total
