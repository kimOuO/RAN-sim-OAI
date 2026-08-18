"""ANR KPM 查詢層 — P0-2/3/4(2026-08-11)。

由既有真實資料表加工出 ANR情境_v8 卷面格式的觀測資料,不新增量測:
  - ho_kpm():        HandoverEvent → cell 級 + 關係級換手速率/成功比
  - meas_aggregate(): MeasurementLog.neighbor_cells_json → 依 reported PCI 的 RSRP 統計
  - cgi_resolve():   CellConfig → PCI(+arfcn) → NCGI(同 PCI 多 cell = confusion)
  - freq_relations(): CellConfig → 頻率關係清單(9.3.38 frequencyRelations)

速率的時間基準:HandoverEvent/MeasurementLog 的 recorded/started_at 是牆鐘;
高倍速 sim 時 rate/min 是「牆鐘分鐘」——xApp 若要 sim-time 速率需自行除 speed_x。
"""
from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.services.common.timestamp_service import TimestampService

_LAST_N = 50          # _last50 慣用式(卷面:與時間窗脫鉤,低流量統計有效)
_DEFAULT_WINDOW_MIN = 10.0


# ── P0-2:HO 速率 / 成功比 ─────────────────────────────────────────

def _rate_and_ratio(events: list[HandoverEvent], window_min: float) -> dict[str, Any]:
    """由事件清單(新→舊排序)算 att rate(窗口內)+ succ ratio(最近 N 筆)。"""
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    in_window = [e for e in events if e.started_at >= win_start]
    last_n = events[:_LAST_N]
    succ = sum(1 for e in last_n if e.status == "SUCC")
    # P2-2:失敗原因速率(窗口內)+ 累計(全事件),對齊卷面
    cause_win: dict[str, int] = {}
    cause_cum: dict[str, int] = {}
    for e in in_window:
        if e.failure_cause:
            cause_win[e.failure_cause] = cause_win.get(e.failure_cause, 0) + 1
    for e in events:
        if e.failure_cause:
            cause_cum[e.failure_cause] = cause_cum.get(e.failure_cause, 0) + 1
    return {
        "MM.HoExeAttRatePerMin": round(len(in_window) / max(window_min, 1e-9), 3),
        "MM.HoExeSuccRatio_last50": round(succ / len(last_n), 3) if last_n else None,
        "sampleCount_last50": len(last_n),   # <50 時 xApp 據此判「樣本不足」(卷面判準)
        "handoverFailureCauseRatePerMin": {
            k: round(v / max(window_min, 1e-9), 3) for k, v in cause_win.items()},
        "handoverFailureCauseCumulativeSinceCreation": cause_cum,
    }


def ho_kpm(window_min: float = _DEFAULT_WINDOW_MIN) -> dict[str, Any]:
    """對齊卷面 kpmIndication:cell 級 + perNeighbourRelation。只計 active cell。"""
    active = set(CellConfig.objects.values_list("cell_id", flat=True))
    events = list(
        HandoverEvent.objects.filter(source_cell__in=active).order_by("-started_at")[:2000]
    )

    by_cell: dict[str, list] = {}
    by_rel: dict[tuple[str, str], list] = {}
    for e in events:
        by_cell.setdefault(e.source_cell, []).append(e)
        by_rel.setdefault((e.source_cell, e.target_cell), []).append(e)

    return {
        "windowMin": window_min,
        "cellLevel": {
            cell: _rate_and_ratio(evts, window_min) for cell, evts in by_cell.items()
        },
        "perNeighbourRelation": [
            {"sourceCellNcgi": src, "targetCellGlobalId": tgt,
             **_rate_and_ratio(evts, window_min)}
            for (src, tgt), evts in sorted(by_rel.items())
        ],
    }


# ── P0-3:量測報告聚合(依 reported PCI)────────────────────────────

