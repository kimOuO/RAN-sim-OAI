"""Deterministic UUID generation for cu_cp entities."""
from __future__ import annotations

import hashlib
import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, key: str | int) -> str:
        """Stable UUID derived from (prefix, key). Same input → same output."""
        seed = f"{prefix}:{key}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"{prefix}-{digest[:32]}"

    @staticmethod
    def random_uuid() -> str:
        return uuid.uuid4().hex
