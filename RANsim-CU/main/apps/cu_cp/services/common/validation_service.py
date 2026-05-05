"""Domain validation helpers used by serializers / actors."""
from __future__ import annotations

import re

_UE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class ValidationError(ValueError):
    """Raised when a domain value fails validation."""


class ValidationService:
    @staticmethod
    def validate_ue_id(ue_id: str) -> str:
        if not isinstance(ue_id, str) or not _UE_ID_RE.match(ue_id):
            raise ValidationError(f"invalid ue_id: {ue_id!r}")
        return ue_id

    @staticmethod
    def validate_pci(pci: int) -> int:
        if not isinstance(pci, int) or not (0 <= pci <= 1007):
            raise ValidationError(f"pci out of NR range [0,1007]: {pci}")
        return pci

    @staticmethod
    def validate_5qi(qos_5qi: int) -> int:
        if not isinstance(qos_5qi, int) or not (1 <= qos_5qi <= 254):
            raise ValidationError(f"5QI out of range [1,254]: {qos_5qi}")
        return qos_5qi
