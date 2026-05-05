"""根據 mode 字串產生對應 RLC entity instance。"""
from __future__ import annotations

from main.apps.rlc.services.optional.entities.am_entity import AmEntity
from main.apps.rlc.services.optional.entities.tm_entity import TmEntity
from main.apps.rlc.services.optional.entities.um_entity import UmEntity


def make_entity(mode: str, sn_field_length: int = 12):
    mode_u = mode.upper()
    if mode_u == "AM":
        return AmEntity(sn_field_length=sn_field_length)
    if mode_u == "UM":
        return UmEntity(sn_field_length=sn_field_length)
    if mode_u == "TM":
        return TmEntity()
    raise ValueError(f"unknown RLC mode: {mode}")


# Module-level singleton registry: 所有 active RLC entity 在這。
# Key = (ue_id, bearer_type, bearer_id),value = entity instance。
_registry: dict[tuple[str, str, int], object] = {}


def register(ue_id: str, bearer_type: str, bearer_id: int, entity) -> None:
    _registry[(ue_id, bearer_type, bearer_id)] = entity


def lookup(ue_id: str, bearer_type: str, bearer_id: int):
    return _registry.get((ue_id, bearer_type, bearer_id))


def unregister(ue_id: str, bearer_type: str, bearer_id: int) -> None:
    _registry.pop((ue_id, bearer_type, bearer_id), None)


def unregister_ue(ue_id: str) -> None:
    keys = [k for k in _registry if k[0] == ue_id]
    for k in keys:
        _registry.pop(k, None)


def all_entities() -> list[tuple[tuple[str, str, int], object]]:
    return list(_registry.items())
