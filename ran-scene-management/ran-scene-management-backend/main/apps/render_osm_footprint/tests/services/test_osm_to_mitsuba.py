"""極小 OSM XML → 建築擠出 → Mitsuba XML(不連網)。"""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from main.apps.render_osm_footprint.services.optional.osm_to_mitsuba import convert_osm_to_mitsuba

OSM = """<?xml version='1.0'?><osm version='0.6'>
<node id='1' lat='25.0330' lon='121.5640'/><node id='2' lat='25.0330' lon='121.5645'/>
<node id='3' lat='25.0334' lon='121.5645'/><node id='4' lat='25.0334' lon='121.5640'/>
<way id='10'><nd ref='1'/><nd ref='2'/><nd ref='3'/><nd ref='4'/><nd ref='1'/><tag k='building' v='yes'/><tag k='height' v='12'/></way>
</osm>"""


class OsmToMitsubaTest(SimpleTestCase):
    def test_single_building(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "t.mitsuba.xml"
            stats = convert_osm_to_mitsuba(OSM, (25.0329, 121.5639, 25.0335, 121.5646), out)
            self.assertEqual(stats["building_count"], 1)
            self.assertAlmostEqual(stats["height_max_m"], 12.0, places=1)
            self.assertTrue(out.exists())
            self.assertIn("itu_", out.read_text())
            self.assertTrue((Path(d) / "t.footprints.json").exists())
