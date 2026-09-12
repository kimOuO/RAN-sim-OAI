"""Validation common service — 留 placeholder；主要驗證已由 DRF Serializer 完成。"""


class ValidationService:
    @staticmethod
    def is_nonempty_str(value) -> bool:
        return isinstance(value, str) and value != ""
