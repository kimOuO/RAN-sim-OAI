"""目前這個請求是不是 RIC 控制觸發的(多 gNB C14:RIC 對帳)。

e2adapter 轉來的控制帶 ric_request = {requestor_id, instance_id, label};E2 控制的處理入口 set,
下游(換手執行器)寫事件時讀。contextvars 讓每個請求執行緒各自一份,不會串到別的請求。
"""
from __future__ import annotations

import contextvars
from typing import Any

_current: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("ric_request", default=None)


def set_request(ric_request: dict[str, Any] | None):
    return _current.set(dict(ric_request) if ric_request else None)


def reset(token) -> None:
    _current.reset(token)


def event_fields() -> dict[str, Any]:
    """寫進 HandoverEvent 的欄位;不是 RIC 觸發就回空(欄位保留預設)。"""
    r = _current.get()
    if not r:
        return {}
    return {"ric_instance_id": r.get("instance_id"), "ric_label": str(r.get("label") or "")[:255]}
