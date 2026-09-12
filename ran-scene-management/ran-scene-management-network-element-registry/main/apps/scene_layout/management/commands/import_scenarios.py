
"""批次匯入劇本 JSON:python manage.py import_scenarios --dir ../../docs/scenarios [--roundtrip]"""
from __future__ import annotations

import glob
import json
import os

from django.core.management.base import BaseCommand

from main.apps.scene_layout.services.optional.scenario_import.roundtrip import canonical
from main.apps.scene_layout.services.optional.scenario_import.scenario_v1 import export_scenario, import_scenario


class Command(BaseCommand):
    help = "Import scenario v1 JSON files into the registry (optionally verify round-trip)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True)
        parser.add_argument("--roundtrip", action="store_true")

    def handle(self, *args, **opts):
        files = sorted(glob.glob(os.path.join(opts["dir"], "*.json")))
        ok = fail = 0
        for f in files:
            raw = json.load(open(f))
            if not raw.get("scenario_id"):
                self.stdout.write(f"skip {os.path.basename(f)} (no scenario_id)"); continue
            try:
                r = import_scenario(raw)
                msg = f"{raw['scenario_id']}: gnbs={r['gnbs']} cells={r['cells']} ues={r['ues']} knobs={len(r['knobs'])}"
                if opts["roundtrip"]:
                    back = export_scenario(r["scene_uuid"], r["scene_run_uuid"])
                    diff = canonical(raw) == canonical(back)
                    msg += "  roundtrip=" + ("OK" if diff else "MISMATCH")
                    if not diff:
                        fail += 1; self.stdout.write("  !! " + msg); continue
                ok += 1; self.stdout.write("  " + msg)
            except Exception as exc:  # noqa: BLE001
                fail += 1; self.stdout.write(f"  !! {os.path.basename(f)}: {exc}")
        self.stdout.write(f"done: ok={ok} fail={fail} of {len(files)}")
