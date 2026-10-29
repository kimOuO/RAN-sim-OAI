"""歸檔保留:啟動新一輪前清理,清完加上新的這輪剛好 ARCHIVE_KEEP_RUN_SEQ 輪。"""
from __future__ import annotations

import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.apps.run_telemetry_archive.services.optional import archive_retention

RUN = "scene_run-retention-test"


def _seed(*seqs: int) -> None:
    now = timezone.now()
    for s in seqs:
        RunKpmSample.objects.create(run_kpm_sample_uuid=str(uuid.uuid4()), run_seq=s, f_scene_run_uuid=RUN,
                                    run_kpm_sample_created_at=now, run_kpm_sample_updated_at=now)


def _seqs() -> list[int]:
    return sorted(set(RunKpmSample.objects.filter(f_scene_run_uuid=RUN).values_list("run_seq", flat=True)))


class ArchiveRetentionTests(TestCase):
    @override_settings(ARCHIVE_KEEP_RUN_SEQ=3, ARCHIVE_RETENTION_DAYS=0)
    def test_keeps_two_old_before_new_run(self) -> None:
        _seed(4, 5, 6, 7)
        archive_retention.apply_on_start(RUN)
        self.assertEqual(_seqs(), [6, 7])   # + 即將開始的第 8 輪 = 3 輪

    @override_settings(ARCHIVE_KEEP_RUN_SEQ=1, ARCHIVE_RETENTION_DAYS=0)
    def test_keep_one_clears_all_old(self) -> None:
        _seed(1, 2)
        archive_retention.apply_on_start(RUN)
        self.assertEqual(_seqs(), [])

    @override_settings(ARCHIVE_KEEP_RUN_SEQ=0, ARCHIVE_RETENTION_DAYS=0)
    def test_zero_disables(self) -> None:
        _seed(1, 2, 3, 4, 5)
        archive_retention.apply_on_start(RUN)
        self.assertEqual(_seqs(), [1, 2, 3, 4, 5])
