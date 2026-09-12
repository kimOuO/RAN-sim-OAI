class ValidationService:
    @staticmethod
    def is_nonempty_str(value) -> bool:
        return isinstance(value, str) and value != ""
