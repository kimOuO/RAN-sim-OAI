
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
        parser.add_argument("--dir", default="")
        parser.add_argument("--from-store", default="", help="舊劇本倉庫 base URL(Omniverse :8001 / Physics :8104),匯入其 list 全部")
        parser.add_argument("--roundtrip", action="store_true")

    def handle(self, *args, **opts):
        items: list[tuple[str, dict, str, str]] = []   # (label, raw, precompute_status, cache_path)
        if opts["dir"]:
            for f in sorted(glob.glob(os.path.join(opts["dir"], "*.json"))):
                items.append((os.path.basename(f), json.load(open(f)), "pending", ""))
        if opts["from_store"]:
            import urllib.request
            base = opts["from_store"].rstrip("/")
            def post(path, body):
                req = urllib.request.Request(f"{base}/api/v0.1/RAN/Scenario/ScenarioController/{path}", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
                return json.load(urllib.request.urlopen(req, timeout=20))["data"]
            listed = post("list", {})
            rows = listed.get("scenarios") if isinstance(listed, dict) else listed   # Omniverse 回 {scenarios:[…]},Physics 回 […]
            for row in rows or []:
                sid = row.get("scenario_id") if isinstance(row, dict) else str(row)
                rec = post("read", {"scenario_id": sid})
                items.append((f"store:{sid}", rec.get("raw_json") or {}, str(rec.get("precompute_status") or "pending"), str(rec.get("cache_path") or "")))
        files = items
        ok = fail = 0
        for label, raw, pstatus, cpath in items:
            f = label
            if not raw.get("scenario_id"):
                self.stdout.write(f"skip {os.path.basename(f)} (no scenario_id)"); continue
            try:
                r = import_scenario(raw, precompute_status=pstatus, cache_path=cpath)
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