def _pctl(sorted_vals: list[float], p: float) -> float:
    """線性內插百分位(sorted_vals 已排序、非空)。"""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def meas_aggregate(window_min: float = _DEFAULT_WINDOW_MIN) -> dict[str, Any]:
    """對齊卷面 e2MessageCopyAggregate.measurementReportAggregate。

    原料:MeasurementLog(每秒每 UE:serving rsrp + neighbor_cells_json)。
    依「被回報的 PCI」分組 —— serving 與鄰區量測都算(UE 有量到就是一筆樣本)。
    """
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    cells = list(CellConfig.objects.all())
    pci_of = {c.cell_id: c.pci for c in cells}
    # NR-ARFCN 換算走 seeder 同款公式,避免兩套算法漂移
    from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
    arfcn_of = {c.cell_id: nr_arfcn_from_ghz(c.frequency_ghz) for c in cells}

    # 樣本收集:pci → {"rsrp": [...], "serving_rsrp": [...]}(同報文 serving 量測)
    samples: dict[int, dict[str, list[float]]] = {}
    rows = MeasurementLog.objects.filter(recorded_at__gte=win_start).only(
        "ue_id", "rsrp_dbm", "neighbor_cells_json", "recorded_at")
    # serving cell 需查 UeContext?量測列本身沒 serving cell id — 從鄰區补:直接
    # 把 serving 量測掛在該 UE serving cell 的 PCI 上需要 join;為避免 N+1,
    # serving 樣本以「該列 rsrp_dbm + 該 UE 當下 serving_cell」計 — 一次撈 UeContext。
    from main.apps.cu_cp.models.ue_context import UeContext
    serving_of = {u.ue_id: u.serving_cell for u in UeContext.objects.all()}

    n_rows = 0
    for m in rows:
        n_rows += 1
        s_cell = serving_of.get(m.ue_id, "")
        s_pci = pci_of.get(s_cell)
        if s_pci is not None:
            d = samples.setdefault(s_pci, {"rsrp": [], "serving_rsrp": []})
            d["rsrp"].append(float(m.rsrp_dbm))
            d["serving_rsrp"].append(float(m.rsrp_dbm))
        for n in (m.neighbor_cells_json or []):
            n_pci = pci_of.get(n.get("cell_id"))
            if n_pci is None:
                continue
            d = samples.setdefault(n_pci, {"rsrp": [], "serving_rsrp": []})
            # ANR 歸屬:鄰區關係是 per source cell,故記錄「回報這筆的 UE 當下 serving cell」。
            # 沒有這個欄位,xApp 拿不到 sourceCellId 就無法決定要對哪個 cell 下 ADD。
            d.setdefault("by_source", {})
            if s_cell:
                d["by_source"][s_cell] = d["by_source"].get(s_cell, 0) + 1
            d["rsrp"].append(float(n.get("rsrp_dbm", -120.0)))
            # 同報文 serving 量測(38.331 measResults 含 serving 結果)
            d["serving_rsrp"].append(float(m.rsrp_dbm))

    agg = []
    for pci, d in sorted(samples.items()):
        vals = sorted(d["rsrp"])
        srv = sorted(d["serving_rsrp"])
        cell_ids = [cid for cid, p in pci_of.items() if p == pci]
        agg.append({
            "reportedRadioAccessTechnology": "NR",
            "reportedArfcn": arfcn_of.get(cell_ids[0]) if cell_ids else None,
            "reportedPhysicalCellId": pci,
            "sampleRatePerMin": round(len(vals) / max(window_min, 1e-9), 2),
            "rsrpPercentile50Dbm": round(_pctl(vals, 0.5), 1),
            "rsrpPercentile90Dbm": round(_pctl(vals, 0.9), 1),
            "rsrpStandardDeviationDb": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
            "servingRsrpPercentile50Dbm": round(_pctl(srv, 0.5), 1),
            # 來源歸屬(卷面處置需要 sourceCellId):bySourceCell = 各 serving cell 貢獻樣本數;
            # sourceCellNcgi = 貢獻最多者(xApp 下 ADD 時的 sourceCellId)。
            "sourceCellNcgi": (max(d.get("by_source", {}).items(), key=lambda kv: kv[1])[0]
                               if d.get("by_source") else None),
            "bySourceCell": {k: round(v / max(window_min, 1e-9), 2)
                             for k, v in sorted(d.get("by_source", {}).items())},
        })
    return {
        "windowMin": window_min,
        "rowsScanned": n_rows,
        "measurementReportAggregate": agg,
    }


# ── P0-4:CGI 解析 ─────────────────────────────────────────────────

