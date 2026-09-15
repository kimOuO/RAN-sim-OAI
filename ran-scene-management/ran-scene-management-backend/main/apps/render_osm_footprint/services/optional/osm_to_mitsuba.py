"""OSM → Mitsuba 轉換服務(自 Omniverse `osm_to_usd.py` 複製並去 USD,2026-09-12 P1-4)。

從 OpenStreetMap 資料(Overpass 抓來的 XML)產生 Kit 可載入的 USD 場景。
移植自已驗證的 Physics_sim/tools/osm_to_scene.py(USD-only 版本)。

座標系(對齊 Kit)
    Y-up 右手、單位公尺、原點 = bbox 中心
    x = 東(East)、y = 上(Up)、z = 南(South,North = -z)

OSM 規則
    - building=* 輪廓;building:part=* 分層(Simple 3D Buildings)
    - 有 part 落在輪廓內 → 只畫 part(避免重疊)
    - multipolygon relation → outer/inner ring(中庭挖洞)
    - 高度:height(可帶 "m")> building:levels × LEVEL_H > 預設
    - ★ levels/height 是「從地面算的絕對頂高」,min_level/min_height 才是底
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import mapbox_earcut as earcut
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely import STRtree

# ── 可調參數 ────────────────────────────────────────────────
LEVEL_HEIGHT_M = 3.2
DEFAULT_HEIGHT_M = 6.0
MIN_AREA_M2 = 4.0
GROUND_MARGIN_M = 20.0
N_BANDS = 12
HEIGHT_MAX = 50.0

DEFAULT_MATERIAL = "concrete"


# ── 地理投影 ────────────────────────────────────────────────
def _meters_per_degree(lat_deg: float) -> tuple[float, float]:
    phi = math.radians(lat_deg)
    m_lat = (111132.92 - 559.82 * math.cos(2 * phi)
             + 1.175 * math.cos(4 * phi) - 0.0023 * math.cos(6 * phi))
    m_lon = (111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
             + 0.118 * math.cos(5 * phi))
    return m_lat, m_lon


class Projector:
    """lat/lon → 本地 (x=東, z=南) 公尺,原點為 bbox 中心。"""

    def __init__(self, lat0: float, lon0: float) -> None:
        self.lat0, self.lon0 = lat0, lon0
        self.m_lat, self.m_lon = _meters_per_degree(lat0)

    def __call__(self, lat: float, lon: float) -> tuple[float, float]:
        east = (lon - self.lon0) * self.m_lon
        north = (lat - self.lat0) * self.m_lat
        return east, -north


# ── OSM 解析 ────────────────────────────────────────────────
def _parse_height(tags: dict[str, str]) -> float | None:
    raw = tags.get("height")
    if raw:
        cleaned = raw.strip().lower().replace("meter", "").replace("m", "").strip()
        try:
            v = float(cleaned)
            if v > 0:
                return v
        except ValueError:
            pass
    lv = tags.get("building:levels")
    if lv:
        try:
            v = float(lv.strip())
            if v > 0:
                return v * LEVEL_HEIGHT_M
        except ValueError:
            pass
    return None


def _parse_min_height(tags: dict[str, str]) -> float:
    raw = tags.get("min_height")
    if raw:
        try:
            return float(raw.strip().lower().replace("m", "").strip())
        except ValueError:
            pass
    lv = tags.get("building:min_level")
    if lv:
        try:
            return float(lv.strip()) * LEVEL_HEIGHT_M
        except ValueError:
            pass
    return 0.0


def parse_osm(osm_xml: bytes | str) -> dict[str, Any]:
    """解析 OSM XML(檔內容或字串),回傳 nodes/ways/relations。"""
    root = ET.fromstring(osm_xml)
    nodes: dict[str, tuple[float, float]] = {}
    for n in root.findall("node"):
        nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")))
    ways: dict[str, dict[str, Any]] = {}
    for w in root.findall("way"):
        ways[w.get("id")] = {
            "refs": [nd.get("ref") for nd in w.findall("nd")],
            "tags": {t.get("k"): t.get("v") for t in w.findall("tag")},
        }
    relations: list[dict[str, Any]] = []
    for r in root.findall("relation"):
        relations.append({
            "id": r.get("id"),
            "members": [(m.get("type"), m.get("ref"), m.get("role"))
                        for m in r.findall("member")],
            "tags": {t.get("k"): t.get("v") for t in r.findall("tag")},
        })
    return {"nodes": nodes, "ways": ways, "relations": relations}


def _ring_coords(refs, nodes, proj):
    pts = []
    for r in refs:
        if r in nodes:
            lat, lon = nodes[r]
            pts.append(proj(lat, lon))
    return pts


def _make_polygon(shell, holes=None):
    if len(shell) < 4:
        return None
    try:
        p = Polygon(shell, holes or [])
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.geom_type != "Polygon" or p.area < MIN_AREA_M2:
            return None
        return orient(p, sign=1.0)
    except Exception:
        return None


def extract_buildings(osm: dict, proj: Projector) -> list[dict[str, Any]]:
    nodes, ways, relations = osm["nodes"], osm["ways"], osm["relations"]
    outlines: list[dict] = []
    parts: list[dict] = []
    consumed_ways: set[str] = set()

    for rel in relations:
        tags = rel["tags"]
        if tags.get("type") != "multipolygon":
            continue
        if "building" not in tags and "building:part" not in tags:
            continue
        outers, inners = [], []
        for mtype, ref, role in rel["members"]:
            if mtype != "way" or ref not in ways:
                continue
            ring = _ring_coords(ways[ref]["refs"], nodes, proj)
            if len(ring) < 4:
                continue
            (outers if role != "inner" else inners).append(ring)
            consumed_ways.add(ref)
        for shell in outers:
            poly = _make_polygon(shell, inners)
            if poly is None:
                continue
            rec = {
                "name": tags.get("name") or f"rel_{rel['id']}",
                "poly": poly, "base": _parse_min_height(tags),
                "height": _parse_height(tags),
                "material": tags.get("building:material", DEFAULT_MATERIAL),
            }
            (parts if "building:part" in tags else outlines).append(rec)

    for wid, w in ways.items():
        if wid in consumed_ways:
            continue
        tags = w["tags"]
        is_part = "building:part" in tags
        is_bld = "building" in tags and tags.get("building") != "no"
        if not (is_part or is_bld):
            continue
        refs = w["refs"]
        if len(refs) < 4 or refs[0] != refs[-1]:
            continue
        poly = _make_polygon(_ring_coords(refs, nodes, proj))
        if poly is None:
            continue
        rec = {
            "name": tags.get("name") or f"way_{wid}",
            "poly": poly, "base": _parse_min_height(tags),
            "height": _parse_height(tags),
            "material": tags.get("building:material", DEFAULT_MATERIAL),
        }
        (parts if is_part else outlines).append(rec)

    kept_outlines = outlines
    if parts:
        tree = STRtree([p["poly"] for p in parts])
        kept_outlines = []
        for o in outlines:
            hit = False
            for idx in tree.query(o["poly"]):
                pp = parts[int(idx)]["poly"]
                if o["poly"].intersection(pp).area > 0.5 * pp.area:
                    hit = True
                    break
            if not hit:
                kept_outlines.append(o)

    result = []
    for rec in kept_outlines + parts:
        h = rec["height"]
        top = (rec["base"] + DEFAULT_HEIGHT_M) if h is None else h
        if top <= rec["base"]:
            continue
        rec["top"] = top
        result.append(rec)
    return result


# ── 幾何:多邊形 → 擠出三角網格 ─────────────────────────────
def extrude(poly: Polygon, base: float, top: float):
    rings = [list(poly.exterior.coords)[:-1]]
    rings += [list(i.coords)[:-1] for i in poly.interiors]
    pts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, z0 = ring[i]
            x1, z1 = ring[(i + 1) % n]
            b = len(pts)
            pts += [(x0, base, z0), (x1, base, z1), (x1, top, z1), (x0, top, z0)]
            tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    flat: list[tuple[float, float]] = []
    ring_ends: list[int] = []
    for ring in rings:
        flat += ring
        ring_ends.append(len(flat))
    verts = np.array(flat, dtype=np.float64)
    idx = earcut.triangulate_float64(verts, np.array(ring_ends, dtype=np.uint32))
    if len(idx):
        off = len(pts)
        pts += [(x, top, z) for (x, z) in flat]
        roof = np.asarray(idx, dtype=np.int64).reshape(-1, 3) + off
        tris += [tuple(t) for t in roof[:, ::-1]]
    return np.asarray(pts, dtype=np.float64), np.asarray(tris, dtype=np.int64)


# ── USD 材質(依樓高分帶)──────────────────────────────────
def _write_ply(path: Path, pts: np.ndarray, tris: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(pts)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write(f"element face {len(tris)}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")
        for p in pts:
            f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")
        for t in tris:
            f.write(f"3 {t[0]} {t[1]} {t[2]}\n")


# 材質 → Sionna ITU BSDF id(自原檔常數區抽回;drop() 曾誤刪)
MATERIAL_MAP = {  # 對齊 Physics 的 mitsuba_builder.MATERIAL_MAP
    "concrete": "itu_concrete", "glass": "itu_glass", "metal": "itu_metal",
    "brick": "itu_brick", "wood": "itu_wood",
}


def write_mitsuba(buildings: list[dict], out_xml: Path, ground) -> None:
    """真實 mesh 的 Mitsuba 場景(非方塊)。Sionna 依 BSDF id(itu_*)判 radio material。"""
    from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    mesh_dir = out_xml.parent / f"{out_xml.stem}_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    scene = Element("scene", {"version": "3.0.0"})
    SubElement(scene, "integrator", {"type": "path"})

    by_mat: dict[str, tuple[list, list]] = {}
    for b in buildings:
        pts, tris = extrude(b["poly"], b["base"], b["top"])
        if len(tris) == 0:
            continue
        mat = MATERIAL_MAP.get(b["material"], "itu_concrete")
        P, T = by_mat.setdefault(mat, ([], []))
        off = sum(len(x) for x in P)
        P.append(pts)
        T.append(tris + off)

    for m in sorted(set(by_mat) | {"itu_concrete"}):
        bsdf = SubElement(scene, "bsdf", {"type": "diffuse", "id": m})
        SubElement(bsdf, "rgb", {"name": "reflectance", "value": "0.5 0.5 0.5"})

    for mat, (P, T) in by_mat.items():
        ply = mesh_dir / f"{mat}.ply"
        _write_ply(ply, np.concatenate(P), np.concatenate(T))
        sh = SubElement(scene, "shape", {"type": "ply", "id": f"buildings_{mat}"})
        SubElement(sh, "string", {"name": "filename",
                                  "value": f"{mesh_dir.name}/{ply.name}"})
        SubElement(sh, "ref", {"id": mat})

    x0, z0, x1, z1 = ground
    gp = np.array([[x0, 0, z0], [x1, 0, z0], [x1, 0, z1], [x0, 0, z1]], dtype=np.float64)
    gt = np.array([[0, 2, 1], [0, 3, 2]], dtype=np.int64)
    gply = mesh_dir / "ground.ply"
    _write_ply(gply, gp, gt)
    sh = SubElement(scene, "shape", {"type": "ply", "id": "ground"})
    SubElement(sh, "string", {"name": "filename", "value": f"{mesh_dir.name}/{gply.name}"})
    SubElement(sh, "ref", {"id": "itu_concrete"})

    tree = ElementTree(scene)
    indent(tree, space="  ")
    tree.write(out_xml, encoding="utf-8", xml_declaration=True)


# ── 對外主函式 ──────────────────────────────────────────────
def convert_osm_to_mitsuba(osm_xml: bytes | str, bbox: tuple[float, float, float, float],
                           out_xml: str | Path) -> dict[str, Any]:
    """OSM XML + bbox(minlat, minlon, maxlat, maxlon)→ Mitsuba XML + footprints.json,回傳統計。
    (自 Omniverse `convert_osm_to_usd` 改寫:不產 USD。)"""
    import json
    minlat, minlon, maxlat, maxlon = bbox
    lat0, lon0 = (minlat + maxlat) / 2, (minlon + maxlon) / 2
    proj = Projector(lat0, lon0)
    osm = parse_osm(osm_xml)
    blds = extract_buildings(osm, proj)
    if not blds:
        raise ValueError("沒有解析到任何建築(範圍內無 building 資料?)")
    xs = [c for b in blds for c in b["poly"].bounds[0::2]]
    zs = [c for b in blds for c in b["poly"].bounds[1::2]]
    ground = (min(xs) - GROUND_MARGIN_M, min(zs) - GROUND_MARGIN_M, max(xs) + GROUND_MARGIN_M, max(zs) + GROUND_MARGIN_M)
    out_xml = Path(out_xml)
    write_mitsuba(blds, out_xml, ground)
    footprints = []
    for b in blds:
        p = b["poly"].simplify(0.5, preserve_topology=True)
        footprints.append({"points": [[round(x, 1), round(z, 1)] for (x, z) in list(p.exterior.coords)],
                           "height": round(b["top"] - b["base"], 1)})
    # out_xml 慣例為 <base>.mitsuba.xml;footprints 放 <base>.footprints.json(with_suffix 只換最後一個副檔名,要手動剝)
    _stem = str(out_xml)[:-len(".mitsuba.xml")] if str(out_xml).endswith(".mitsuba.xml") else str(out_xml.with_suffix(""))
    fp = Path(_stem + ".footprints.json")
    fp.write_text(json.dumps(footprints), encoding="utf-8")
    hs = [b["top"] - b["base"] for b in blds]
    (sx, sz) = proj(maxlat, maxlon)
    return {"mitsuba_path": str(out_xml), "footprints_path": str(fp), "building_count": len(blds),
            "height_max_m": round(max(hs), 1), "height_mean_m": round(sum(hs) / len(hs), 1),
            "extent_ew_m": round(abs(sx) * 2, 1), "extent_ns_m": round(abs(sz) * 2, 1),
            "origin_lat": lat0, "origin_lon": lon0}
