"""把 registry 的場景樹翻成外部 Agent 要的「場域配置」(介面 I-2)。

對方拿這份配置做兩件事,兩件都對識別很敏感:
  1. 當分析基準 —— 鄰區關係、cell 座標與功率是問題判定的依據
  2. **依此部署 xApp 到 RIC** —— E2 訂閱與 RICcontrolRequest 都用 meid + NCI 定位

所以 cell 識別必須跟 RIC 端看到的完全一致,而且要在模擬啟動前就算得出來。
這靠場景的 `e2_block`:區塊釘住 → 每個 gNB 的 gNB ID 固定 → cell 標籤固定 → NCI 固定
(推導在同目錄的 e2_identity,呼叫的是執行期同一份 ran_sim_protocol.run_topology)。
場景沒釘區塊時 E2 識別欄位一律回 None 並列進 unavailable_fields —— 寧可明講沒有,
也不要給一個啟動後會變的值讓 xApp 訂閱失敗。

缺項一律 None 並列進 unavailable_fields,不用 0 或空字串頂替(0 是有效觀測值)。
"""
from __future__ import annotations

import hashlib
from typing import Any

from main.apps.agent_api.services.optional.e2_identity import cells_by_name, field_e2_identities

# 收集參數。PM 視窗秒數與 DU 的 PM_WINDOW_SEC 同源(預設 1.0 秒)。
# 2026-09-22:I-5 觀測統一由 RIC 閘道提供,視窗與基準規則以 RIC 的 preproc 為準:
# 60 s 一窗;基準最快在第 10 個視窗才有(前 3 窗判不出期望報告數,之後累積 6 個合格窗)。
# 以前寫 1 s / 6 窗是照我方 KPM 樣本節奏,對方拿去算最短長度會少一個數量級。
GRANULARITY_PERIOD_SEC = 60.0
TIMEZONE = "Asia/Taipei"
# 對方計算各時段常態基準所需的最少無事件窗數(規格 I-2 collection)。
BASELINE_WINDOWS_REQUIRED = 10
COORDINATE_CONVENTION = "x 向右、z 向前、y 向上,單位公尺,原點為場域基準點"


