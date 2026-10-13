"""RAN 端點查表(2026-09-27 多 gNB)。

per-run 容器有 env RUN_TOPOLOGY(orchestrator 給的整場拓樸):每個 cell 屬於哪個 DU / CU 查這裡。
沒有拓樸時(舊的共用 ransim-* 容器)一律退回 settings.SIM_CU_URL / SIM_DU_URL,行為與改版前相同。

時鐘:SIM_CLOCK=external 時由 RU 的全場鎖步時鐘驅動(見 RU phy_low/lockstep_clock),
UE 端的 tick_start / 劇本時鐘讀取改打 RU;否則沿用 DU 自己的時鐘。
"""
from __future__ import annotations

import os
import threading

from django.conf import settings


def topology():
    try:
        from ran_sim_protocol.run_topology import RunTopology
    except ImportError:   # 舊 image 沒掛 protocol 套件
        return None
    return RunTopology.from_env()


def external_clock() -> bool:
    return (os.environ.get("SIM_CLOCK") or "internal").strip().lower() == "external"


def ru_url() -> str:
    return settings.SIM_RU_URL.rstrip("/")


def cu_urls() -> list[str]:
    t = topology()
    return [g.cu_url for g in t.gnbs] if t else [settings.SIM_CU_URL.rstrip("/")]


def du_urls() -> list[str]:
    t = topology()
    return [d.url for d in t.dus()] if t else [settings.SIM_DU_URL.rstrip("/")]


def du_url_for_cell(cell_id: str) -> str:
    t = topology()
    if t is not None:
        d = t.du_of_cell(cell_id)
        if d is not None:
            return d.url
        return t.dus()[0].url if t.dus() else settings.SIM_DU_URL.rstrip("/")
    return settings.SIM_DU_URL.rstrip("/")


def cu_url_for_cell(cell_id: str) -> str:
    t = topology()
    if t is not None:
        g = t.gnb_of_cell(cell_id)
        if g is not None:
            return g.cu_url
        return t.gnbs[0].cu_url if t.gnbs else settings.SIM_CU_URL.rstrip("/")
    return settings.SIM_CU_URL.rstrip("/")


class _UeRoutes:
    """UE 目前的服務 cell(= 下行資料送去哪個 DU、控制送去哪個 CU)。

    流量產生器扮演核心網,下行 SDU 直接送進 UE 的服務 DU;UE 換手後由 CU 通知這裡更新
    (UserPlane/path_update),查不到時由 manager 的 CU session 同步補上。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cell: dict[str, str] = {}

    def set(self, ue_id: str, cell_id: str) -> None:
        if ue_id and cell_id:
            with self._lock:
                self._cell[ue_id] = cell_id

    def drop(self, ue_id: str) -> None:
        with self._lock:
            self._cell.pop(ue_id, None)

    def cell_of(self, ue_id: str) -> str:
        with self._lock:
            return self._cell.get(ue_id, "")

    def clear(self) -> None:
        with self._lock:
            self._cell.clear()

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self._cell)


routes = _UeRoutes()


def du_url_for_ue(ue_id: str) -> str:
    return du_url_for_cell(routes.cell_of(ue_id))


def cu_url_for_ue(ue_id: str) -> str:
    return cu_url_for_cell(routes.cell_of(ue_id))
