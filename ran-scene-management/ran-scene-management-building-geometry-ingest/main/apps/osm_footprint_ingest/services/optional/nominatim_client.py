"""Nominatim 地理編碼用戶端 — 地標名稱 → 座標 + 建議 bbox。

openstreetmap.org 搜尋框背後的同一服務。給 MapController.geocode 用:
使用者在前端輸入「台北101」「中正紀念堂」等地名,回傳候選地點與
「適合做場景的 bbox」(Nominatim 原始 bbox 常太小〔單棟建築〕或
太大〔整個行政區〕,這裡正規化到 min~max 範圍)。

使用政策:需帶 User-Agent,≤1 req/s(前端單次搜尋,遠低於限制)。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "XAPP_DT-mapgen/1.0 (RAN digital twin)"

# 場景 bbox 正規化參數(度)
MIN_SPAN_LAT = 0.0045   # ~500 m
MIN_SPAN_LON = 0.0050   # ~500 m(台灣緯度)
MAX_SPAN = 0.028        # 略低於 MapController 的 0.03 防呆上限
MARGIN = 1.10           # 對原始 bbox 外擴 10%


def _suggest_bbox(lat: float, lon: float, raw_bbox: list[str] | None) -> dict[str, float]:
    """把 Nominatim bbox 正規化成適合做場景的範圍(以中心點擴展/裁切)。"""
    if raw_bbox and len(raw_bbox) == 4:
        south, north, west, east = (float(v) for v in raw_bbox)
        span_lat = (north - south) * MARGIN
        span_lon = (east - west) * MARGIN
    else:
        span_lat = span_lon = 0.0

    span_lat = min(max(span_lat, MIN_SPAN_LAT), MAX_SPAN)
    span_lon = min(max(span_lon, MIN_SPAN_LON), MAX_SPAN)

    return {
        "min_lon": round(lon - span_lon / 2, 6),
        "min_lat": round(lat - span_lat / 2, 6),
        "max_lon": round(lon + span_lon / 2, 6),
        "max_lat": round(lat + span_lat / 2, 6),
    }


def geocode(query: str, limit: int = 5, timeout: int = 15) -> list[dict]:
    """地名 → 候選地點列表(含建議 bbox)。查不到回空 list。"""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": max(1, min(int(limit), 10)),
        "accept-language": "zh-TW,en",
    })
    req = urllib.request.Request(
        f"{ENDPOINT}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        rows = json.loads(resp.read())

    out: list[dict] = []
    for r in rows:
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "display_name": r.get("display_name", ""),
            "name": r.get("name") or (r.get("display_name", "").split(",")[0]),
            "type": f"{r.get('category', '')}/{r.get('type', '')}",
            "lat": lat,
            "lon": lon,
            "bbox": _suggest_bbox(lat, lon, r.get("boundingbox")),
        })
    return out
