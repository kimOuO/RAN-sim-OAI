from django.test import SimpleTestCase

from main.apps.render_osm_footprint.services.optional.nominatim_client import MAX_SPAN, MIN_SPAN_LAT, _suggest_bbox


class SuggestBboxTest(SimpleTestCase):
    def test_min_span_enforced(self):
        b = _suggest_bbox(25.0, 121.5, ["24.9999", "25.0001", "121.4999", "121.5001"])
        self.assertAlmostEqual(b["max_lat"] - b["min_lat"], MIN_SPAN_LAT, places=6)

    def test_max_span_capped(self):
        b = _suggest_bbox(25.0, 121.5, ["24.5", "25.5", "121.0", "122.0"])
        self.assertAlmostEqual(b["max_lat"] - b["min_lat"], MAX_SPAN, places=6)
