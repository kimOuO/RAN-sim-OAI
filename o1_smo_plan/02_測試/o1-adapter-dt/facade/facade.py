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
DU_CELL = os.environ.get("DU_CELL", "")          # DU 身分要呈現哪個 cell;空 = components 第一個
CUCP_PORT = int(os.environ.get("CUCP_PORT", "9091"))
DU_PORT = int(os.environ.get("DU_PORT", "9092"))
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
        node, du_cells, kpm, cstate = await asyncio.gather(
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/E2NodeId/read"),
            _post(c, f"{DU_URL}/api/v0.1/DU/MAC/MacCellController/read"),
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/E2FullReporter/read"),
            _post(c, f"{CU_URL}/api/v0.1/CU/E2/CellState/read"),   # 2026-10-01 H3:節能 / barred 狀態(舊 CU 無此端點 → 例外 → 空)
            return_exceptions=True,
        )
    out = {"node": node if isinstance(node, dict) else None,
           "du_cells": du_cells if isinstance(du_cells, list) else [],
           "kpm": kpm if isinstance(kpm, dict) else None,
           "cstate": (cstate.get("cells") if isinstance(cstate, dict) else {}) or {},
           # DU 不可達(HTTP 失敗)→ DU 身分的 telnet 埠拒絕服務,讓 adapter 觸發 internalConnectionLoss 告警
           "du_down": isinstance(du_cells, Exception),
           "cu_down": isinstance(node, Exception)}
    for k, v in (("node", node), ("du_cells", du_cells), ("kpm", kpm)):
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
    for i, c in enumerate(cells):
        cmcc, cmnc = _plmn(None, c) if c.get("served_plmn") else (mcc, mnc)
        nrcellcu.append({
            "nrcellcu3gpp:cellLocalId": _local_cell_id(c, i),
            "nrcellcu3gpp:mcc": cmcc,
            "nrcellcu3gpp:mnc": cmnc,
            "nrcellcu3gpp:sst": int((c.get("s_nssai") or {}).get("sst", 1)),
            "nrcellcu3gpp:sd": 16777215,
        })
    return {"o1-config": {
        "NRFREQREL": {"nrfreqrel3gpp:pMax": 23},
        "NRCELLCU": nrcellcu,
        "device": {"gnbId": _gnb_id_int(node), "gnbName": GNB_NAME, "vendor": VENDOR},
    }}


def build_du(d: dict) -> dict:
    node, du_cells, kpm = d["node"], d["du_cells"], d["kpm"]
    cells = _cells(node)
    cell = None
    if DU_CELL:
        cell = next((c for c in cells if c.get("cell_id") == DU_CELL), None)
    if cell is None and cells:
        cell = cells[0]
    cell = cell or {}
    mcc, mnc = _plmn(node, cell)
    du_row = next((r for r in du_cells if r.get("cell_id") == cell.get("cell_id")), {}) if cell else {}
    nrb = int(du_row.get("total_prb") or 106)
    bw = int(round(_num(cell.get("bandwidth_mhz"), 40)))
    arfcn = int(cell.get("arfcn") or 633333)
    # ── 動態值(2026-09-30 PM-V1 修正)────────────────────────────────
    # UE 清單、每 UE 吞吐與 PRB 取自 FullKPM 的 e2[].cells[].ues[](浮點 Mbps、rb_width),
    # 不用 ue_status(吞吐被取整成整數 Mbps)也不用 pm 的 RRU.PrbTotDl(那是累計 PRB 個數,不是百分比)。
    # load(%)= 該 cell 目前所有 UE 的 rb_width 總和 / 該 cell 總 PRB。
    ues, thp, rb_sum = [], [], 0
    cell_pci = int(cell.get("pci", -1)) if cell else -1
    for g in (kpm or {}).get("e2", []) or []:
        for c in g.get("cells", []) or []:
            if int(c.get("pci", -2)) != cell_pci:
                continue
            for u in c.get("ues", []) or []:
                uid = str(u.get("ue_id", ""))
                rnti = (int(uid) & 0xFFFF) if uid.isdigit() else (int(hashlib.md5(uid.encode()).hexdigest()[:4], 16) or 1)
                ues.append(rnti)
                thp.append({"rnti": rnti,
                            "dl": int(round(_num(u.get("dl_throughput")) * 1000)),   # Mbps → kbit/s
                            "ul": int(round(_num(u.get("ul_throughput")) * 1000)),
                            "unres_dl": 0, "unres_ul": 0})
                rb_sum += int(_num(u.get("rb_width")))
    load = int(round(100.0 * rb_sum / nrb)) if nrb > 0 else 0
    load = max(0, min(100, load))
    _adm, _op, _cs = _cell_states(d, cell)
    log.info("STAT du cell=%s pci=%s num_ues=%d load=%d sum_dl_kbps=%d sum_ul_kbps=%d",
             cell.get("cell_id"), cell_pci, len(ues), load, sum(t["dl"] for t in thp), sum(t["ul"] for t in thp))
    return {
        "o1-config": {
            "BWP": {
                "dl": [{"bwp3gpp:isInitialBwp": True, "bwp3gpp:numberOfRBs": nrb,
                        "bwp3gpp:startRB": 0, "bwp3gpp:subCarrierSpacing": 30}],
                "ul": [{"bwp3gpp:isInitialBwp": True, "bwp3gpp:numberOfRBs": nrb,
                        "bwp3gpp:startRB": 0, "bwp3gpp:subCarrierSpacing": 30}],
            },
            "NRCELLDU": {
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
                "nrcelldu3gpp:cellLocalId": str(_local_cell_id(cell, 0)),  # adapter 要字串
                "nrcelldu3gpp:ssbSubCarrierSpacing": 30,
                "nrcelldu3gpp:ssbPeriodicity": 20,
                "nrcelldu3gpp:ssbOffset": 0,
                "nrcelldu3gpp:ssbDuration": 1,
                "nrcelldu3gpp:administrativeState": _adm,
                "nrcelldu3gpp:operationalState": _op,
                "nrcelldu3gpp:cellState": _cs,
            },
            "device": {"gnbId": _gnb_id_int(node),   # adapter 拿它填 GNBDUFunction.gNBId;gNBDUId 由 config gnb-du-id 決定
                       "gnbName": GNB_NAME, "vendor": VENDOR},
        },
        "O1-Operational": {
            "frame-type": "tdd",
            "band-number": 78,
            "num-ues": len(ues),
            "ues": ues,
            "load": load,
            "ues-thp": thp,
            "RlcPacketDropRateDl": 0,
        },
    }


