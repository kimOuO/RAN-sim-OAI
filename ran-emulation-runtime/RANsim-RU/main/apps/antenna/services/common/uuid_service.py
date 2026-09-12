"""UUID 生成 — backend_rule §14 common service。"""
import hashlib
import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, business_key: str | None = None) -> str:
        """`<prefix>_<key>` 算 SHA1 取前 12 hex；無 key 時退回 uuid4。"""
        if business_key is None or business_key == "":
            return f"{prefix}_{uuid.uuid4().hex[:12]}"
        digest = hashlib.sha1(f"{prefix}:{business_key}".encode()).hexdigest()[:12]
        return f"{prefix}_{digest}"
