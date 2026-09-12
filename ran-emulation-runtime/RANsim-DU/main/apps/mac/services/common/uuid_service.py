"""UUID 生成 — 同一個 entity_id 永遠對到同一個 uuid (deterministic)。"""
from __future__ import annotations

import hashlib
import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, key: str) -> str:
        """以 SHA1(prefix:key) 截 hex 32 字元產生 deterministic uuid。"""
        h = hashlib.sha1(f"{prefix}:{key}".encode()).hexdigest()
        return f"{prefix}-{h[:32]}"

    @staticmethod
    def random_uuid() -> str:
        return uuid.uuid4().hex
