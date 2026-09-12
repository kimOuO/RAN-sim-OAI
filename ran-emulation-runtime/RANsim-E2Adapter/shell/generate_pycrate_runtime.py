"""Pre-generate pycrate runtime module from O-RAN ASN.1 schemas.

Runs **once at docker build time** (or manually on dev box). Output 800KB+
file is too big for compile-on-startup; we want adapter to launch in seconds.

Output: main/apps/e2_adapter/services/optional/codec/_generated/pycrate_e2.py

Usage:
  python shell/generate_pycrate_runtime.py
"""
from __future__ import annotations

import io
import os
import pathlib
import sys

# Suppress pycrate compiler chatter
sys.stdout = io.StringIO()

from pycrate_asn1c.asnproc import compile_text  # noqa: E402
from pycrate_asn1c.generator import PycrateGenerator  # noqa: E402

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
ASN1_DIR = REPO_DIR / "asn1"
OUT_DIR = REPO_DIR / "main/apps/e2_adapter/services/optional/codec/_generated"
OUT_FILE = OUT_DIR / "pycrate_e2.py"

SCHEMAS = [
    "e2ap_v2.asn1",
    "e2sm_kpm_v2.0.03.asn",
    "e2sm_rc_v01.03.asn",
]


def main() -> int:
    sys.stdout = sys.__stdout__
    print(f"[gen] schema dir : {ASN1_DIR}", flush=True)
    print(f"[gen] output     : {OUT_FILE}", flush=True)

    missing = [s for s in SCHEMAS if not (ASN1_DIR / s).exists()]
    if missing:
        print(f"[gen] ERROR: missing schemas: {missing}")
        print(f"[gen] Run shell/fetch_asn1_schemas.sh first")
        return 2

    chunks: list[str] = []
    for s in SCHEMAS:
        chunks.append((ASN1_DIR / s).read_text(encoding="utf-8"))
    combined = "\n".join(chunks)

    print("[gen] compile_text() ... (takes ~20-40s)", flush=True)
    sys.stdout = io.StringIO()
    try:
        compile_text(combined)
    finally:
        sys.stdout = sys.__stdout__

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text("", encoding="utf-8")

    print("[gen] PycrateGenerator() ...", flush=True)
    sys.stdout = io.StringIO()
    try:
        PycrateGenerator(dest=str(OUT_FILE))
    finally:
        sys.stdout = sys.__stdout__

    size = OUT_FILE.stat().st_size
    print(f"[gen] OK — wrote {size:,} bytes ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
