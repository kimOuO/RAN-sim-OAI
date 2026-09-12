"""ASN.1 schema loader — compile O-RAN E2AP / E2SM schemas at startup.

Schema files are bundled in repo at ``asn1/`` and copied into image at /app/asn1/.

Standard versions (per RIC team confirmation 2026-05):
  - e2ap_v2.asn1            (E2AP v2.0.3)
  - e2sm_kpm_v2.0.03.asn    (E2SM-KPM v2.0.03)
  - e2sm_rc_v01.03.asn      (E2SM-RC  v01.03)

Wire encoding rule: APER (Aligned Packed Encoding Rules) per E2AP §5.1.

實作選擇：用 pycrate（OAI/Eurecom 系，跟 RIC team 用的 lib 同源）。
asn1tools 對 ASN.1 information object classes (`PROTOCOL-IES`) 跟 parameterized
types 處理不完整，E2AP schema 會 crash。pycrate 完整支援這兩個 features。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_SCHEMA_DIR = "/app/asn1"

_EXPECTED_FILES = [
    "e2ap_v2.asn1",
    "e2sm_kpm_v2.0.03.asn",
    "e2sm_rc_v01.03.asn",
]

# Module-level cache — first call compiles schemas, later calls return cached
_compiled: dict[str, Any] | None = None
_load_error: str = ""
_loaded_files: list[str] = []


def _schema_dir() -> Path:
    return Path(get_str("ASN1_SCHEMA_DIR", _DEFAULT_SCHEMA_DIR))


def _try_compile(file_paths: list[str]) -> dict[str, Any]:
    """Compile all schemas together with pycrate, return summary dict.

    pycrate compile_text 是 stateful — 把 schemas 合一個 string 餵進去，
    它自動處理 cross-schema typeref（例如 e2sm_rc 引用 NR-CGI from e2ap_v2）。
    """
    from pycrate_asn1c.asnproc import compile_text

    chunks: list[str] = []
    for path in file_paths:
        with open(path, encoding="utf-8") as f:
            chunks.append(f.read())
    combined = "\n".join(chunks)
    compile_text(combined)
    # pycrate 把編好的 module 放在 GLOBAL.MOD 全域字典 — 直接拿最新狀態
    from pycrate_asn1c.glob import GLOBAL
    modules = [m for m in GLOBAL.MOD.keys() if not m.startswith("_")]
    return {"modules": modules, "files": [Path(p).name for p in file_paths]}


def get_schema() -> dict[str, Any] | None:
    """Return compiled schema dict or None if not loaded.

    P2.7b 完成後此方法應該總是回 non-None；asn1/ 還沒填就回 None + error msg。
    """
    global _compiled, _load_error, _loaded_files
    if _compiled is not None:
        return _compiled

    schema_dir = _schema_dir()
    if not schema_dir.exists():
        _load_error = f"schema dir does not exist: {schema_dir}"
        logger.warning(_load_error)
        return None

    found = sorted(p.name for p in schema_dir.iterdir() if p.is_file())
    expected_present = [f for f in _EXPECTED_FILES if f in found]
    if not expected_present:
        _load_error = f"none of expected schemas found in {schema_dir}; have={found}"
        logger.warning(_load_error)
        return None

    try:
        full_paths = [str(schema_dir / f) for f in expected_present]
        _compiled = _try_compile(full_paths)
        _loaded_files = expected_present
        _load_error = ""
        logger.info("ASN.1 schemas compiled OK: %s", expected_present)
        return _compiled
    except Exception as exc:
        _load_error = f"compile failed: {exc!r}"
        logger.exception("ASN.1 schema compile failed")
        return None


def schemas_status() -> dict:
    """For /Status/read — adapter 自報狀態。"""
    spec = get_schema()
    return {
        "loaded": spec is not None,
        "file_list": list(_loaded_files),
        "error": _load_error,
    }
