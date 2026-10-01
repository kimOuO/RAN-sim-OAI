#!/usr/bin/env python3
"""
o1-telnet-facade —— 讓 DT RAN sim 假扮 OAI gNB 的 telnet O1 模組。

OAI o1-adapter(gitlab.eurecom.fr/oai/o1-adapter)南向只認 telnet 上的四個指令:
  o1 stats / o1 stop_modem / o1 start_modem / o1 bwconfig <MHz>
並以 "softmodem_gnb> " 當提示符,回應中第一個 '{' 到最後一個 '}' 之間視為 JSON。
本程式把 CU / DU 的 HTTP API 組成同一份 JSON(合約見 OAI
common/utils/telnetsrv/DOC/telneto1.md 與 o1-adapter src/oai/oai_data.c)。

一個 facade 行程同時服務兩種身分(不同埠):
  CU-CP 埠:o1-config.NRCELLCU[](多小區)+ device
  DU    埠:o1-config.BWP / NRCELLDU(單小區,由 DU_CELL 指定)+ device + O1-Operational
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any

import httpx
import telnetlib3

log = logging.getLogger("facade")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(message)s")

CU_URL = os.environ.get("CU_URL", "http://127.0.0.1:8101").rstrip("/")
DU_URL = os.environ.get("DU_URL", "http://127.0.0.1:8102").rstrip("/")
GNB_NAME = os.environ.get("GNB_NAME", "gnb_208_095_000e00")   # = meid,也是 O1 ME 名
VENDOR = os.environ.get("VENDOR", "MITLAB RANsim-DT")
DU_CELL = os.environ.get("DU_CELL", "")          # 舊:只呈現一個 cell;空 = 該 DU 的全部 cell(2026-10-01 多 cell 起)
CUCP_PORT = int(os.environ.get("CUCP_PORT", "9091"))
DU_PORT = int(os.environ.get("DU_PORT", "9092"))
# 多 DU(2026-10-01):DU_PORTS="<telnet port>:<gnb_du_id>:<DU URL>,..."。沒給就退回單 DU(DU_PORT / DU_URL,gnb_du_id 取 CU components 第一個)。
def _parse_du_ports() -> list[dict]:
    raw = os.environ.get("DU_PORTS", "").strip()
    out = []
    if raw:
        for item in raw.split(","):
            port, du_id, url = item.split(":", 2)
            out.append({"port": int(port), "du_id": int(du_id), "url": url.rstrip("/")})
    else:
        out.append({"port": DU_PORT, "du_id": None, "url": DU_URL})
    return out
DU_LIST = _parse_du_ports()
def _du_by_role(role: str) -> dict:
    """role 'du' 或 'du:<gnb_du_id>'。"""
    if ":" in role:
        want = int(role.split(":", 1)[1])
        return next((d for d in DU_LIST if d["du_id"] == want), DU_LIST[0])
    return DU_LIST[0]
CACHE_SEC = float(os.environ.get("CACHE_SEC", "0.8"))   # adapter 每秒問一次,兩身分共用一次抓取
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "4"))
PROMPT = "softmodem_gnb> "

_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_lock = asyncio.Lock()
_state = {"modem_running": True, "bw_requested": None, "cell_disabled": set()}


# ───────────────────────── 資料抓取 ─────────────────────────
async def _post(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.post(url, json={}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    return body.get("data", body)


async def fetch_all() -> dict:
    """一次抓 CU E2NodeId(身分 + cell 靜態)、DU cells(PRB)、FullKPM(動態)。"""
    async with httpx.AsyncClient() as c:
        res = await asyncio.gather(
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/E2NodeId/read"),
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/E2FullReporter/read"),
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/CellState/read"),   # 2026-10-01 H3:節能 / barred 狀態(舊 CU 無此端點 → 例外 → 空)
            *[_post(c, f"{du['url']}/api/v0.1/DU/MAC/MacCellController/read") for du in DU_LIST],
            return_exceptions=True,
        )
    node, kpm, cstate = res[0], res[1], res[2]
    du_res = res[3:]
    du_cells_all: list = []
    du_down: dict = {}
    for du, r in zip(DU_LIST, du_res):
        key = du["du_id"] if du["du_id"] is not None else 0
        du_down[key] = isinstance(r, Exception)
        if isinstance(r, list):
            for row in r:
                row = dict(row)
                row["_du_id"] = du["du_id"]
                du_cells_all.append(row)
        else:
            log.warning("fetch du %s failed: %s", du["url"], r)
    out = {"node": node if isinstance(node, dict) else None,
           "du_cells": du_cells_all,
           "kpm": kpm if isinstance(kpm, dict) else None,
           "cstate": (cstate.get("cells") if isinstance(cstate, dict) else {}) or {},
           # DU 不可達(HTTP 失敗)→ 該 DU 身分的 telnet 埠拒絕服務,讓 adapter 觸發 internalConnectionLoss 告警
           "du_down": du_down.get(0, False) if DU_LIST[0]["du_id"] is None else all(du_down.values()),
           "du_down_by_id": du_down,
           "cu_down": isinstance(node, Exception)}
    for k, v in (("node", node), ("kpm", kpm)):
        if isinstance(v, Exception):
            log.warning("fetch %s failed: %s", k, v)
    return out


async def get_data() -> dict:
    async with _lock:
        now = time.monotonic()
        if _cache["data"] is None or now - _cache["ts"] > CACHE_SEC:
            _cache["data"] = await fetch_all()
            _cache["ts"] = now
        return _cache["data"]



def _cell_states(d: dict, cell: dict) -> tuple[str, str, str]:
    """TS 28.541 NRCellDU:administrativeState / operationalState / cellState(2026-10-01 H3)。
    operationalState:DU 的 cell is_active → ENABLED,否則 DISABLED。
    administrativeState:DU 關閉且不是節能流程(CCC es-on)→ LOCKED(硬開關 / barred / facade stop_modem);否則 UNLOCKED。
      節能關閉是 RIC 依 policy 的動作,不是 OAM 的 LOCK,所以保持 UNLOCKED、以 operationalState=DISABLED 呈現。
    cellState:ENABLED → ACTIVE;關閉 → INACTIVE;沒有 cell → IDLE。"""
    cid = cell.get("cell_id")
    du = next((x for x in d.get("du_cells", []) or [] if x.get("cell_id") == cid), None)
    active = bool(du.get("is_active", True)) if du else bool(cell.get("is_active", True))
    st = (d.get("cstate") or {}).get(cid, {})
    es = st.get("es_state", "isNotEnergySaving") in ("toBeEnergySaving", "isEnergySaving")
    barred = bool(st.get("is_barred", False))
    if cid in _state["cell_disabled"] or barred or (not active and not es):
        admin = "LOCKED"
    else:
        admin = "UNLOCKED"
    op = "ENABLED" if active else "DISABLED"
    cs = "ACTIVE" if active else "INACTIVE"
    return admin, op, cs

# ───────────────────────── 組 JSON ─────────────────────────
def _plmn(node: dict | None, cell: dict | None) -> tuple[str, str]:
    if node:
        p = node.get("global_e2_node_id", {}).get("plmn_id", {})
        if p.get("mcc"):
            mnc = str(p.get("mnc", "95"))
            if p.get("mnc_digit_count") == 2 and len(mnc) == 3 and mnc[0] == "0":
                mnc = mnc[1:]
            return str(p["mcc"]), mnc
    s = (cell or {}).get("served_plmn") or "20895"
    return s[:3], s[3:]


def _gnb_id_int(node: dict | None) -> int:
    try:
        return int(node["global_e2_node_id"]["gnb_id"]["value_int"])
    except Exception:
        return 3584


def _cells(node: dict | None) -> list[dict]:
    cells: list[dict] = []
    for comp in (node or {}).get("components", []) or []:
        for c in comp.get("cells", []) or []:
            c = dict(c)
            c["_gnb_du_id"] = comp.get("gnb_du_id", 0)
            cells.append(c)
    return cells


def _local_cell_id(cell: dict, idx: int) -> int:
    """優先用 CU 給的 nr_cellid(NCI)低 14 bit;沒有就用順位。"""
    nci = cell.get("nr_cellid")
    if isinstance(nci, int):
        return nci & 0x3FFF
    if isinstance(nci, str):
        try:
            return int(nci, 0) & 0x3FFF
        except ValueError:
            pass
    return idx


def _pm_for(kpm: dict | None, cell_id: str) -> dict:
    """FullKPM pm 是 {"gnb-<gnb 名>": [ {cell_id, du_..., cu_...}, ... ]}。
    鍵是 gNB 名(run 裡是 src/nbr/mid),不是 cell id(run 裡是 e10:src),所以要用記錄內的 cell_id 欄位比對。
    2026-09-30 修:原本用 f"gnb-{cell_id}" 查鍵,在 per-run(cell id 帶 tag)永遠查不到 → load 恆 0。"""
    if not kpm:
        return {}
    pm = kpm.get("pm") or {}
    bare = cell_id.split(":")[-1]
    for recs in pm.values():
        for r in recs or []:
            rc = str(r.get("cell_id", ""))
            if rc == cell_id or rc.split(":")[-1] == bare:
                return r
    return {}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_cucp(d: dict) -> dict:
    node = d["node"]
    cells = _cells(node)
    mcc, mnc = _plmn(node, cells[0] if cells else None)
    nrcellcu = []
    kpm = d.get("kpm")
    for i, c in enumerate(cells):
        cmcc, cmnc = _plmn(None, c) if c.get("served_plmn") else (mcc, mnc)
        # G9(2026-10-01):NRCellCU 的 RRC 重建 / 異常釋放計數器(TS 28.552 5.1.1.17 / 5.1.1.10.x),
        # 來源 FullKPM 的 cu_* 欄位(自 run 起累計;adapter 每週期取差分)。
        rec = _pm_for(kpm, c.get("cell_id", "")) if kpm else {}
        def _i(k):
            try:
                return int(float(rec.get(k, 0) or 0))
            except (TypeError, ValueError):
                return 0
        nrcellcu.append({
            "nrcellcu3gpp:cellLocalId": _local_cell_id(c, i),
            "nrcellcu3gpp:mcc": cmcc,
            "nrcellcu3gpp:mnc": cmnc,
            "nrcellcu3gpp:sst": int((c.get("s_nssai") or {}).get("sst", 1)),
            "nrcellcu3gpp:sd": 16777215,
            "counters": {
                "RRC.ReEstabAtt": _i("cu_RRC.ReEstabAtt"),
                "RRC.ReEstabSuccWithUeContext": _i("cu_RRC.ReEstabSuccWithUeContext.sum"),
                "RRC.ReEstabSuccWithoutUeContext": _i("cu_RRC.ReEstabSuccWithoutUeContext.sum"),
                "DRB.RelActNbr.5QI9": _i("cu_DRB.RelActNbr.5QI9"),
            },
        })
    return {"o1-config": {
        "NRFREQREL": {"nrfreqrel3gpp:pMax": 23},
        "NRCELLCU": nrcellcu,
        "device": {"gnbId": _gnb_id_int(node), "gnbName": GNB_NAME, "vendor": VENDOR},
    }}


def _du_cells_of(d: dict, du_id) -> list[dict]:
    """這個 DU 身分要呈現的 cell:依 CU components 的 gnb_du_id 過濾;舊模式(du_id None)= 全部;DU_CELL 指定時只留那個。"""
    cells = _cells(d["node"])
    if du_id is not None:
        cells = [c for c in cells if int(c.get("_gnb_du_id", 0)) == int(du_id)]
    if DU_CELL:
        cells = [c for c in cells if c.get("cell_id") == DU_CELL] or cells[:1]
    return cells


def _cell_dynamic(d: dict, cell: dict) -> tuple[list, list, int]:
    """(ues, thp, load) 取自 FullKPM 的 e2[].cells[].ues[](2026-09-30 PM-V1 修正)。"""
    kpm, du_cells = d["kpm"], d["du_cells"]
    du_row = next((r for r in du_cells if r.get("cell_id") == cell.get("cell_id")), {})
    nrb = int(du_row.get("total_prb") or 106)
    ues, thp, rb_sum = [], [], 0
    cell_pci = int(cell.get("pci", -1))
    for g in (kpm or {}).get("e2", []) or []:
        for c in g.get("cells", []) or []:
            if int(c.get("pci", -2)) != cell_pci:
                continue
            for u in c.get("ues", []) or []:
                uid = str(u.get("ue_id", ""))
                rnti = (int(uid) & 0xFFFF) if uid.isdigit() else (int(hashlib.md5(uid.encode()).hexdigest()[:4], 16) or 1)
                ues.append(rnti)
                thp.append({"rnti": rnti,
                            "dl": round(_num(u.get("dl_throughput")) * 1000.0, 1),   # Mbps → kbit/s(H6)
                            "ul": round(_num(u.get("ul_throughput")) * 1000.0, 1),
                            "unres_dl": 0, "unres_ul": 0})
                rb_sum += int(_num(u.get("rb_width")))
    load = int(round(100.0 * rb_sum / nrb)) if nrb > 0 else 0
    return ues, thp, max(0, min(100, load))


def _nrcelldu_obj(d: dict, cell: dict, idx: int) -> dict:
    node = d["node"]
    du_row = next((r for r in d["du_cells"] if r.get("cell_id") == cell.get("cell_id")), {})
    mcc, mnc = _plmn(node, cell)
    bw = int(round(_num(cell.get("bandwidth_mhz"), 40)))
    arfcn = int(cell.get("arfcn") or 633333)
    adm, op, cs = _cell_states(d, cell)
    return {
        "nrcelldu3gpp:ssbFrequency": arfcn,
        "nrcelldu3gpp:arfcnDL": arfcn,
        "nrcelldu3gpp:bSChannelBwDL": bw,
        "nrcelldu3gpp:arfcnUL": arfcn,
        "nrcelldu3gpp:bSChannelBwUL": bw,
        "nrcelldu3gpp:nRPCI": int(cell.get("pci", 0)),
        "nrcelldu3gpp:nRTAC": int(cell.get("tac", 1)),
        "nrcelldu3gpp:mcc": mcc,
        "nrcelldu3gpp:mnc": mnc,
        "nrcelldu3gpp:sd": 16777215,
        "nrcelldu3gpp:sst": int((cell.get("s_nssai") or {}).get("sst", 1)),
        "nrcelldu3gpp:cellLocalId": str(_local_cell_id(cell, idx)),  # adapter 要字串
        "nrcelldu3gpp:ssbSubCarrierSpacing": 30,
        "nrcelldu3gpp:ssbPeriodicity": 20,
        "nrcelldu3gpp:ssbOffset": 0,
        "nrcelldu3gpp:ssbDuration": 1,
        "nrcelldu3gpp:administrativeState": adm,
        "nrcelldu3gpp:operationalState": op,
        "nrcelldu3gpp:cellState": cs,
        "_total_prb": int(du_row.get("total_prb") or 106),
    }


def build_du(d: dict, du_id=None) -> dict:
    """DU 身分:該 DU 的全部 cell(2026-10-01 多 cell):NRCELLDU 為陣列、O1-Operational.cells 逐 cell;
    平面欄位(ues / load / ues-thp)維持 = 第一個 cell,給舊版 adapter 相容。"""
    node = d["node"]
    cells = _du_cells_of(d, du_id)
    nrcelldu, ops = [], []
    for i, cell in enumerate(cells):
        obj = _nrcelldu_obj(d, cell, i)
        ues, thp, load = _cell_dynamic(d, cell)
        log.info("STAT du%s cell=%s pci=%s num_ues=%d load=%d sum_dl_kbps=%d sum_ul_kbps=%d",
                 f"[{du_id}]" if du_id is not None else "", cell.get("cell_id"), cell.get("pci"), len(ues), load,
                 int(sum(t["dl"] for t in thp)), int(sum(t["ul"] for t in thp)))
        nrcelldu.append(obj)
        ops.append({"cellLocalId": obj["nrcelldu3gpp:cellLocalId"], "num-ues": len(ues), "ues": ues, "load": load,
                    "ues-thp": thp, "RlcPacketDropRateDl": 0})
    nrb = nrcelldu[0]["_total_prb"] if nrcelldu else 106
    for obj in nrcelldu:
        obj.pop("_total_prb", None)
    first = ops[0] if ops else {"num-ues": 0, "ues": [], "load": 0, "ues-thp": []}
    return {
        "o1-config": {
            "BWP": {
                "dl": [{"bwp3gpp:isInitialBwp": True, "bwp3gpp:numberOfRBs": nrb,
                        "bwp3gpp:startRB": 0, "bwp3gpp:subCarrierSpacing": 30}],
                "ul": [{"bwp3gpp:isInitialBwp": True, "bwp3gpp:numberOfRBs": nrb,
                        "bwp3gpp:startRB": 0, "bwp3gpp:subCarrierSpacing": 30}],
            },
            "NRCELLDU": nrcelldu if len(nrcelldu) != 1 else nrcelldu[0],   # 單 cell 維持物件(舊 adapter 相容);多 cell 為陣列
            "device": {"gnbId": _gnb_id_int(node), "gnbName": GNB_NAME, "vendor": VENDOR},
        },
        "O1-Operational": {
            "frame-type": "tdd",
            "band-number": 78,
            "num-ues": first["num-ues"],
            "ues": first["ues"],
            "load": first["load"],
            "ues-thp": first["ues-thp"],
            "RlcPacketDropRateDl": 0,
            "cells": ops,
        },
    }


# ───────────────────────── 指令處理 ─────────────────────────
async def _du_cell_toggle(enable: bool, role: str = "du") -> str:
    """stop_modem / start_modem:對該 DU 身分的全部 cell 下 disable / enable。"""
    d = await get_data()
    du = _du_by_role(role)
    cells = _du_cells_of(d, du["du_id"])
    if not cells:
        return "FAILURE: no cell"
    ep = "enable" if enable else "disable"
    oks = 0
    try:
        async with httpx.AsyncClient() as c:
            for cell in cells:
                r = await c.post(f"{du['url']}/api/v0.1/DU/MAC/MacCellController/{ep}",
                                 json={"cell_id": cell["cell_id"]}, timeout=HTTP_TIMEOUT)
                log.info("%s cell %s -> %s %s", ep, cell["cell_id"], r.status_code, r.text[:120])
                oks += 1 if r.status_code < 300 else 0
        return "OK" if oks == len(cells) else f"FAILURE: {oks}/{len(cells)}"
    except Exception as e:  # noqa: BLE001
        return f"FAILURE: {e}"


def _is_du(role: str) -> bool:
    return role == "du" or role.startswith("du:")


def _down(d: dict, role: str) -> bool:
    if role == "cucp":
        return bool(d.get("cu_down"))
    du = _du_by_role(role)
    key = du["du_id"] if du["du_id"] is not None else 0
    return bool((d.get("du_down_by_id") or {}).get(key, d.get("du_down")))


async def handle(command: str, role: str) -> str:
    if command == "o1 stats":
        d = await get_data()
        body = build_cucp(d) if role == "cucp" else build_du(d, _du_by_role(role)["du_id"])
        return json.dumps(body, indent=2) + "\nOK"
    if command == "o1 stop_modem":
        if not _state["modem_running"]:
            return "FAILURE"
        _state["modem_running"] = False
        return await _du_cell_toggle(False, role) if _is_du(role) else "OK"
    if command == "o1 start_modem":
        if _state["modem_running"]:
            return "FAILURE"
        _state["modem_running"] = True
        return await _du_cell_toggle(True, role) if _is_du(role) else "OK"
    if command.startswith("o1 bwconfig "):
        if _state["modem_running"]:
            return "FAILURE: modem still running"
        try:
            _state["bw_requested"] = int(command.split()[-1])
        except ValueError:
            return "FAILURE: parsing new bw"
        log.info("bwconfig %s requested (recorded only; DT n_prb is global)", _state["bw_requested"])
        return "OK"
    if command in ("help", "?"):
        return "o1 stats | o1 stop_modem | o1 start_modem | o1 bwconfig <MHz>"
    return "ERROR: command not found"


def make_shell(role: str):
    async def shell(reader, writer):
        peer = writer.get_extra_info("peername")
        log.info("[%s] connection from %s", role, peer)
        d = await get_data()
        if _down(d, role):
            log.warning("[%s] backend unreachable, refusing telnet session (adapter will raise alarm)", role)
            writer.close()
            return
        writer.write(PROMPT)
        await writer.drain()
        buf = ""
        try:
            while True:
                ch = await reader.read(1)
                if not ch:
                    break
                buf += ch
                writer.echo(ch)
                if buf.endswith("\r") or buf.endswith("\n"):
                    cmd = buf.strip("\r\n ")
                    buf = ""
                    if cmd:
                        d = await get_data()
                        if _down(d, role):
                            log.warning("[%s] backend went down, closing telnet session", role)
                            break
                        resp = await handle(cmd, role)
                        writer.write("\r\n" + resp.replace("\n", "\r\n") + "\r\n")
                    writer.write(PROMPT)
                    await writer.drain()
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] session error: %s", role, e)
        finally:
            writer.close()
            log.info("[%s] connection closed %s", role, peer)
    return shell


# 身分:cucp + 每個 DU 一個("du" 舊單 DU;"du:<gnb_du_id>" 多 DU)
_PORTS: dict[str, int] = {"cucp": CUCP_PORT}
for _du in DU_LIST:
    _PORTS["du" if _du["du_id"] is None else f"du:{_du['du_id']}"] = _du["port"]
_servers: dict[str, Any] = {r: None for r in _PORTS}


async def _open(role: str):
    if _servers[role] is None:
        _servers[role] = await telnetlib3.create_server(port=_PORTS[role], shell=make_shell(role))
        log.info("[%s] listener OPEN on :%d", role, _PORTS[role])


async def _close(role: str):
    srv = _servers[role]
    if srv is not None:
        srv.close()
        try:
            await srv.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        _servers[role] = None
        log.warning("[%s] listener CLOSED (backend unreachable) — adapter will see connection refused and raise alarm", role)


async def watchdog():
    """後端(CU / DU 的 HTTP)不可達時關掉對應身分的 listener,恢復時再開。
    重點:必須讓 adapter 的 connect() 被拒,而不是接受後立刻關 —— 接受會讓 adapter 認為「已連線」而清掉告警。"""
    while True:
        try:
            d = await get_data()
            for role in list(_PORTS):
                down = _down(d, role)
                if down:
                    await _close(role)
                else:
                    await _open(role)
        except Exception as e:  # noqa: BLE001
            log.warning("watchdog error: %s", e)
        await asyncio.sleep(2)


async def main():
    log.info("facade up: CU-CP :%d  DUs %s  CU=%s gnb=%s cell=%s",
             CUCP_PORT, [(r, p) for r, p in _PORTS.items() if r != "cucp"], CU_URL, GNB_NAME, DU_CELL or "<all>")
    await watchdog()


if __name__ == "__main__":
    asyncio.run(main())