def _cfg_version(tree: dict) -> str:
    """配置版本:拿會影響分析的欄位算短雜湊,配置一改就換版號。

    用 updated_at 當版號不行 —— 場景本身沒動、底下的 cell 改了功率,scene_updated_at
    不會變,但配置實際上已經不同了。
    """
    parts: list[str] = [str((tree.get("scene") or {}).get("scene_updated_at") or "")]
    for g in tree.get("gnbs") or []:
        parts.append(f"{g.get('name')}|{g.get('position')}|{g.get('gnb_updated_at')}")
        for du in g.get("dus") or []:
            for c in du.get("cells") or []:
                parts.append(f"{c.get('name')}|{c.get('pci')}|{c.get('arfcn')}|{c.get('power_dbm')}"
                             f"|{c.get('azimuth_deg')}|{c.get('tilt_deg')}|{c.get('cell_updated_at')}")
    for n in tree.get("neighbor_seeds") or []:
        parts.append(f"{n.get('source_cell')}>{n.get('target_cell')}|{n.get('neighbor_seed_updated_at')}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def _cells_of(tree: dict) -> list[tuple[dict, dict]]:
    """攤平成 [(gnb, cell), ...],保留 gNB 歸屬 —— 觀測資料要依 gnb_id 分組。"""
    out: list[tuple[dict, dict]] = []
    for g in tree.get("gnbs") or []:
        for du in g.get("dus") or []:
            for c in du.get("cells") or []:
                out.append((g, c))
    return out


def _position(gnb: dict, cell: dict) -> dict | None:
    """cell 的 position 是選配覆寫(DAS / multi-TRP 用),沒給就繼承 gNB 的。

    registry 存 [x, y, z] 且 y 是高度;對方要 {x, z, h}。
    """
    pos = cell.get("position") or gnb.get("position")
    if not pos or len(pos) < 3:
        return None
    return {"x": round(float(pos[0]), 3), "z": round(float(pos[2]), 3), "h": round(float(pos[1]), 3)}


def _antenna(cell: dict) -> dict:
    """天線。沒指定 preset 時 Physics 端預設是 1×1 tr38901(有元件方向性、無陣列增益)。"""
    ru = cell.get("ru") or {}
    preset = ru.get("antenna_preset") or {}
    return {
        "azimuth_deg": float(cell.get("azimuth_deg") or 0.0),
        "tilt_deg": float(cell.get("tilt_deg") or 0.0),
        "type": str(preset.get("pattern") or "tr38901"),
        "rows": int(preset.get("rows") or 1),
        "cols": int(preset.get("cols") or 1),
    }


def _relations(tree: dict, ncgi_of: dict[str, str | None], pci_of: dict[str, int],
               arfcn_of: dict[str, int]) -> list[dict]:
    """registry 的 NeighborSeed → 對方的 neighbour_relations(單向)。

    NeighborSeed 存的是「禁止旗標」,對方要的是「允許旗標」,所以三個布林都要反過來。
    注意這是**宣告值**:執行期 ANR 自主建立的關係不在這裡,那些要從 I-5 的當下觀測看。
    兩者相比就是「ANR 新增或缺漏了什麼」—— 正是對方要判的東西。
    """
    out = []
    for n in tree.get("neighbor_seeds") or []:
        src, tgt = str(n.get("source_cell") or ""), str(n.get("target_cell") or "")
        if not src or not tgt:
            continue
        out.append({
            "source_ncgi": ncgi_of.get(src), "source_cell_id": src,
            "target_ncgi": ncgi_of.get(tgt), "target_cell_id": tgt,
            "target_pci": pci_of.get(tgt), "target_arfcn": arfcn_of.get(tgt),
            "xn_x2_established": not bool(n.get("xn_blocklist")),
            "is_ho_allowed": not bool(n.get("ho_blocklist")),
            "is_remove_allowed": not bool(n.get("no_remove")),
            "ho_validated": None,     # 只有執行期 CU 的 NrCellRelation 才知道
            "created_at": n.get("neighbor_seed_created_at"),
            "updated_at": n.get("neighbor_seed_updated_at"),
        })
    return out


def _xn_links(relations: list[dict], gnb_of_cell: dict[str, str]) -> list[dict]:
    """由鄰區關係的 xn_x2_established 依 gNB 配對導出。"""
    seen: dict[tuple[str, str], bool] = {}
    for r in relations:
        a, b = gnb_of_cell.get(r["source_cell_id"] or ""), gnb_of_cell.get(r["target_cell_id"] or "")
        if not a or not b or a == b:
            continue
        key = (a, b) if a < b else (b, a)
        seen[key] = seen.get(key, False) or bool(r["xn_x2_established"])
    return [{"gnb_a": a, "gnb_b": b, "established": ok, "since": None} for (a, b), ok in sorted(seen.items())]


def build(tree: dict, bounds: dict | None = None) -> dict:
    """組出 I-2 的回應。tree = registry read_full_tree,bounds = 幾何範圍(可為 None)。"""
    scene = tree.get("scene") or {}
    pairs = _cells_of(tree)
    block = scene.get("e2_block")
    unavailable: list[str] = []

    # E2 識別:只有釘了區塊才算得出來,否則啟動後才確定 —— 那對 xApp 沒用,寧可回 None
    ident_by_name: dict[str, dict] = {}
    e2: list[dict[str, Any]] | None = None
    if block:
        e2 = field_e2_identities(tree, int(block))
        ident_by_name = cells_by_name(e2)
    else:
        unavailable += ["cells[].ncgi", "cells[].ran_name", "e2_identities"]

    ncgi_of = {(c.get("name") or ""): (ident_by_name.get(c.get("name") or "") or {}).get("ncgi") for _g, c in pairs}
    pci_of = {(c.get("name") or ""): int(c.get("pci") or 0) for _g, c in pairs}
    arfcn_of = {(c.get("name") or ""): int(c.get("arfcn") or 0) for _g, c in pairs}
    gnb_of_cell = {(c.get("name") or ""): (g.get("name") or "") for g, c in pairs}

    cells = []
    for g, c in pairs:
        name = c.get("name") or ""
        ident = ident_by_name.get(name) or {}
        pos = _position(g, c)
        if pos is None:
            unavailable.append(f"cells[{name}].position")
        cells.append({
            "cell_id": name,
            "ncgi": ident.get("ncgi"),
            "nr_cell_identity": ident.get("nr_cell_identity"),
            "ran_cell_id": ident.get("cell_id"),          # 執行期的 cell 識別(帶所屬 gNB 前綴)
            "ran_name": ident.get("ran_name"),             # 所屬 E2 node(多 gNB:每個 gNB 一個)
            "gnb_id": g.get("name") or "",
            "pci": pci_of[name],
            "arfcn": arfcn_of[name],
            "band": c.get("band"),
            "center_frequency_ghz": c.get("center_frequency_ghz"),
            "bandwidth_mhz": c.get("bandwidth_mhz"),
            "tx_power_dbm": c.get("power_dbm"),
            "position": pos,
            "antenna": _antenna(c),
            # is_active/is_barred 是我們僅有的兩個狀態旗標,對映到 3GPP 的兩個 state。
            "administrative_state": "unlocked" if c.get("is_active") else "locked",
            # 2026-09-22:is_active=False 也要算 disabled。被鎖住的 cell 不可能在運作,
            # 只看 is_barred 會讓場域預留的備用 cell(cell_addition 的目標)看起來像正常服務中。
            "operational_state": ("disabled" if (c.get("is_barred") or not c.get("is_active"))
                                  else "enabled"),
            # 這是**場域基準配置**的節能狀態,註冊表沒有這個旗標,所以恆為 notEnergySaving。
            # 模擬中的節能狀態會變(I-3 的 energy_saving_state 事件),但那屬於執行期,
            # 要看 I-7 的組態變更紀錄,不是這裡。
            "energy_saving_state": "notEnergySaving",
            "ric_managed": True,
            "noise_figure_db": (c.get("ru") or {}).get("noise_figure_db"),
        })

    relations = _relations(tree, ncgi_of, pci_of, arfcn_of)
    if not relations:
        unavailable.append("neighbour_relations(場景未宣告;執行期 ANR 建立的關係見 I-5 當下觀測)")

    # 空間:我們只有三維網格與範圍,沒有「主走廊/轉角」這種語意切分
    unavailable += ["space.segments", "space.junctions", "space.obstacles"]
    b = (bounds or {}).get("bounds") or bounds or {}
    space = {
        "coordinate_convention": COORDINATE_CONVENTION,
        "environment": "indoor_corridor" if (tree.get("buildings") or []) == [] else "mixed",
        "bounds": b or None,
        "ceiling_height_m": (b.get("max") or [None, None, None])[1] if isinstance(b.get("max"), list) else None,
        "segments": None,
        "junctions": None,
        "obstacles": None,
    }

    return {
        "field_id": scene.get("scene_uuid"),
        "name": scene.get("name"),
        "config_version": _cfg_version(tree),
        "updated_at": scene.get("scene_updated_at"),
        "space": space,
        "cells": cells,
        "neighbour_relations": relations,
        "xn_links": _xn_links(relations, gnb_of_cell),
        "collection": {
            "granularity_period_s": GRANULARITY_PERIOD_SEC,
            "timezone": TIMEZONE,
            "baseline_windows_required": BASELINE_WINDOWS_REQUIRED,
            "clock_source": "simulated",
        },
        "e2_identities": e2,   # C13:每個 gNB 一筆
        # gNB 自主 SON 功能的現行開關(場景層設定;I-3 可帶 `son` 覆寫,啟動時生效、整場固定)
        "son": _son_block(tree),
        "unavailable_fields": sorted(set(unavailable)),
    }


def _son_block(tree: dict) -> dict:
    from main.apps.agent_api.actors.scenario_actor import son_effective_from_knobs
    kn = (tree.get("run") or {}).get("knobs") or {}
    if isinstance(kn, list):
        kn = {k.get("key"): k.get("value") for k in kn if isinstance(k, dict)}
    return son_effective_from_knobs(kn)
