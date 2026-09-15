"""把掃描網格切成「共面面片」，作為材質判斷的基本單位。

為什麼需要這一層：逐三角形分類會把 4096² 的貼圖壓成每面一個 RGB，用掉的
證據不到 0.15%，而分辨窗戶與白牆的線索（窗框、矩形邊界、是否嵌在牆內）
全活在空間結構裡。把 9 萬個三角形聚成幾百個面片之後：

  - 規則可以問「這個面片是不是矩形、是不是嵌在牆平面內、有沒有成排」
  - VLM 只需要判規則說不知道的十幾個面片，而不是 9 萬個面
  - 人工標註驗證集時，標的也是面片

做法是平面區域成長：從面積最大的未訪面出發，把「法線夾角夠小 + 到目前
擬合平面的距離夠近」的鄰接面併進來，邊長邊更新擬合平面。門、窗、牆、
地板天花會各自聚成獨立面片。

座標與面的順序**與 scan_material_classifier 完全一致**（都從同一份 GLB
以相同順序展開），所以 segment id 可以直接對上 .materials.npz 的逐面標籤。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

# 區域成長門檻
# 容差是對「掃描表面很皺」調出來的：12°/0.06 m 會把一面牆切成上百塊
# （實測 1498 個面片、817 個小於 0.5 m²），VLM 那層就沒有意義了。
ANGLE_TOL_DEG = 22.0      # 法線與擬合平面的夾角上限
DIST_TOL_M = 0.12         # 面心到擬合平面的距離上限
MIN_SEGMENT_AREA_M2 = 1.0   # 小於此面積的面片併回鄰居，避免碎片爆量

# 色彩相似度門檻（RGB 0..1 的歐氏距離）。
# 純幾何分不開門與牆 —— 它們共面，而門的內凹深度遠小於掃描雜訊（實測只有
# 4% 的木頭面積落在「純度 > 50%」的面片裡，門全被吸進牆的面片）。
# 這裡用色彩做**分割**而非**分類**：門看起來和牆不同就會自己成一片，
# 之後由幾何規則判它是什麼。這與「用色彩判玻璃」是兩件事。
COLOR_TOL = 0.18


def _weld(points: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """回傳焊接後的面索引（1 mm 容差）。

    GLB 的 chunk 之間頂點不共用，不焊就找不到跨 chunk 的鄰接，
    一面牆會被切成 15 塊。
    """
    key = np.round(points * 1000).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv[faces]


def build_adjacency(welded: np.ndarray) -> list[list[int]]:
    """共用邊 → 鄰接表。"""
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for fi, t in enumerate(welded):
        for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edge_faces[(min(e), max(e))].append(fi)
    adj: list[list[int]] = [[] for _ in range(len(welded))]
    for group in edge_faces.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                adj[group[i]].append(group[j])
                adj[group[j]].append(group[i])
    return adj


def segment_planar(
    points: np.ndarray,
    faces: np.ndarray,
    *,
    rgb: np.ndarray | None = None,
    angle_tol_deg: float = ANGLE_TOL_DEG,
    dist_tol_m: float = DIST_TOL_M,
    color_tol: float = COLOR_TOL,
    min_area_m2: float = MIN_SEGMENT_AREA_M2,
) -> dict[str, Any]:
    """平面區域成長。回傳每個面的 segment id（-1 = 未分配）與各面片的統計。"""
    welded = _weld(points, faces)
    adj = build_adjacency(welded)

    v0, v1, v2 = points[faces[:, 0]], points[faces[:, 1]], points[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    area = np.linalg.norm(cross, axis=1) / 2.0
    normal = cross / np.maximum(np.linalg.norm(cross, axis=1, keepdims=True), 1e-12)
    centroid = (v0 + v1 + v2) / 3.0

    use_color = rgb is not None and not np.isnan(rgb).all()
    if use_color:
        rgb = np.nan_to_num(np.asarray(rgb, dtype=np.float64), nan=0.5)
    cos_tol = np.cos(np.radians(angle_tol_deg))
    seg = np.full(len(faces), -1, dtype=np.int64)
    order = np.argsort(-area)          # 從大面開始長，讓大牆先佔住
    segments: list[dict[str, Any]] = []

    for seed in order:
        if seg[seed] >= 0:
            continue
        sid = len(segments)
        # 擬合平面用「面積加權的法線與重心」增量更新：比每步重跑 SVD 便宜，
        # 對掃描這種近平面但有起伏的資料也夠穩
        acc_n = normal[seed] * area[seed]
        acc_c = centroid[seed] * area[seed]
        acc_a = area[seed]
        acc_rgb = (rgb[seed] * area[seed]) if use_color else None
        members = [int(seed)]
        seg[seed] = sid
        stack = [int(seed)]

        while stack:
            cur = stack.pop()
            plane_n = acc_n / max(np.linalg.norm(acc_n), 1e-12)
            plane_c = acc_c / acc_a
            mean_rgb = (acc_rgb / acc_a) if use_color else None
            for nb in adj[cur]:
                if seg[nb] >= 0:
                    continue
                if abs(float(normal[nb] @ plane_n)) < cos_tol:
                    continue
                if abs(float((centroid[nb] - plane_c) @ plane_n)) > dist_tol_m:
                    continue
                if use_color and float(np.linalg.norm(rgb[nb] - mean_rgb)) > color_tol:
                    continue
                seg[nb] = sid
                members.append(nb)
                stack.append(nb)
                acc_n = acc_n + normal[nb] * area[nb] * np.sign(float(normal[nb] @ plane_n))
                acc_c = acc_c + centroid[nb] * area[nb]
                acc_a += area[nb]
                if use_color:
                    acc_rgb = acc_rgb + rgb[nb] * area[nb]

        segments.append({"id": sid, "faces": members, "area": float(area[members].sum())})

    # 小碎片併回「接觸面積最大的鄰居面片」——掃描邊緣與轉角會產生大量單面碎片，
    # 留著會讓面片數爆到上千，VLM 那層就沒有意義了。
    #
    # 要**反覆**做直到收斂：一輪只併掉當下最小的那些，被併走的面片會改變
    # 其他碎片的鄰居結構，單輪處理會留下一批「鄰居剛好也被併掉」的孤兒。
    merged = 0
    for _round in range(12):
        changed = 0
        for s in sorted(segments, key=lambda x: x["area"]):
            if s["area"] >= min_area_m2 or not s["faces"]:
                continue
            # 合併時以「接觸面積 x 色彩相近度」計分：純看接觸面積的話，
            # 剛從牆上切出來的小塊門板會立刻被大面積的牆吃回去
            score: dict[int, float] = defaultdict(float)
            contact_area: dict[int, float] = defaultdict(float)
            my_rgb = (rgb[s["faces"]].mean(axis=0) if use_color else None)
            for f in s["faces"]:
                for nb in adj[f]:
                    t = int(seg[nb])
                    if t == s["id"] or t < 0:
                        continue
                    contact = float(area[nb])
                    weight = contact
                    if use_color:
                        dc = float(np.linalg.norm(rgb[nb] - my_rgb))
                        weight = contact * max(0.0, 1.0 - dc / max(color_tol, 1e-6))
                    score[t] += weight
                    contact_area[t] += contact
            positive = {k: v for k, v in score.items() if v > 0}
            if positive:
                target = max(positive, key=positive.get)
            elif contact_area:
                # 所有鄰居的顏色都不像 —— 仍然要併掉，否則色彩分割產生的碎片
                # 會全部留下來（實測面片數從 278 爆到 2473，總面積對不上）。
                # 這種孤立小塊多半是污漬、貼紙、光斑，併進接觸最多的鄰居即可。
                target = max(contact_area, key=contact_area.get)
            else:
                continue
            for f in s["faces"]:
                seg[f] = target
            segments[target]["faces"].extend(s["faces"])
            segments[target]["area"] += s["area"]
            s["faces"] = []
            s["area"] = 0.0
            merged += 1
            changed += 1
        if not changed:
            break

    kept = [s for s in segments if s["faces"]]
    remap = {s["id"]: i for i, s in enumerate(kept)}
    seg = np.array([remap.get(int(x), -1) for x in seg], dtype=np.int64)
    for i, s in enumerate(kept):
        s["id"] = i

    return {
        "segment_of_face": seg,
        "segments": kept,
        "area": area,
        "normal": normal,
        "centroid": centroid,
        "adjacency": adj,
        "stats": {
            "face_count": int(len(faces)),
            "segment_count": len(kept),
            "merged_fragments": merged,
            "angle_tol_deg": angle_tol_deg,
            "dist_tol_m": dist_tol_m,
            "color_tol": color_tol if use_color else None,
            "min_area_m2": min_area_m2,
        },
    }


def segment_features(
    points: np.ndarray,
    result: dict[str, Any],
    floor_y: float,
) -> list[dict[str, Any]]:
    """每個面片的幾何證據表。

    這些欄位是給規則層與 VLM 層判讀用的，刻意都是「人看得懂、講得出理由」
    的量：門是站在地板上的高瘦矩形、窗是離地一段的矩形、牆是很大的一片。
    """
    seg = result["segment_of_face"]
    area = result["area"]
    normal = result["normal"]
    adj = result["adjacency"]
    faces_idx = result["_faces"]

    out: list[dict[str, Any]] = []
    for s in result["segments"]:
        fs = np.asarray(s["faces"], dtype=np.int64)
        pts = points[faces_idx[fs]].reshape(-1, 3)
        w = area[fs]
        n = normal[fs] * np.sign(normal[fs] @ (normal[fs][np.argmax(w)]))[:, None]
        plane_n = n.T @ w
        plane_n = plane_n / max(np.linalg.norm(plane_n), 1e-12)

        tilt = float(np.degrees(np.arcsin(min(1.0, abs(plane_n[1])))))
        ctr = pts.mean(axis=0)
        X = pts - ctr
        # 平面內的兩個主方向 → 面片的長寬
        _u, _sv, vt = np.linalg.svd(X[np.random.default_rng(0).choice(
            len(X), size=min(len(X), 4000), replace=False)], full_matrices=False)
        a = X @ vt[0]
        b = X @ vt[1]
        width = float(a.max() - a.min())
        height_extent = float(b.max() - b.min())
        # 矩形度：邊界點落在外接矩形邊上的比例
        ea = np.minimum(a - a.min(), a.max() - a)
        eb = np.minimum(b - b.min(), b.max() - b)
        tol = 0.12 * max(width, height_extent, 1e-6)
        rect = float(np.mean((ea < tol) | (eb < tol)))

        ylo = float(pts[:, 1].min() - floor_y)
        yhi = float(pts[:, 1].max() - floor_y)

        neigh = set()
        for f in fs:
            for nb in adj[f]:
                if seg[nb] != s["id"] and seg[nb] >= 0:
                    neigh.add(int(seg[nb]))

        out.append({
            "id": s["id"],
            "faces": int(len(fs)),
            "area_m2": round(float(s["area"]), 3),
            "tilt_deg": round(tilt, 1),
            "orientation": "horizontal" if tilt > 60 else ("vertical" if tilt < 30 else "slanted"),
            "normal": [round(float(x), 3) for x in plane_n],
            "centre": [round(float(x), 2) for x in ctr],
            "size_in_plane_m": [round(width, 2), round(height_extent, 2)],
            "aspect_ratio": round(max(width, height_extent) / max(min(width, height_extent), 1e-6), 2),
            "rectangularity": round(rect, 2),
            "y_above_floor_m": [round(ylo, 2), round(yhi, 2)],
            "stands_on_floor": bool(ylo < 0.15),
            "neighbours": sorted(neigh),
        })
    return out


def segment_from_npz(npz_path: str | Path, **kw) -> dict[str, Any]:
    """從 classifier 落地的 .npz 讀幾何做分割（面順序與標籤一致）。"""
    from main.apps.render_scan_mesh.services.optional.glb_reader import estimate_floor_y

    data = np.load(Path(npz_path), allow_pickle=False)
    points = data["points"].astype(np.float64)
    faces = data["faces"].astype(np.int64)
    rgb = data["rgb"].astype(np.float64) if "rgb" in data.files else None
    res = segment_planar(points, faces, rgb=rgb, **kw)
    res["_faces"] = faces
    floor_y = estimate_floor_y(points, faces)
    res["features"] = segment_features(points, res, floor_y)
    res["stats"]["floor_y"] = round(float(floor_y), 3)
    return res


def record_segments(npz_path: str | Path, out_json: str | Path | None = None, **kw) -> dict[str, Any]:
    """分割並落地：{stem}.segments.json（證據表）+ .segments.npy（逐面 segment id）。"""
    npz_path = Path(npz_path)
    res = segment_from_npz(npz_path, **kw)
    base = npz_path.with_suffix("")            # 去掉 .npz
    base = base.with_suffix("")                # 去掉 .materials
    np.save(base.with_suffix(".segments.npy"), res["segment_of_face"])
    payload = {"stats": res["stats"], "segments": res["features"]}
    path = Path(out_json) if out_json else base.with_suffix(".segments.json")
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"json": str(path), "npy": str(base.with_suffix(".segments.npy")), **res["stats"]}
