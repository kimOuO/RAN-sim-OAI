"""最小合法 GLB(一個三角形)→ parse_glb / read_accessor 正確。"""
import json
import struct

import numpy as np
from django.test import SimpleTestCase

from main.apps.scan_mesh_ingest.services.optional import glb_reader


def _tiny_glb() -> bytes:
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32).tobytes()
    idx = np.array([0, 1, 2], dtype=np.uint16).tobytes() + b"\x00\x00"
    bin_chunk = pts + idx
    gltf = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(bin_chunk)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pts)}, {"buffer": 0, "byteOffset": len(pts), "byteLength": 6}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                          {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}], "scene": 0}
    js = json.dumps(gltf).encode(); js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_chunk)
    return (b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk)


class GlbReaderTest(SimpleTestCase):
    def test_parse_and_accessor(self):
        gltf, binary = glb_reader.parse_glb(_tiny_glb())
        pts = glb_reader.read_accessor(gltf, binary, 0)
        self.assertEqual(pts.shape, (3, 3))
