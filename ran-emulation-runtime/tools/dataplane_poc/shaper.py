#!/usr/bin/env python3
"""P0 資料面 PoC:把 DT 對某個 UE 算出的吞吐,套到 veth 的 tc 上。

資料來源:CU ``Logs/TelemetryExportReader/read``(唯讀、游標式匯出,不改 DT 狀態)。
每次輪詢取該 UE 最新一筆 MeasurementLog,依其 ``throughput_dl_mbps`` / ``throughput_ul_mbps``
改寫 htb 速率;延遲與丟包為固定參數(見下)。

前提:測試 UE 的 traffic profile 須為 full-buffer(CBR 高於容量),DT 回報的吞吐才等於通道容量。
不是 full-buffer 時,這裡套上的是「DT 實際服務量」而非容量。

延遲:只加 ``--air-delay-ms``(空中介面單向延遲)。排隊延遲由 tc 佇列自然產生,
不再疊加 DT 的 ``rlc_sdu_delay_dl_ms``(那是 DT 假流量的排隊延遲),只記錄在 CSV 供對照。
丟包:預設 0。HARQ + RLC AM 之後的殘餘丟包在真實系統中趨近 0;BLER 的影響已反映在 DT 吞吐裡。
吞吐為 0(未連線、換手中斷)時套 ``--min-rate-kbit`` 加 100% 丟包,代表無法傳送。
上行預設不整形(``--shape-ul`` 才開):full-buffer 劇本的上行需求是 0,DT 回報的上行吞吐 0 代表「沒有流量」
而不是「沒有容量」;若照套,下行 TCP 的 ACK 會被擋掉。

用法(tc 需 root):
  sudo python3 shaper.py --ue-id <UE> --csv out/shaper.csv
  python3 shaper.py --ue-id <UE> --dry-run      # 只印出 tc 指令,不需 root
"""
from __future__ import annotations

import argparse
import csv
import json
import signal
import subprocess
import sys
import time
import urllib.request

EXPORT_PATH = "/api/v0.1/CU/Logs/TelemetryExportReader/read"
CSV_FIELDS = [
    "wall_ms", "meas_id", "scene_sim_ms", "serving_cell",
    "dt_dl_mbps", "dt_ul_mbps", "mcs_dl", "rb_width_dl", "sinr_db", "dt_rlc_delay_dl_ms",
    "applied_dl_kbit", "applied_ul_kbit", "delay_ms", "loss_pct", "event",
]


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    if not payload.get("success", payload.get("status") == "success"):
        raise RuntimeError(f"CU 回應失敗:{payload.get('message')}")
    return payload["data"]


