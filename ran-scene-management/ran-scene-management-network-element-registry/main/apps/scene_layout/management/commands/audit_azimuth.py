"""audit_azimuth — 核對每個場景 cell 的 azimuth(羅盤:0=北=-z, 90=東=+x)是否面向 UE 質心。
2026-09-14 P5-2 座標系改正後,azimuth 的語意從「進 Sionna α(實際是仰角)」變成真正的羅盤方位;
舊劇本裡 az=0 常是「沒指定」而非「朝北」,重算 cache 前要逐一看。輸出每 cell 的 boresight 與 UE 質心夾角。
用法:python manage.py audit_azimuth [--only <prefix>] [--fix-centroid <prefix>]
  --fix-centroid:把該前綴場景中「全部 cell 都是 0°」的 gNB,其 cell azimuth 改成指向 UE 質心的羅盤方位(作者顯然沒做扇區)。"""
from __future__ import annotations

import math

from django.core.management.base import BaseCommand

from main.apps.scene_layout.models.scene import Scene
from main.apps.scene_layout.services.optional.scene_tree.scene_tree import build_scene_tree
from main.apps.radio_access_element.models.cell import Cell
from main.apps.scene_layout.services.common.timestamp_service import TimestampService


def _bearing_deg(dx: float, dz: float) -> float:
    """向量 (dx, dz) → 羅盤方位(0=北=-z, 90=東=+x)。"""
    return (math.degrees(math.atan2(dx, -dz)) + 360.0) % 360.0


class Command(BaseCommand):
    help = "核對 / 修正場景 cell azimuth(羅盤語意)"

    def add_arguments(self, parser):
        parser.add_argument("--only", default="", help="只看 legacy_scenario_id 以此開頭的場景")
        parser.add_argument("--fix-centroid", default="", help="對此前綴場景:gNB 所有 cell 都 0° 時改成指向 UE 質心")

    def handle(self, *args, **opts):
        only, fix = opts["only"], opts["fix_centroid"]
        n_fix = 0
        for s in Scene.objects.order_by("legacy_scenario_id", "id"):
            sid = s.legacy_scenario_id or s.name
            if only and not sid.startswith(only):
                continue
            t = build_scene_tree(s)
            pts = [(w[1], w[3]) for u in t["ues"] for w in u["waypoints"]]
            if not pts:
                continue
            cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
            for g in t["gnbs"]:
                cells = [c for d in g["dus"] for c in d["cells"]]
                for c in cells:
                    p = c["position"] or g["position"]; az = float(c["azimuth_deg"])
                    dx, dz = cx - p[0], cz - p[2]
                    if abs(dx) + abs(dz) < 1e-6:
                        continue
                    b = _bearing_deg(dx, dz); off = abs((az - b + 180) % 360 - 180)
                    verdict = "OK" if off <= 90 else ("背對" if off >= 135 else "側向")
                    self.stdout.write(f"{sid:22s} {g['name']:8s} {c['name']:12s} az={az:5.0f} 質心方位={b:5.0f} 偏角={off:4.0f}  {verdict}")
                if fix and sid.startswith(fix) and cells and all(float(c["azimuth_deg"]) == 0.0 for c in cells):
                    p = g["position"]; b = _bearing_deg(cx - p[0], cz - p[2])
                    for c in cells:
                        Cell.objects.filter(cell_uuid=c["cell_uuid"]).update(azimuth_deg=round(b, 1), cell_updated_at=TimestampService.get_current_timestamp())
                        n_fix += 1
                    self.stdout.write(f"  → {sid} {g['name']}: {len(cells)} cells 改成 {b:.1f}°(指向 UE 質心)")
        if fix:
            self.stdout.write(f"fixed {n_fix} cells")
