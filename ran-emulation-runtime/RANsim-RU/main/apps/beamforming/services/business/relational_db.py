"""Generic SQL CRUD（同 antenna 版，beamforming 沒 model 但保留契合 §5-5）。"""
from typing import Any


class SqlDbBusinessService:
    @staticmethod
    def create_entity(model_class, data: dict):
        return model_class.objects.create(**data)

    @staticmethod
    def get_entity(model_class, **kwargs) -> Any:
        return model_class.objects.get(**kwargs)
