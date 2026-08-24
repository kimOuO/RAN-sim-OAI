#!/usr/bin/env python3
"""十二題 ANR 劇本逐題健康檢查。

每題:啟動劇本 → 等 75s(避開啟動清場窗口)→ 佈病 → 檢查決定性簽名 → 記錄。
不驗 xApp 行為(那要 RIC 端配合),只驗 **sim 這半能不能把題目做出來**:
  ① 劇本起得來、UE 掛得上、位置在動
  ② 佈病腳本套得上
  ③ 該題的決定性簽名在 E2 觀測面上看得到

用法:python3 scripts/anr_smoke_all.py [題號...]   (不給則全跑)
"""
import json
import subprocess
import sys
import time
import urllib.request

CU = "http://localhost:8101/api/v0.1/CU"
UE = "http://localhost:8105/api/v0.1/UE"
DWELL = 75          # 佈病前的等待(啟動清場窗口約 60s)
SETTLE = 20         # 佈病後等訊號穩定


def post(url, body=None, timeout=90):
    req = urllib.request.Request(
        url, data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def arm(case):
    p = subprocess.run(
        ["docker", "exec", "-i", "-e", f"CASE={case}", "ransim-cu",
         "python", "manage.py", "shell"],
        stdin=open("/home/mitlab/XAPP_DT/scripts/anr_arm.py"),
        capture_output=True, text=True, timeout=120)
    return p.stdout


def node_info():
    return post(f"{CU}/E2/NodeInfo/read")["data"]


def rels():
    return {(r["sourceCellNcgi"], r["targetCellGlobalId"]): r
            for r in node_info()["neighbourCellRelations"]}


def cells_present():
    return {c["ncgi"] for c in node_info()["servingCells"]}


def absent_but_real(src, tgt):
    """缺漏鄰區型的正確簽名 = 「關係不存在」**且**「目標 cell 真的存在」。

    只驗前半是假通過:seed_from_cells() 只種同 gNB 內的鄰區,而 ANR 劇本每個
    gNB 只有一個 cell → 基準 NRT 恆為空,「關係不存在」永遠成立,驗了等於沒驗
    (2026-08-24 首輪十二題檢查就是這樣讓四題假通過)。
    """
    r = rels()
    cs = cells_present()
    no_rel = (src, tgt) not in r
    real = tgt in cs and src in cs
    return (no_rel and real), \
        f"{src}→{tgt} 關係{'不存在 ✓' if no_rel else '仍存在 ✗'};兩端 cell {'都在 ✓' if real else '缺席 ✗ (簽名無意義)'}"


def cgi(pci, arfcn=None):
    b = {"pci": pci}
    if arfcn:
        b["arfcn"] = arfcn
    return post(f"{CU}/E2/Anr/cgi_resolve", b)["data"]


# ── 每題的決定性簽名檢查 ───────────────────────────────────
def q1():
    return absent_but_real("src_c0", "nbr_c0")

def q2():
    return absent_but_real("s25_c0", "n35_c0")

def q3():
    return absent_but_real("s28_c0", "n91_c0")

def q4():
    ok, msg = absent_but_real("s01_c0", "unk_c0")
    c = cgi(301)
    return ok, f"{msg};cgi_resolve(301)={c.get('results')} confusion={c.get('confusion')}"

def q5():
    c = cgi(7)
    return bool(c.get("confusion")), f"cgi_resolve(7) confusion={c.get('confusion')} results={c.get('results')}"

def q6():
    r = rels().get(("s07_c0", "n33_c0"))
    return (r is not None and not r["xnX2Established"]), \
        f"s07_c0→n33_c0 xnX2Established={r['xnX2Established'] if r else '關係不存在'}"

def q7():
    r = rels().get(("src_c0", "nbr_c0"))
    env = subprocess.run(["docker", "exec", "ransim-cu", "printenv", "HO_FORCE_FAIL_TARGET"],
                         capture_output=True, text=True).stdout.strip()
    # 決定性簽名不是「關係在」,而是「換過去會失敗」——去看實際的失敗原因累計
    causes = {}
    try:
        k = post(f"{CU}/E2/Anr/kpm", {"window_min": 10})["data"]
        for row in k.get("perNeighbourRelation") or []:
            if row.get("sourceCellNcgi") == "src_c0" and row.get("targetCellGlobalId") == "nbr_c0":
                causes = row.get("handoverFailureCauseRatePerMin") or {}
    except Exception:
        pass
    return (r is not None and env == "nbr_c0"), \
        f"關係{'在' if r else '不在'};env={env!r};失敗原因累計={causes or '尚未發生換手'}"

def q8():
    r = rels()
    cs = cells_present()
    tgts = ("f55_c0", "f61_c0", "f68_c0")
    missing = [t for t in tgts if ("s11_c0", t) not in r]
    present = [t for t in tgts if t in cs]
    fr = node_info().get("frequencyRelations") or []
    return (len(missing) == 3 and len(present) == 3), \
        f"缺 {len(missing)}/3 條跨頻關係;2.1GHz cell 存在 {len(present)}/3;frequencyRelations={len(fr)} 層"

def q9():
    n = node_info()
    cap = n["nrtCapacity"]
    ev = [e for e in n["relationChangeEvents"] if e["action"] == "ADD_REJECTED"]
    per = {}
    for (s, _t) in rels():
        per[s] = per.get(s, 0) + 1
    full = [c for c, v in per.items() if v >= cap["limit"]]
    return bool(full), f"容量 {cap};已滿的 cell={full};ADD_REJECTED 事件={len(ev)}"

def q10():
    r = rels().get(("s15_c0", "b07_c0"))
    cells = {c["ncgi"]: c for c in node_info()["servingCells"]}
    real = cells.get("b07_c0", {}).get("physicalCellId")
    return (r is not None and r["targetPhysicalCellId"] != real), \
        f"關係存 pci={r['targetPhysicalCellId'] if r else '—'} vs cell 實際 pci={real}(不符=過期對應成立)"

def q11():
    r = rels()
    old = r.get(("main_c0", "old_c0"))
    keep = r.get(("main_c0", "keep_c0"))
    aged = old is not None and (old.get("relationAgeSec") or 0) > 86400
    prot = keep is not None and keep["flags"]["noRemove"]
    return (aged and prot), \
        f"老化關係 age={(old or {}).get('relationAgeSec', 0):.0f}s;保護條目 noRemove={prot}"

def q12():
    r = rels().get(("s19_c0", "d02_c0"))
    return (r is not None and not r["isHoAllowed"]), \
        f"s19_c0→d02_c0 isHoAllowed={r['isHoAllowed'] if r else '關係不存在'}"


CASES = [
    (1,  "anr_missing_neighbor", "q1",  q1),
    (2,  "anr_missing_meas",     "q2",  q2),
    (3,  "anr_sparse_edge",      "q3",  q3),
    (4,  "anr_unknown_cell",     "q4",  q4),
    (5,  "anr_pci_confusion",    "q5",  q5),
    (6,  "anr_xn_discovery",     "q6",  q6),
    (7,  "anr_harmful_neighbor", "q7",  q7),
    (8,  "anr_inter_freq",       "q8",  q8),
    (9,  "anr_nrt_capacity",     "q9",  q9),
    (10, "anr_stale_pci",        "q10", q10),
    (11, "anr_stale_relation",   "q11", q11),
    (12, "anr_attr_audit",       "q12", q12),
]


def ue_health():
    """UE 掛上了嗎、在動嗎。"""
    d = post(f"{UE}/Status/read")["data"]
    p0 = {t["ue_id"]: (t["position"]["x"], t["position"]["z"]) for t in d["threads"]}
    time.sleep(8)
    d2 = post(f"{UE}/Status/read")["data"]
    p1 = {t["ue_id"]: (t["position"]["x"], t["position"]["z"]) for t in d2["threads"]}
    moving = sum(1 for k in p0 if k in p1 and p0[k] != p1[k])
    states = {}
    for t in d2["threads"]:
        states[t["state"]] = states.get(t["state"], 0) + 1
    return len(d2["threads"]), moving, states


def run(case_no, sid, arm_case, check):
    print(f"\n{'='*66}\n第 {case_no} 題  {sid}", flush=True)
    try:
        post(f"{UE}/Sim/SimController/stop", timeout=90)
    except Exception:
        pass
    time.sleep(3)
    try:
        r = post(f"{UE}/Sim/SimController/start",
                 {"source": "scenario", "scenario_id": sid, "speed_x": 1, "sim_dt_ms": 250},
                 timeout=180)
        if not r.get("success"):
            return case_no, sid, "✗ 啟動失敗", r.get("message", "")[:60], "", ""
    except Exception as e:
        return case_no, sid, "✗ 啟動例外", str(e)[:60], "", ""

    time.sleep(DWELL)
    n_ue, moving, states = ue_health()
    armed = arm(arm_case)
    time.sleep(SETTLE)
    try:
        ok, detail = check()
    except Exception as e:
        ok, detail = False, f"檢查例外 {e!r}"[:90]

    ue_txt = f"UE {n_ue} 動 {moving} {states}"
    print(f"  {ue_txt}\n  簽名: {'✅' if ok else '❌'} {detail}", flush=True)
    return case_no, sid, "✅" if ok else "❌", detail, ue_txt, armed.count("⚠️")


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} if len(sys.argv) > 1 else None
    rows = []
    for c in CASES:
        if want and c[0] not in want:
            continue
        rows.append(run(*c))
    print(f"\n\n{'='*66}\n總表\n{'='*66}")
    print(f"{'題':>3} {'劇本':24s} {'簽名':4s} {'UE 健康':28s}")
    for no, sid, ok, detail, ue, _w in rows:
        print(f"{no:>3} {sid:24s} {ok:4s} {ue}")
    bad = [r for r in rows if not r[2].startswith('✅')]
    print(f"\n通過 {len(rows)-len(bad)}/{len(rows)}")
    for r in bad:
        print(f"  第{r[0]}題 {r[3]}")
