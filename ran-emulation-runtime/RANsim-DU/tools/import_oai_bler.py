#!/usr/bin/env python3
"""把 OAI 官方 NR AWGN link-level BLER 曲線轉成 DT 的 bler_curve.csv。

來源(OAI 官方 repo,隨 openairinterface5g 發佈):
    openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/AWGN_results/mcs{N}_awgn_5G.csv

產生方法(見來源目錄 README.md):
    "The tables result from an exponential effective SINR mapping (EESM) and
     comparison to MATLAB link-level simulation models."
    → 這些是 AWGN 通道的 link-level 模擬結果;衰落通道的 BLER 由
      per-RB SINR 經 EESM 壓成 effective SINR 後查同一張表取得。

為什麼取 SISO(AWGN_results)而不是 MIMO 2x2(AWGN_MIMO2x2_results):
    AWGN 曲線是「每一層」的原語。MIMO 增益在本模擬中顯式建模為
    (a) TBS × 層數、(b) 每層 SINR 因等功率分配而下降,
    而非換一張把 2x2 效應預先吸收的表。用 MIMO 表會讓 rank 1/2 共用同一條
    曲線 → 看不出天線選擇的差異,且只在 2x2 成立。

輸入格式: SNR;MCS;TBS;rate;err0;trials0;err1;trials1;...
    err0/trials0 = 首傳(initial transmission)的錯誤數/試驗數 → 首傳 BLER。
    後續 errN/trialsN 是第 N 次 HARQ 重傳,本模型的 link adaptation 操作點
    只需要首傳 BLER(對齊 OAI target_dl_bler)。

輸出格式: mcs,sinr_db,bler  —— ldpc_abstract._load_curve() 直接吃。

用法:
    python3 tools/import_oai_bler.py \
        --src /home/mitlab/openairinterface5g/openair1/SIMULATION/NR_PHY/BLER_SIMULATIONS/AWGN/AWGN_results \
        --out main/apps/phy_high/data/bler_curve.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

FNAME_RE = re.compile(r"mcs(\d+)_awgn_5G\.csv$")


def parse_one(path: Path, mcs: int) -> list[tuple[float, float]]:
    """回傳 [(sinr_db, bler), ...],依 SNR 升冪、去重。"""
    pts: dict[float, float] = {}
    with path.open() as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                snr = float(row["SNR"])
                err = float(row["err0"])
                trials = float(row["trials0"])
            except (KeyError, TypeError, ValueError):
                continue
            if trials <= 0:
                continue
            # 同一 SNR 出現多次 → 累加後再算(OAI 檔內偶有重複點)
            prev = pts.get(snr)
            bler = max(0.0, min(1.0, err / trials))
            pts[snr] = bler if prev is None else min(prev, bler)
    return sorted(pts.items())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    if not args.src.is_dir():
        print(f"ERROR: src not a directory: {args.src}", file=sys.stderr)
        return 1

    rows: list[tuple[int, float, float]] = []
    found: list[int] = []
    for p in sorted(args.src.glob("mcs*_awgn_5G.csv")):
        m = FNAME_RE.search(p.name)
        if not m:
            continue
        mcs = int(m.group(1))
        pts = parse_one(p, mcs)
        if not pts:
            print(f"WARN: no usable points in {p.name}", file=sys.stderr)
            continue
        found.append(mcs)
        for snr, bler in pts:
            rows.append((mcs, snr, bler))

    if not rows:
        print("ERROR: nothing parsed", file=sys.stderr)
        return 1

    rows.sort(key=lambda r: (r[0], r[1]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mcs", "sinr_db", "bler"])
        for mcs, snr, bler in rows:
            w.writerow([mcs, f"{snr:g}", f"{bler:.6g}"])

    found.sort()
    print(f"wrote {len(rows)} rows to {args.out}")
    print(f"MCS covered: {found[0]}..{found[-1]} ({len(found)} tables)")
    missing = sorted(set(range(found[0], found[-1] + 1)) - set(found))
    if missing:
        print(f"WARN: missing MCS: {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
