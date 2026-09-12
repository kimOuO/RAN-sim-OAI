from __future__ import annotations

from typing import Any


class RelationalDbBusinessService:
    @staticmethod
    def upsert_entity(model_class, lookup_field: str, lookup_value: Any, data: dict[str, Any]):
        obj, _ = model_class.objects.update_or_create(
            **{lookup_field: lookup_value}, defaults=data,
        )
        return obj

    @staticmethod
    def get_entity(model_class, lookup_field: str, lookup_value: Any):
        return model_class.objects.filter(**{lookup_field: lookup_value}).first()
