from __future__ import annotations

import hashlib


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, key: str) -> str:
        h = hashlib.sha1(f"{prefix}:{key}".encode()).hexdigest()
        return f"{prefix}-{h[:32]}"
