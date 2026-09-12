"""Validation helpers for cu_up."""
from __future__ import annotations

import re

_UE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class ValidationError(ValueError):
    pass


class ValidationService:
    @staticmethod
    def validate_ue_id(ue_id: str) -> str:
        if not isinstance(ue_id, str) or not _UE_ID_RE.match(ue_id):
            raise ValidationError(f"invalid ue_id: {ue_id!r}")
        return ue_id

    @staticmethod
    def validate_drb_id(drb_id: int) -> int:
        if not isinstance(drb_id, int) or not (1 <= drb_id <= 32):
            raise ValidationError(f"drb_id out of range [1,32]: {drb_id}")
        return drb_id
