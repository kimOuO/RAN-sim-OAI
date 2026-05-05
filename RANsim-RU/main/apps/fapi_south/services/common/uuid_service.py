import hashlib
import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, business_key: str | None = None) -> str:
        if business_key is None or business_key == "":
            return f"{prefix}_{uuid.uuid4().hex[:12]}"
        return f"{prefix}_{hashlib.sha1(f'{prefix}:{business_key}'.encode()).hexdigest()[:12]}"
