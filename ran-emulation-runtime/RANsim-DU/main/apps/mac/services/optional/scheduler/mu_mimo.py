"""MU-MIMO 配對(階段 D,2026-09-17)。

同一個 cell、不同波束的兩個 UE,如果彼此的波束漏到對方的量夠低,就讓它們在同一段 PRB 上同時傳。

干擾估計只用 RU 已經回報的東西:
    beam_top[u] = [(beam_id, 相對 u 最佳波束的 dB), …]   (RU gob.select 的前 K 名)
所以「v 的波束打到 u」相對「u 自己的波束打到 u」的功率比 = beam_top[u] 裡 v 的波束那一項;
不在前 K 名 → 保守取「前 K 名最弱那一項 − 3 dB」。

功率一分為二(兩個 UE 各拿 1/2),所以 u 的 MU SINR:
    1 / SINR_mu = 2 / SINR_su + 10^(leak_uv / 10)
SINR_su 已含失真上限,所以高 SINR 時 MU 也會被壓住,不會算出假的倍增。

配對規則(greedy,每次一對):
  - 兩者都有 beam_id 且不同、雙向洩漏 ≤ LEAK_MAX_DB
  - 配對後兩人各拿整段 PRB 的速率和,要比「不配、各分一半 PRB」好(否則不配)
  - 配到的 UE 本 tick 限單層(MU 下每 UE 1 層是常見設定)
"""
from __future__ import annotations

import math
from typing import Any

LEAK_MAX_DB = -10.0
_MISSING_MARGIN_DB = 3.0


def _lin(db: float) -> float:
    return 10.0 ** (db / 10.0)


def leakage_db(u: dict, beam_v: int) -> float | None:
    """v 的波束打到 u 的相對功率(dB,≤ 0)。u 沒有 beam_top 回 None。"""
    top = u.get("beam_top") or []
    if not top:
        return None
    rel = {int(b): float(d) for b, d in top}
    if int(beam_v) in rel:
        return rel[int(beam_v)]
    return min(rel.values()) - _MISSING_MARGIN_DB


def mu_sinr_db(sinr_su_db: float, leak_db: float) -> float:
    s = _lin(sinr_su_db)
    return 10.0 * math.log10(1.0 / (2.0 / max(s, 1e-12) + _lin(leak_db)))


def _rate(sinr_db: float) -> float:
    return math.log2(1.0 + _lin(sinr_db))


def pair(ues: list[dict[str, Any]], leak_max_db: float = LEAK_MAX_DB) -> tuple[list[tuple[dict, dict, float, float]], list[dict]]:
    """回傳 (pairs, singles)。pairs 每項 = (u, v, sinr_mu_u, sinr_mu_v)。

    依 buffer 由大到小逐一找搭檔;同一 UE 只配一次。
    """
    cand = sorted(ues, key=lambda x: -int(x.get("buffer_occupancy") or 0))
    used: set[str] = set()
    pairs = []
    for i, u in enumerate(cand):
        if u["id"] in used or u.get("beam_id") is None:
            continue
        best = None
        for v in cand[i + 1:]:
            if v["id"] in used or v.get("beam_id") is None or v["beam_id"] == u["beam_id"]:
                continue
            luv, lvu = leakage_db(u, v["beam_id"]), leakage_db(v, u["beam_id"])
            if luv is None or lvu is None or luv > leak_max_db or lvu > leak_max_db:
                continue
            su, sv = float(u["sinr_db"]), float(v["sinr_db"])
            mu, mv = mu_sinr_db(su, luv), mu_sinr_db(sv, lvu)
            gain = (_rate(mu) + _rate(mv)) - 0.5 * (_rate(su) + _rate(sv))
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, v, mu, mv)
        if best is not None:
            _, v, mu, mv = best
            used.update((u["id"], v["id"]))
            pairs.append((u, v, mu, mv))
    singles = [x for x in ues if x["id"] not in used]
    return pairs, singles


def virtual_ue(u: dict, v: dict, mu: float, mv: float) -> dict:
    """給既有 scheduler 用的「一組 MU」:一個 id、共同 PRB、buffer 取大者。"""
    return {**u, "id": f"mu:{u['id']}+{v['id']}", "sinr_db": (mu + mv) / 2.0,
            "buffer_occupancy": max(int(u.get("buffer_occupancy") or 0), int(v.get("buffer_occupancy") or 0))}
