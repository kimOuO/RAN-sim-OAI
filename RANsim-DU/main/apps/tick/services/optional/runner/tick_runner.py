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
from ran_sim_protocol.common import NeighborMeas

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

    def update_ue_serving_cell(self, ue_id: str, serving_cell: str) -> None:
        """從 F1AP UE Context Setup / Modification 收到 serving_cell 變更時呼叫。

        AG4 fix: F1AP UE Context Setup 是 UE 進 tick_runner 的權威 path
        (對齊 OAI: spec compliant register 路徑). 之前舊實作只在 UE 已存在
        才更新, AG2 改成 update_traffic_profile 走 F1AP 後 demo_0508 type 老 UE
        永遠不會被 register (Dashboard direct register_ue 的 sim hack 砍掉了).
        改成 upsert: 不存在就 register 一個 default state, 後續 cqi_indication
        會把 sinr/rsrp 更新成真實值.
        """
        if ue_id in self._ue_registry:
            self._ue_registry[ue_id]["serving_cell"] = serving_cell
        else:
            self._ue_registry[ue_id] = {
                "id": ue_id,
                "serving_cell": serving_cell,
                "sinr_db": 10.0,        # default 直到第一次 cqi_indication
                "rsrp_dbm": -85.0,
                "qos_5qi": 9,
            }

    def update_ue_neighbors(self, ue_id: str, neighbors: list[dict[str, Any]]) -> None:
        """緩存 RU 來的 neighbor cell measurements。每次覆蓋，要 fresh 量測。

        neighbors: [{cell_id, rsrp_dbm, rsrq_db}, ...]
        在 measurement_report flush 時帶給 CU，供 A3 evaluator 用。
        """
        if ue_id in self._ue_registry:
            self._ue_registry[ue_id]["neighbors"] = list(neighbors)

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

        # 1) RLC buffer status + 收集 SDU delay samples → PM aggregator
        bo_by_ue: dict[str, int] = {}
        delay_by_ue: dict[str, list[float]] = {}
        for (ue_id, _btype, _bid), entity in rlc_factory.all_entities():
            bo_by_ue[ue_id] = bo_by_ue.get(ue_id, 0) + entity.buffer_status()
            # 收 RLC entity 累計的 SDU delivery delay（取出後 entity 內部 buffer 清空）
            try:
                samples = entity.take_delay_samples()
                if samples:
                    delay_by_ue.setdefault(ue_id, []).extend(samples)
            except AttributeError:
                pass  # 舊 entity 沒有此 API — 忽略
        # 所有 CONNECTED UE 都要 measurement (對齊真實 OAI: CSI-RS 跟 PDSCH 解耦).
        # measurement 跟 scheduling 解耦 — 沒 traffic 的 UE 也要算 channel state,
        # 否則 RIC 看到的 KPM 會凍結 (rsrp/sinr 永遠是 attach 當下的值).
        ues_for_measurement = list(self._ue_registry.values())
        ues_with_bo = [
            self._ue_registry[u] for u in self._ue_registry if bo_by_ue.get(u, 0) > 0
        ]

        # 2) Scheduling — 把 UE 依 serving_cell 分組
        prb_per_cell = get_int("SIM_DEFAULT_PRB_PER_CELL", 273)
        # Energy-saving: 跳過 is_active=False 的 cell（FAPI 不發給 RU、PM 不累積）
        try:
            from main.apps.mac.models.cell_state import CellState
            inactive_cells = set(
                CellState.objects.filter(is_active=False).values_list("cell_id", flat=True)
            )
        except Exception:
            inactive_cells = set()

        per_cell_alloc: dict[str, dict[str, int]] = {}
        for ue in ues_with_bo:
            cell = ue["serving_cell"]
            if cell in inactive_cells:
                continue  # 該 cell 已關，本 tick 不排程這個 UE
            per_cell_alloc.setdefault(cell, []).append(ue)

        # PRB quota cap：xApp 透過 E2 Control Style 2/Action 6 設的 max_prb%
        # 套到 scheduler 的 n_prb_total — DU MAC 的 max_rbSize 對齊。
        from main.apps.mac.services.optional.scheduler.prb_quota import get_store as _get_quota_store
        _quota_store = _get_quota_store()

        rb_alloc_global: dict[str, int] = {}
        scheduler = get_scheduler()
        for cell_name, group in per_cell_alloc.items():
            cap = _quota_store.cap_factor(cell_name)
            capped_prb = max(1, int(prb_per_cell * cap))   # 至少 1 個 PRB，防 0 除錯
            alloc = scheduler.allocate(
                gnb_name=cell_name, ues_on_gnb=group, n_prb_total=capped_prb,
            )
            rb_alloc_global.update(alloc)

        # 沒 traffic 的 CONNECTED UE 也要送 dl_tti (PRB=0, measurement-only).
        # build_dl_tti 會幫他們建 0-PRB PDU, RU 收到照樣跑 PathSolver 算 channel,
        # 回傳的 CqiIndication 會更新 _ue_registry sinr/rsrp → KPM 不再凍結.
        for ue in ues_for_measurement:
            rb_alloc_global.setdefault(ue["id"], 0)

        # MCS map — 由 mcs_controller 給(若無歷史就用 mcs_table 推)
        # 跑 ues_for_measurement (不只 ues_with_bo): 沒 traffic 的 UE 也要更新 SINR 歷史,
        # mcs_controller 才能持續追蹤 link adaptation 用的 CQI history.
        # 沒 traffic 的 UE rb_alloc=0 → mbps=0 → tbs=0, 自然不會有假 throughput.
        mcs_ctl = get_mcs_controller()
        mcs_map: dict[str, int] = {}
        tbs_map: dict[str, int] = {}
        for ue in ues_for_measurement:
            uid = ue["id"]
            mcs_ctl.update(uid, ue["sinr_db"], self.status.last_tick_ms)
            mcs = mcs_ctl.get_mcs(uid)
            mcs_map[uid] = mcs
            _, bps_re = sinr_to_mcs(ue["sinr_db"])
            mbps = mcs_to_throughput_mbps(mcs=mcs, bps_re=bps_re, n_rb=rb_alloc_global.get(uid, 0))
            # 每 tick 對應 bytes(粗估)
            tick_s = get_int("SIM_TICK_MS", 500) / 1000.0
            tbs_map[uid] = int(mbps * 1e6 * tick_s / 8)

        # 3.5) Drain RLC queue — 對應 MAC 給 RLC 的 PDU 預算
        # 沒這步 RLC SDU 永遠塞在 queue，不會 deliver → 沒 delay sample。
        # 對齊 OAI nr_mac_rlc_data_req() 的角色 — MAC 通知 RLC 該送多少 bytes 出去。
        # ★ 重要: capture generate_pdu return value (= 真實 drain 出的 byte) 累計到
        #   actual_drained_map. 之後 PM aggregator 用 actual_drained_map 而非 tbs_map
        #   (理論 capacity), 對齊 OAI dlsch_total_bytes 統計實際 PDU bytes 的語意.
        actual_drained_map: dict[str, int] = {}
        for ue in ues_with_bo:
            uid = ue["id"]
            budget = tbs_map.get(uid, 0)
            if budget <= 0:
                continue
            entities_for_ue = [
                e for k, e in rlc_factory.all_entities() if k[0] == uid
            ]
            if not entities_for_ue:
                continue
            # 簡化：平均分配 budget 給此 UE 的所有 RLC entity
            per_entity = max(1, budget // len(entities_for_ue))
            total_actual = 0
            for ent in entities_for_ue:
                try:
                    actual = ent.generate_pdu(per_entity)
                    if isinstance(actual, int) and actual > 0:
                        total_actual += actual
                except Exception as e:
                    logger.warning("RLC generate_pdu failed for ue=%s: %s", uid, e)
            actual_drained_map[uid] = total_actual

        # 3) Build & dispatch DL TTI request
        # cell_id_map: per-UE 的 serving cell（CU-CP 透過 F1AP 同步進 _ue_registry）
        # → emit 進 PDU.cell_id → RU 用這個當 serving label，不再用 Sionna argmax 自己挑.
        cell_id_map = {ue["id"]: ue.get("serving_cell", "") for ue in ues_for_measurement}
        dl_msg = build_dl_tti(
            sfn=self.status.sfn,
            slot=self.status.slot,
            rb_alloc=rb_alloc_global,
            mcs_map=mcs_map,
            tbs_map=tbs_map,
            cell_id_map=cell_id_map,
        )
        dispatched = RuClientBusinessService.post_dl_tti_request(encode_dl_tti(dl_msg))

        # 4) Accumulate PM (per-gNB cumulative + per-UE rolling window)
        # 跑 ues_for_measurement: 沒 traffic 的 UE 仍要 accumulate SINR/RSRP/MCS,
        # 否則 MeasurementReport flush 時拿不到 fresh sample, RIC KPM 會凍結.
        # prb_dl / dl_bytes 對 measurement-only UE 自然 0 (rb_alloc=0), throughput 不假裝.
        # ★ dl_bytes 用 actual_drained_map (RLC 真實 drain 的 byte) 不用 tbs_map (理論 capacity).
        # 對齊 OAI: stats counter 統計 mac_rlc_data_req return 的 actual_pdu_bytes,
        # 不是 nr_compute_tbs() 的理論 capacity. 這樣不同 traffic rate 才會在 KPM 反映出來.
        pm = get_pm_aggregator()
        for ue in ues_for_measurement:
            uid = ue["id"]
            actual_dl = actual_drained_map.get(uid, 0)
            pm.accumulate_ue(
                gnb_name=ue["serving_cell"],
                ue_id=uid,
                mcs_dl=mcs_map.get(uid, 9),
                mcs_ul=max(0, mcs_map.get(uid, 9) - 2),
                sinr_db=ue["sinr_db"],
                rsrp_dbm=ue["rsrp_dbm"],
                prb_dl=rb_alloc_global.get(uid, 0),
                prb_ul=rb_alloc_global.get(uid, 0) // 5,
                dl_bytes=actual_dl,
                ul_bytes=actual_dl // 5,
                qos_5qi=ue["qos_5qi"],
                rank=ue.get("rank", 1),
            )
        # 4b) Accumulate RLC SDU delay (從 step 1 收的 samples)
        for uid, delays in delay_by_ue.items():
            pm.accumulate_rlc_delay(uid, delays)
        # DEBUG (commented out — enable to trace per-tick PM)
        if False and (ues_with_bo or delay_by_ue):
            logger.info(
                "[tick %d] ues_with_bo=%s delays=%s rb_alloc=%s tbs=%s",
                self.status.tick_count,
                [(u["id"], bo_by_ue.get(u["id"], 0)) for u in ues_with_bo],
                {uid: len(d) for uid, d in delay_by_ue.items()},
                rb_alloc_global,
                {uid: tbs_map.get(uid, 0) for uid in (u["id"] for u in ues_with_bo)},
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
                # 帶 neighbor measurements — 從 _ue_registry 拿緩存的最新 RU CQI 樣本
                ue_state = self._ue_registry.get(uid, {})
                neighbor_dicts = ue_state.get("neighbors") or []
                neighbor_meas_list = [
                    NeighborMeas(
                        cell_id=n.get("cell_id", ""),
                        rsrp_dbm=float(n.get("rsrp_dbm", -120.0)),
                        rsrq_db=float(n.get("rsrq_db", 0.0)),
                    )
                    for n in neighbor_dicts
                    if n.get("cell_id")
                ]

                report = GnbDuMeasurementReport(
                    ue_id=uid,
                    rsrp_dbm=w["avg_rsrp_dbm"],
                    sinr_db=w["avg_sinr_db"],
                    throughput_dl_mbps=w["throughput_dl_mbps"],
                    throughput_ul_mbps=w["throughput_ul_mbps"],
                    mcs_dl=w["avg_mcs_dl"],
                    rb_width_dl=w["avg_prb_dl"],
                    mimo_rank=w["avg_rank"],
                    pdcp_sdu_volume_dl=w.get("pdcp_sdu_volume_dl", 0),
                    pdcp_sdu_volume_ul=w.get("pdcp_sdu_volume_ul", 0),
                    rlc_sdu_delay_dl_ms=w.get("rlc_sdu_delay_dl_ms", 0.0),
                    neighbor_cells=neighbor_meas_list,    # ★ A3 evaluator 終於有料
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
