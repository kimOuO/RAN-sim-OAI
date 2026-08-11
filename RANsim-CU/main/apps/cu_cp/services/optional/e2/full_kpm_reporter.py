"""FullKpmReporter — 完整版 E2 KPM snapshot,欄位架構 1:1 對齊 docs/E2_data_example.md。

輸出 top-level keys:timestamp_ms / compute_ms / tick_ms / e2 / ue_status / pm /
bbu_status / warnings。量測得到的欄位給真值,量不到且推不出來的一律 "0"
(pm 區值型別跟範例一樣全部是字串)。

資料源:
  - CU DB:UeContext / MeasurementLog(含 neighbor rsrp+rsrq)/ CellConfig /
    HandoverEvent / CellMeasurementLog
  - DU dump_pm(HTTP):per-cell MCS 32-bin / CQI 16-bin / PRB 累計 / PDCP bytes
    per-5QI / wall_tick_ms
  - UE Status/read(HTTP):UE 即時位置
  - BbuTelemetryService:host psutil/pynvml(per-gNB 分攤 → proxy 值)

RSRQ:3GPP 真實版(2026-08-07 升級,見 _derive_rsrq)—— RSRQ = RSRP/RSSI,
RSSI = 12·Σ(P_cell×activity) + noise,activity 含 per-cell PRB 負載(負載感知)。
legacy 公式(10log10(P/ΣP)−10.8)已棄用;新公式在「全滿載+忽略雜訊」極限下
收斂回 legacy 值(差 <1dB),語意連續。
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.optional.e2.bbu_telemetry import BbuTelemetryService
from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_HTTP_TIMEOUT = 3.0
MCS_BINS = 32
CQI_BINS = 16

# interfered 判定:任一鄰區 RSRP 進到 serving 10 dB 以內 → 視為受干擾
_INTERFERED_GAP_DB = 10.0

# RRC.ConnMax 追蹤(process 存活期間的高水位;restart 歸零)
_conn_max_seen: dict[str, int] = defaultdict(int)


# ── 小工具 ─────────────────────────────────────────────────────────

def _lin(dbm: float) -> float:
    return 10.0 ** (dbm / 10.0)


# 3GPP 真實版 RSRQ(2026-08-07 升級,取代 legacy 10log10(P/ΣP)−10.8):
#   RSRQ = N·RSRP/RSSI,RSSI 為量測頻寬全能量 = 各 cell 能量×活動係數 + 熱雜訊。
#   activity = α_ref + (1−α_ref)·load —— 空閒 cell 只發參考訊號/控制(α_ref=1/6,
#   對齊 3GPP「idle cell RSRQ ≈ −3dB、滿載 ≈ −10.8dB」兩個錨點),load 取該 cell
#   PrbTot%(DU 真實排程負載)→ RSRQ 具負載感知:鄰站閒時 RSRQ 變好。
#   雜訊用 RU_NOISE_FLOOR_DBM(與 SINR 計算同一尺度,預設 −98)。
_RSRQ_ALPHA_REF = 1.0 / 6.0
_NOISE_FLOOR_DBM = float(get_str("RU_NOISE_FLOOR_DBM", "-98") or "-98")


def _derive_rsrq(target_dbm: float, cells_dbm_load: list[tuple[float, float]]) -> int:
    """3GPP 版:target 對「12×Σ(P_c×activity_c)+noise」的比值(dB),四捨五入取整。

    cells_dbm_load: [(rsrp_dbm, load_0_1), ...] — 該 UE 量得到的所有 cell(含 serving)。
    """
    rssi = sum(
        12.0 * _lin(p) * (_RSRQ_ALPHA_REF + (1.0 - _RSRQ_ALPHA_REF) * max(0.0, min(1.0, ld)))
        for p, ld in cells_dbm_load
    ) + _lin(_NOISE_FLOOR_DBM)
    ratio = _lin(target_dbm) / max(rssi, 1e-30)
    rsrq = 10.0 * math.log10(max(ratio, 1e-30))
    return int(round(max(-43.0, min(20.0, rsrq))))  # clamp 到 3GPP SS-RSRQ 值域


def _quality(sinr_db: float) -> str:
    if sinr_db >= 10.0:
        return "good"
    if sinr_db >= 0.0:
        return "fair"
    return "poor"


def _cell_hex_id(cfg: CellConfig) -> str:
    """範例 cell_id 是 36-bit NCI hex(15 位)。有 nr_cellid 用 hex,否則退回字串 id。"""
    if cfg.nr_cellid:
        return f"{int(cfg.nr_cellid):015x}"
    return cfg.cell_id


def _fetch_du_dump_pm() -> dict[str, Any]:
    host = get_str("HTTP_DU_HOST")
    if not host:
        return {}
    port = get_str("HTTP_DU_PORT", "8000")
    try:
        r = requests.post(
            f"http://{host}:{port}/api/v0.1/DU/Tick/TickController/dump_pm",
            json={}, timeout=_HTTP_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("data", {}) or {}
    except requests.RequestException as exc:
        logger.warning("dump_pm fetch failed: %s", exc)
        return {}


def _fetch_ue_positions() -> dict[str, list[float]]:
    """UE 容器 Status/read → {ue_id: [x, y, z]}。抓不到回空 dict(position 補 0)。"""
    host = get_str("HTTP_UE_HOST", "ue")
    port = get_str("HTTP_UE_PORT", "8000")
    try:
        r = requests.post(
            f"http://{host}:{port}/api/v0.1/UE/Status/read",
            json={}, timeout=_HTTP_TIMEOUT,
        )
        r.raise_for_status()
        out: dict[str, list[float]] = {}
        for t in (r.json().get("data", {}) or {}).get("threads", []):
            pos = t.get("position") or {}
            out[t.get("ue_id", "")] = [
                round(float(pos.get("x", 0.0)), 2),
                round(float(pos.get("y", 0.0)), 2),
                round(float(pos.get("z", 0.0)), 2),
            ]
        return out
    except requests.RequestException as exc:
        logger.warning("UE position fetch failed: %s", exc)
        return {}


# ── pm 區:190 欄模板 ───────────────────────────────────────────────

def _pm_record(
    cfg: CellConfig,
    *,
    now: datetime,
    conn_cnt: int,
    conn_max: int,
    ho: dict[str, int],
    du_acc: dict[str, Any],
    prb_log: CellMeasurementLog | None,
    cell_delay_ms: float,
    cpu_temp: float,
) -> dict[str, str]:
    """單一 cell 的 pm dict — 鍵名/順序/值型別(字串)完全對齊範例。"""
    ts_start = now.strftime("%Y%m%d.%H%M%z")
    ts_end = now.strftime("%H%M%z")
    gid = cfg.gnb_id or "unknown"

    attach = str(conn_cnt)   # 附著代理值:目前 CONNECTED 在本 cell 的 UE 數(見報告)
    pdcp_dl = str(int(du_acc.get("pdcp_bytes_dl", {}).get("9", du_acc.get("pdcp_bytes_dl", {}).get(9, 0))))
    pdcp_ul = str(int(du_acc.get("pdcp_bytes_ul", {}).get("9", du_acc.get("pdcp_bytes_ul", {}).get(9, 0))))

    rec: dict[str, str] = {
        "cell_id": _cell_hex_id(cfg),
        "cu_timestamp_start": ts_start,
        "cu_timestamp_end": ts_end,
        "cu_filename": f"A{ts_start}-{ts_end}_{gid}-cu.xml",
        "du_timestamp_start": ts_start,
        "du_timestamp_end": ts_end,
        "du_filename": f"A{ts_start}-{ts_end}_{gid}-du.xml",
        "cu_CU_Capability": "1",
        # RRC 連線建立(代理:目前 CONNECTED 數;皆為 mo-Data)
        "cu_RRC.ConnEstabAtt.sum": attach,
        "cu_RRC.ConnEstabAtt.mo-Data": attach,
        "cu_RRC.ConnEstabAtt.mo-Signalling": "0",
        "cu_RRC.ConnEstabSucc.sum": attach,
        "cu_RRC.ConnEstabSucc.mo-Data": attach,
        "cu_RRC.ConnEstabSucc.mo-Signalling": "0",
        "cu_RRC.ConnEstabSucc.emergency": "0",
        "cu_RRC.ConnMax": str(conn_max),
        "cu_RRC.ConnMean": str(conn_cnt),
        # ReEstab — 模擬器無 RRC re-establishment 流程 → 0
        "cu_RRC.ConnReEstabSetup.sum": "0",
        "cu_RRC.ReEstabAtt": "0",
        "cu_RRC.ReEstabAtt.otherFailure": "0",
        "cu_RRC.ReEstabSuccWithUeContext.sum": "0",
        "cu_RRC.ReEstabSuccWithUeContext.otherFailure": "0",
        "cu_RRC.ReEstabSuccWithoutUeContext.sum": "0",
        "cu_RRC.ReEstabSuccWithoutUeContext.otherFailure": "0",
        # HO — 真值(HandoverEvent;全部 intra-freq)
        "cu_MM.HoExeIntraFreqReq": str(ho.get("exe_req", 0)),
        "cu_MM.HoExeIntraFreqSucc": str(ho.get("exe_succ", 0)),
        "cu_MM.HoExeIntraReq": str(ho.get("exe_req", 0)),
        "cu_MM.HoExeIntraSucc": str(ho.get("exe_succ", 0)),
        "cu_MM.HoPrepIntraReq": str(ho.get("prep_req", 0)),
        "cu_MM.HoPrepIntraSucc": str(ho.get("prep_succ", 0)),
        "cu_gnb.MR.Event.A3": str(ho.get("a3", 0)),
        # UECNTX — 與 RRC ConnEstab 同源
        "cu_UECNTX.ConnEstabAtt.sum": attach,
        "cu_UECNTX.ConnEstabAtt.mo-Data": attach,
        "cu_UECNTX.ConnEstabAtt.mo-Signalling": "0",
        "cu_UECNTX.ConnEstabSucc.sum": attach,
        "cu_UECNTX.ConnEstabSucc.mo-Data": attach,
        "cu_UECNTX.ConnEstabSucc.mo-Signalling": "0",
        "cu_UECNTX.Release.5GCinit.NASCause": "0",
        "cu_UECNTX.Release.5GCinit.RNCause": "0",
        "cu_UECNTX.Release.5GCinit.sum": "0",
        "cu_gnb.UECNTX.Release.gNBinit.RNCause": "0",
        "cu_gnb.UECNTX.Release.gNBinit.sum": "0",
        # PDU session / DRB:一 UE 一 session(5QI9)
        "cu_SM.PDUSessionSetupReq": attach,
        "cu_SM.PDUSessionSetupSucc": attach,
        "cu_gnb.SM.PDUSessionRelease.Att": "0",
        "cu_gnb.SM.PDUSessionRelease.Succ": "0",
        "cu_DRB.EstabAtt.5QI.sum": attach,
        "cu_DRB.EstabAtt.5QI9": attach,
        "cu_DRB.EstabSucc.5QI.sum": attach,
        "cu_DRB.EstabSucc.5QI9": attach,
        "cu_DRB.InitialEstabAtt.5QI.sum": attach,
        "cu_DRB.InitialEstabAtt.5QI1": "0",
        "cu_DRB.InitialEstabSucc.5QI.sum": attach,
        "cu_DRB.InitialEstabSucc.5QI9": attach,
        "cu_DRB.PdcpPacketDiscardDL.5QI9": "0",
        "cu_DRB.PdcpReordDelayUl": "0",
        "cu_DRB.RelActNbr.5QI.sum": "0",
        "cu_DRB.RelActNbr.5QI9": "0",
        "cu_DRB.SessionTime.5QI.sum": "0",
        "cu_DRB.SessionTime.5QI9": "0",
        # PDCP/SDAP volume — 真值(DU 累計 bytes,5QI 分桶)
        "cu_DRB.PdcpSduVolumeDL_5QI1": "0",
        "cu_DRB.PdcpSduVolumeUl_5QI1": "0",
        "cu_gnb.DRB.SdapSduVolumeDL.5QI1": "0",
        "cu_gnb.DRB.SdapSduVolumeUl.5QI1": "0",
        "cu_DRB.PdcpSduVolumeDL_5QI4": "0",
        "cu_DRB.PdcpSduVolumeUl_5QI4": "0",
        "cu_gnb.DRB.SdapSduVolumeDL.5QI4": "0",
        "cu_gnb.DRB.SdapSduVolumeUl.5QI4": "0",
        "cu_DRB.PdcpSduVolumeDL_5QI9": pdcp_dl,
        "cu_DRB.PdcpSduVolumeUl_5QI9": pdcp_ul,
        "cu_gnb.DRB.SdapSduVolumeDL.5QI9": pdcp_dl,
        "cu_gnb.DRB.SdapSduVolumeUl.5QI9": pdcp_ul,
        # QoS flow / SigTime — 模擬器無此流程 → 0
        "cu_QF.EstabAttNbr.5QI.sum": "0",
        "cu_QF.EstabAttNbr.5QI9": "0",
        "cu_QF.EstabSuccNbr.5QI.sum": "0",
        "cu_QF.EstabSuccNbr.5QI9": "0",
        "cu_QF.InitialEstabAttNbr.5QI.sum": "0",
        "cu_QF.InitialEstabAttNbr.5QI9": "0",
        "cu_QF.InitialEstabSuccNbr.5QI.sum": "0",
        "cu_QF.InitialEstabSuccNbr.5QI9": "0",
        "cu_QF.RelActNbr.Qos.sum": "0",
        "cu_QF.RelActNbr.Qos9": "0",
        "cu_QF.ReleaseAttNbr.5QI.sum": "0",
        "cu_QF.ReleaseAttNbr.5QI9": "0",
        "cu_gnb.RRC.ConnEstabSetup.emergency": "0",
        "cu_gnb.RRC.ConnEstabSetup.mo-Data": "0",
        "cu_gnb.RRC.ConnEstabSetup.mo-Signalling": "0",
        "cu_gnb.RRC.ConnEstabSetup.sum": attach,
        "cu_gnb.RRC.ConnReConfigAtt": "0",
        "cu_gnb.RRC.ConnReConfigSucc": "0",
        "cu_gnb.RRC.ConnReEstab.ReEstab.otherFailure": "0",
        "cu_gnb.RRC.ConnReEstab.ReEstab.sum": "0",
        "cu_gnb.RRC.ConnReEstabSetup.otherFailure": "0",
        "cu_gnb.RRC.ConnRelease.Other": "0",
        "cu_gnb.RRC.ConnRelease.sum": "0",
        "cu_gnb.RRC.SigTimeReEstab.Avg": "0",
        "cu_gnb.RRC.SigTimeReEstab.Max": "0",
        "cu_gnb.RRC.SigTimeReconfig.Avg": "0",
        "cu_gnb.RRC.SigTimeReconfig.Max": "0",
        "cu_gnb.RRC.SigTimeSetup.Avg": "0",
        "cu_gnb.RRC.SigTimeSetup.Max": "0",
        # PEE 溫度 — host CPU 溫度(proxy;無 min/max 追蹤 → 三值同源)
        "du_169:PEE.AvgTemperature": f"{cpu_temp:.2f}",
        "du_170:PEE.MinTemperature": f"{cpu_temp:.2f}",
        "du_171:PEE.MaxTemperature": f"{cpu_temp:.2f}",
    }

    # MCS / CQI 分布 — 真值(DU pm_aggregator bins)
    mcs_dl = du_acc.get("mcs_dl_bins") or [0] * MCS_BINS
    mcs_ul = du_acc.get("mcs_ul_bins") or [0] * MCS_BINS
    cqi = du_acc.get("cqi_bins") or [0] * CQI_BINS
    for i in range(MCS_BINS):
        rec[f"du_CARR.PDSCHMCSDist.BinTable2.BinMCS{i}"] = str(int(mcs_dl[i]) if i < len(mcs_dl) else 0)
    for i in range(MCS_BINS):
        rec[f"du_CARR.PUSCHMCSDist.BinTable1.BinMCS{i}"] = str(int(mcs_ul[i]) if i < len(mcs_ul) else 0)
    for i in range(CQI_BINS):
        rec[f"du_CARR.WBCQIDist.BinCQI{i}.BinTable2"] = str(int(cqi[i]) if i < len(cqi) else 0)

    # PRB 累計 — 真值(DU 累計 PRB 數)
    rec["du_CARR.PRBUsageDLNbr"] = str(int(du_acc.get("prb_used_dl", 0)))
    rec["du_CARR.PRBUsageULNbr"] = str(int(du_acc.get("prb_used_ul", 0)))
    # 空口 delay — RLC SDU delay 當 proxy(5QI9;UL 未建模 → 0)
    rec["du_DRB.AirIfDelayDlAvg.5QI1"] = "0"
    rec["du_DRB.AirIfDelayDlAvg.5QI9"] = f"{cell_delay_ms:.0f}"
    rec["du_DRB.AirIfDelayUlAvg.5QI1"] = "0"
    rec["du_DRB.AirIfDelayUlAvg.5QI9"] = "0"
    return rec


# ── 主流程 ─────────────────────────────────────────────────────────

class FullKpmReporter:
    @staticmethod
    def collect() -> dict[str, Any]:
        t0 = time.monotonic()
        now = datetime.now(timezone.utc)
        now_ms = int(time.time() * 1000)
        warnings: list[str] = []

        cells = list(CellConfig.objects.all())
        active_cell_ids = {c.cell_id for c in cells}
        cell_by_id = {c.cell_id: c for c in cells}
        # cell_id → gNB 名(all_rsrp / ran_name 用)
        gnb_of_cell = {c.cell_id: (c.gnb_id or "unknown") for c in cells}
        gnb_ids = sorted({c.gnb_id or "unknown" for c in cells})

        du_dump = _fetch_du_dump_pm()
        du_gnbs: dict[str, Any] = du_dump.get("gnbs", {}) or {}
        tick_ms = int(du_dump.get("wall_tick_ms") or 0)
        if not du_dump:
            warnings.append("du dump_pm unreachable — du_* counters are 0")

        positions = _fetch_ue_positions()
        if not positions:
            warnings.append("ue positions unavailable — position filled with 0")

        # per-cell DL 負載(0~1)— 3GPP RSRQ 的 activity factor 用(idle 鄰站干擾低)
        cell_load: dict[str, float] = {}
        for cid in active_cell_ids:
            last_prb = (
                CellMeasurementLog.objects.filter(cell_id=cid)
                .order_by("-recorded_at")
                .first()
            )
            cell_load[cid] = float(last_prb.prb_pct_dl) / 100.0 if last_prb else 0.0

        # per-UE 快照(CONNECTED only,對齊現行 KpmReporter 行為)
        ue_rows: list[dict[str, Any]] = []
        conn_per_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ue in UeContext.objects.filter(rrc_state="CONNECTED"):
            if not ue.serving_cell or ue.serving_cell not in active_cell_ids:
                continue
            m = (
                MeasurementLog.objects.filter(ue_id=ue.ue_id)
                .order_by("-recorded_at")
                .first()
            )
            if m is None:
                continue
            neighbors = [
                n for n in (m.neighbor_cells_json or [])
                if n.get("cell_id") and n["cell_id"] in active_cell_ids
                and n["cell_id"] != ue.serving_cell
            ]
            all_dbm = [m.rsrp_dbm] + [float(n.get("rsrp_dbm", -120.0)) for n in neighbors]
            # (rsrp, load) 配對 — serving + 鄰區,RSRQ 的 RSSI 分母用
            cells_dbm_load = [(m.rsrp_dbm, cell_load.get(ue.serving_cell, 0.0))] + [
                (float(n.get("rsrp_dbm", -120.0)), cell_load.get(n["cell_id"], 0.0))
                for n in neighbors
            ]
            interfered = int(any(
                float(n.get("rsrp_dbm", -999.0)) >= m.rsrp_dbm - _INTERFERED_GAP_DB
                for n in neighbors
            ))
            qos_5qi = int((ue.traffic_profile_json or {}).get("qos_5qi", 9) or 9)
            row = {
                "ue": ue, "meas": m, "neighbors": neighbors,
                "all_dbm": all_dbm, "cells_dbm_load": cells_dbm_load,
                "interfered": interfered, "qos_5qi": qos_5qi,
            }
            ue_rows.append(row)
            conn_per_cell[ue.serving_cell].append(row)

        # HO 計數(只算 active cell;對齊現行 fresh-only filter)
        ho_per_cell: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for evt in HandoverEvent.objects.filter(source_cell__in=active_cell_ids):
            d = ho_per_cell[evt.source_cell]
            d["prep_req"] += 1
            if evt.status in ("EXEC", "SUCC", "FAIL"):
                d["prep_succ"] += 1
                d["exe_req"] += 1
            if evt.status == "SUCC":
                d["exe_succ"] += 1
            if evt.trigger == "A3_TTT":
                d["a3"] += 1

        host_bbu = BbuTelemetryService.snapshot_host()

        # ── e2[] ───────────────────────────────────────────────────
        e2_out: list[dict[str, Any]] = []
        for gid in gnb_ids:
            g_cells = []
            for cfg in cells:
                if (cfg.gnb_id or "unknown") != gid:
                    continue
                ues_out = []
                rb_cursor = 0  # 同 cell 內以實際 rb_width 疊出虛擬連續配置的起點
                for row in conn_per_cell.get(cfg.cell_id, []):
                    m = row["meas"]
                    neigh_list = []
                    for n in row["neighbors"]:
                        n_cfg = cell_by_id.get(n["cell_id"])
                        n_hex = _cell_hex_id(n_cfg) if n_cfg else n["cell_id"]
                        n_rsrp = float(n.get("rsrp_dbm", -120.0))
                        # 一律用 3GPP 公式重算(RU 舊值公式不明,棄用求一致)
                        n_rsrq = _derive_rsrq(n_rsrp, row["cells_dbm_load"])
                        neigh_list.append({n_hex: {
                            "rsrp": int(round(n_rsrp)),
                            "rsrq": int(round(float(n_rsrq))),
                        }})
                    ues_out.append({
                        "role": 1,
                        "ue_id": row["ue"].ue_id,
                        "interfered": row["interfered"],
                        "rsrp": int(round(m.rsrp_dbm)),
                        "rsrq": _derive_rsrq(m.rsrp_dbm, row["cells_dbm_load"]),
                        "sinr": int(round(m.sinr_db)),
                        "neighbors": neigh_list,
                        "dl_throughput": int(round(m.throughput_dl_mbps)),
                        "ul_throughput": int(round(m.throughput_ul_mbps)),
                        "rb_start": rb_cursor,
                        "rb_width": int(m.rb_width_dl),
                    })
                    rb_cursor += int(m.rb_width_dl)
                g_cells.append({
                    "cell_id": _cell_hex_id(cfg),
                    "ran_name": gid,
                    "pci": int(cfg.pci),
                    "ues": ues_out,
                })
            e2_out.append({
                "gnb_id": gid,
                "timestamp": now_ms // 1000,
                "cells": g_cells,
            })

        # ── ue_status[] ────────────────────────────────────────────
        ue_status_out: list[dict[str, Any]] = []
        for row in ue_rows:
            ue, m = row["ue"], row["meas"]
            all_rsrp: dict[str, float] = {}
            serv_gnb = gnb_of_cell.get(ue.serving_cell, "unknown")
            all_rsrp[serv_gnb] = round(float(m.rsrp_dbm), 1)
            for n in row["neighbors"]:
                g = gnb_of_cell.get(n["cell_id"], n["cell_id"])
                v = round(float(n.get("rsrp_dbm", -120.0)), 1)
                # 同 gNB 多 cell → 取最強
                if g not in all_rsrp or v > all_rsrp[g]:
                    all_rsrp[g] = v
            ue_status_out.append({
                "ue_id": ue.ue_id,
                "position": positions.get(ue.ue_id, [0.0, 0.0, 0.0]),
                "serving_gnb": serv_gnb,
                "serving_pci": int(cell_by_id[ue.serving_cell].pci),
                "rsrp_dbm": round(float(m.rsrp_dbm), 1),
                "sinr_db": round(float(m.sinr_db), 1),
                "all_rsrp": all_rsrp,
                "throughput_dl_mbps": int(round(m.throughput_dl_mbps)),
                "throughput_ul_mbps": int(round(m.throughput_ul_mbps)),
                "quality": _quality(m.sinr_db),
                "qos_5qi": row["qos_5qi"],
                "role": 1,
                "mcs_dl": int(m.mcs_dl),
                "rb_width_dl": int(m.rb_width_dl),
            })

        # ── pm{} ───────────────────────────────────────────────────
        pm_out: dict[str, list[dict[str, str]]] = {}
        for gid in gnb_ids:
            recs = []
            for cfg in cells:
                if (cfg.gnb_id or "unknown") != gid:
                    continue
                conn_cnt = len(conn_per_cell.get(cfg.cell_id, []))
                _conn_max_seen[cfg.cell_id] = max(_conn_max_seen[cfg.cell_id], conn_cnt)
                delays = [
                    float(getattr(r["meas"], "rlc_sdu_delay_dl_ms", 0.0) or 0.0)
                    for r in conn_per_cell.get(cfg.cell_id, [])
                ]
                recs.append(_pm_record(
                    cfg,
                    now=now,
                    conn_cnt=conn_cnt,
                    conn_max=_conn_max_seen[cfg.cell_id],
                    ho=ho_per_cell.get(cfg.cell_id, {}),
                    du_acc=du_gnbs.get(cfg.cell_id, {}),
                    prb_log=None,
                    cell_delay_ms=(sum(delays) / len(delays)) if delays else 0.0,
                    cpu_temp=host_bbu["cpu_temp"],
                ))
            pm_out[f"gnb-{gid}"] = recs

        # ── bbu_status ─────────────────────────────────────────────
        bbu_raw = BbuTelemetryService.per_gnb_snapshot(gnb_ids)
        bbu_out: dict[str, Any] = {f"gnb-{g}": v for g, v in bbu_raw.items()}
        bbu_out["timestamp"] = str(now_ms)

        return {
            "timestamp_ms": now_ms,
            "compute_ms": int((time.monotonic() - t0) * 1000),
            "tick_ms": tick_ms,
            "e2": e2_out,
            "ue_status": ue_status_out,
            "pm": pm_out,
            "bbu_status": bbu_out,
            "warnings": warnings,
        }
