"""Generic SQL DB CRUD — Business Service per backend_rule §5-3.

Iron rule: never write per-Model methods here. All callers pass ``model_class``.
"""
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
        # 2026-09-27:只寫這次要改的欄位。以前 save() 寫回整列 —— 同一個 UE 的量測報告、
        # 流量設定、換手、AMF 的 Initial Context Setup 同時在寫時,後存的一方會用它讀到的
        # 舊值蓋掉別人剛寫的欄位(實測:UE 的 traffic profile 被蓋回 {} 整場沒流量;
        # serving cell 被蓋回舊值,CU 與 DU 認知不同 → 每秒一次假 RLF)。
        instance.save(update_fields=list(update_data.keys()))
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
    def delete_entity(model_class: type[Model], lookup_field: str, lookup_value: Any) -> int:
        return model_class.objects.filter(**{lookup_field: lookup_value}).delete()[0]
