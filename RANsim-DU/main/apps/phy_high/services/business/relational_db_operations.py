"""phy_high 沒有 Model 持久化,但保留 business service 滿足 rule §14-2。"""
from __future__ import annotations


class RelationalDbBusinessService:
    @staticmethod
    def noop() -> None:
        return None
