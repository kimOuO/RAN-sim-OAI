class ValidationService:
    @staticmethod
    def require_keys(payload: dict, keys: list[str]) -> list[str]:
        return [k for k in keys if k not in payload]
