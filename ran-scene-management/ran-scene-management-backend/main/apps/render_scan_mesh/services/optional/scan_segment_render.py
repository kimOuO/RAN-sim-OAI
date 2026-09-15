"""把面片沿法線正射投影成一張「拉正的照片」，供人或 VLM 判讀。

為什麼不能直接裁 UV atlas：atlas 的排版是 photogrammetry 工具任意切的，
同一面牆會散在好幾塊不相鄰的區域，裁出來的方框裡有 7 成是鄰居的像素
（實測平均只有 31% 屬於該面片），而且形狀是鋸齒團塊，看不出是窗還是海報。

這裡對面片自己的平面做正射投影並逐像素取樣貼圖，等於「站在這面牆正前方
拍一張照」。判讀窗框、門板分割線、公告欄邊界都需要這個視角。

沒有用 Kit/OpenGL：那要跨容器且非同步。純 numpy 的重心座標光柵化對
單一面片（數千個三角形）綽綽有餘，也讓這步保持確定性。
"""
from __future__ import annotations

import numpy as np

MM_PER_PIXEL_DEFAULT = 6.0     # 6 mm/px：2 m 的門約 330 px，看得到門板分割線
MAX_SIDE_PX = 900


def plane_basis(points: np.ndarray, normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """給定平面法線，取一組平面內的正交基。

    盡量讓第二軸朝上（世界 +Y），這樣輸出的照片是「直立」的 —— 門窗判讀
    很依賴上下關係，隨機取基會讓圖橫躺。
    """
    up = np.array([0.0, 1.0, 0.0])
    if abs(float(normal @ up)) > 0.95:      # 水平面：改用 +Z 當參考
        up = np.array([0.0, 0.0, 1.0])
    axis_u = np.cross(up, normal)
    axis_u /= max(np.linalg.norm(axis_u), 1e-12)
    axis_v = np.cross(normal, axis_u)
    axis_v /= max(np.linalg.norm(axis_v), 1e-12)
    if axis_v[1] < 0:                        # 讓 v 軸朝上
        axis_v = -axis_v
        axis_u = -axis_u
    return axis_u, axis_v


def render_segment(
    tri_world: np.ndarray,     # (n, 3, 3) 三角形頂點的世界座標
    tri_uv: np.ndarray,        # (n, 3, 2) 對應的 UV
    tri_image: np.ndarray,     # (n,) 每個三角形用哪張貼圖
    images: dict[int, np.ndarray],
    normal: np.ndarray,
    mm_per_px: float = MM_PER_PIXEL_DEFAULT,
) -> np.ndarray | None:
    """回傳正射投影後的 RGB 影像（未覆蓋處為深灰）。"""
    if not len(tri_world):
        return None
    axis_u, axis_v = plane_basis(tri_world.reshape(-1, 3).mean(axis=0) * 0 + normal, normal)
    origin = tri_world.reshape(-1, 3).mean(axis=0)
    rel = tri_world - origin
    pu = rel @ axis_u
    pv = rel @ axis_v

    scale = 1000.0 / mm_per_px          # px per metre
    w = int(np.ceil((pu.max() - pu.min()) * scale)) + 1
    h = int(np.ceil((pv.max() - pv.min()) * scale)) + 1
    if w < 8 or h < 8:
        return None
    if max(w, h) > MAX_SIDE_PX:          # 大牆面降解析度，避免產生巨圖
        scale *= MAX_SIDE_PX / max(w, h)
        w = int(np.ceil((pu.max() - pu.min()) * scale)) + 1
        h = int(np.ceil((pv.max() - pv.min()) * scale)) + 1

    xs = (pu - pu.min()) * scale
    ys = (pv.max() - pv) * scale         # 影像 y 往下，世界 v 往上 → 翻轉
    out = np.full((h, w, 3), 32, dtype=np.uint8)

    for i in range(len(tri_world)):
        img = images.get(int(tri_image[i]))
        if img is None:
            continue
        ih, iw = img.shape[:2]
        x = xs[i]
        y = ys[i]
        x0 = max(0, int(np.floor(x.min())))
        x1 = min(w - 1, int(np.ceil(x.max())))
        y0 = max(0, int(np.floor(y.min())))
        y1 = min(h - 1, int(np.ceil(y.max())))
        if x1 < x0 or y1 < y0:
            continue

        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        # 重心座標
        d = ((y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]))
        if abs(d) < 1e-9:
            continue
        l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        l2 = 1.0 - l0 - l1
        inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not inside.any():
            continue

        uv = tri_uv[i]
        u = l0 * uv[0, 0] + l1 * uv[1, 0] + l2 * uv[2, 0]
        v = l0 * uv[0, 1] + l1 * uv[1, 1] + l2 * uv[2, 1]
        px = np.clip((np.mod(u, 1.0) * iw).astype(np.int64), 0, iw - 1)
        py = np.clip((np.mod(v, 1.0) * ih).astype(np.int64), 0, ih - 1)
        out[gy[inside], gx[inside]] = img[py[inside], px[inside], :3]

    return out
