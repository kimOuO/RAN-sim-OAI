"""Generic SQL CRUD — backend_rule §5-3：通用方法，不為單一 Model 寫專門方法。"""
from typing import Any


class SqlDbBusinessService:
    @staticmethod
    def create_entity(model_class, data: dict):
        return model_class.objects.create(**data)

    @staticmethod
    def get_entity(model_class, **kwargs) -> Any:
        return model_class.objects.get(**kwargs)

    @staticmethod
    def filter_entities(model_class, **kwargs):
        return model_class.objects.filter(**kwargs)

    @staticmethod
    def list_entities(model_class):
        return model_class.objects.all()

    @staticmethod
    def latest_entity(model_class, field: str):
        return model_class.objects.latest(field)

    @staticmethod
    def update_entity(model_class, lookup: dict, data: dict):
        model_class.objects.filter(**lookup).update(**data)
        return model_class.objects.get(**lookup)

    @staticmethod
    def upsert_entity(model_class, lookup: dict, defaults: dict):
        obj, _ = model_class.objects.update_or_create(**lookup, defaults=defaults)
        return obj

    @staticmethod
    def delete_entities(model_class, **kwargs) -> int:
        deleted, _ = model_class.objects.filter(**kwargs).delete()
        return deleted
