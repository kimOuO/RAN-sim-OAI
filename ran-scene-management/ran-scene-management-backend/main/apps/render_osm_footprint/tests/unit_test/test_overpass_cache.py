"""2026-10-13:Overpass 本機快取 —— 同 bbox 不重抓;外部全失敗時退回過期快取。"""
import os
import tempfile
import time
from unittest import TestCase
from unittest.mock import MagicMock, patch

from main.apps.render_osm_footprint.services.optional import overpass_client as oc

XML = b"<osm>" + b"x" * 300 + b"</osm>"


def _resp(data):
    r = MagicMock()
    r.read.return_value = data
    r.__enter__ = lambda s: s
    r.__exit__ = lambda *a: False
    return r


class OverpassCacheTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [patch.object(oc, "CACHE_DIR", self.tmp.name), patch.object(oc, "BACKOFF_SEC", 0)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_second_call_served_from_cache(self):
        with patch.object(oc.urllib.request, "urlopen", return_value=_resp(XML)) as uo:
            self.assertEqual(oc.fetch_osm(25.0, 121.0, 25.1, 121.1), XML)
            self.assertEqual(oc.fetch_osm(25.0, 121.0, 25.1, 121.1), XML)
        self.assertEqual(uo.call_count, 1)

    def test_stale_cache_used_when_all_mirrors_fail(self):
        with patch.object(oc.urllib.request, "urlopen", return_value=_resp(XML)):
            oc.fetch_osm(25.0, 121.0, 25.1, 121.1)
        for f in os.listdir(self.tmp.name):                       # 讓快取過期
            old = time.time() - oc.CACHE_TTL_SEC - 10
            os.utime(os.path.join(self.tmp.name, f), (old, old))
        with patch.object(oc.urllib.request, "urlopen", side_effect=TimeoutError()):
            self.assertEqual(oc.fetch_osm(25.0, 121.0, 25.1, 121.1, budget=6), XML)

    def test_no_cache_and_all_fail_raises(self):
        with patch.object(oc.urllib.request, "urlopen", side_effect=TimeoutError()):
            with self.assertRaises(RuntimeError):
                oc.fetch_osm(24.0, 120.0, 24.1, 120.1, budget=6)
