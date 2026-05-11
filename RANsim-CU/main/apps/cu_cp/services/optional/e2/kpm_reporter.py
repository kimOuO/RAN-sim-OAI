"""E2 KPM aggregator — produce a snapshot for xApp / RIC.

Combines:
  - per-cell HO event counters (derived on demand from HandoverEvent table)
  - latest UE measurements (from MeasurementLog)
  - host telemetry (BbuTelemetryService)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.optional.e2.bbu_telemetry import BbuTelemetryService


class KpmReporter:
    @staticmethod
    def collect() -> dict[str, Any]:
        timestamp = TimestampService.now_iso()

        ue_status: list[dict[str, Any]] = []
        for ue in UeContext.objects.all():
            # IDLE / 未 attach UE: 不 report active KPM, 全部歸 0.
            # last_meas 對 IDLE UE 是 RRC=CONNECTED 時的殘值, 用會誤導 xApp 與 dashboard.
            # 對齊真實 OAI/O-RAN: KPM Indication 只 cover active UE.
            if ue.rrc_state != "CONNECTED":
                ue_status.append({
                    "ue_id": ue.ue_id,
                    "rrc_state": ue.rrc_state,
                    "serving_cell": "",
                    "rsrp_dbm": None,
                    "sinr_db": None,
                    "throughput_dl_mbps": 0.0,
                    "throughput_ul_mbps": 0.0,
                    "mcs_dl": 0,
                    "rb_width_dl": 0,
                    "mimo_rank": 0,
                    "pdcp_sdu_volume_dl": 0,
                    "pdcp_sdu_volume_ul": 0,
                    "rlc_sdu_delay_dl_ms": 0.0,
                    "neighbor_cells": [],
                    "measured_at": None,
                })
                continue
            last_meas = (
                MeasurementLog.objects.filter(ue_id=ue.ue_id)
                .order_by("-recorded_at")
                .first()
            )
            ue_status.append({
                "ue_id": ue.ue_id,
                "rrc_state": ue.rrc_state,
                "serving_cell": ue.serving_cell,
                "rsrp_dbm": last_meas.rsrp_dbm if last_meas else None,
                "sinr_db": last_meas.sinr_db if last_meas else None,
                "throughput_dl_mbps": last_meas.throughput_dl_mbps if last_meas else 0.0,
                "throughput_ul_mbps": last_meas.throughput_ul_mbps if last_meas else 0.0,
                "mcs_dl": last_meas.mcs_dl if last_meas else 0,
                "rb_width_dl": last_meas.rb_width_dl if last_meas else 0,
                "mimo_rank": last_meas.mimo_rank if last_meas else 1,
                "pdcp_sdu_volume_dl": getattr(last_meas, "pdcp_sdu_volume_dl", 0) if last_meas else 0,
                "pdcp_sdu_volume_ul": getattr(last_meas, "pdcp_sdu_volume_ul", 0) if last_meas else 0,
                "rlc_sdu_delay_dl_ms": getattr(last_meas, "rlc_sdu_delay_dl_ms", 0.0) if last_meas else 0.0,
                "neighbor_cells": last_meas.neighbor_cells_json if last_meas else [],
                "measured_at": last_meas.recorded_at.isoformat() if last_meas else None,
            })

        # Per-cell HO counters (rolling — full-table counts).
        pm_per_cell: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for evt in HandoverEvent.objects.all():
            pm_per_cell[evt.source_cell]["MM.HoExeIntraReq"] += 1
            if evt.status == "SUCC":
                pm_per_cell[evt.source_cell]["MM.HoExeIntraSucc"] += 1
            if evt.trigger == "A3_TTT":
                pm_per_cell[evt.source_cell]["gnb.MR.Event.A3"] += 1

        # Connection counts
        connected_per_cell: dict[str, int] = defaultdict(int)
        for ue in UeContext.objects.filter(rrc_state="CONNECTED"):
            if ue.serving_cell:
                connected_per_cell[ue.serving_cell] += 1
        for cell_id, n in connected_per_cell.items():
            pm_per_cell[cell_id]["RRC.ConnMean"] = n
            pm_per_cell[cell_id]["RRC.ConnMax"] = max(pm_per_cell[cell_id]["RRC.ConnMax"], n)

        cells = list(CellConfig.objects.values_list("cell_id", flat=True))
        bbu_status = BbuTelemetryService.per_gnb_snapshot(cells)
        bbu_status["timestamp"] = timestamp  # type: ignore[assignment]

        return {
            "timestamp": timestamp,
            "ue_status": ue_status,
            "pm": {cell_id: dict(metrics) for cell_id, metrics in pm_per_cell.items()},
            "bbu_status": bbu_status,
        }
