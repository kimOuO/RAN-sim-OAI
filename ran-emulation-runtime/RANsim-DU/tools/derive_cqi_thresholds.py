#!/usr/bin/env python3
"""由 OAI AWGN BLER 曲線推導 CQI 切點,寫進共用套件 ran_sim_protocol/nr_link_tables.py。

推導規則見 main/apps/mac/services/optional/link_adaptation/cqi_table.py。
換了 BLER 曲線(tools/import_oai_bler.py)之後要重跑這支,否則 DU 單元測試
test_cqi_table 會因為表與曲線不一致而失敗。

用法(在 DU 容器內,/app 為 RANsim-DU,/opt/ran-sim-protocol 為共用套件):
    python tools/derive_cqi_thresholds.py                 # 只印出
    python tools/derive_cqi_thresholds.py --write /opt/ran-sim-protocol/ran_sim_protocol/nr_link_tables.py
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.test")

from main.apps.mac.services.optional.link_adaptation.cqi_table import derive_cqi_thresholds  # noqa: E402

_BLOCK = re.compile(r"(CQI_SINR_THRESHOLDS_DB: tuple\[float, \.\.\.\] = \(\n    -math\.inf,\n)(.*?)(\n\))", re.S)


def _render(th: tuple[float, ...]) -> str:
    vals = [f"{v:.2f}" for v in th[1:]]
    lines = ["    " + ", ".join(vals[i:i + 8]) + "," for i in range(0, len(vals), 8)]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", type=Path, help="要改寫的 nr_link_tables.py")
    args = ap.parse_args()
    th = derive_cqi_thresholds()
    for i, v in enumerate(th):
        print(f"CQI {i:2d}: {'-inf' if math.isinf(v) else f'{v:6.2f} dB'}")
    if args.write:
        src = args.write.read_text()
        new, n = _BLOCK.subn(lambda m: m.group(1) + _render(th) + m.group(3), src)
        if n != 1:
            print(f"找不到 CQI_SINR_THRESHOLDS_DB 區塊:{args.write}", file=sys.stderr)
            return 1
        args.write.write_text(new)
        print(f"已寫入 {args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
