"""Overpass API 用戶端 — 依 bbox 抓 OpenStreetMap 建築資料(XML)。

取代手動去 openstreetmap.org Export;給定 4 座標即回傳該範圍 OSM XML。
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request

# 多鏡像輪替 —— Overpass 是免費公開服務,單一站點常忙碌/逾時。
# 2026-10-13 實測:osm.jp 憑證過期(永久失敗)已移除;private.coffee 有回應,補上。
# 主站忙碌時回 504、鏡像常要 13–40 秒才回,單站等待放寬到 60 秒。
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "XAPP_DT-mapgen/1.0 (RAN digital twin)"
PER_TRY_TIMEOUT_SEC = 60
# 總時間預算:必須小於前端 generateOsmMap 的 240 秒(services/api/geometry.ts),
# 否則後端還在重試、前端已逾時,使用者只看到「斷了」而拿不到錯誤原因。
TOTAL_BUDGET_SEC = 200
BACKOFF_SEC = 3.0   # 全部鏡像輪完一輪後退避


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
              timeout: int = PER_TRY_TIMEOUT_SEC, budget: float = TOTAL_BUDGET_SEC) -> bytes:
    """抓 bbox 內建築的 OSM XML。

    多鏡像輪替:單站失敗就換下一站,全部輪完退避後再輪,直到總時間預算用完。
    每次嘗試的等待不超過剩餘預算;全失敗才 raise(訊息列出各站失敗原因)。
    """
    q = _query(minlat, minlon, maxlat, maxlon)
    body = urllib.parse.urlencode({"data": q}).encode()
    errors: list[str] = []
    deadline = time.monotonic() + budget
    rnd = 0
    while True:
        for ep in ENDPOINTS:
            remaining = deadline - time.monotonic()
            if remaining < 5:
                break
            try:
                req = urllib.request.Request(
                    ep, data=body,
                    headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                )
                with urllib.request.urlopen(req, timeout=min(timeout, remaining)) as resp:
                    data = resp.read()
                if data and len(data) > 200:      # 太短多半是錯誤頁
                    return data
                errors.append(f"{ep.split('/')[2]}: 回應過短({len(data)}B)")
            except Exception as e:  # noqa: BLE001
                code = getattr(e, "code", None)
                errors.append(f"{ep.split('/')[2]}: {type(e).__name__}{f' {code}' if code else ''}")
        rnd += 1
        if deadline - time.monotonic() < 5 + BACKOFF_SEC:
            break
        time.sleep(BACKOFF_SEC)
    raise RuntimeError(
        f"Overpass 抓取失敗(已試 {len(ENDPOINTS)} 鏡像 × {rnd} 輪,{budget:.0f} 秒內):"
        + "; ".join(errors[-6:])
    )
