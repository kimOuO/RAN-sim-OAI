"""Generic input validation helpers — Common Service."""
from __future__ import annotations


class ValidationService:
    @staticmethod
    def is_non_empty_str(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def is_positive_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0
