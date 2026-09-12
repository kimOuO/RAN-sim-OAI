"""Serialize / deserialize helpers — 把 dataclass 跟 dict 互轉。

支援 nested dataclass、list[dataclass]、Optional 欄位。
"""
from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from typing import Any, Type, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_dict(obj: Any) -> Any:
    """把 dataclass（含 nested）轉成 plain dict。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def from_dict(cls: Type[T], data: Any) -> T:
    """把 dict 還原成 dataclass，自動處理 nested 跟 list[dataclass]。"""
    if data is None:
        return None  # type: ignore[return-value]
    if not is_dataclass(cls):
        return data  # primitive

    # 取 type hints 處理 forward reference
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = {f.name: f.type for f in fields(cls)}

    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        v = data[f.name]
        f_type = hints.get(f.name, f.type)
        kwargs[f.name] = _convert(v, f_type)
    return cls(**kwargs)  # type: ignore[return-value]


def _convert(value: Any, target_type: Any) -> Any:
    """遞迴 convert，處理 list[X] / Optional[X] / dataclass。"""
    if value is None:
        return None
    origin = get_origin(target_type)
    args = get_args(target_type)

    # Optional[X] / Union[X, None]
    if origin is type(None) or (origin is None and target_type is type(None)):
        return value

    # list[X]
    if origin is list and args:
        inner = args[0]
        if is_dataclass(inner):
            return [from_dict(inner, x) for x in value]
        return list(value)

    # dict[str, X]
    if origin is dict:
        return dict(value)

    # Direct dataclass
    if is_dataclass(target_type):
        if isinstance(value, dict):
            return from_dict(target_type, value)
        return value

    return value
