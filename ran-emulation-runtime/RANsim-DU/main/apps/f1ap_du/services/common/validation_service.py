from __future__ import annotations


class ValidationService:
    @staticmethod
    def require_non_empty(value, field_name: str) -> None:
        if value is None or value == "":
            raise ValueError(f"{field_name} is required")
