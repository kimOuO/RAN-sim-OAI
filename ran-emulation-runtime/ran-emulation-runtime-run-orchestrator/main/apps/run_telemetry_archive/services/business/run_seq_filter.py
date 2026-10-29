"""同一 run uuid 多次執行共用同一張表:Reader 預設只回最近一次執行(2026-10-14,換手 / RIC 命令比照 KPM)。"""
from __future__ import annotations

from django.db.models import Max

from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample


def latest_run_seq(model, run_uuid: str) -> int | None:
    """最近一次執行的 run_seq。KPM 每秒都寫,新一次執行剛開、事件表還沒有新列時也能判對。"""
    seqs = [m.objects.filter(f_scene_run_uuid=run_uuid).aggregate(m=Max("run_seq")).get("m")
            for m in {model, RunKpmSample}]
    seqs = [s for s in seqs if s]
    return max(seqs) if seqs else None


def apply_run_seq(qs, model, run_uuid: str | None, run_seq: int | None):
    """run_seq=None → 最近一次;run_seq=0 → 全部;其他 → 指定那一次。"""
    if run_seq is None and run_uuid:
        latest = latest_run_seq(model, run_uuid)
        return qs.filter(run_seq=latest) if latest else qs
    if run_seq:
        return qs.filter(run_seq=run_seq)
    return qs
