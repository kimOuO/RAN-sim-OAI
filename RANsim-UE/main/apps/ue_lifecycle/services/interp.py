"""Linear waypoint interpolation。

waypoint 格式: [{x, y, z, t_ms}, ...]   t_ms 從 0 開始, 遞增
"""
from __future__ import annotations

from typing import Any


def interp_position(
    waypoints: list[dict[str, Any]],
    elapsed_ms: int,
    mode: str = "loop",
) -> tuple[float, float, float]:
    """根據 elapsed_ms (距離 trajectory start 多少 ms) 線性內插出位置。

    mode:
      - "loop": 走完從頭重複
      - "once": 走完停在最後一點
      - "stay": 第一次跑完就停 (=once)

    回傳 (x, y, z)
    """
    if not waypoints:
        return (0.0, 0.0, 0.0)
    if len(waypoints) == 1:
        wp = waypoints[0]
        return (float(wp["x"]), float(wp["y"]), float(wp["z"]))

    total_ms = waypoints[-1].get("t_ms", 0)
    if total_ms <= 0:
        wp = waypoints[0]
        return (float(wp["x"]), float(wp["y"]), float(wp["z"]))

    # 處理 mode
    if elapsed_ms < 0:
        elapsed_ms = 0
    if elapsed_ms >= total_ms:
        if mode == "loop":
            elapsed_ms = elapsed_ms % total_ms
        else:  # once / stay
            wp = waypoints[-1]
            return (float(wp["x"]), float(wp["y"]), float(wp["z"]))

    # 找第一個 t_ms >= elapsed_ms 的 waypoint
    for i in range(1, len(waypoints)):
        wp_curr = waypoints[i]
        wp_prev = waypoints[i - 1]
        t_curr = wp_curr.get("t_ms", 0)
        t_prev = wp_prev.get("t_ms", 0)
        if elapsed_ms <= t_curr:
            if t_curr == t_prev:
                return (
                    float(wp_curr["x"]), float(wp_curr["y"]), float(wp_curr["z"]),
                )
            # 線性內插
            ratio = (elapsed_ms - t_prev) / (t_curr - t_prev)
            x = wp_prev["x"] + (wp_curr["x"] - wp_prev["x"]) * ratio
            y = wp_prev["y"] + (wp_curr["y"] - wp_prev["y"]) * ratio
            z = wp_prev["z"] + (wp_curr["z"] - wp_prev["z"]) * ratio
            return (float(x), float(y), float(z))

    wp = waypoints[-1]
    return (float(wp["x"]), float(wp["y"]), float(wp["z"]))
