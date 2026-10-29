"""一場的拓樸 —— 哪個 cell 屬於哪個 DU、哪個 gNB,各自的端點在哪(2026-09-27 多 gNB 改版)。

orchestrator 開場時由 registry 的場景樹組出來,以 env `RUN_TOPOLOGY`(JSON)交給每個容器;
容器只查表,不自行推導 gNB ID、NCI、cell 標籤或對方的主機名 —— 這些都只在這裡算一次。
規格:docs/architecture/multi_gnb_plan.md D2、D3。

沒有 `RUN_TOPOLOGY` 的容器(舊的共用 ransim-* 或單元測試)`from_env()` 回 None,
呼叫端退回原本的單一端點 env(HTTP_DU_HOST、SIM_CU_URL…),行為與改版前相同。

命名(per-run 容器,rid = scene_run_uuid 後 8 碼):
    cu-<rid>-<e2_index>    e2adapter-<rid>-<e2_index>
    du-<rid>-<du 全場序號>  amf-<rid>  ru-<rid>  ue-<rid>
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from ran_sim_protocol import e2_identity as ident

__all__ = ["TopoCell", "TopoDu", "TopoGnb", "RunTopology", "default_names", "build_from_tree", "ENV_VAR"]

ENV_VAR = "RUN_TOPOLOGY"


@dataclass
class TopoCell:
    cell_id: str            # 全場唯一、對外的 cell 名(帶 gNB 前綴,例 e31:src)
    name: str               # registry 原名(例 src)
    local_cell_id: int
    nci: int
    ncgi: str
    pci: int
    gnb: str                # 所屬 gNB 名稱
    du: str                 # 所屬 DU 名稱(拓樸內唯一)
    freq_ghz: float | None = None   # 中心頻率(跨 DU 干擾判斷頻段是否重疊用)
    bw_mhz: float | None = None
    tx_power_dbm: float | None = None   # registry power_dbm;跨 DU 的 SINR 干擾項要用各 cell 真實功率(2026-10-14 #22)


@dataclass
class TopoDu:
    name: str               # 拓樸內唯一:<gNB 名稱>/<registry DU 名稱>
    index: int              # 全場序號(容器名 du-<rid>-<index>)
    gnb_du_id: int          # F1 的 gNB-DU ID,gNB 內唯一
    host: str
    url: str
    gnb: str
    du_uuid: str = ""
    cells: list[TopoCell] = field(default_factory=list)


@dataclass
class TopoGnb:
    name: str
    e2_index: int
    gnb_id: int
    gnb_id_hex: str
    meid: str
    cell_tag: str
    mcc: str
    mnc: str
    plmn_bcd: str
    gnb_id_bits: str
    cu_host: str
    cu_url: str
    e2_host: str = ""
    e2_port: int = 0
    gnb_uuid: str = ""
    dus: list[TopoDu] = field(default_factory=list)


def default_names(rid: str) -> Callable[..., str]:
    """容器主機名規則(orchestrator 與測試共用)。"""
    def _name(role: str, idx: int | None = None) -> str:
        return f"{role}-{rid}" if idx is None else f"{role}-{rid}-{idx}"
    return _name


class RunTopology:
    def __init__(self, *, run: str, block: int, gnbs: list[TopoGnb], ru_url: str = "", ue_url: str = "",
                 amf_url: str = "", mcc: str = "208", mnc: str = "95"):
        self.run, self.block, self.gnbs = run, int(block), list(gnbs)
        self.ru_url, self.ue_url, self.amf_url = ru_url, ue_url, amf_url
        self.mcc, self.mnc = str(mcc), str(mnc)
        self._index()

    # ── 建索引 ──────────────────────────────────────────────
    def _index(self) -> None:
        self._gnb_by_name = {g.name: g for g in self.gnbs}
        self._gnb_by_id = {g.gnb_id: g for g in self.gnbs}
        self._du_by_name: dict[str, TopoDu] = {}
        self._cell: dict[str, TopoCell] = {}
        self._cell_by_nci: dict[int, TopoCell] = {}
        for g in self.gnbs:
            for d in g.dus:
                if d.name in self._du_by_name:
                    raise ValueError(f"DU 名稱重複:{d.name}")
                self._du_by_name[d.name] = d
                for c in d.cells:
                    if c.cell_id in self._cell:
                        raise ValueError(f"cell 名稱重複:{c.cell_id}")
                    self._cell[c.cell_id] = c
                    self._cell_by_nci[c.nci] = c

    # ── 序列化 ──────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "run": self.run, "block": self.block, "mcc": self.mcc, "mnc": self.mnc,
                "ru_url": self.ru_url, "ue_url": self.ue_url, "amf_url": self.amf_url,
                "gnbs": [asdict(g) for g in self.gnbs]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunTopology":
        gnbs = []
        for g in d.get("gnbs") or []:
            dus = []
            for du in g.get("dus") or []:
                cells = [TopoCell(**c) for c in du.get("cells") or []]
                dus.append(TopoDu(**{**{k: v for k, v in du.items() if k != "cells"}, "cells": cells}))
            gnbs.append(TopoGnb(**{**{k: v for k, v in g.items() if k != "dus"}, "dus": dus}))
        return cls(run=d.get("run", ""), block=int(d.get("block") or 0), gnbs=gnbs, ru_url=d.get("ru_url", ""),
                   ue_url=d.get("ue_url", ""), amf_url=d.get("amf_url", ""), mcc=d.get("mcc", "208"), mnc=d.get("mnc", "95"))

    @classmethod
    def from_json(cls, text: str) -> "RunTopology":
        return cls.from_dict(json.loads(text))

    _ENV_CACHE: dict[str, "RunTopology"] = {}

    @classmethod
    def from_env(cls, var: str = ENV_VAR) -> "RunTopology | None":
        """讀 env;沒有就回 None(舊的單一端點模式)。同一字串只解析一次。"""
        raw = (os.environ.get(var) or "").strip()
        if not raw:
            return None
        topo = cls._ENV_CACHE.get(raw)
        if topo is None:
            topo = cls.from_json(raw)
            cls._ENV_CACHE[raw] = topo
        return topo

    # ── 查詢 ────────────────────────────────────────────────
    def cells(self) -> list[TopoCell]:
        return list(self._cell.values())

    def dus(self) -> list[TopoDu]:
        return [d for g in self.gnbs for d in g.dus]

    def cell(self, cell_id: str) -> TopoCell | None:
        return self._cell.get(cell_id)

    def cell_by_nci(self, nci: int) -> TopoCell | None:
        return self._cell_by_nci.get(int(nci))

    def gnb(self, name: str) -> TopoGnb | None:
        return self._gnb_by_name.get(name)

    def gnb_by_id(self, gnb_id: int) -> TopoGnb | None:
        return self._gnb_by_id.get(int(gnb_id))

    def gnb_of_nci(self, nci: int) -> TopoGnb | None:
        return self._gnb_by_id.get(ident.gnb_id_of_nci(nci))

    def du(self, name: str) -> TopoDu | None:
        return self._du_by_name.get(name)

    def gnb_of_cell(self, cell_id: str) -> TopoGnb | None:
        c = self._cell.get(cell_id)
        return self._gnb_by_name.get(c.gnb) if c else None

    def du_of_cell(self, cell_id: str) -> TopoDu | None:
        c = self._cell.get(cell_id)
        return self._du_by_name.get(c.du) if c else None

    def self_gnb(self) -> TopoGnb | None:
        """本容器所屬的 gNB(env GNB_NAME;CU、e2adapter、DU 都有)。"""
        return self.gnb(os.environ.get("GNB_NAME", ""))

    def self_du(self) -> TopoDu | None:
        return self.du(os.environ.get("DU_NAME", ""))

    def is_multi_node(self) -> bool:
        return len(self.gnbs) > 1


def _pick_gnb_du_ids(dus: list[dict[str, Any]]) -> list[int]:
    """registry 的 gnb_du_id 在 gNB 內不重複就沿用,否則依序 1、2、3…(F1 只要求 gNB 內唯一)。"""
    ids = [int(d.get("gnb_du_id") or 0) for d in dus]
    if all(i > 0 for i in ids) and len(set(ids)) == len(ids):
        return ids
    return list(range(1, len(dus) + 1))


def build_from_tree(tree: dict[str, Any], *, run_uuid: str, block: int,
                    names: Callable[..., str] | None = None, port: int = 8000,
                    e2_host: str = "", e2_port_base: int = 8400) -> RunTopology:
    """registry `read_full_tree` 的 data → 拓樸。

    gNB 順序以 e2_index 為準(registry 保證場景內唯一);cell 的 local_cell_id 由 registry 配發,
    缺值時(舊資料)依 gNB 內出現順序補,但仍檢查不重複。
    """
    names = names or default_names(run_uuid[-8:])
    gnbs_raw = sorted(tree.get("gnbs") or [], key=lambda g: (g.get("e2_index") is None, g.get("e2_index") or 0))
    seen_idx: set[int] = set()
    gnbs: list[TopoGnb] = []
    du_seq = 0
    for pos, g in enumerate(gnbs_raw):
        e2_index = g.get("e2_index")
        e2_index = pos if e2_index is None else int(e2_index)
        if e2_index in seen_idx:
            raise ValueError(f"gNB e2_index 重複:{e2_index}")
        seen_idx.add(e2_index)
        mcc, mnc = str(g.get("plmn_mcc") or "208"), str(g.get("plmn_mnc") or "95")
        nid = ident.node_identity(block, e2_index, str(g["name"]), mcc, mnc)
        cu_host = names("cu", e2_index)
        tg = TopoGnb(name=str(g["name"]), e2_index=e2_index, gnb_id=nid["gnb_id"], gnb_id_hex=nid["gnb_id_hex"],
                     meid=nid["meid"], cell_tag=nid["cell_tag"], mcc=mcc, mnc=mnc, plmn_bcd=nid["plmn_bcd"],
                     gnb_id_bits=nid["gnb_id_bits"], cu_host=cu_host, cu_url=f"http://{cu_host}:{port}",
                     e2_host=e2_host, e2_port=(e2_port_base + ident.slot_for(block, e2_index)) if e2_port_base else 0,
                     gnb_uuid=str(g.get("gnb_uuid") or ""))
        dus_raw = list(g.get("dus") or [])
        # 頻率:cell 沒填就用本 gNB 第一個有填的 cell(與 UE driver 的 scenario loader 同規則),再沒有 3.5 GHz / 40 MHz
        _f0 = next((c.get("center_frequency_ghz") for d in dus_raw for c in d.get("cells") or [] if c.get("center_frequency_ghz") is not None), 3.5)
        _b0 = next((c.get("bandwidth_mhz") for d in dus_raw for c in d.get("cells") or [] if c.get("bandwidth_mhz") is not None), 40.0)
        used_lc: set[int] = set()
        next_lc = 0
        for du_raw, gdu in zip(dus_raw, _pick_gnb_du_ids(dus_raw)):
            du_host = names("du", du_seq)
            du_name = f"{tg.name}/{du_raw.get('name') or gdu}"
            td = TopoDu(name=du_name, index=du_seq, gnb_du_id=gdu, host=du_host, url=f"http://{du_host}:{port}",
                        gnb=tg.name, du_uuid=str(du_raw.get("du_uuid") or ""))
            du_seq += 1
            for c in du_raw.get("cells") or []:
                lc = c.get("local_cell_id")
                if lc is None:
                    while next_lc in used_lc:
                        next_lc += 1
                    lc = next_lc
                lc = int(lc)
                if lc in used_lc:
                    raise ValueError(f"gNB {tg.name} 的 local_cell_id 重複:{lc}")
                used_lc.add(lc)
                nci = ident.nci(tg.gnb_id, lc)
                td.cells.append(TopoCell(
                    cell_id=ident.tag_cell(tg.cell_tag, str(c["name"])), name=str(c["name"]), local_cell_id=lc,
                    nci=nci, ncgi=ident.ncgi(nci, mcc, mnc), pci=int(c.get("pci") or 0), gnb=tg.name, du=du_name,
                    freq_ghz=float(c["center_frequency_ghz"] if c.get("center_frequency_ghz") is not None else _f0),
                    bw_mhz=float(c["bandwidth_mhz"] if c.get("bandwidth_mhz") is not None else _b0),
                    tx_power_dbm=float(c["power_dbm"]) if c.get("power_dbm") is not None else None))
            tg.dus.append(td)
        gnbs.append(tg)
    first = gnbs[0] if gnbs else None
    return RunTopology(run=run_uuid, block=block, gnbs=gnbs,
                       ru_url=f"http://{names('ru')}:{port}", ue_url=f"http://{names('ue')}:{port}",
                       amf_url=f"http://{names('amf')}:{port}",
                       mcc=first.mcc if first else "208", mnc=first.mnc if first else "95")


def iter_cell_ids(topo: RunTopology | None, cells: Iterable[str]) -> list[str]:
    """過濾出拓樸認得的 cell(topo 為 None 時原樣回)。"""
    if topo is None:
        return list(cells)
    return [c for c in cells if topo.cell(c) is not None]
