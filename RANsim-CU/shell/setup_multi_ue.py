#!/usr/bin/env python3
"""把 sim 從 1 UE 變成多 UE 不均勻分布 — 為 IM 真實觸發 + CCO cell-level demo 鋪路.

目標 cell-level 負載分布 (對應 intents-interface.md):
  gnb4_c0  ★ HOT  : 8 UEs each 20 Mbps demand → cell PRB 滿載, per-UE Thp 低 (<5M 容易達)
                    → IM 三條件 (PRB>70 + Thp<5k + Delay>50) 真實觸發
  gnb4_c1     warm : 4 UEs each 5 Mbps
  gnb4_c2     cold : 1 UE   1 Mbps
  gnb4_c3   ★ idle : 0 UE
                    → CCO cell-level 負載差距 (hot 100% vs cold 0%) 觸發 demo 條件

每個 UE:
  - rrc_state=CONNECTED, serving_cell 指定
  - amf_ue_ngap_id deterministic (從 ue_id hash)
  - traffic_profile CBR rate
  - DU register + RLC entity + tick.start (CU update_traffic_profile 鏈自動觸發)
  - UE container per-UE thread (Lifecycle/sync attach 觸發)

Usage:
  python3 setup_multi_ue.py [--dry-run]  # 預覽 plan 不執行
  python3 setup_multi_ue.py              # 真執行
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

CU_BASE = "http://localhost:8101"
DU_BASE = "http://localhost:8102"
UE_BASE = "http://localhost:8105"

# (cell_id, count, rate_mbps_per_ue)
# AK12: 4 cell 都有 UE, 各自不同 traffic load 展示 cell-level KPM 差異
UE_PLAN = [
    ("gnb4_c0", 4, 30.0),   # east   high traffic
    ("gnb4_c1", 3, 10.0),   # north  medium
    ("gnb4_c2", 3,  5.0),   # west   low
    ("gnb4_c3", 3,  1.0),   # south  minimal
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post(url: str, body: dict, timeout: float = 5.0) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode("utf-8", errors="replace")[:200]}
    except Exception as exc:
        return {"_error": repr(exc)}


def _stable_ngap_id(ue_id: str) -> int:
    """跟 sim CU f1ap_router_actor.py:208 同算法: abs(hash(ue_id)) % 2^31."""
    return abs(hash(ue_id)) % (2 ** 31)


def insert_ue_via_db(ue_id: str, serving_cell: str, ngap_id: int) -> bool:
    """直接 SQL INSERT UeContext (sim CU mock AMF 沒提供 attach API 給外部呼叫)."""
    import subprocess
    sql = f"""
    INSERT INTO cu_cp_ue_context
      (ue_uuid, ue_id, rrc_state, serving_cell, rrc_ue_id, ran_ue_ngap_id, amf_ue_ngap_id,
       traffic_profile_json, created_at, updated_at)
    VALUES
      ('ue-{ue_id}-{int(time.time())}', '{ue_id}', 'CONNECTED', '{serving_cell}',
       {ngap_id}, {ngap_id}, {ngap_id + 1},
       '{{}}',
       NOW(), NOW())
    ON CONFLICT (ue_id) DO UPDATE SET
      rrc_state='CONNECTED',
      serving_cell='{serving_cell}',
      amf_ue_ngap_id={ngap_id + 1},
      ran_ue_ngap_id={ngap_id},
      updated_at=NOW();
    """
    cmd = ["docker", "exec", "ransim-postgres", "psql", "-U", "ransim", "-d", "cu_db",
           "-c", sql]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"  ✗ DB insert failed: {result.stderr.strip()[:200]}")
            return False
        return True
    except Exception as exc:
        print(f"  ✗ DB insert exception: {exc}")
        return False


def set_traffic_profile(ue_id: str, rate_mbps: float) -> bool:
    body = {
        "ue_id": ue_id,
        "traffic_profile": {
            "pattern": "cbr",
            "rate_mbps": rate_mbps,
            "sdu_size": 1500,
            "bearer_id": 1,
        },
    }
    resp = _post(f"{CU_BASE}/api/v0.1/CU/Session/SessionController/update_traffic_profile", body)
    return resp.get("success", False)


def du_register_ue(ue_id: str, serving_cell: str) -> bool:
    resp = _post(f"{DU_BASE}/api/v0.1/DU/Tick/TickController/register_ue",
                 {"ue_id": ue_id, "serving_cell": serving_cell})
    return resp.get("status") == "success" or resp.get("success", False)


def du_create_rlc(ue_id: str, bearer_id: int = 1) -> bool:
    resp = _post(f"{DU_BASE}/api/v0.1/DU/RLC/RlcEntityController/create",
                 {"ue_id": ue_id, "bearer_type": "DRB", "bearer_id": bearer_id, "mode": "AM"})
    return resp.get("status") == "success" or resp.get("success", False)


def ue_container_attach(ue_id: str) -> bool:
    resp = _post(f"{UE_BASE}/api/v0.1/UE/Lifecycle/sync",
                 {"event": "attach", "ue_id": ue_id})
    return resp.get("success", False)


# AK12: 4 cluster 各自貼 cell beam 方向 (Sionna azimuth 對應)
#   c0 east(+X), c1 north(+Z), c2 west(-X), c3 south(-Z)
_CELL_CENTER = {
    "gnb4_c0": (200.0, 1.5, 0.0),    # east
    "gnb4_c1": (0.0, 1.5, 200.0),    # north
    "gnb4_c2": (-200.0, 1.5, 0.0),   # west
    "gnb4_c3": (0.0, 1.5, -200.0),   # south
}

def ue_set_static_position(ue_id: str, serving_cell: str, idx: int) -> bool:
    """以 cell center 為 anchor, idx 偏移避免 UE 重疊 (Y-up, 偏移在 X / Z 水平面)."""
    cx, cy, cz = _CELL_CENTER.get(serving_cell, (0.0, 1.5, 0.0))
    # idx 0..N spread 在 cell 水平 X-Z 周圍 5m 範圍, Y(高度) 保持 cy.
    offset_x = (idx % 4) * 3.0 - 4.5
    offset_z = ((idx // 4) % 3) * 3.0 - 3.0
    x, y, z = cx + offset_x, cy, cz + offset_z
    resp = _post(f"{UE_BASE}/api/v0.1/UE/Trajectory/set",
                 {"ue_id": ue_id, "waypoints": [{"x": x, "y": y, "z": z, "t_ms": 0}],
                  "mode": "hold"})
    return resp.get("success", False)


def setup_one(ue_id: str, serving_cell: str, rate_mbps: float, dry_run: bool) -> bool:
    if not hasattr(setup_one, "_counter"):
        setup_one._counter = 0
    ngap_id = _stable_ngap_id(ue_id)
    print(f"  • {ue_id:15s} cell={serving_cell:8s} rate={rate_mbps:>5.1f} Mbps  ngap_id={ngap_id}")
    if dry_run:
        return True

    # AG2 — 移除 du_register_ue + du_create_rlc 直接 call (sim hack).
    # CU.update_traffic_profile 內部會 trigger F1AP UE Context Setup, DU 收到後
    # 同步建 MAC + RLC entity per DRB + RA + HARQ + tick UE registry.
    # 對齊真實 OAI flow (3GPP TS 38.473 §8.3.1).
    #
    # AG3 — set_static_position 確保 RU UePosition table 有真實座標,
    # sionna ray-tracing 才能對每 UE 算出不同 path_gain.
    # 全 (0,0,0) 等同沒 sync, 會走 graceful empty channel → noise-only.
    idx = setup_one._counter
    setup_one._counter += 1
    steps = [
        ("DB insert UeContext",         lambda: insert_ue_via_db(ue_id, serving_cell, ngap_id)),
        ("CU update_traffic_profile",   lambda: set_traffic_profile(ue_id, rate_mbps)),
        ("UE container attach (sync)",  lambda: ue_container_attach(ue_id)),
        ("UE set static position",      lambda: ue_set_static_position(ue_id, serving_cell, idx)),
    ]
    all_ok = True
    for name, fn in steps:
        ok = fn()
        mark = "✓" if ok else "✗"
        print(f"      {mark} {name}")
        if not ok:
            all_ok = False
    return all_ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="預覽 plan 不真執行")
    ap.add_argument("--prefix", default="demo",
                    help="UE id 前綴, default 'demo' (產出 demo_0509, demo_0510, ...)")
    ap.add_argument("--start-num", type=int, default=509,
                    help="起始編號 (default 509, 接 demo_0508 之後)")
    args = ap.parse_args()

    print(f"=== Multi-UE Setup ({_now_iso()}) ===")
    total = sum(c for _, c, _ in UE_PLAN)
    print(f"目標: {total} UEs 分布在 4 cells (gnb4_c3 留 idle 給 CCO cold side)")
    print(f"Plan:")
    for cell, count, rate in UE_PLAN:
        print(f"  {cell}: {count} UE × {rate} Mbps")
    print(f"  gnb4_c3: 0 UE (idle, CCO cold side)")
    print()

    if args.dry_run:
        print("[DRY RUN] 不執行")

    n = args.start_num
    success = 0
    for cell, count, rate in UE_PLAN:
        for _ in range(count):
            ue_id = f"{args.prefix}_{n:04d}"
            n += 1
            if setup_one(ue_id, cell, rate, args.dry_run):
                success += 1

    print()
    print(f"=== Done: {success}/{total} UEs configured ===")
    if not args.dry_run:
        # final verify
        print("\nVerify CU UeContext:")
        import subprocess
        cmd = ["docker", "exec", "ransim-postgres", "psql", "-U", "ransim", "-d", "cu_db",
               "-c", "SELECT ue_id, rrc_state, serving_cell, amf_ue_ngap_id FROM cu_cp_ue_context ORDER BY serving_cell, ue_id;"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(result.stdout)
    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
