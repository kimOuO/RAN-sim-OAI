"""讀 Mitsuba 場景 XML → 可在瀏覽器畫的網格清單(2026-09-17,畫布顯示掃描模型用)。

只回傳場景檔裡有引用的 ply / obj,檔案內容另由 mesh_file 端點依 shape id 取,不接受任意路徑。
座標系:平台與 Mitsuba 場景檔同為 Y-up(physics 才在邊界轉成 z-up),前端不用再轉。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

# registry 與 physics 都把 scanned-building-assets 掛在 /app/scenes(2026-09-18),路徑兩邊通用
PATH_ALIASES: dict[str, str] = {}
ALLOWED_ROOTS = (Path("/home/mitlab/XAPP_DT/Omnivers_platform/assets/maps"), Path("/app/scenes"))
MAX_MESH_BYTES = 60 * 1024 * 1024


def resolve(path: str) -> Path | None:
    for a, b in PATH_ALIASES.items():
        if path.startswith(a):
            path = b + path[len(a):]
    p = Path(path).resolve()
    if not any(p == r or r in p.parents for r in (x.resolve() for x in ALLOWED_ROOTS)):
        return None
    return p if p.exists() else None


def _floats(s: str | None) -> list[float]:
    return [float(v) for v in (s or "").replace(",", " ").split()]


def _transform_ops(shape: ET.Element) -> list[dict[str, Any]]:
    """to_world 的子元素依序轉成 {op, ...}(Mitsuba 語意:後面的 op 套在前面的結果上)。"""
    tw = next((t for t in shape.findall("transform") if t.get("name") == "to_world"), None)
    ops: list[dict[str, Any]] = []
    for e in list(tw) if tw is not None else []:
        if e.tag == "translate":
            v = _floats(e.get("value")) or [float(e.get(k, 0)) for k in "xyz"]
            ops.append({"op": "translate", "v": v})
        elif e.tag == "scale":
            v = _floats(e.get("value"))
            v = (v * 3 if len(v) == 1 else v) or [float(e.get(k, 1)) for k in "xyz"]
            ops.append({"op": "scale", "v": v})
        elif e.tag == "rotate":
            ops.append({"op": "rotate", "axis": [float(e.get(k, 0)) for k in "xyz"], "deg": float(e.get("angle", 0))})
        elif e.tag == "matrix":
            ops.append({"op": "matrix", "v": _floats(e.get("value"))})
    return ops


def list_shapes(xml_path: str) -> list[dict[str, Any]]:
    src = resolve(xml_path)
    if src is None:
        return []
    stat = src.stat()
    return _list_shapes(str(src), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=16)
def _list_shapes(xml_path: str, mtime_ns: int, size: int) -> list[dict[str, Any]]:
    src = Path(xml_path)
    root = ET.parse(src).getroot()
    bsdf_color = {}
    for b in root.iter("bsdf"):
        rgb = next((r for r in b.iter("rgb") if r.get("name") == "reflectance"), None)
        bsdf_color[b.get("id")] = _floats(rgb.get("value")) if rgb is not None else None
    out = []
    for i, sh in enumerate(root.iter("shape")):
        if sh.get("type") not in ("ply", "obj"):
            continue
        fn = next((s.get("value") for s in sh.findall("string") if s.get("name") == "filename"), None)
        if not fn:
            continue
        f = resolve(fn if fn.startswith("/") else str(src.parent / fn))
        if f is None:
            continue
        ref = next((r.get("id") for r in sh.findall("ref")), None)
        name = sh.get('id') or str(i)
        row = {"shape_id": name, "name": sh.get("id") or f.stem, "format": sh.get("type"), "material": ref or "",
                    "color": bsdf_color.get(ref), "bytes": f.stat().st_size, "too_large": f.stat().st_size > MAX_MESH_BYTES,
                    "transform": _transform_ops(sh), "_path": str(f), '_xml_path': str(src), '_shape_index': i,
                    'kind': 'surface' if name == 'ground' else 'mesh'}
        if name.startswith('buildings_') and not row['too_large']:
            from .osm_mesh_parts import read_parts, part_bytes
            try:
                _, _, ranges = read_parts(str(f))
                for part, vertex_range in enumerate(ranges):
                    part_id = f'{name}__building_{part}' if len(ranges) > 1 else name
                    content = part_bytes(str(f), vertex_range)
                    out.append({**row, 'shape_id': part_id, 'name': f'建築 {len(out) + 1}', 'kind': 'building',
                                'bytes': len(content), '_vertex_range': vertex_range,
                                'geometry_key': hashlib.sha256(content).hexdigest()})
                continue
            except (ValueError, IndexError, StopIteration, UnicodeError):
                pass
        row['geometry_key'] = f'{f}:{f.stat().st_mtime_ns}:{f.stat().st_size}'
        out.append(row)
    return out


def scene_xml_paths(geometry_source: Any, buildings: list[Any]) -> list[str]:
    paths = []
    if isinstance(geometry_source, dict) and geometry_source.get("type") == "mitsuba_xml_path" and geometry_source.get("path"):
        paths.append(str(geometry_source["path"]))
    for b in buildings:
        ref = getattr(b, "geometry_ref", "") or ""
        if ref.endswith(".xml") and ref not in paths:
            paths.append(ref)
    return paths