class TcLink:
    """一個方向的整形:netns 內某張 veth 出口的 htb class 1:10 與其下的 netem 10:。"""

    def __init__(self, ns: str, dev: str, dry_run: bool) -> None:
        self.ns, self.dev, self.dry_run = ns, dev, dry_run
        self.applied: tuple[int, float, float] | None = None

    def _run(self, args: list[str]) -> None:
        cmd = ["ip", "netns", "exec", self.ns, "tc", *args]
        if self.dry_run:
            print("[dry-run]", " ".join(cmd))
            return
        subprocess.run(cmd, check=True, capture_output=True)

    def apply(self, rate_kbit: int, delay_ms: float, loss_pct: float) -> bool:
        """有變化才下 tc,回傳是否有改寫。"""
        target = (rate_kbit, delay_ms, loss_pct)
        if target == self.applied:
            return False
        # burst 取約 5 ms 的量:太小時高速率下 htb 跑不滿,太大會造成一次放出過多
        burst = max(3000, rate_kbit * 1000 // 8 * 5 // 1000)
        self._run(["class", "change", "dev", self.dev, "parent", "1:", "classid", "1:10", "htb",
                   "rate", f"{rate_kbit}kbit", "ceil", f"{rate_kbit}kbit",
                   "burst", str(burst), "cburst", str(burst)])
        netem = ["qdisc", "change", "dev", self.dev, "parent", "1:10", "handle", "10:", "netem",
                 "delay", f"{delay_ms}ms", "limit", "100000"]
        if loss_pct > 0:
            netem += ["loss", f"{loss_pct}%"]
        self._run(netem)
        self.applied = target
        return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ue-id", required=True, help="DT 裡作為鏡像對象的 UE")
    ap.add_argument("--cu-url", default="http://localhost:8101")
    ap.add_argument("--poll-ms", type=int, default=100)
    ap.add_argument("--air-delay-ms", type=float, default=0.0, help="空中介面單向延遲,兩個方向都加")
    ap.add_argument("--loss-pct", type=float, default=0.0)
    ap.add_argument("--min-rate-kbit", type=int, default=8, help="吞吐為 0 時的下限(tc 不接受 0)")
    ap.add_argument("--shape-ul", action="store_true", help="上行也依 DT 的上行吞吐整形")
    ap.add_argument("--stale-s", type=float, default=5.0, help="超過此秒數沒有新資料就警告")
    ap.add_argument("--ue-ns", default="dtpoc-ue1")
    ap.add_argument("--dn-ns", default="dtpoc-dn")
    ap.add_argument("--csv", default="shaper.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url = args.cu_url.rstrip("/") + EXPORT_PATH
    timeout = max(1.0, args.poll_ms / 1000 * 5)
    dl = TcLink(args.dn_ns, "veth-dn", args.dry_run)   # DN → UE
    ul = TcLink(args.ue_ns, "veth-ue", args.dry_run)   # UE → DN

    # 從「現在」開始讀,不回放歷史
    cursor = _post(url, {"max_only": True}, timeout)["cursor"]
    print(f"起始游標 {cursor},鏡像 UE {args.ue_id},每 {args.poll_ms} ms 輪詢", file=sys.stderr)

    stop = False

    def _sig(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    last_seen = time.monotonic()
    warned_stale = False
    with open(args.csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        while not stop:
            t0 = time.monotonic()
            try:
                data = _post(url, {"since": cursor, "limit": 5000}, timeout)
            except Exception as exc:  # CU 暫時不可達時保留上一次的整形值
                print(f"輪詢失敗:{exc}", file=sys.stderr)
                time.sleep(args.poll_ms / 1000)
                continue
            cursor = {**cursor, **data.get("cursor", {})}

            events = [f"ho:{h['source_cell']}->{h['target_cell']}:{h['status']}"
                      for h in data.get("handover", []) if h.get("ue_id") == args.ue_id]
            events += [f"rlf:{r['source_cell']}:{r['reason']}"
                       for r in data.get("rlf", []) if r.get("ue_id") == args.ue_id]
            rows = [m for m in data.get("measurement", []) if m.get("ue_id") == args.ue_id]

            if rows:
                last_seen, warned_stale = time.monotonic(), False
            elif not warned_stale and time.monotonic() - last_seen > args.stale_s:
                print(f"警告:{args.stale_s}s 內沒有 {args.ue_id} 的新量測", file=sys.stderr)
                warned_stale = True

            if rows or events:
                m = rows[-1] if rows else {}
                dl_mbps = float(m.get("throughput_dl_mbps") or 0.0) if rows else None
                ul_mbps = float(m.get("throughput_ul_mbps") or 0.0) if rows else None
                if rows:
                    links = [(dl, dl_mbps)] + ([(ul, ul_mbps)] if args.shape_ul else [])
                    for link, mbps in links:
                        if mbps > 0:
                            link.apply(max(args.min_rate_kbit, int(mbps * 1000)), args.air_delay_ms, args.loss_pct)
                        else:
                            link.apply(args.min_rate_kbit, args.air_delay_ms, 100.0)
                w.writerow({
                    "wall_ms": int(time.time() * 1000),
                    "meas_id": m.get("id", ""), "scene_sim_ms": m.get("scene_sim_ms", ""),
                    "serving_cell": m.get("serving_cell", ""),
                    "dt_dl_mbps": "" if dl_mbps is None else dl_mbps,
                    "dt_ul_mbps": "" if ul_mbps is None else ul_mbps,
                    "mcs_dl": m.get("mcs_dl", ""), "rb_width_dl": m.get("rb_width_dl", ""),
                    "sinr_db": m.get("sinr_db", ""), "dt_rlc_delay_dl_ms": m.get("rlc_sdu_delay_dl_ms", ""),
                    "applied_dl_kbit": dl.applied[0] if dl.applied else "",
                    "applied_ul_kbit": ul.applied[0] if ul.applied else "",
                    "delay_ms": args.air_delay_ms,
                    "loss_pct": dl.applied[2] if dl.applied else "",
                    "event": ";".join(events),
                })
                fh.flush()

            time.sleep(max(0.0, args.poll_ms / 1000 - (time.monotonic() - t0)))
    print("shaper 結束", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
