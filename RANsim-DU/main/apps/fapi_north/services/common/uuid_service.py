from __future__ import annotations

import hashlib


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, key: str) -> str:
        return f"{prefix}-{hashlib.sha1(f'{prefix}:{key}'.encode()).hexdigest()[:32]}"