def cgi_resolve(pci: int, arfcn: int | None = None, attempts: int = 3) -> dict[str, Any]:
    """PCI(+arfcn)→ NCGI。同 PCI 多 cell = confusion(results 多鍵)。

    對齊卷面 cgiResolutionSampling 結構。平台解析是確定性的(讀組態),
    attempts 只是把同一結果重複計次以符合卷面「抽樣」形狀。
    """
    qs = CellConfig.objects.filter(pci=int(pci))
    matches = []
    for c in qs:
        if arfcn is not None:
            try:
                from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
                if nr_arfcn_from_ghz(c.frequency_ghz) != int(arfcn):
                    continue
            except Exception:
                pass
        ncgi = f"{int(c.nr_cellid):015x}" if c.nr_cellid else c.cell_id
        matches.append(ncgi)

    if not matches:
        results = {"FAIL": attempts}
    elif len(matches) == 1:
        results = {matches[0]: attempts}
    else:
        # confusion:輪流回不同 NCGI(模擬不同 UE 解到不同者)
        results = {}
        for i in range(attempts):
            k = matches[i % len(matches)]
            results[k] = results.get(k, 0) + 1

    return {
        "physicalCellId": int(pci),
        "arfcn": arfcn,
        "attempts": attempts,
        "results": results,
        "unique": len(matches) == 1,
        "confusion": len(matches) > 1,
    }


# ── P1-3:RLF / 重建速率 + reestablishmentInboundByPreviousPci ──────

def rlf_kpm(window_min: float = _DEFAULT_WINDOW_MIN) -> dict[str, Any]:
    """RlfEvent → cell 級 RLF/重建速率 + 依重建落點 cell 的 inbound-by-previous-PCI。

    對齊 ANR 卷:RLF.DetectedRate / DropWithoutReestablishmentRate /
    RRC.ConnReEstabInboundRatePerMin / reestablishmentInboundByPreviousPci。
    """
    from main.apps.cu_cp.models.rlf_event import RlfEvent
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    active = set(CellConfig.objects.values_list("cell_id", flat=True))
    evts = list(RlfEvent.objects.filter(detected_at__gte=win_start))

    by_src: dict[str, dict[str, int]] = {}
    # inbound:依「重建落點 cell」→ {previous_pci: 次數}
    inbound: dict[str, dict[int, int]] = {}
    for e in evts:
        if e.source_cell in active:
            d = by_src.setdefault(e.source_cell, {"rlf": 0, "drop": 0, "reestab": 0})
            d["rlf"] += 1
            if e.outcome == "DROP":
                d["drop"] += 1
            elif e.outcome in ("REESTAB_WITH_CTX", "REESTAB_WITHOUT_CTX"):
                d["reestab"] += 1
        if e.reestab_cell and e.outcome != "DROP":
            inbound.setdefault(e.reestab_cell, {})
            inbound[e.reestab_cell][e.source_pci] = \
                inbound[e.reestab_cell].get(e.source_pci, 0) + 1

    def _r(n: int) -> float:
        return round(n / max(window_min, 1e-9), 3)

    return {
        "windowMin": window_min,
        "cellLevel": {
            cell: {
                "RLF.DetectedRate": _r(d["rlf"]),
                "RLF.DropWithoutReestablishmentRate": _r(d["drop"]),
                "RRC.ConnReEstabInboundRatePerMin": _r(d["reestab"]),
            } for cell, d in by_src.items()
        },
        "reestablishmentInboundByPreviousPci": [
            {"cellNcgi": cell,
             "byPreviousPci": [{"previousPhysicalCellId": pci, "ratePerMin": _r(n)}
                               for pci, n in sorted(pcis.items())]}
            for cell, pcis in sorted(inbound.items())
        ],
    }


# ── P0-5:frequencyRelations ──────────────────────────────────────

def freq_relations() -> list[dict[str, Any]]:
    """由 CellConfig 聚合頻率關係(去重 arfcn)。單頻平台 = 一條。"""
    try:
        from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
        arfcns = sorted({nr_arfcn_from_ghz(c.frequency_ghz)
                         for c in CellConfig.objects.all()})
    except Exception:
        arfcns = []
    return [{"radioAccessTechnology": "NR", "arfcn": a} for a in arfcns]
