"""RLC 用通用 SQL DB CRUD (rule §5-3)。"""
from __future__ import annotations

from typing import Any


class RelationalDbBusinessService:
    @staticmethod
    def create_entity(model_class, data: dict[str, Any]):
        return model_class.objects.create(**data)

    @staticmethod
    def get_entity(model_class, lookup_field: str, lookup_value: Any):
        return model_class.objects.filter(**{lookup_field: lookup_value}).first()

    @staticmethod
    def list_entities(model_class, filters: dict[str, Any] | None = None) -> list:
        qs = model_class.objects.all()
        if filters:
            qs = qs.filter(**filters)
        return list(qs)

    @staticmethod
    def update_entity(model_class, lookup_field: str, lookup_value: Any, data: dict[str, Any]):
        return model_class.objects.filter(**{lookup_field: lookup_value}).update(**data)

    @staticmethod
    def delete_entity(model_class, lookup_field: str, lookup_value: Any) -> int:
        deleted, _ = model_class.objects.filter(**{lookup_field: lookup_value}).delete()
        return deleted

    @staticmethod
    def upsert_entity(model_class, lookup_field: str, lookup_value: Any, data: dict[str, Any]):
        obj, _created = model_class.objects.update_or_create(
            **{lookup_field: lookup_value}, defaults=data,
        )
        return obj
