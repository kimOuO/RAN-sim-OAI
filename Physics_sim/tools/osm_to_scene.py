#!/usr/bin/env python3
"""osm_to_scene.py — OSM (.osm XML) → Omniverse USD + Sionna Mitsuba XML/PLY。

★ 設計核心:單一幾何來源、雙輸出 ★
    Omniverse Kit 讀 USD(/World/Environment reference)
    Sionna RT  讀 Mitsuba XML(+ PLY)
兩者由同一份 OSM、同一個原點、同一個座標系產生,確保
「3D 看到的」與「光追算到的」是同一個世界。

座標系(對齊平台既有慣例)
    Y-up 右手、單位公尺、原點 = bbox 中心
    x = 東(East)、y = 上(Up)、z = 南(South,即 North = -z)
    → 與 Kit 的 SetStageUpAxis(y) / SetStageMetersPerUnit(1.0) 一致

OSM 處理規則
    - building=* 輪廓;building:part=* 分層(Simple 3D Buildings)
    - 有 part 落在輪廓內 → 只畫 part,不畫輪廓(避免幾何重疊)
    - type=multipolygon relation → outer/inner ring(中庭挖洞)
    - 高度:height(可帶 "m")> building:levels × LEVEL_H > 預設
    - min_height / building:min_level → part 的底部高度

用法
    python osm_to_scene.py map.osm \\
        --usd  ../../Omnivers_platform/assets/maps/NTUST_campus.usd \\
        --mitsuba ../scenes/ntust_campus.xml
"""
from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import mapbox_earcut as earcut
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import STRtree

# ── 可調參數 ────────────────────────────────────────────────
LEVEL_HEIGHT_M = 3.2      # building:levels → 高度的每層高
DEFAULT_HEIGHT_M = 6.0    # 完全沒高度資訊時的預設(約 2 層)
MIN_AREA_M2 = 4.0         # 太小的多邊形丟掉(雜訊)
GROUND_MARGIN_M = 20.0    # 地面比 bbox 外擴多少

DEFAULT_MATERIAL = "concrete"
MATERIAL_MAP = {  # 對齊 mitsuba_builder.MATERIAL_MAP
    "concrete": "itu_concrete",
    "glass": "itu_glass",
    "metal": "itu_metal",
    "brick": "itu_brick",
    "wood": "itu_wood",
}


# ── 地理投影:WGS84 → 本地 ENU 公尺(小範圍局部切平面近似)──
def _meters_per_degree(lat_deg: float) -> tuple[float, float]:
    """回傳 (每緯度公尺, 每經度公尺)。500m 尺度下誤差可忽略,免 pyproj。"""
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
        return east, -north          # z = -North(Y-up 右手)


# ── OSM 解析 ────────────────────────────────────────────────
def _parse_height(tags: dict[str, str]) -> float | None:
    """height 可能是 "36.5" / "4" / "1.42 m" / "12'" 等。"""
    raw = tags.get("height")
    if raw:
        cleaned = raw.strip().lower().replace("m", "").replace("meter", "").strip()
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


