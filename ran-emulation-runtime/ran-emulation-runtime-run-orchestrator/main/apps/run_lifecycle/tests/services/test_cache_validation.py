import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from main.apps.run_lifecycle.services.optional import channel_cache as cc


def npy(descr, shape, data=b''):
    header = repr({'descr': descr, 'fortran_order': False, 'shape': shape}).encode()
    return b'\x93NUMPY\x01\x00' + len(header).to_bytes(2, 'little') + header + data


class CacheValidationTest(TestCase):
    def test_reject_short_cache_and_changed_path(self):
        tree = {'scene': {'scene_uuid': 'test'}, 'gnbs': [], 'ues': [{'name': 'ue11', 'waypoints': [[0, 1, 1.5, 2]]}],
                'run': {'duration_sec': 600, 'sim_dt_ms': 500}, 'buildings': []}
        with tempfile.TemporaryDirectory() as d, patch.object(cc, 'CACHE_DIR', d):
            path = Path(d) / 'test.npz'
            def write(duration):
                ticks = int(duration * 2)
                with zipfile.ZipFile(path, 'w') as z:
                    for key, descr, value, fmt in [('duration_sec', '<f4', duration, '<f'), ('tick_ms', '<i4', 500, '<i'), ('total_ticks', '<i4', ticks, '<i')]:
                        z.writestr(key + '.npy', npy(descr, (), struct.pack(fmt, value)))
                    z.writestr('path_gain_db.npy', npy('<f4', (ticks, 1, 1)))
                path.with_suffix('.manifest.json').write_text(json.dumps({'fingerprint': cc.fingerprint(tree), 'cache_size': path.stat().st_size}))
            write(60)
            self.assertFalse(cc.inspect_cache(tree)['valid'])
            self.assertIn('60', cc.inspect_cache(tree)['reason'])
            write(600)
            self.assertTrue(cc.inspect_cache(tree)['valid'])
            tree['ues'][0]['waypoints'][0][1] = 10
            self.assertFalse(cc.inspect_cache(tree)['valid'])

    def test_status_and_a3_do_not_change_physical_version(self):
        tree = {'scene': {'name': 'test'}, 'run': {'duration_sec': 600, 'sim_dt_ms': 500},
                'gnbs': [{'name': 'gnb1', 'a3_enabled': False}], 'ues': [], 'buildings': []}
        before = cc.fingerprint(tree)
        tree['run']['status'] = 'precomputing'
        tree['gnbs'][0]['a3_enabled'] = True
        self.assertEqual(cc.fingerprint(tree), before)
