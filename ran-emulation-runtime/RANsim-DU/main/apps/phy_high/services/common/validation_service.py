from __future__ import annotations


class ValidationService:
    @staticmethod
    def require_positive(value: float, field_name: str) -> None:
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
