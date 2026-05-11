"""E2 event ring buffer — 紀錄 adapter 收/送的 E2 plane event 給 Dashboard 顯示。

Thread-safe in-memory FIFO，最多保 _MAX_ENTRIES 筆。Dashboard 端 polling 用
since_seq 取增量。
"""
from __future__ import annotations

import threading
import time
from typing import Any

_MAX_ENTRIES = 500


class _Ring:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._next_seq = 1

    def append(self, kind: str, **fields: Any) -> None:
        with self._lock:
            entry = {
                "seq": self._next_seq,
                "ts_ms": int(time.time() * 1000),
                "kind": kind,
                **fields,
            }
            self._next_seq += 1
            self._entries.append(entry)
            if len(self._entries) > _MAX_ENTRIES:
                # 切到 FIFO 上限後丟最舊的
                del self._entries[: len(self._entries) - _MAX_ENTRIES]

    def read(self, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if since_seq <= 0:
                items = self._entries[-limit:]
            else:
                items = [e for e in self._entries if e["seq"] > since_seq]
                items = items[:limit]
            return list(items)


_ring = _Ring()


def get_ring() -> _Ring:
    return _ring


def append(kind: str, **fields: Any) -> None:
    """Module-level shortcut so callers can do `event_ring.append(...)`."""
    _ring.append(kind, **fields)


# ── Convenience helpers (called from sctp_loop) ───────────────

def record_sctp_connect(host: str, port: int) -> None:
    _ring.append("sctp_connect", host=host, port=port)


def record_sctp_disconnect(reason: str = "") -> None:
    _ring.append("sctp_disconnect", reason=reason)


def record_e2_setup_outcome(outcome: str, accepted: list[int], rejected: list[int],
                             reason: str = "") -> None:
    _ring.append(
        "e2_setup_outcome",
        outcome=outcome,
        accepted=accepted,
        rejected=rejected,
        reason=reason,
    )


def record_sub_req_recv(sub_id: str, ric_req_id: dict, ran_func_id: int,
                         metrics: list[str], period_ms: int) -> None:
    _ring.append(
        "sub_req_recv",
        sub_id=sub_id,
        ric_req_id=ric_req_id,
        ran_func_id=ran_func_id,
        metrics=metrics,
        period_ms=period_ms,
    )


def record_sub_resp_sent(sub_id: str, admitted_action_ids: list[int], pdu_size: int) -> None:
    _ring.append(
        "sub_resp_sent",
        sub_id=sub_id,
        admitted_action_ids=admitted_action_ids,
        pdu_size=pdu_size,
    )


def record_indication_sent(sub_id: str, sn: int, pdu_size: int, ue_count: int = 0) -> None:
    """每送出 RIC_INDICATION 記一筆。flood-protected：每 10 筆才記一次。"""
    if sn != 1 and sn % 10 != 0:
        return
    _ring.append(
        "indication_sent",
        sub_id=sub_id,
        sn=sn,
        pdu_size=pdu_size,
        ue_count=ue_count,
    )


def record_indication_encode_fail(sub_id: str, error: str) -> None:
    _ring.append("indication_encode_fail", sub_id=sub_id, error=error[:200])


def record_pdu_dispatch(proc_code: int, type_name: str, size: int) -> None:
    """For unhandled or info-level recv PDUs."""
    _ring.append("pdu_recv", proc_code=proc_code, type_name=type_name, size=size)


def record_control_req_recv(style: int, action: int, sim_action: str, ueid: dict) -> None:
    _ring.append(
        "control_req_recv", style=style, action=action,
        sim_action=sim_action, ueid=ueid,
    )


def record_control_ack_sent(style: int, action: int, sim_action: str, pdu_size: int,
                             outcome: str = "ok") -> None:
    _ring.append(
        "control_ack_sent", style=style, action=action,
        sim_action=sim_action, pdu_size=pdu_size, outcome=outcome,
    )


def record_control_failure(reason: str, style: int = 0, action: int = 0) -> None:
    _ring.append("control_failure", reason=reason, style=style, action=action)
