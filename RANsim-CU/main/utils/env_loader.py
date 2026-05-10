"""Centralised environment-variable loader.

Iron rule: nowhere in the project may call ``os.getenv()`` directly. Always
import from this module so behaviour is uniform and testable.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BASE_DIR / ".env")

_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


class EnvVarMissing(RuntimeError):
    """Raised when a required env var is absent."""


def get_str(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and (val is None or val == ""):
        raise EnvVarMissing(f"required env var {key!r} is missing or empty")
    return "" if val is None else val


def get_int(key: str, default: int | None = None, *, required: bool = False) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        if required:
            raise EnvVarMissing(f"required env var {key!r} is missing")
        if default is None:
            raise EnvVarMissing(f"env var {key!r} has no default")
        return default
    return int(raw)


def get_float(key: str, default: float | None = None, *, required: bool = False) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        if required:
            raise EnvVarMissing(f"required env var {key!r} is missing")
        if default is None:
            raise EnvVarMissing(f"env var {key!r} has no default")
        return default
    return float(raw)


def get_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def get_list(key: str, default: list[str] | None = None, sep: str = ",") -> list[str]:
    raw = os.environ.get(key)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(sep) if item.strip()]


def get_url(host_key: str, port_key: str, scheme_key: str = "") -> str:
    """Compose ``scheme://host:port`` from three env keys."""
    host = get_str(host_key)
    port = get_str(port_key)
    scheme = get_str(scheme_key) if scheme_key else "http"
    if not scheme:
        scheme = "http"
    if not host:
        return ""
    if port:
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def default_served_plmn() -> str:
    """Compose served-PLMN string from PLMN_MCC + PLMN_MNC env vars.

    對齊 globalE2node-ID 的 PLMN — sim 內 cell.served_plmn 應該跟 R-NIB
    inventoryName 衍生的 PLMN 一致, 不該寫死 dummy '00101'。
    格式: "<MCC><MNC zero-padded to 2 or 3>". 例: 208/95 → "208095".
    Env 缺值或讀失敗 fallback "00101" 跟舊行為相容 (測試環境用).
    """
    mcc = (get_str("PLMN_MCC", "") or "").strip()
    mnc = (get_str("PLMN_MNC", "") or "").strip()
    if not mcc or not mnc:
        return "00101"
    # MNC 0/1/2 位都常見, 對齊 OAI 慣例 zero-pad 到 2 位 (3 位 MNC 不 pad).
    mnc_padded = mnc if len(mnc) >= 3 else mnc.zfill(2)
    return f"{mcc}{mnc_padded}"


__all__ = [
    "EnvVarMissing",
    "default_served_plmn",
    "get_bool",
    "get_float",
    "get_int",
    "get_list",
    "get_str",
    "get_url",
]
