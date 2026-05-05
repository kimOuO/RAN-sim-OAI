"""UUID helper for cu_up — same contract as cu_cp's UUIDService."""
from __future__ import annotations

import hashlib
import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, key: str | int) -> str:
        seed = f"{prefix}:{key}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"{prefix}-{digest[:32]}"

    @staticmethod
    def random_uuid() -> str:
        return uuid.uuid4().hex
