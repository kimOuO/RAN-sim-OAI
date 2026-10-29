"""Recover individual extrusions from legacy OSM meshes grouped by material.

Our OSM writer appends each building's wall quads followed by its roof vertices.
Use that exact layout, not coordinate welding: adjacent buildings may touch and
must still be selected separately. Unknown mesh layouts stay a single object.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=3)
def _read(path: str, mtime_ns: int, size: int):
    with Path(path).open('rb') as f:
        lines = []
        while True:
            line = f.readline()
            if not line or sum(map(len, lines)) > 65536:
                raise ValueError('Invalid PLY header')
            lines.append(line)
            if line.strip() == b'end_header':
                break
        header = b''.join(lines).decode('ascii')
        if 'format ascii 1.0' not in header:
            raise ValueError('Not an OSM ASCII mesh')
        nv = int(next(s.split()[-1] for s in header.splitlines() if s.startswith('element vertex ')))
        nf = int(next(s.split()[-1] for s in header.splitlines() if s.startswith('element face ')))
        vertices = np.loadtxt([f.readline() for _ in range(nv)], dtype=np.float64, ndmin=2)
        triangles = np.loadtxt([f.readline() for _ in range(nf)], dtype=np.int64, ndmin=2)
    if vertices.shape != (nv, 3) or triangles.shape != (nf, 4) or not np.all(triangles[:, 0] == 3):
        raise ValueError('Unsupported OSM mesh')
    faces = triangles[:, 1:]
    if faces.size and (faces.min() < 0 or faces.max() >= nv):
        raise ValueError('Invalid mesh indices')
    ranges, start = [], 0
    while start < nv:
        end = start
        base, top = vertices[start, 1], vertices[start + 2, 1] if start + 2 < nv else 0
        if top <= base:
            raise ValueError('Not an extrusion')
        while end + 4 <= nv:
            quad = vertices[end:end + 4]
            if not (np.allclose(quad[:, 1], [base, base, top, top], atol=1e-4)
                    and np.allclose(quad[0, [0, 2]], quad[3, [0, 2]], atol=1e-4)
                    and np.allclose(quad[1, [0, 2]], quad[2, [0, 2]], atol=1e-4)):
                break
            end += 4
        count = (end - start) // 4
        stop = end + count
        if count < 3 or stop > nv or not np.allclose(vertices[end:stop], vertices[start:end:4] + [0, top - base, 0], atol=1e-4):
            raise ValueError('Unsupported roof layout')
        ranges.append((start, stop))
        start = stop
    return vertices, faces, ranges


def read_parts(path: str):
    p = Path(path)
    st = p.stat()
    return _read(str(p), st.st_mtime_ns, st.st_size)


def part_bytes(path: str, vertex_range) -> bytes:
    vertices, faces, _ = read_parts(path)
    lo, hi = vertex_range
    selected = faces[(faces.min(axis=1) >= lo) & (faces.max(axis=1) < hi)] - lo
    if not len(selected):
        raise ValueError('Empty building')
    header = f'ply\nformat ascii 1.0\nelement vertex {hi - lo}\nproperty float x\nproperty float y\nproperty float z\nelement face {len(selected)}\nproperty list uchar int vertex_indices\nend_header\n'
    points = ''.join(f'{x:.4f} {y:.4f} {z:.4f}\n' for x, y, z in vertices[lo:hi])
    triangles = ''.join(f'3 {a} {b} {c}\n' for a, b, c in selected)
    return (header + points + triangles).encode('ascii')
