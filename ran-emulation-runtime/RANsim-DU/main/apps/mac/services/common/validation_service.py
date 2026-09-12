"""通用驗證工具。"""
from __future__ import annotations


class ValidationService:
    @staticmethod
    def require_non_empty(value, field_name: str) -> None:
        if value is None or value == "":
            raise ValueError(f"{field_name} is required")

    @staticmethod
    def require_in_range(value: float, lo: float, hi: float, field_name: str) -> None:
        if value < lo or value > hi:
            raise ValueError(f"{field_name} must be in [{lo}, {hi}], got {value}")
