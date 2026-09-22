"""RunControlEvent → Agent 介面 I-7 的組態變更紀錄。

I-7 的用途只有一個:讓對方分辨「我方注入的事件」與「貴方系統的自主行為」。
對方刻意讓新 cell 缺鄰區當考題,我方的自主 ANR 會在數秒內補上 —— 沒有這份紀錄,
對方無從得知正確答案已被破壞。

來源前綴決定 origin:
    ric/*    → triggered_event   (RIC / xApp 下來的控制)
    agent/*  → triggered_event   (對方經 I-3 注入的事件)
    son/*  → son_function      (我方自主:anr_auto 等)
    其他   → system
"""
from __future__ import annotations

# action_type 前綴 → I-7 的 object_type。RIC 控制的 action_type 是 command 名
# (control_handover / anr_add …),沒有結構化的物件型別,只能照命名推斷。
_OBJECT_BY_PREFIX = (
    ("neighbour_relation", "neighbour_relation"),
    ("anr_", "neighbour_relation"),
    ("xn_", "xn_link"),
    ("cell_", "cell"),
    ("control_cell", "cell"),
    ("control_handover", "cell"),
    ("control_beam", "cell"),
    ("control_slice", "cell"),
)


def _origin(source: str) -> str:
    # son/ric_* 是 CU 對 RIC 命令的「落地」稽核(例如 PRB 配額真的套到 DU),歸 RIC 觸發
    if source.startswith("son/ric_"):
        return "triggered_event"
    if source.startswith("son/"):
        return "son_function"
    # agent/* 是對方自己經 I-3 注入的事件;ric/* 是 RIC / xApp 下來的控制。
    # 兩者對 I-7 都是 triggered_event(非我方自主),與 son_function 分得開即可。
    if source.startswith(("ric/", "agent/")):
        return "triggered_event"
    return "system"


def _object_type(action_type: str, detail: dict) -> str | None:
    # 自主行為的稽核列自己帶了型別,優先用
    ot = (detail or {}).get("object_type")
    if ot:
        return str(ot)
    a = (action_type or "").lower()
    for prefix, kind in _OBJECT_BY_PREFIX:
        if a.startswith(prefix):
            return kind
    # 其餘 RIC 控制(control_reportcgi / handover_group …)作用對象都是 cell,
    # 回 null 會讓對方以為我們不知道改了什麼
    if a.startswith("control_") or a.startswith("handover"):
        return "cell"
    return None


# RunControlEvent.target 存的是 adapter 稽核列的 `result`,對某些命令那是動作結果
# 而不是物件識別(anr_add 的 target 是字串 "ADDED")。真正的識別在 detail.params 裡。
_RESULT_WORDS = {"added", "removed", "ok", "applied", "accepted", "", "none"}


def _object_id(row: dict, detail: dict) -> str | None:
    p = (detail or {}).get("params") or {}
    src, tgt = p.get("source"), p.get("target")
    if src and tgt:
        return f"{src}>{tgt}"          # 鄰區關係:來源>目標
    for v in (detail.get("object_id"), tgt, src, p.get("cell_id"), p.get("ncgi")):
        if v:
            return str(v)
    t = str(row.get("target") or "")
    return t if t and t.lower() not in _RESULT_WORDS else None


def to_change(row: dict) -> dict:
    """單筆 RunControlEvent → I-7 的 change 物件。"""
    detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
    source = str(row.get("source") or "")
    at_ms = int(row.get("at_sim_ms") or 0)
    unavailable = []
    before, after = detail.get("before"), detail.get("after")
    if _object_id(row, detail) is None:
        unavailable.append("object_id")
    if before is None and after is None:
        # RIC 控制的稽核列沒有前後值(E2Adapter 只記 command / result / acked)
        unavailable.append("before/after")
    return {
        "offset_s": round(at_ms / 1000.0, 3),
        "ts_iso": row.get("run_control_event_created_at"),
        "object_type": _object_type(str(row.get("action_type") or ""), detail),
        "object_id": _object_id(row, detail),
        "attribute": detail.get("attribute"),
        "before": before,
        "after": after,
        "origin": _origin(source),
        "source": source,
        "action": row.get("action_type"),
        "outcome": row.get("outcome"),
        "reason": detail.get("reason"),
        "unavailable_fields": unavailable,
    }
