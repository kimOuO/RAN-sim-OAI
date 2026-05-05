"""Generic SQL CRUD（同 antenna 版）。"""
from typing import Any


class SqlDbBusinessService:
    @staticmethod
    def create_entity(model_class, data: dict):
        return model_class.objects.create(**data)

    @staticmethod
    def get_entity(model_class, **kwargs) -> Any:
        return model_class.objects.get(**kwargs)

    @staticmethod
    def upsert_entity(model_class, lookup: dict, defaults: dict):
        obj, _ = model_class.objects.update_or_create(**lookup, defaults=defaults)
        return obj

    @staticmethod
    def update_entity(model_class, lookup: dict, data: dict):
        model_class.objects.filter(**lookup).update(**data)
        return model_class.objects.get(**lookup)
