"""AMF 的狀態:已做 NG Setup 的 gNB,以及 UE 的 NG 關聯(TS 23.502 / 38.413 的最小子集)。

全在記憶體、單一 process。一場一個 AMF 容器,場次結束即丟,所以不落地。

UE 識別:
  AMF UE NGAP ID —— AMF 配發,全場唯一,換手前後不變(介面 C9:RIC 的 ngap_id 就是它)。
                     取值與改版前 CU 內建假 AMF 一致(SHA-1(ue_id) + 1、UE_ID_FIXED_MAP 例外),
                     單 gNB 場景對外看到的 ngap_id 與改版前相同。
  RAN UE NGAP ID —— 由各 gNB(CU)自己配發;UE 換到另一個 gNB 後會變。AMF 以 (gNB ID, RAN UE NGAP ID) 找 UE。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


def amf_ue_ngap_id_for(ue_id: str) -> int:
    """與改版前 CU 的 _resolve_ue_base + 1 相同(RIC / xApp 表上記的是這個值)。"""
    fixed_map = os.getenv("UE_ID_FIXED_MAP", "cco_ue_01:1056001737") or ""
    for pair in fixed_map.split(","):
        name, sep, val = pair.partition(":")
        if sep and name.strip() == ue_id:
            try:
                return int(val.strip()) % (2 ** 31) + 1
            except ValueError:
                break
    return int.from_bytes(hashlib.sha1(ue_id.encode("utf-8")).digest()[:4], "big") % (2 ** 31) + 1


@dataclass
class GnbEntry:
    gnb_id: int
    gnb_name: str
    cu_url: str
    plmn: str
    tac: int
    served_cells: list[dict] = field(default_factory=list)   # [{cell_id, nci, pci}]
    setup_at: float = 0.0


@dataclass
class UeEntry:
    ue_id: str                  # sim 內的 UE 名稱(= SUPI 的替身)
    amf_ue_ngap_id: int
    gnb_id: int                 # 目前服務它的 gNB
    ran_ue_ngap_id: int
    cell_id: str = ""
    cm_state: str = "CONNECTED"   # CONNECTED / IDLE
    pdu_sessions: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)          # 換手 / path switch 紀錄(最近 20 筆)
    updated_at: float = 0.0


class AmfRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.gnbs: dict[int, GnbEntry] = {}
        self.ues: dict[int, UeEntry] = {}                # amf_ue_ngap_id → UE
        self._by_ran: dict[tuple[int, int], int] = {}    # (gnb_id, ran_ue_ngap_id) → amf_ue_ngap_id
        self.counters: dict[str, int] = {}

    # ── gNB ──
    def ng_setup(self, gnb_id: int, gnb_name: str, cu_url: str, plmn: str, tac: int,
                 served_cells: list[dict] | None = None) -> GnbEntry:
        with self._lock:
            g = GnbEntry(int(gnb_id), gnb_name, cu_url.rstrip("/"), plmn, int(tac), list(served_cells or []), time.time())
            self.gnbs[g.gnb_id] = g
            self.bump("ng_setup")
            return g

    def gnb(self, gnb_id: int) -> GnbEntry | None:
        with self._lock:
            return self.gnbs.get(int(gnb_id))

    # ── UE ──
    def attach(self, ue_id: str, gnb_id: int, ran_ue_ngap_id: int, cell_id: str = "") -> UeEntry:
        """Initial UE Message:建立(或接回)UE 的 NG 關聯。同一個 UE 重新接入沿用同一個 AMF UE NGAP ID。"""
        with self._lock:
            amf_id = amf_ue_ngap_id_for(ue_id)
            old = self.ues.get(amf_id)
            if old is not None:
                self._by_ran.pop((old.gnb_id, old.ran_ue_ngap_id), None)
            ue = UeEntry(ue_id, amf_id, int(gnb_id), int(ran_ue_ngap_id), cell_id, "CONNECTED",
                         old.pdu_sessions if old else [], old.history if old else [], time.time())
            self.ues[amf_id] = ue
            self._by_ran[(ue.gnb_id, ue.ran_ue_ngap_id)] = amf_id
            self.bump("initial_ue_message")
            return ue

    def ue(self, amf_ue_ngap_id: int) -> UeEntry | None:
        with self._lock:
            return self.ues.get(int(amf_ue_ngap_id))

    def ue_by_ran(self, gnb_id: int, ran_ue_ngap_id: int) -> UeEntry | None:
        with self._lock:
            amf = self._by_ran.get((int(gnb_id), int(ran_ue_ngap_id)))
            return self.ues.get(amf) if amf is not None else None

    def move(self, amf_ue_ngap_id: int, gnb_id: int, ran_ue_ngap_id: int, cell_id: str, how: str) -> UeEntry | None:
        """UE 換到另一個 gNB(Path Switch 或 NG 換手完成):更新 (gNB, RAN UE NGAP ID) 對照。"""
        with self._lock:
            ue = self.ues.get(int(amf_ue_ngap_id))
            if ue is None:
                return None
            self._by_ran.pop((ue.gnb_id, ue.ran_ue_ngap_id), None)
            ue.history = (ue.history + [{"at": time.time(), "how": how, "from_gnb": ue.gnb_id, "to_gnb": int(gnb_id),
                                         "from_ran_id": ue.ran_ue_ngap_id, "to_ran_id": int(ran_ue_ngap_id),
                                         "cell_id": cell_id}])[-20:]
            ue.gnb_id, ue.ran_ue_ngap_id, ue.cell_id = int(gnb_id), int(ran_ue_ngap_id), cell_id or ue.cell_id
            ue.cm_state = "CONNECTED"
            ue.updated_at = time.time()
            self._by_ran[(ue.gnb_id, ue.ran_ue_ngap_id)] = ue.amf_ue_ngap_id
            return ue

    def release(self, amf_ue_ngap_id: int, gnb_id: int | None = None) -> UeEntry | None:
        """UE Context Release:只有「目前服務它的 gNB」送的才生效(換手後舊 gNB 的釋放不影響新關聯)。"""
        with self._lock:
            ue = self.ues.get(int(amf_ue_ngap_id))
            if ue is None:
                return None
            if gnb_id is not None and int(gnb_id) != ue.gnb_id:
                return ue
            self._by_ran.pop((ue.gnb_id, ue.ran_ue_ngap_id), None)
            ue.cm_state = "IDLE"
            ue.updated_at = time.time()
            self.bump("ue_context_release")
            return ue

    def bump(self, key: str) -> None:
        self.counters[key] = self.counters.get(key, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"gnbs": [asdict(g) for g in self.gnbs.values()],
                    "ues": [asdict(u) for u in self.ues.values()],
                    "counters": dict(self.counters)}

    def reset(self) -> None:
        with self._lock:
            self.gnbs.clear(); self.ues.clear(); self._by_ran.clear(); self.counters.clear()


_registry = AmfRegistry()


def get_registry() -> AmfRegistry:
    return _registry
