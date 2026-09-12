"""Adapter 內部 in-memory 狀態 — 不落 DB（生命週期跟 process 同進退）。

backend_rule.md 的 Model 通常 = Django Model = DB row。但 e2-adapter 沒持久化資料，
唯一「狀態」是當前 SCTP link 的活性、E2 Setup ack 拿到的 ranFunctionId、
buffered indication count 等。落 DB 反而負擔。

選擇用 dataclass + thread-safe getter/setter（在 business/memory_state_operations.py 操作）。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class ConnectionState:
    """單一 SCTP 連線生命週期狀態。"""

    sctp_connected: bool = False
    last_connect_at_ms: int = 0
    last_disconnect_at_ms: int = 0
    last_error: str = ""
    e2_setup_completed: bool = False
    accepted_ran_function_ids: list[int] = field(default_factory=list)
    rejected_ran_function_ids: list[int] = field(default_factory=list)
    pdu_sent_count: int = 0
    pdu_recv_count: int = 0


class _StateRegistry:
    """Thread-safe singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection = ConnectionState()

    def get_connection(self) -> ConnectionState:
        with self._lock:
            # Return a shallow copy so callers can't mutate without lock
            return ConnectionState(**self._connection.__dict__)

    def update_connection(self, **kwargs) -> ConnectionState:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._connection, key):
                    setattr(self._connection, key, value)
            return ConnectionState(**self._connection.__dict__)

    def reset(self) -> None:
        with self._lock:
            self._connection = ConnectionState()


_REGISTRY = _StateRegistry()


def get_registry() -> _StateRegistry:
    return _REGISTRY
