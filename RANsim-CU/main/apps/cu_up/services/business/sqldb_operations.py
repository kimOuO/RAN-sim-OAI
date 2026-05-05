"""Generic SQL DB CRUD for cu_up — same contract as cu_cp's."""
from __future__ import annotations

from typing import Any

from django.db.models import Model, QuerySet


class SqlDbBusinessService:
    @staticmethod
    def create_entity(model_class: type[Model], validated_data: dict[str, Any]) -> Model:
        return model_class.objects.create(**validated_data)

    @staticmethod
    def get_entity(model_class: type[Model], lookup_field: str, lookup_value: Any) -> Model:
        return model_class.objects.get(**{lookup_field: lookup_value})

    @staticmethod
    def get_or_none(model_class: type[Model], lookup_field: str, lookup_value: Any) -> Model | None:
        return model_class.objects.filter(**{lookup_field: lookup_value}).first()

    @staticmethod
    def list_entities(model_class: type[Model], **filters: Any) -> QuerySet:
        return model_class.objects.filter(**filters)

    @staticmethod
    def update_entity(
        model_class: type[Model],
        lookup_field: str,
        lookup_value: Any,
        update_data: dict[str, Any],
    ) -> Model:
        instance = model_class.objects.get(**{lookup_field: lookup_value})
        for k, v in update_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance

    @staticmethod
    def upsert_entity(
        model_class: type[Model],
        lookup_field: str,
        lookup_value: Any,
        defaults: dict[str, Any],
    ) -> tuple[Model, bool]:
        return model_class.objects.update_or_create(
            **{lookup_field: lookup_value},
            defaults=defaults,
        )

    @staticmethod
    def upsert_compound(
        model_class: type[Model],
        keys: dict[str, Any],
        defaults: dict[str, Any],
    ) -> tuple[Model, bool]:
        return model_class.objects.update_or_create(**keys, defaults=defaults)

    @staticmethod
    def delete_entity(model_class: type[Model], lookup_field: str, lookup_value: Any) -> int:
        return model_class.objects.filter(**{lookup_field: lookup_value}).delete()[0]
