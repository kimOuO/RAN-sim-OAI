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


# ── 執行期覆寫 ──────────────────────────────────────────────────────────
# 為什麼需要:有些「環境設定」其實是**劇本的一部分**(第 2 題要停用 ANR 自動建立、
# 第 9 題要指定鄰區表容量)。放在環境變數裡的話,改一個值就得重啟容器,
# 而重啟會殺掉正在跑的時間軸、清掉量測歷史、打斷 xApp 的計時 ——
# 佈場的動作反而干擾了被測的系統。
#
# 這一層讓劇本能在運行中覆寫,不必重啟。覆寫寫在檔案而不是行程記憶體,
# 因為讀取端散在多個 worker,各自有獨立的記憶體。
# 用 mtime 判斷是否需要重讀,避免每次讀值都碰檔案內容。
_OVERRIDE_PATH = Path("/app/tmp/env_override.json")
_ov_cache: dict[str, Any] = {}
_ov_mtime: float = -1.0


def _overrides() -> dict[str, Any]:
    global _ov_cache, _ov_mtime
    try:
        m = _OVERRIDE_PATH.stat().st_mtime
    except OSError:
        if _ov_mtime != -1.0:
            _ov_cache, _ov_mtime = {}, -1.0
        return _ov_cache
    if m != _ov_mtime:
        import json as _j
        try:
            _ov_cache = _j.loads(_OVERRIDE_PATH.read_text()) or {}
        except (OSError, ValueError):
            _ov_cache = {}
        _ov_mtime = m
    return _ov_cache


def set_overrides(values: dict[str, Any], *, replace: bool = False) -> dict[str, Any]:
    """劇本設定執行期覆寫。replace=True 先清掉舊的(換場景時用,防跨場污染)。"""
    import json as _j
    import os as _os
    import tempfile
    cur = {} if replace else dict(_overrides())
    cur.update({k: v for k, v in values.items() if v is not None})
    try:
        _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(_OVERRIDE_PATH.parent))
        with _os.fdopen(fd, "w") as f:
            _j.dump(cur, f)
        _os.replace(tmp, _OVERRIDE_PATH)
    except OSError:
        pass
    return cur


def clear_overrides() -> None:
    import os as _os
    try:
        _os.remove(_OVERRIDE_PATH)
    except OSError:
        pass


class EnvVarMissing(RuntimeError):
    """Raised when a required env var is absent."""


def get_str(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and (val is None or val == ""):
        raise EnvVarMissing(f"required env var {key!r} is missing or empty")
    return "" if val is None else val


def get_int(key: str, default: int | None = None, *, required: bool = False) -> int:
    ov = _overrides()
    if key in ov:
        try:
            return int(ov[key])
        except (TypeError, ValueError):
            pass
    raw = os.environ.get(key)
    if raw is None or raw == "":
        if required:
            raise EnvVarMissing(f"required env var {key!r} is missing")
        if default is None:
            raise EnvVarMissing(f"env var {key!r} has no default")
        return default
    # 2026-05-16: 認 hex prefix "0x..." (TAC=0xa000 等對齊 OAI 慣例);其餘走十進制。
    s = raw.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s)


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
    ov = _overrides()
    if key in ov:
        v = ov[key]
        return bool(v) if isinstance(v, bool) else str(v).strip().lower() in _TRUTHY
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
