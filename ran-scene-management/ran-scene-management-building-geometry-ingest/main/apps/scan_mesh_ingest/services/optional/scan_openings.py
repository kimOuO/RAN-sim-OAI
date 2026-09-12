"""把色彩碎片合併回「表面」，再在表面平面上找開口（門洞／窗）。

為什麼需要這一層：色彩分割能把門從牆上切出來（純度 4% → 69%），但**同時
也把牆本身沿光影邊界切碎了**。碎片「沒碰到地板」純粹是切割位置的偶然，
不是因為它們離地，所以 stands_on_floor / rectangularity 這些幾何先驗全部失效
（實測 61 個「離地矩形板」候選裡幾乎沒有窗戶，都是寬扁的牆面碎片）。

正確的層次是：
  1. 把**共面且相鄰**的碎片合併回一個表面（一面牆 = 它所有色彩碎片的聯集）
  2. 在表面自己的平面上做 2D 佔用柵格
  3. 開口 = 柵格內部的空洞

窗戶的真正幾何特徵不是「離地的矩形面片」，而是**牆平面上的一個開口**：
掃描時玻璃要嘛沒被重建（深度感測穿透）、要嘛內凹一段，兩種都會在牆平面上
留下洞。門洞同理，只是它從地板開始。這是結構性的線索，不依賴色彩。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

SURFACE_ANGLE_TOL_DEG = 15.0   # 兩個碎片視為共面的法線夾角上限
SURFACE_OFFSET_TOL_M = 0.20    # 兩個碎片視為共面的平面偏移上限
GRID_CELL_M = 0.05             # 表面上的佔用柵格解析度
MIN_SURFACE_AREA_M2 = 3.0      # 小於此面積的表面不值得找開口
MIN_OPENING_AREA_M2 = 0.3      # 小於此面積的洞視為掃描雜訊
# 閉運算半徑（格）。表面邊界是鋸齒狀的，不先把細縫封起來，任何洞都會從
# 邊界缺口漏到外面，灌水法會判定「沒有洞」（實測封之前找到 0 個開口）。
CLOSING_RADIUS_CELLS = 4


def _segment_planes(points, faces, seg, n_segments):
    """每個 segment 的面積加權法線、重心與面積。"""
    v = points[faces]
    cross = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    area = np.linalg.norm(cross, axis=1) / 2.0
    normal = cross / np.maximum(np.linalg.norm(cross, axis=1, keepdims=True), 1e-12)
    centroid = v.mean(axis=1)

    planes = []
    for sid in range(n_segments):
        m = seg == sid
        if not m.any():
            planes.append(None)
            continue
        w = area[m]
        n = normal[m]
        ref = n[np.argmax(w)]
        n = n * np.sign(n @ ref)[:, None]          # 統一朝向再平均
        nn = (n * w[:, None]).sum(axis=0)
        nn /= max(np.linalg.norm(nn), 1e-12)
        c = (centroid[m] * w[:, None]).sum(axis=0) / w.sum()
        planes.append({"n": nn, "c": c, "area": float(w.sum())})
    return planes, area


def merge_into_surfaces(
    points: np.ndarray,
    faces: np.ndarray,
    seg: np.ndarray,
    seg_neighbours: dict[int, list[int]],
    *,
    angle_tol_deg: float = SURFACE_ANGLE_TOL_DEG,
    offset_tol_m: float = SURFACE_OFFSET_TOL_M,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """相鄰且共面的 segment 併成同一個 surface。回傳逐面 surface id 與統計。"""
    n_seg = int(seg.max()) + 1
    planes, area = _segment_planes(points, faces, seg, n_seg)
    cos_tol = np.cos(np.radians(angle_tol_deg))

    parent = list(range(n_seg))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, nbs in seg_neighbours.items():
        pa = planes[a]
        if pa is None:
            continue
        for b in nbs:
            if b <= a:
                continue
            pb = planes[b]
            if pb is None:
                continue
            if abs(float(pa["n"] @ pb["n"])) < cos_tol:
                continue
            # 用兩邊的法線各量一次偏移，取大的：薄板的兩面法線相反但共面，
            # 只量一邊會把「牆的正反兩面」誤併
            off = max(abs(float((pb["c"] - pa["c"]) @ pa["n"])),
                      abs(float((pa["c"] - pb["c"]) @ pb["n"])))
            if off > offset_tol_m:
                continue
            union(a, b)

    roots = {}
    surface_of_seg = np.zeros(n_seg, dtype=np.int64)
    for s in range(n_seg):
        r = find(s)
        if r not in roots:
            roots[r] = len(roots)
        surface_of_seg[s] = roots[r]

    surface_of_face = surface_of_seg[seg]
    surfaces = []
    for sid in range(len(roots)):
        members = [s for s in range(n_seg) if surface_of_seg[s] == sid]
        m = surface_of_face == sid
        if not m.any():
            continue
        w = area[m]
        v = points[faces[m]]
        cross = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        nrm = cross / np.maximum(np.linalg.norm(cross, axis=1, keepdims=True), 1e-12)
        ref = nrm[np.argmax(w)]
        nrm = nrm * np.sign(nrm @ ref)[:, None]
        nn = (nrm * w[:, None]).sum(axis=0)
        nn /= max(np.linalg.norm(nn), 1e-12)
        surfaces.append({
            "id": sid,
            "segments": members,
            "area_m2": float(w.sum()),
            "normal": nn,
            "centroid": v.reshape(-1, 3).mean(axis=0),
            "tilt_deg": float(np.degrees(np.arcsin(min(1.0, abs(nn[1]))))),
        })
    return surface_of_face, surfaces


def _binary_closing(mask: np.ndarray, r: int) -> np.ndarray:
    """方形結構元素的閉運算（先膨脹再侵蝕），用位移疊加實作，不引入 scipy。"""
    if r <= 0:
        return mask

    def shift_or(m):
        out = m.copy()
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                sh = np.zeros_like(m)
                si = slice(max(0, di), m.shape[0] + min(0, di))
                ti = slice(max(0, -di), m.shape[0] + min(0, -di))
                sj = slice(max(0, dj), m.shape[1] + min(0, dj))
                tj = slice(max(0, -dj), m.shape[1] + min(0, -dj))
                sh[ti, tj] = m[si, sj]
                out |= sh
        return out

    return ~shift_or(~shift_or(mask))


def find_openings(
    points: np.ndarray,
    faces: np.ndarray,
    surface_of_face: np.ndarray,
    surface: dict[str, Any],
    floor_y: float,
    *,
    cell_m: float = GRID_CELL_M,
    min_area_m2: float = MIN_OPENING_AREA_M2,
    closing_radius: int = CLOSING_RADIUS_CELLS,
) -> list[dict[str, Any]]:
    """在一個表面的平面上找「被幾何包圍的空洞」。

    空洞就是牆上該有東西卻沒有的地方 —— 窗（玻璃沒被重建或內凹）、門洞、
    或掃描死角。回傳每個洞的尺寸與離地高度，讓上層規則判它是什麼。
    """
    from main.apps.scan_mesh_ingest.services.optional.scan_segment_render import plane_basis

    m = surface_of_face == surface["id"]
    if not m.any():
        return []
    n = surface["normal"]
    axis_u, axis_v = plane_basis(np.zeros(3), n)
    tri = points[faces[m]]
    origin = tri.reshape(-1, 3).mean(axis=0)
    rel = tri - origin
    pu = rel @ axis_u
    pv = rel @ axis_v

    umin, umax = float(pu.min()), float(pu.max())
    vmin, vmax = float(pv.min()), float(pv.max())
    nu = int(np.ceil((umax - umin) / cell_m)) + 3
    nv = int(np.ceil((vmax - vmin) / cell_m)) + 3
    if nu < 6 or nv < 6 or nu * nv > 4_000_000:
        return []

    occ = np.zeros((nv, nu), dtype=bool)
    iu = np.clip(((pu - umin) / cell_m + 1).astype(np.int64), 0, nu - 1)
    iv = np.clip(((pv - vmin) / cell_m + 1).astype(np.int64), 0, nv - 1)
    # 以三角形的外接框填格：三角形邊長約 17 cm、格子 5 cm，逐點填會留下縫隙
    for k in range(len(iu)):
        occ[iv[k].min():iv[k].max() + 1, iu[k].min():iu[k].max() + 1] = True

    occ = _binary_closing(occ, closing_radius)
    # 空洞 = 空格中「連不到影像邊界」的連通塊
    free = ~occ
    nvv, nuu = free.shape
    seen = np.zeros_like(free)
    stack = []
    for i in range(nuu):
        for j in (0, nvv - 1):
            if free[j, i] and not seen[j, i]:
                seen[j, i] = True
                stack.append((j, i))
    for j in range(nvv):
        for i in (0, nuu - 1):
            if free[j, i] and not seen[j, i]:
                seen[j, i] = True
                stack.append((j, i))
    while stack:                                  # 從外框往內灌水 → 標記「外部」
        j, i = stack.pop()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = j + dj, i + di
            if 0 <= a < nvv and 0 <= b < nuu and free[a, b] and not seen[a, b]:
                seen[a, b] = True
                stack.append((a, b))

    holes = free & ~seen
    out: list[dict[str, Any]] = []
    visited = np.zeros_like(holes)
    for j in range(nvv):
        for i in range(nuu):
            if not holes[j, i] or visited[j, i]:
                continue
            comp = []
            st = [(j, i)]
            visited[j, i] = True
            while st:
                a, b = st.pop()
                comp.append((a, b))
                for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    c, d = a + dj, b + di
                    if 0 <= c < nvv and 0 <= d < nuu and holes[c, d] and not visited[c, d]:
                        visited[c, d] = True
                        st.append((c, d))
            a_m2 = len(comp) * cell_m * cell_m
            if a_m2 < min_area_m2:
                continue
            arr = np.array(comp)
            v_idx = arr[:, 0]
            u_idx = arr[:, 1]
            w_m = (u_idx.max() - u_idx.min() + 1) * cell_m
            h_m = (v_idx.max() - v_idx.min() + 1) * cell_m
            # 洞的中心換回世界座標，才能算離地高度
            cu = umin + (u_idx.mean() - 1) * cell_m
            cv = vmin + (v_idx.mean() - 1) * cell_m
            centre = origin + axis_u * cu + axis_v * cv
            ylo = origin[1] + axis_v[1] * (vmin + (v_idx.min() - 1) * cell_m) - floor_y
            yhi = origin[1] + axis_v[1] * (vmin + (v_idx.max() - 1) * cell_m) - floor_y
            out.append({
                "surface_id": surface["id"],
                "area_m2": round(a_m2, 2),
                "size_m": [round(w_m, 2), round(h_m, 2)],
                "fill_ratio": round(a_m2 / max(w_m * h_m, 1e-6), 2),
                "centre": [round(float(x), 2) for x in centre],
                "y_above_floor_m": [round(float(min(ylo, yhi)), 2), round(float(max(ylo, yhi)), 2)],
            })
    return out
