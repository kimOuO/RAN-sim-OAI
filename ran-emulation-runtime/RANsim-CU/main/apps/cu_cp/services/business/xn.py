"""Xn(gNB ↔ gNB,TS 38.423)—— 多 gNB 改版 P6。HTTP + JSON,與 F1 / NG 同一套作法。

一場裡每個 gNB 一個 CU;鄰居 gNB 的端點由場次拓樸(RUN_TOPOLOGY)給,對應真實網路裡 Xn-C 的 TNL 位址。

實作的程序:
  Xn Setup(§8.4.1)                交換 served cells → 本 CU 的「外部鄰區表」(XnNeighbourCell)、CGI 解析表
  Handover Preparation(§8.2.1)    Handover Request / Acknowledge:目標 CU 允入、配 RAN UE NGAP ID、目標 DU 建 context
  SN Status Transfer(§8.2.2)      來源 → 目標;目標收到代表 UE 正在接入 → 目標送 Path Switch 給 AMF、通知 UE driver 改路由
  UE Context Release(§8.2.7)      目標 → 來源:來源刪掉 UE context
  Retrieve UE Context(§8.2.4)     跨 gNB 的 RRC 重建取回 context(由來源 CU 代轉 UE 的重建請求)
  Handover Report(§8.4.6 MRO)     目標發現「換過來很快又 RLF 並重建回來源」→ 通知來源(TooEarly)

同一個 gNB 內(同 CU)的換手、重建仍走 F1,與 Xn 無關(見 handover_executor)。
"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from main.utils.env_loader import get_float, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_session = requests.Session()
_TIMEOUT = get_float("XN_TIMEOUT_SEC", 5.0)


# ── 身分 ────────────────────────────────────────────────────────────────
def topology():
    try:
        from ran_sim_protocol.run_topology import RunTopology
    except ImportError:
        return None
    return RunTopology.from_env()


def self_gnb():
    t = topology()
    return t.self_gnb() if t is not None else None


def enabled() -> bool:
    """有拓樸、而且本場不只一個 gNB 才有 Xn。"""
    t = topology()
    return t is not None and t.self_gnb() is not None and len(t.gnbs) > 1


def local_served_cells() -> list[dict[str, Any]]:
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
    return [{"cell_id": c.cell_id, "nci": c.nr_cellid, "pci": c.pci, "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
             "frequency_ghz": c.frequency_ghz, "bandwidth_mhz": c.bandwidth_mhz, "plmn": c.served_plmn,
             "is_active": c.is_active, "is_barred": c.is_barred}
            for c in CellConfig.objects.all().order_by("cell_id")]


def _post(url: str, path: str, body: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    r = _session.post(f"{url}/api/v0.1/CU/Xn/XnRouter/{path}", json=body, timeout=timeout or _TIMEOUT)
    try:
        data = r.json()
    except ValueError:
        data = {"success": False, "message": r.text[:200]}
    if not r.ok:
        raise XnError(str(data.get("message") or f"HTTP {r.status_code}"), data.get("errors") or {})
    return data.get("data") or {}


class XnError(Exception):
    def __init__(self, cause: str, detail: Any = None):
        super().__init__(f"{cause}: {detail}")
        self.cause, self.detail = cause, detail


# ── Xn Setup ────────────────────────────────────────────────────────────
def store_peer(gnb_id: int, gnb_name: str, cu_url: str, cells: list[dict[str, Any]]) -> int:
    """記下對端 gNB 與它的 served cells(外部鄰區表 + CGI 解析表)。回傳 cell 數。"""
    from main.apps.cu_cp.models.cgi_resolution import CgiResolution
    from main.apps.cu_cp.models.xn import XnNeighbourCell, XnPeer
    from main.apps.cu_cp.services.common.timestamp_service import TimestampService
    now = TimestampService.now()
    XnPeer.objects.update_or_create(gnb_id=int(gnb_id), defaults={
        "gnb_name": gnb_name, "cu_url": cu_url.rstrip("/"), "state": "ESTABLISHED",
        "established_at": now, "updated_at": now})
    ids = []
    for c in cells:
        ids.append(c["cell_id"])
        XnNeighbourCell.objects.update_or_create(cell_id=c["cell_id"], defaults={
            "gnb_id": int(gnb_id), "nci": c.get("nci"), "pci": int(c.get("pci") or 0), "arfcn": int(c.get("arfcn") or 0),
            "frequency_ghz": float(c.get("frequency_ghz") or 0.0), "bandwidth_mhz": float(c.get("bandwidth_mhz") or 0.0),
            "plmn": str(c.get("plmn") or ""), "is_active": bool(c.get("is_active", True)),
            "is_barred": bool(c.get("is_barred", False)), "updated_at": now})
        # ReportCGI(C12):UE 回報的 PCI@ARFCN 若是鄰 gNB 的 cell,也要解得出來
        CgiResolution.objects.update_or_create(pci=int(c.get("pci") or 0), arfcn=int(c.get("arfcn") or 0), defaults={
            "cgi": c["cell_id"], "plmn": str(c.get("plmn") or ""), "created_at": now, "updated_at": now})
    XnNeighbourCell.objects.filter(gnb_id=int(gnb_id)).exclude(cell_id__in=ids).delete()
    return len(ids)


def xn_setup_with(peer) -> bool:
    """對一個鄰居 gNB 做 Xn Setup(雙向交換 served cells)。"""
    me = self_gnb()
    if me is None:
        return False
    try:
        resp = _post(peer.cu_url, "xn_setup", {"gnb_id": me.gnb_id, "gnb_name": me.name, "cu_url": me.cu_url,
                                               "served_cells": local_served_cells()})
    except Exception as exc:  # noqa: BLE001
        logger.info("Xn Setup → %s (%s) 尚未成功: %s", peer.name, peer.cu_url, exc)
        return False
    n = store_peer(int(resp["gnb_id"]), str(resp.get("gnb_name") or peer.name), peer.cu_url, resp.get("served_cells") or [])
    logger.info("Xn Setup with %s (0x%06x) established: %d served cell(s)", peer.name, peer.gnb_id, n)
    return True


_setup_lock = threading.Lock()
_setup_thread: threading.Thread | None = None


def ensure_xn_setup(retry_sec: float = 3.0, give_up_sec: float = 900.0) -> None:
    """背景對每個鄰居 gNB 做 Xn Setup,直到全部成功(鄰居的 CU 可能還沒起來)。
    本 CU 的 cell 有變(F1 Setup / DU Configuration Update)時再呼叫一次 = NG-RAN node Configuration Update。"""
    global _setup_thread
    if not enabled():
        return

    def _run() -> None:
        from django.db import close_old_connections
        t0 = time.time()
        pending = [g for g in topology().gnbs if g.name != self_gnb().name]
        while pending and time.time() - t0 < give_up_sec:
            close_old_connections()
            pending = [g for g in pending if not xn_setup_with(g)]
            if pending:
                time.sleep(retry_sec)
        close_old_connections()
        if pending:
            logger.warning("Xn Setup 放棄:%s 在 %.0f s 內都沒回應", [g.name for g in pending], give_up_sec)

    with _setup_lock:
        if _setup_thread is not None and _setup_thread.is_alive():
            # 已在跑:cell 有變時讓它跑完這一輪後再做一次
            threading.Timer(retry_sec, ensure_xn_setup).start()
            return
        _setup_thread = threading.Thread(target=_run, name="xn-setup", daemon=True)
        _setup_thread.start()


# ── 查表 ────────────────────────────────────────────────────────────────
def foreign_cell(cell_id: str):
    from main.apps.cu_cp.models.xn import XnNeighbourCell
    return XnNeighbourCell.objects.filter(cell_id=cell_id).first() if cell_id else None


def foreign_cell_by_nci(nci: int):
    from main.apps.cu_cp.models.xn import XnNeighbourCell
    return XnNeighbourCell.objects.filter(nci=int(nci)).first()


def peer(gnb_id: int):
    from main.apps.cu_cp.models.xn import XnPeer
    return XnPeer.objects.filter(gnb_id=int(gnb_id)).first()


def peer_url_for_gnb(gnb_id: int) -> str:
    """Xn Setup 還沒完成時退回拓樸(端點本來就是拓樸給的)。"""
    p = peer(gnb_id)
    if p is not None and p.cu_url:
        return p.cu_url
    t = topology()
    g = t.gnb_by_id(gnb_id) if t is not None else None
    return g.cu_url if g is not None else ""


def xn_available(gnb_id: int) -> bool:
    p = peer(gnb_id)
    return p is not None and p.state == "ESTABLISHED"


# ── RAN UE NGAP ID(每個 gNB 自己配)─────────────────────────────────────
def ran_ue_ngap_id_for(ue_id: str) -> int:
    """本 gNB 給這個 UE 的 RAN UE NGAP ID。多 gNB 時以 (gNB ID, UE) 決定(決定性、跨 gNB 不同);
    沒有拓樸時與改版前相同(只看 UE)。"""
    import hashlib
    me = self_gnb()
    key = f"{me.gnb_id}:{ue_id}" if me is not None else ue_id
    return int.from_bytes(hashlib.sha1(key.encode("utf-8")).digest()[:4], "big") % (2 ** 31)


def ncgi_of(cell_id: str) -> str:
    """cell → ncgi 字串(D2 固定格式);本 gNB 或 Xn 鄰居的 cell 都查得到,查不到回空字串。"""
    t = topology()
    c = t.cell(cell_id) if t is not None and cell_id else None
    return c.ncgi if c is not None else ""


def std_ids(cell_id: str) -> dict[str, Any]:
    """cell 的標準識別(RIC 選項 A,2026-09-27):ran_func 6 的 `ncgi` 欄位維持 cell 名稱,
    另外附 nci(36-bit 整數)與 ncgiStd(D2 字串 <PLMN6>-<NCI 9 hex>)。本 gNB 與 Xn 鄰居的 cell 都查得到。"""
    t = topology()
    c = t.cell(cell_id) if t is not None and cell_id else None
    if c is not None:
        return {"nci": c.nci, "ncgiStd": c.ncgi}
    nci = None
    try:
        from main.apps.cu_cp.models.cell_config import CellConfig
        nci = CellConfig.objects.filter(cell_id=cell_id).values_list("nr_cellid", flat=True).first()
        if nci is None:
            f = foreign_cell(cell_id)
            nci = f.nci if f is not None else None
    except Exception:  # noqa: BLE001
        nci = None
    if nci is None:
        return {"nci": None, "ncgiStd": None}
    from ran_sim_protocol.e2_identity import ncgi as _ncgi
    return {"nci": int(nci), "ncgiStd": _ncgi(int(nci), get_str("PLMN_MCC", "208"), get_str("PLMN_MNC", "95"))}
