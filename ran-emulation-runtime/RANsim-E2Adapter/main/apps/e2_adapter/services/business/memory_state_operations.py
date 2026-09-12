"""通用 in-memory state 操作 — 對應 backend_rule.md §14-2 通用方法原則。

不為單一資料類型寫專門方法；接受 dataclass instance 或 registry 作為參數。
"""
from __future__ import annotations

from typing import Any


class MemoryStateBusinessService:
    """In-memory state CRUD（取代 SQL DB）— 通用方法。

    Adapter 沒持久化資料，所有狀態都靠 ConnectionState 之類的 dataclass + lock。
    這層提供 read / update / reset 通用 API 供 Actor 編排。
    """

    @staticmethod
    def read_state(registry: Any) -> Any:
        """通用讀取 — registry 必須有 .get_connection() 等 method。"""
        if hasattr(registry, "get_connection"):
            return registry.get_connection()
        raise TypeError(f"unsupported registry: {registry!r}")

    @staticmethod
    def update_state(registry: Any, **kwargs) -> Any:
        if hasattr(registry, "update_connection"):
            return registry.update_connection(**kwargs)
        raise TypeError(f"unsupported registry: {registry!r}")

    @staticmethod
    def reset_state(registry: Any) -> None:
        if hasattr(registry, "reset"):
            registry.reset()
            return
        raise TypeError(f"unsupported registry: {registry!r}")
