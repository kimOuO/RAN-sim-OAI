"""環境變數載入器 — 鐵則 8-3：禁止 os.getenv()，統一從這裡取。"""
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=False)


class EnvLoadError(RuntimeError):
    pass


def get_str(key: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(key, default)
    if required and (value is None or value == ""):
        raise EnvLoadError(f"Required env var missing: {key}")
    return value or ""


def get_int(key: str, default: int | None = None, *, required: bool = False) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        if required:
            raise EnvLoadError(f"Required env var missing: {key}")
        return default if default is not None else 0
    try:
        return int(raw)
    except ValueError as exc:
        raise EnvLoadError(f"Env var {key}={raw!r} is not a valid int") from exc


def get_float(key: str, default: float | None = None, *, required: bool = False) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        if required:
            raise EnvLoadError(f"Required env var missing: {key}")
        return default if default is not None else 0.0
    try:
        return float(raw)
    except ValueError as exc:
        raise EnvLoadError(f"Env var {key}={raw!r} is not a valid float") from exc


def get_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def get_list(key: str, default: list[str] | None = None, *, sep: str = ",") -> list[str]:
    raw = os.environ.get(key, "")
    if raw == "":
        return default or []
    return [item.strip() for item in raw.split(sep) if item.strip()]
