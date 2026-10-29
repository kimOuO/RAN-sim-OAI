#!/usr/bin/env python3
"""P0 資料面 PoC:比對 iperf3 實測吞吐與 DT 回報的吞吐。

DT 的值是階梯函數(每筆量測一直有效到下一筆),對每個 iperf3 區間取時間加權平均。
指標:
  - MAPE:平均絕對百分比誤差(只算 DT > 0 的區間,跳過開頭 --warmup-s 秒)
  - corr:Pearson 相關係數
  - lag:實測相對 DT 落後多少秒時誤差最小(在 ±--max-lag-s 內搜尋)
  - 總量比:實測總 byte / DT 總 byte

用法:python3 compare.py out/<SCENARIO>_<時間>
產出:同目錄下的 summary.md、aligned_<kind>.csv,有 matplotlib 時另出 plot_<kind>.png
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def load_dt(path: Path) -> list[tuple[float, float]]:
    """回傳 [(秒, dl_mbps)],只取有量測值的列。"""
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["dt_dl_mbps"] != "":
                out.append((int(r["wall_ms"]) / 1000.0, float(r["dt_dl_mbps"])))
    return out


def load_iperf(path: Path) -> list[tuple[float, float, float]]:
    """回傳 [(開始秒, 結束秒, mbps)],時間為 epoch 秒。"""
    d = json.loads(path.read_text())
    if "error" in d:
        raise RuntimeError(f"{path.name}:{d['error']}")
    # timesecs 只到整秒(最多差 1 s);有 run_poc.sh 另存的精確起點就用它
    start_file = path.with_suffix(".start")
    t0 = float(start_file.read_text()) if start_file.exists() else float(d["start"]["timestamp"]["timesecs"])
    return [(t0 + iv["sum"]["start"], t0 + iv["sum"]["end"], iv["sum"]["bits_per_second"] / 1e6)
            for iv in d["intervals"]]


def dt_avg(dt: list[tuple[float, float]], a: float, b: float) -> float | None:
    """DT 階梯函數在 [a, b) 的時間加權平均;a 之前沒有任何量測時回 None。"""
    if not dt or dt[0][0] > a:
        return None
    total = 0.0
    for i, (t, v) in enumerate(dt):
        nxt = dt[i + 1][0] if i + 1 < len(dt) else math.inf
        lo, hi = max(a, t), min(b, nxt)
        if hi > lo:
            total += v * (hi - lo)
    return total / (b - a)


def metrics(pairs: list[tuple[float, float]]) -> dict[str, float]:
    meas = [m for m, _ in pairs]
    ref = [r for _, r in pairs]
    n = len(pairs)
    nz = [(m, r) for m, r in pairs if r > 0]
    mape = sum(abs(m - r) / r for m, r in nz) / len(nz) * 100 if nz else math.nan
    mae = sum(abs(m - r) for m, r in pairs) / n if n else math.nan
    mm, mr = sum(meas) / n, sum(ref) / n
    sm = math.sqrt(sum((x - mm) ** 2 for x in meas))
    sr = math.sqrt(sum((x - mr) ** 2 for x in ref))
    corr = sum((x - mm) * (y - mr) for x, y in pairs) / (sm * sr) if sm and sr else math.nan
    ratio = sum(meas) / sum(ref) if sum(ref) else math.nan
    return {"n": n, "mape_pct": mape, "mae_mbps": mae, "corr": corr, "volume_ratio": ratio,
            "mean_meas_mbps": mm, "mean_dt_mbps": mr}


def align(dt, iperf, lag: float, warmup: float):
    start = iperf[0][0] if iperf else 0.0
    rows = []
    for a, b, m in iperf:
        if a - start < warmup:
            continue
        ref = dt_avg(dt, a - lag, b - lag)
        if ref is not None:
            rows.append((a, b, m, ref))
    return rows


def best_lag(dt, iperf, warmup: float, max_lag: float, step: float = 0.1) -> float:
    best, best_mae = 0.0, math.inf
    k = int(round(max_lag / step))
    for i in range(-k, k + 1):
        lag = i * step
        rows = align(dt, iperf, lag, warmup)
        if len(rows) < 10:
            continue
        mae = sum(abs(m - r) for _, _, m, r in rows) / len(rows)
        if mae < best_mae:
            best, best_mae = lag, mae
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--warmup-s", type=float, default=2.0, help="跳過開頭秒數(TCP 慢啟動)")
    ap.add_argument("--max-lag-s", type=float, default=2.0)
    args = ap.parse_args()

    lines = [f"# P0 比對結果:{args.run_dir.name}", "",
             "| 測試 | 區間數 | 實測平均 Mbps | DT 平均 Mbps | MAPE % | MAE Mbps | corr | 總量比 | lag s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for kind in ("udp", "tcp"):
        sp, ip = args.run_dir / f"shaper_{kind}.csv", args.run_dir / f"iperf_{kind}.json"
        if not (sp.exists() and ip.exists()):
            lines.append(f"| {kind} | 缺檔 | | | | | | | |")
            continue
        dt, iperf = load_dt(sp), load_iperf(ip)
        lag = best_lag(dt, iperf, args.warmup_s, args.max_lag_s)
        rows = align(dt, iperf, lag, args.warmup_s)
        if not rows:
            lines.append(f"| {kind} | 0(DT 沒有量測或時間對不上) | | | | | | | |")
            continue
        m = metrics([(meas, ref) for _, _, meas, ref in rows])
        lines.append(f"| {kind} | {m['n']} | {m['mean_meas_mbps']:.2f} | {m['mean_dt_mbps']:.2f} | "
                     f"{m['mape_pct']:.1f} | {m['mae_mbps']:.2f} | {m['corr']:.3f} | "
                     f"{m['volume_ratio']:.3f} | {lag:+.1f} |")
        t0 = rows[0][0]
        with (args.run_dir / f"aligned_{kind}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s", "iperf_mbps", "dt_mbps"])
            for a, b, meas, ref in rows:
                w.writerow([f"{(a + b) / 2 - t0:.2f}", f"{meas:.3f}", f"{ref:.3f}"])
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            continue
        fig, ax = plt.subplots(figsize=(10, 4))
        ts = [(a + b) / 2 - t0 for a, b, _, _ in rows]
        ax.plot(ts, [r for *_, r in rows], label="DT", drawstyle="steps-mid")
        ax.plot(ts, [x for _, _, x, _ in rows], label=f"iperf3 {kind}", alpha=0.8)
        ax.set_xlabel("s")
        ax.set_ylabel("Mbit/s")
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.run_dir / f"plot_{kind}.png", dpi=120)
        plt.close(fig)

    lines += ["", f"warmup {args.warmup_s}s;lag 正值代表實測落後 DT。"]
    (args.run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