# ───────────────────────── 指令處理 ─────────────────────────
async def _du_cell_toggle(enable: bool) -> str:
    d = await get_data()
    cells = _cells(d["node"])
    cell = next((c for c in cells if c.get("cell_id") == DU_CELL), None) if DU_CELL else (cells[0] if cells else None)
    if not cell:
        return "FAILURE: no cell"
    ep = "enable" if enable else "disable"
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{DU_URL}/api/v0.1/DU/MAC/MacCellController/{ep}",
                             json={"cell_id": cell["cell_id"]}, timeout=HTTP_TIMEOUT)
        log.info("%s cell %s -> %s %s", ep, cell["cell_id"], r.status_code, r.text[:120])
        return "OK" if r.status_code < 300 else f"FAILURE: {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return f"FAILURE: {e}"


async def handle(command: str, role: str) -> str:
    if command == "o1 stats":
        d = await get_data()
        body = build_cucp(d) if role == "cucp" else build_du(d)
        return json.dumps(body, indent=2) + "\nOK"
    if command == "o1 stop_modem":
        if not _state["modem_running"]:
            return "FAILURE"
        _state["modem_running"] = False
        return await _du_cell_toggle(False) if role == "du" else "OK"
    if command == "o1 start_modem":
        if _state["modem_running"]:
            return "FAILURE"
        _state["modem_running"] = True
        return await _du_cell_toggle(True) if role == "du" else "OK"
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
        if (role == "du" and d.get("du_down")) or (role == "cucp" and d.get("cu_down")):
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
                        if (role == "du" and d.get("du_down")) or (role == "cucp" and d.get("cu_down")):
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


_servers: dict[str, Any] = {"cucp": None, "du": None}
_PORTS = {"cucp": CUCP_PORT, "du": DU_PORT}


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
            for role, down in (("cucp", d.get("cu_down")), ("du", d.get("du_down"))):
                if down:
                    await _close(role)
                else:
                    await _open(role)
        except Exception as e:  # noqa: BLE001
            log.warning("watchdog error: %s", e)
        await asyncio.sleep(2)


async def main():
    log.info("facade up: CU-CP :%d  DU :%d  CU=%s DU=%s gnb=%s cell=%s",
             CUCP_PORT, DU_PORT, CU_URL, DU_URL, GNB_NAME, DU_CELL or "<first>")
    await watchdog()


if __name__ == "__main__":
    asyncio.run(main())
