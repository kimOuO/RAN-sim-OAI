"""DU tick driver — 整合所有 app 的 per-tick 流程。

對應 prompt LLM_DU §7:
  1. RLC 各 entity 看 BO
  2. PF scheduler 分配 PRB / 選 MCS
  3. 組 DlTtiRequest 送給 RU
  4. (CQI/CRC 由 RU 主動 POST 進來,不在 tick 內 polling)
  5. 累積 PM 計數器
  6. 每 5 tick 送 measurement_report 給 CU

設計:module-level singleton + threading.Event 控制 stop。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from ran_sim_protocol.f1ap import GnbDuMeasurementReport

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    encode_measurement_report,
)
from main.apps.fapi_north.services.business.ru_client_operations import RuClientBusinessService
from main.apps.fapi_north.services.optional.message_codec.fapi_codec import encode_dl_tti
from main.apps.fapi_north.services.optional.tti_builder.tti_builder import build_dl_tti
from main.apps.mac.services.optional.link_adaptation.mcs_controller import get_mcs_controller
from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import get_pm_aggregator
from main.apps.mac.services.optional.scheduler.scheduler_factory import get_scheduler
from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.utils.env_loader import get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TickStatus:
    tick_count: int = 0
    sfn: int = 0
    slot: int = 0
    started_at_ms: int | None = None
    last_tick_ms: int = 0
    is_running: bool = False


class TickRunner:
    """全局 tick driver 單例。"""

    REPORT_EVERY_N_TICKS = 5
    SLOTS_PER_FRAME = 20  # numerology=1 (30 kHz SCS)
    SFN_MAX = 1024

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.status = TickStatus()
        # in-memory UE registry — UE info by ue_id (sinr / cell / qos)
        self._ue_registry: dict[str, dict[str, Any]] = {}

    # --- public API ----------------------------------------------------------

    def register_ue(
        self,
        ue_id: str,
        *,
        serving_cell: str,
        sinr_db: float = 10.0,
        rsrp_dbm: float = -85.0,
        qos_5qi: int = 9,
    ) -> None:
        self._ue_registry[ue_id] = {
            "id": ue_id,
            "serving_cell": serving_cell,
            "sinr_db": sinr_db,
            "rsrp_dbm": rsrp_dbm,
            "qos_5qi": qos_5qi,
        }

    def update_ue_sinr(self, ue_id: str, sinr_db: float, rsrp_dbm: float | None = None) -> None:
        if ue_id in self._ue_registry:
            self._ue_registry[ue_id]["sinr_db"] = sinr_db
            if rsrp_dbm is not None:
                self._ue_registry[ue_id]["rsrp_dbm"] = rsrp_dbm

    def unregister_ue(self, ue_id: str) -> None:
        self._ue_registry.pop(ue_id, None)

    def start(self) -> bool:
        if self.status.is_running:
            return False
        self._stop_event.clear()
        self.status.is_running = True
        self.status.started_at_ms = int(time.time() * 1000)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="du-tick")
        self._thread.start()
        return True

    def stop(self) -> bool:
        if not self.status.is_running:
            return False
        self._stop_event.set()
        self.status.is_running = False
        return True

    def run_once(self) -> dict[str, Any]:
        """同步跑一個 tick — 給測試/除錯用。"""
        return self._tick_body()

    # --- internals -----------------------------------------------------------

    def _loop(self) -> None:
        tick_ms = get_int("SIM_TICK_MS", 500)
        period = tick_ms / 1000.0
        logger.info("TickRunner started, period=%.2fs", period)
        next_t = time.time()
        while not self._stop_event.is_set():
            try:
                self._tick_body()
            except Exception as e:
                logger.exception("tick body error: %s", e)
            next_t += period
            sleep_for = next_t - time.time()
            if sleep_for > 0:
                self._stop_event.wait(sleep_for)
            else:
                next_t = time.time()
        logger.info("TickRunner stopped after %d ticks", self.status.tick_count)

    def _tick_body(self) -> dict[str, Any]:
        self.status.tick_count += 1
        self.status.last_tick_ms = int(time.time() * 1000)

        # 1) RLC buffer status
        bo_by_ue: dict[str, int] = {}
        for (ue_id, _btype, _bid), entity in rlc_factory.all_entities():
            bo_by_ue[ue_id] = bo_by_ue.get(ue_id, 0) + entity.buffer_status()
        ues_with_bo = [
            self._ue_registry[u] for u in self._ue_registry if bo_by_ue.get(u, 0) > 0
        ]

        # 2) Scheduling — 把 UE 依 serving_cell 分組
        prb_per_cell = get_int("SIM_DEFAULT_PRB_PER_CELL", 273)
        per_cell_alloc: dict[str, dict[str, int]] = {}
        for ue in ues_with_bo:
            per_cell_alloc.setdefault(ue["serving_cell"], []).append(ue)
        rb_alloc_global: dict[str, int] = {}
        scheduler = get_scheduler()
        for cell_name, group in per_cell_alloc.items():
            alloc = scheduler.allocate(
                gnb_name=cell_name, ues_on_gnb=group, n_prb_total=prb_per_cell,
            )
            rb_alloc_global.update(alloc)

        # MCS map — 由 mcs_controller 給(若無歷史就用 mcs_table 推)
        mcs_ctl = get_mcs_controller()
        mcs_map: dict[str, int] = {}
        tbs_map: dict[str, int] = {}
        for ue in ues_with_bo:
            uid = ue["id"]
            mcs_ctl.update(uid, ue["sinr_db"], self.status.last_tick_ms)
            mcs = mcs_ctl.get_mcs(uid)
            mcs_map[uid] = mcs
            _, bps_re = sinr_to_mcs(ue["sinr_db"])
            mbps = mcs_to_throughput_mbps(mcs=mcs, bps_re=bps_re, n_rb=rb_alloc_global.get(uid, 0))
            # 每 tick 對應 bytes(粗估)
            tick_s = get_int("SIM_TICK_MS", 500) / 1000.0
            tbs_map[uid] = int(mbps * 1e6 * tick_s / 8)

        # 3) Build & dispatch DL TTI request
        dl_msg = build_dl_tti(
            sfn=self.status.sfn,
            slot=self.status.slot,
            rb_alloc=rb_alloc_global,
            mcs_map=mcs_map,
            tbs_map=tbs_map,
        )
        dispatched = RuClientBusinessService.post_dl_tti_request(encode_dl_tti(dl_msg))

        # 4) Accumulate PM (per-gNB cumulative + per-UE rolling window)
        pm = get_pm_aggregator()
        for ue in ues_with_bo:
            uid = ue["id"]
            pm.accumulate_ue(
                gnb_name=ue["serving_cell"],
                ue_id=uid,
                mcs_dl=mcs_map.get(uid, 9),
                mcs_ul=max(0, mcs_map.get(uid, 9) - 2),
                sinr_db=ue["sinr_db"],
                rsrp_dbm=ue["rsrp_dbm"],
                prb_dl=rb_alloc_global.get(uid, 0),
                prb_ul=rb_alloc_global.get(uid, 0) // 5,
                dl_bytes=tbs_map.get(uid, 0),
                ul_bytes=tbs_map.get(uid, 0) // 5,
                qos_5qi=ue["qos_5qi"],
                rank=ue.get("rank", 1),
            )

        # 5) Periodic measurement report — 從 PM aggregator window 取平均/總和而非當下瞬時
        report_sent = False
        if self.status.tick_count % self.REPORT_EVERY_N_TICKS == 0:
            tick_s = get_int("SIM_TICK_MS", 500) / 1000.0
            window_s = self.REPORT_EVERY_N_TICKS * tick_s
            for uid in pm.active_ue_ids():
                w = pm.flush_ue_report(uid, window_seconds=window_s)
                if w is None:
                    continue
                report = GnbDuMeasurementReport(
                    ue_id=uid,
                    rsrp_dbm=w["avg_rsrp_dbm"],
                    sinr_db=w["avg_sinr_db"],
                    throughput_dl_mbps=w["throughput_dl_mbps"],
                    throughput_ul_mbps=w["throughput_ul_mbps"],
                    mcs_dl=w["avg_mcs_dl"],
                    rb_width_dl=w["avg_prb_dl"],
                    mimo_rank=w["avg_rank"],
                )
                CuClientBusinessService.post_measurement_report(encode_measurement_report(report))
            report_sent = True

        # 6) Advance sfn/slot
        self.status.slot += 1
        if self.status.slot >= self.SLOTS_PER_FRAME:
            self.status.slot = 0
            self.status.sfn = (self.status.sfn + 1) % self.SFN_MAX

        return {
            "tick_count": self.status.tick_count,
            "sfn": self.status.sfn,
            "slot": self.status.slot,
            "scheduled_ues": list(rb_alloc_global.keys()),
            "dispatched_ru": dispatched,
            "report_sent_to_cu": report_sent,
        }


_singleton: TickRunner | None = None


def get_tick_runner() -> TickRunner:
    global _singleton
    if _singleton is None:
        _singleton = TickRunner()
    return _singleton
