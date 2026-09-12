"""掃描網格 → Mitsuba 場景（給 Sionna 光追）。

輸出格式刻意與 `osm_to_usd.write_mitsuba()` 一致：一份 XML + 每種材質一個 PLY，
BSDF 的 id 就是 `itu_*` —— Sionna 依這個 id 決定 radio material。格式一致的
好處是 `map_actor._push_scene_to_physics()` 完全不用改，照樣把
`{stem}.mitsuba.xml` 推給 Physics 容器（該路徑兩邊同路徑掛載，已驗證）。

材質分群來自 `scan_material_classifier` 落地的 .npz（逐面標籤），不在這裡重跑
分類 —— 分類要解 15 張 4K JPEG，是匯入時做一次的事。

破洞：這份掃描焊接後只有 6 個洞（佔外殼約 3%），射線會從那裡漏出去。
`cap_holes=True` 會用扇形三角化把邊界迴圈封起來，材質沿用 concrete。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

import numpy as np

from main.apps.scan_mesh_ingest.services.optional.glb_reader import estimate_floor_y
from main.apps.osm_footprint_ingest.services.optional.osm_to_mitsuba import _write_ply  # PLY 寫入器與 OSM 管線共用
from main.apps.scan_mesh_ingest.services.optional.scan_material_classifier import LABELS


def _weld(points: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """以 1 mm 容差焊接重複頂點。

    GLB 的 chunk 之間頂點不共用，不焊的話拓樸上到處都是「邊界」，
    補洞會從補 6 個洞變成補幾百個假洞。
    """
    key = np.round(points * 1000).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    welded_pts = np.zeros((len(uniq), 3), dtype=np.float64)
    welded_pts[inv] = points
    welded_faces = inv[faces]
    keep = (
        (welded_faces[:, 0] != welded_faces[:, 1])
        & (welded_faces[:, 1] != welded_faces[:, 2])
        & (welded_faces[:, 0] != welded_faces[:, 2])
    )
    return welded_pts, welded_faces, keep


def find_hole_loops(faces: np.ndarray) -> list[list[int]]:
    """找出邊界迴圈（每條邊只被一個面用到 → 洞的邊緣）。"""
    from collections import defaultdict

    count: dict[tuple[int, int], int] = defaultdict(int)
    for t in faces:
        for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            count[(min(e), max(e))] += 1
    boundary = [e for e, c in count.items() if c == 1]
    if not boundary:
        return []

    adj: dict[int, list[int]] = defaultdict(list)
    for a, b in boundary:
        adj[a].append(b)
        adj[b].append(a)

    seen: set[int] = set()
    loops: list[list[int]] = []
    for start in adj:
        if start in seen:
            continue
        comp: list[int] = []
        stack = [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(comp) >= 3:
            loops.append(comp)
    return loops


def cap_hole_loops(points: np.ndarray, loops: list[list[int]]) -> np.ndarray:
    """把每個邊界迴圈以「質心扇形」封起來，回傳新增的三角形（索引指向 points）。

    不用 Poisson 之類的重建：這些洞是掃描死角，補上去只是為了擋住射線外洩，
    形狀對不對不重要，能封住就好。質心扇形對非凸迴圈也不會產生破面。
    """
    if not loops:
        return np.zeros((0, 3), dtype=np.int64)

    extra_pts: list[np.ndarray] = []
    tris: list[tuple[int, int, int]] = []
    next_idx = len(points)
    for comp in loops:
        ring = np.asarray(comp, dtype=np.int64)
        pts = points[ring]
        centre = pts.mean(axis=0)
        # 以質心為原點、迴圈主平面上的角度排序，讓扇形不自交
        centred = pts - centre
        u, _s, _vt = np.linalg.svd(centred.T @ centred)
        axis1, axis2 = u[:, 0], u[:, 1]
        ang = np.arctan2(centred @ axis2, centred @ axis1)
        order = ring[np.argsort(ang)]

        extra_pts.append(centre)
        c_idx = next_idx
        next_idx += 1
        for i in range(len(order)):
            tris.append((c_idx, int(order[i]), int(order[(i + 1) % len(order)])))

    return np.asarray(tris, dtype=np.int64), np.asarray(extra_pts, dtype=np.float64)


def build_mitsuba_from_labels(
    npz_path: str | Path,
    out_xml: str | Path,
    *,
    cap_holes: bool = True,
    recenter: bool = True,
    ground_align: bool = True,
) -> dict[str, Any]:
    """讀分類結果 → 寫 Mitsuba XML + 每材質一個 PLY。

    recenter / ground_align 預設開啟，且與 `glb_to_usd.convert_glb_to_usd()`
    用同一套規則 —— Kit 看到的幾何與 Sionna 算的幾何必須在同一個原點上，
    否則 gNB/UE 的座標在兩邊指到不同地方。
    """
    npz_path = Path(npz_path)
    out_xml = Path(out_xml)
    data = np.load(npz_path, allow_pickle=False)
    points = data["points"].astype(np.float64)
    faces = data["faces"].astype(np.int64)
    labels = data["labels"].astype(np.int64)

    points, faces, keep = _weld(points, faces)
    faces = faces[keep]
    labels = labels[keep]

    capped = 0
    if cap_holes:
        loops = find_hole_loops(faces)
        if loops:
            cap_tris, cap_pts = cap_hole_loops(points, loops)
            points = np.vstack([points, cap_pts])
            faces = np.vstack([faces, cap_tris])
            # 補出來的面沒有貼圖可判，一律當混凝土
            labels = np.concatenate([labels, np.zeros(len(cap_tris), dtype=np.int64)])
            capped = len(loops)

    if recenter or ground_align:
        lo = points.min(axis=0)
        hi = points.max(axis=0)
        offset = np.zeros(3)
        if recenter:
            offset[0] = -(lo[0] + hi[0]) / 2.0
            offset[2] = -(lo[2] + hi[2]) / 2.0
        if ground_align:
            # 與 glb_to_usd 用同一個地板基準，否則 Kit 與 Sionna 的 y=0 會差 2 m
            offset[1] = -estimate_floor_y(points, faces)
        points = points + offset

    mesh_dir = out_xml.parent / f"{out_xml.stem}_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    # 先清掉舊的 PLY：材質分類模式改變時（例如關掉 glass/metal）會少產幾個檔，
    # 不清就會留下孤兒 PLY —— XML 沒引用所以 Sionna 不會載，但看檔案的人
    # 會以為玻璃還在場景裡
    for stale in mesh_dir.glob("*.ply"):
        stale.unlink()
    out_xml.parent.mkdir(parents=True, exist_ok=True)

    scene = Element("scene", {"version": "3.0.0"})
    SubElement(scene, "integrator", {"type": "path"})

    written: dict[str, dict[str, Any]] = {}
    for li, name in enumerate(LABELS):
        sel = labels == li
        if not sel.any():
            continue
        tris = faces[sel]
        used, remap = np.unique(tris, return_inverse=True)
        sub_pts = points[used]
        sub_tris = remap.reshape(-1, 3)

        bsdf = SubElement(scene, "bsdf", {"type": "diffuse", "id": name})
        SubElement(bsdf, "rgb", {"name": "reflectance", "value": "0.5 0.5 0.5"})

        ply = mesh_dir / f"{name}.ply"
        _write_ply(ply, sub_pts, sub_tris)
        shape = SubElement(scene, "shape", {"type": "ply", "id": f"scan_{name}"})
        SubElement(shape, "string", {"name": "filename",
                                     "value": f"{mesh_dir.name}/{ply.name}"})
        SubElement(shape, "ref", {"id": name})
        written[name] = {"faces": int(len(sub_tris)), "vertices": int(len(sub_pts))}

    tree = ElementTree(scene)
    indent(tree, space="  ")
    tree.write(out_xml, encoding="utf-8", xml_declaration=True)

    lo = points.min(axis=0)
    hi = points.max(axis=0)
    stats = {
        "xml_path": str(out_xml),
        "mesh_dir": mesh_dir.name,
        "materials": written,
        "face_count": int(len(faces)),
        "holes_capped": capped,
        "bbox_min": [round(float(v), 3) for v in lo],
        "bbox_max": [round(float(v), 3) for v in hi],
    }
    out_xml.with_suffix(".stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return stats
