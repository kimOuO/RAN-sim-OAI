"""fapi_north 不持久化 wire message,但依 rule §14-2 保留 business service。"""
from __future__ import annotations


class RelationalDbBusinessService:
    @staticmethod
    def noop() -> None:
        return None
