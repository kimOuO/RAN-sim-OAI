"""Overpass API 用戶端 — 依 bbox 抓 OpenStreetMap 建築資料(XML)。

取代手動去 openstreetmap.org Export;給定 4 座標即回傳該範圍 OSM XML。
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request

# 多鏡像輪替 —— Overpass 是免費公開服務,單一站點常忙碌/逾時。
# osm.jp 在日本(離台灣近),實測常比主站快;kumi 為常用備援。
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "XAPP_DT-mapgen/1.0 (RAN digital twin)"
ROUNDS = 2          # 全部鏡像輪完算一輪,最多兩輪
BACKOFF_SEC = 3.0   # 每輪之間退避


def _query(minlat: float, minlon: float, maxlat: float, maxlon: float) -> str:
    return f"""[out:xml][timeout:60];
(
  way["building"]({minlat},{minlon},{maxlat},{maxlon});
  way["building:part"]({minlat},{minlon},{maxlat},{maxlon});
  relation["building"]({minlat},{minlon},{maxlat},{maxlon});
  relation["type"="multipolygon"]["building"]({minlat},{minlon},{maxlat},{maxlon});
);
(._;>;);
out body;"""


def fetch_osm(minlat: float, minlon: float, maxlat: float, maxlon: float,
              timeout: int = 45) -> bytes:
    """抓 bbox 內建築的 OSM XML。

    多鏡像 × 多輪重試:單站逾時就快速換下一站(timeout 縮短為 45s,
    失敗成本低),全部輪完再退避重來一輪。全失敗才 raise。
    """
    q = _query(minlat, minlon, maxlat, maxlon)
    body = urllib.parse.urlencode({"data": q}).encode()
    errors: list[str] = []
    for rnd in range(ROUNDS):
        for ep in ENDPOINTS:
            try:
                req = urllib.request.Request(
                    ep, data=body,
                    headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                if data and len(data) > 200:      # 太短多半是錯誤頁
                    return data
                errors.append(f"{ep.split('/')[2]}: 回應過短({len(data)}B)")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{ep.split('/')[2]}: {type(e).__name__}")
        if rnd < ROUNDS - 1:
            time.sleep(BACKOFF_SEC)
    raise RuntimeError(
        "Overpass 抓取失敗(已試 "
        f"{len(ENDPOINTS)} 鏡像 × {ROUNDS} 輪):" + "; ".join(errors[-6:])
    )