def load_osm(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()

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

    b = root.find("bounds")
    bounds = None
    if b is not None:
        bounds = (float(b.get("minlat")), float(b.get("minlon")),
                  float(b.get("maxlat")), float(b.get("maxlon")))
    return {"nodes": nodes, "ways": ways, "relations": relations, "bounds": bounds}


def _ring_coords(refs: list[str], nodes: dict, proj: Projector) -> list[tuple[float, float]]:
    pts = []
    for r in refs:
        if r in nodes:
            lat, lon = nodes[r]
            pts.append(proj(lat, lon))
    return pts


def _make_polygon(shell: list, holes: list[list] | None = None) -> Polygon | None:
    if len(shell) < 4:
        return None
    try:
        p = Polygon(shell, holes or [])
        if not p.is_valid:
            p = p.buffer(0)          # 修自交
        if p.is_empty or p.geom_type != "Polygon" or p.area < MIN_AREA_M2:
            return None
        return orient(p, sign=1.0)   # 外環 CCW、內環 CW → 法線一致
    except Exception:
        return None


def extract_buildings(osm: dict, proj: Projector) -> list[dict[str, Any]]:
    """回傳 [{name, poly, base, top, material, kind}]，已處理 part/輪廓重疊。"""
    nodes, ways, relations = osm["nodes"], osm["ways"], osm["relations"]
    outlines: list[dict] = []
    parts: list[dict] = []
    consumed_ways: set[str] = set()

    # 1) multipolygon relations(含中庭挖洞)
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
            h = _parse_height(tags)
            rec = {
                "name": tags.get("name") or f"rel_{rel['id']}",
                "poly": poly,
                "base": _parse_min_height(tags),
                "height": h,
                "material": tags.get("building:material", DEFAULT_MATERIAL),
            }
            (parts if "building:part" in tags else outlines).append(rec)

    # 2) 一般 closed way
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
            continue                      # 非閉合
        poly = _make_polygon(_ring_coords(refs, nodes, proj))
        if poly is None:
            continue
        rec = {
            "name": tags.get("name") or f"way_{wid}",
            "poly": poly,
            "base": _parse_min_height(tags),
            "height": _parse_height(tags),
            "material": tags.get("building:material", DEFAULT_MATERIAL),
        }
        (parts if is_part else outlines).append(rec)

    # 3) 有 part 落在輪廓內 → 丟掉該輪廓(Simple 3D Buildings 規則)
    kept_outlines = outlines
    if parts:
        tree = STRtree([p["poly"] for p in parts])
        kept_outlines = []
        for o in outlines:
            hit = False
            for idx in tree.query(o["poly"]):
                pp = parts[int(idx)]["poly"]
                inter = o["poly"].intersection(pp).area
                if inter > 0.5 * pp.area:     # part 主要落在此輪廓內
                    hit = True
                    break
            if not hit:
                kept_outlines.append(o)

    result = []
    for rec in kept_outlines + parts:
        # OSM Simple 3D Buildings:height / building:levels 是「從地面算起的絕對頂高」,
        # min_height / building:min_level 才是底。part 佔 [base, top],不可再相加。
        h = rec["height"]
        top = (rec["base"] + DEFAULT_HEIGHT_M) if h is None else h
        if top <= rec["base"]:
            continue
        rec["top"] = top
        result.append(rec)
    return result


# ── 幾何:多邊形 → 擠出成三角網格 ──────────────────────────
def extrude(poly: Polygon, base: float, top: float
            ) -> tuple[np.ndarray, np.ndarray]:
    """回傳 (points Nx3, tris Mx3)。Y-up:y=高度。"""
    rings = [list(poly.exterior.coords)[:-1]]
    rings += [list(i.coords)[:-1] for i in poly.interiors]

    pts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []

    # 牆面:每條邊 → 2 個三角形
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, z0 = ring[i]
            x1, z1 = ring[(i + 1) % n]
            b = len(pts)
            pts += [(x0, base, z0), (x1, base, z1), (x1, top, z1), (x0, top, z0)]
            tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]

    # 屋頂:earcut 三角化(支援挖洞)
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
        # 屋頂法線朝上:外環 CCW(XZ)在 Y-up 下需反轉繞序
        tris += [tuple(t) for t in roof[:, ::-1]]

    return np.asarray(pts, dtype=np.float64), np.asarray(tris, dtype=np.int64)


# ── 輸出:USD ───────────────────────────────────────────────
def _viridis(t: float) -> tuple[float, float, float]:
    """簡化 viridis 色帶(t∈[0,1]),低=深紫、高=黃綠。"""
    stops = [
        (0.0, (0.267, 0.005, 0.329)), (0.25, (0.283, 0.141, 0.458)),
        (0.5, (0.128, 0.567, 0.551)), (0.75, (0.369, 0.789, 0.383)),
        (1.0, (0.993, 0.906, 0.144)),
    ]
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return tuple(c0[j] + f * (c1[j] - c0[j]) for j in range(3))
    return stops[-1][1]


