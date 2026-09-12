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

# 控制事件(RIC → sim 的下發命令)另存一份。
# 原因:主 ring 是全事件流,indication 約每秒一筆,500 筆上限等於**控制紀錄只留得住
# 約 8 分鐘** —— 等發現異常再去查,證據必然已經被擠掉(RIC 2026-08-20 實測 count=0,
# 要查的 instId=191 是 8 分鐘前的事)。控制命令一整天也才百來筆,獨立 buffer 能撐很久。
# 控制事件會同時進兩個 ring:主 ring 給 /logs 的 timeline 保持完整,
# 獨立 ring 給 /e2 的下發命令面板做事後對帳。
_control_ring = _Ring()


def get_ring() -> _Ring:
    return _ring


def get_control_ring() -> _Ring:
    """只含控制面事件(control_req_recv / control_ack_sent / control_failure)。"""
    return _control_ring


def _append_control(kind: str, **fields: Any) -> None:
    _ring.append(kind, **fields)
    _control_ring.append(kind, **fields)


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


def record_control_req_recv(style: int, action: int, sim_action: str, ueid: dict,
                            *, ran_func: int = 3, inst_id: int | None = None,
                            params: dict | None = None) -> None:
    """xApp 下發的控制命令進來了。

    ran_func / inst_id / params 是 2026-08-20 補的:Dashboard /e2 的「下發命令」面板
    要能顯示「誰下了什麼」並和 RIC 端的 instId 直接對帳。adapter 是 RC / ANR / CCC
    三種控制的唯一咽喉點,所以這裡是唯一能一次看完所有下發命令的地方。
    """
    _append_control(
        "control_req_recv", style=style, action=action,
        sim_action=sim_action, ueid=ueid,
        ran_func=ran_func, inst_id=inst_id, params=params or {},
    )


def record_control_ack_sent(style: int, action: int, sim_action: str, pdu_size: int,
                             outcome: str = "ok", *, ran_func: int = 3,
                             inst_id: int | None = None, result: str = "",
                             detail: str = "", rtt_ms: float | None = None) -> None:
    """ACK 送出。result 是 sim 回的 outcome 碼(ADDED / REJECTED_PROTECTED / …),
    與 ACK 的 RICcontrolOutcome(IE id=32)內容同源 —— 光看 outcome="ok" 只知道
    傳輸層成功,分不出業務層被拒。"""
    _append_control(
        "control_ack_sent", style=style, action=action,
        sim_action=sim_action, pdu_size=pdu_size, outcome=outcome,
        ran_func=ran_func, inst_id=inst_id, result=result, detail=detail,
        rtt_ms=None if rtt_ms is None else round(rtt_ms, 1),
    )


def record_control_failure(reason: str, style: int = 0, action: int = 0) -> None:
    _append_control("control_failure", reason=reason, style=style, action=action)
