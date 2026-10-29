"""RunKpmSample read API 行為(backend_rule §3-4)。"""
from django.test import Client, TestCase

BASE = "/api/v0.1/Run_orchestrator/Run_telemetry_archive"


class RunKpmSampleReadApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/RunKpmSampleReader/read").status_code, 405)

    def test_rejects_bad_json(self):
        r = Client().post(f"{BASE}/RunKpmSampleReader/read", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)


class EventReaderRunSeqTest(TestCase):
    """2026-10-14:換手 / RIC 命令 Reader 預設只回最近一次執行(以前混入同 run uuid 的舊執行,監控頁換手數暴增)。"""
    RUN = "scene_run-test"

    def _mk(self, model, seq, **kw):
        from django.utils import timezone
        from main.apps.run_telemetry_archive.services.common.uuid_service import UUIDService
        now = timezone.now()
        p = model._meta.db_table.rsplit("_run_", 1)[-1]
        model.objects.create(**{f"run_{p}_uuid": UUIDService.generate_uuid(f"run_{p}"), "run_seq": seq,
                                "f_scene_run_uuid": self.RUN, f"run_{p}_created_at": now,
                                f"run_{p}_updated_at": now, **kw})

    def _read(self, ep, **body):
        r = Client().post(f"{BASE}/{ep}/read", data={"f_scene_run_uuid": self.RUN, **body}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["data"]

    def test_handover_defaults_to_latest_run(self):
        from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
        for seq in (1, 1, 2):
            self._mk(RunHandoverEvent, seq, ue_id="u", source_cell="a", target_cell="b")
        self.assertEqual([x["run_seq"] for x in self._read("RunHandoverEventReader")], [2])
        self.assertEqual(len(self._read("RunHandoverEventReader", run_seq=0)), 3)
        self.assertEqual(len(self._read("RunHandoverEventReader", run_seq=1)), 2)

    def test_control_defaults_to_latest_run_even_before_first_event(self):
        """新一次執行剛開(KPM 已寫、還沒有命令)→ 回空,不回上一次執行的命令。"""
        from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
        from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
        self._mk(RunControlEvent, 1, action_type="x", target="c")
        self.assertEqual(len(self._read("RunControlEventReader")), 1)
        self._mk(RunKpmSample, 2)
        self.assertEqual(self._read("RunControlEventReader"), [])


class RunExecutionReaderTest(EventReaderRunSeqTest):
    """2026-10-16:回放清單 —— 每個 (run, run_seq) 一列,含起訖、模擬時長、換手 / RLF / 命令數。"""

    def test_one_row_per_execution_newest_first(self):
        from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
        from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
        from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
        for seq, t0 in ((1, 1000), (2, 9000)):
            for i in range(3):
                self._mk(RunKpmSample, seq, wall_time_ms=t0 + i * 1000, scene_t_sec=float(i),
                         per_ue={"u1": {}, "u2": {}}, per_cell={"c": {}})
        self._mk(RunHandoverEvent, 2, ue_id="u", source_cell="a", target_cell="b", outcome="SUCC")
        self._mk(RunHandoverEvent, 2, ue_id="u", source_cell="a", target_cell="", outcome="RLF")
        self._mk(RunControlEvent, 2, source="ric/x", action_type="ho", target="u", outcome="ACK")
        rows = self._read("RunExecutionReader")
        self.assertEqual([r["run_seq"] for r in rows], [2, 1])
        r = rows[0]
        self.assertEqual((r["windows"], r["sim_sec"], r["wall_sec"], r["ue_count"], r["cell_count"]), (3, 2.0, 2.0, 2, 1))
        self.assertEqual((r["handovers"], r["handover_succ"], r["rlf"], r["controls"]), (1, 1, 1, 1))