def _make_band_materials(stage, n_bands: int = 12):
    """在 /World/OSM/Looks 建 n 條依樓高分帶的 UsdPreviewSurface 材質。
    RTX 下綁定材質優先於 displayColor → 不會被 extension 的灰色 fallback 蓋掉。"""
    from pxr import UsdShade, Sdf, Gf
    UsdGeom_Scope = __import__("pxr").UsdGeom
    stage.DefinePrim("/World/OSM/Looks", "Scope")
    mats = []
    for i in range(n_bands):
        t = i / (n_bands - 1)
        r, g, b = _viridis(t)
        mat = UsdShade.Material.Define(stage, f"/World/OSM/Looks/band_{i:02d}")
        sh = UsdShade.Shader.Define(stage, f"/World/OSM/Looks/band_{i:02d}/Surface")
        sh.CreateIdAttr("UsdPreviewSurface")
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(r, g, b))
        sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.75)
        sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
        mats.append(mat)
    return mats


def write_usd(buildings: list[dict], out: Path, ground: tuple[float, float, float, float]) -> None:
    from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf, Vt

    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(out))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)      # ★ 對齊 Kit
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)            # ★ 公尺

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    UsdGeom.Xform.Define(stage, "/World/OSM")

    N_BANDS = 12
    HEIGHT_MAX = 50.0
    band_mats = _make_band_materials(stage, N_BANDS)

    # 地面
    x0, z0, x1, z1 = ground
    g = UsdGeom.Mesh.Define(stage, "/World/OSM/Ground")
    g.CreatePointsAttr([Gf.Vec3f(x0, 0, z0), Gf.Vec3f(x1, 0, z0),
                        Gf.Vec3f(x1, 0, z1), Gf.Vec3f(x0, 0, z1)])
    g.CreateFaceVertexCountsAttr([4])
    g.CreateFaceVertexIndicesAttr([0, 3, 2, 1])
    g.CreateDisplayColorAttr([Gf.Vec3f(0.35, 0.42, 0.32)])

    bl = UsdGeom.Xform.Define(stage, "/World/OSM/Buildings")
    used: set[str] = set()
    for i, b in enumerate(buildings):
        pts, tris = extrude(b["poly"], b["base"], b["top"])
        if len(tris) == 0:
            continue
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in b["name"])
        if not name or name[0].isdigit():
            name = f"b_{name}"
        while name in used:
            name = f"{name}_{i}"
        used.add(name)

        m = UsdGeom.Mesh.Define(stage, f"/World/OSM/Buildings/{name}")
        m.CreatePointsAttr([Gf.Vec3f(*map(float, p)) for p in pts])
        m.CreateFaceVertexCountsAttr([3] * len(tris))
        m.CreateFaceVertexIndicesAttr([int(v) for v in tris.flatten()])
        m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        h = b["top"] - b["base"]
        t = min(h / HEIGHT_MAX, 1.0)
        band = min(int(t * N_BANDS), N_BANDS - 1)
        # displayColor(給 Storm / fallback)+ 綁材質(給 RTX,優先生效不被灰色蓋)
        m.CreateDisplayColorAttr([Gf.Vec3f(*_viridis(t))])
        UsdShade.MaterialBindingAPI(m.GetPrim()).Bind(band_mats[band])

    # 地面改深灰材質,讓上色建築更凸出
    gmat = UsdShade.Material.Define(stage, "/World/OSM/Looks/ground")
    gsh = UsdShade.Shader.Define(stage, "/World/OSM/Looks/ground/Surface")
    gsh.CreateIdAttr("UsdPreviewSurface")
    gsh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.12, 0.13, 0.14))
    gsh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.9)
    gmat.CreateSurfaceOutput().ConnectToSource(gsh.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI(g.GetPrim()).Bind(gmat)

    stage.GetRootLayer().Save()


# ── 輸出:Mitsuba XML + PLY ─────────────────────────────────
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


def write_mitsuba(buildings: list[dict], out_xml: Path,
                  ground: tuple[float, float, float, float]) -> None:
    from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    mesh_dir = out_xml.parent / f"{out_xml.stem}_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    scene = Element("scene", {"version": "3.0.0"})
    SubElement(scene, "integrator", {"type": "path"})

    # 依材質合併(Sionna 依 BSDF 判 radio material,不需 per-building 分件)
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

    mats = set(by_mat) | {"itu_concrete"}
    for m in sorted(mats):
        bsdf = SubElement(scene, "bsdf", {"type": "diffuse", "id": m})
        SubElement(bsdf, "rgb", {"name": "reflectance", "value": "0.5 0.5 0.5"})

    for mat, (P, T) in by_mat.items():
        pts = np.concatenate(P)
        tris = np.concatenate(T)
        ply = mesh_dir / f"{mat}.ply"
        _write_ply(ply, pts, tris)
        sh = SubElement(scene, "shape", {"type": "ply", "id": f"buildings_{mat}"})
        SubElement(sh, "string", {"name": "filename",
                                  "value": f"{mesh_dir.name}/{ply.name}"})
        SubElement(sh, "ref", {"id": mat})

    # 地面
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


# ── main ────────────────────────────────────────────────────
def main() -> int:
    global LEVEL_HEIGHT_M, DEFAULT_HEIGHT_M

    ap = argparse.ArgumentParser(description="OSM → Omniverse USD + Sionna Mitsuba")
    ap.add_argument("osm", type=Path)
    ap.add_argument("--usd", type=Path, help="輸出 USD(給 Omniverse Kit)")
    ap.add_argument("--mitsuba", type=Path, help="輸出 Mitsuba XML(給 Sionna)")
    ap.add_argument("--level-height", type=float, default=LEVEL_HEIGHT_M)
    ap.add_argument("--default-height", type=float, default=DEFAULT_HEIGHT_M)
    args = ap.parse_args()

    LEVEL_HEIGHT_M = args.level_height
    DEFAULT_HEIGHT_M = args.default_height

    osm = load_osm(args.osm)
    if not osm["bounds"]:
        print("ERROR: .osm 缺 <bounds>", file=sys.stderr)
        return 1
    minlat, minlon, maxlat, maxlon = osm["bounds"]
    lat0, lon0 = (minlat + maxlat) / 2, (minlon + maxlon) / 2
    proj = Projector(lat0, lon0)

    (sx, sz) = proj(maxlat, maxlon)
    print(f"origin  : lat={lat0:.7f} lon={lon0:.7f}  (→ 本地 0,0)")
    print(f"範圍    : {abs(sx)*2:.1f} m (E-W) × {abs(sz)*2:.1f} m (N-S)")

    blds = extract_buildings(osm, proj)
    if not blds:
        print("ERROR: 沒有解析到任何建築", file=sys.stderr)
        return 1

    hs = [b["top"] - b["base"] for b in blds]
    tagged = sum(1 for b in blds if b["height"] is not None)
    print(f"建築    : {len(blds)} 棟  (有高度標籤 {tagged}、"
          f"用預設 {len(blds)-tagged})")
    print(f"高度    : min={min(hs):.1f} m  max={max(hs):.1f} m  "
          f"mean={sum(hs)/len(hs):.1f} m")

    xs = [c for b in blds for c in b["poly"].bounds[0::2]]
    zs = [c for b in blds for c in b["poly"].bounds[1::2]]
    ground = (min(xs) - GROUND_MARGIN_M, min(zs) - GROUND_MARGIN_M,
              max(xs) + GROUND_MARGIN_M, max(zs) + GROUND_MARGIN_M)

    if args.usd:
        write_usd(blds, args.usd, ground)
        print(f"USD     → {args.usd}")
    if args.mitsuba:
        write_mitsuba(blds, args.mitsuba, ground)
        print(f"Mitsuba → {args.mitsuba}")
    if not args.usd and not args.mitsuba:
        print("(未指定 --usd / --mitsuba,只做解析)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
