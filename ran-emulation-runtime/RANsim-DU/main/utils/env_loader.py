"""集中管理環境變數讀取 — 全 repo 嚴禁直接 os.getenv()。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # python-dotenv optional
    _load_dotenv = None


_REPO_ROOT = Path(__file__).resolve().parents[2]
_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    if _load_dotenv is not None:
        env_path = _REPO_ROOT / ".env"
        if env_path.exists():
            _load_dotenv(env_path, override=False)
    _loaded = True


def get_str(key: str, default: str | None = None) -> str:
    _ensure_loaded()
    val = os.environ.get(key)
    if val is None:
        if default is None:
            raise KeyError(f"Required env var missing: {key}")
        return default
    return val


def get_int(key: str, default: int | None = None) -> int:
    raw = get_str(key, None if default is None else str(default))
    return int(raw)


def get_float(key: str, default: float | None = None) -> float:
    raw = get_str(key, None if default is None else str(default))
    return float(raw)


def get_bool(key: str, default: bool = False) -> bool:
    raw = get_str(key, str(default)).lower()
    return raw in ("1", "true", "yes", "on")


def get_list(key: str, default: list[str] | None = None, sep: str = ",") -> list[str]:
    raw = get_str(key, "" if default is None else sep.join(default))
    if not raw:
        return []
    return [x.strip() for x in raw.split(sep) if x.strip()]


def base_dir() -> Path:
    return _REPO_ROOT


def get_any(key: str, default: Any = None) -> Any:
    _ensure_loaded()
    return os.environ.get(key, default)


def default_served_plmn() -> str:
    """Compose served-PLMN string from PLMN_MCC + PLMN_MNC env vars.

    對齊 globalE2node-ID 的 PLMN — sim 內 cell.served_plmn 應該跟 R-NIB
    inventoryName 衍生的 PLMN 一致, 不該寫死 dummy '00101'。
    格式: "<MCC><MNC zero-padded to 2 or 3>". 例: 208/95 → "208095".
    Env 缺值 fallback "00101" 跟舊行為相容 (測試環境用).
    """
    _ensure_loaded()
    mcc = (os.environ.get("PLMN_MCC") or "").strip()
    mnc = (os.environ.get("PLMN_MNC") or "").strip()
    if not mcc or not mnc:
        return "00101"
    mnc_padded = mnc if len(mnc) >= 3 else mnc.zfill(2)
    return f"{mcc}{mnc_padded}"
