import uuid


class UUIDService:
    @staticmethod
    def generate_uuid(prefix: str, seed: str = "") -> str:
        return f"{prefix}-{uuid.uuid4().hex}"
