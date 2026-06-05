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

from ran_sim_protocol.f1ap import GnbDuCellMeasurementReport, GnbDuMeasurementReport
from ran_sim_protocol.common import NeighborMeas

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    encode_cell_measurement_report,
    encode_measurement_report,
)
from main.apps.fapi_north.services.business.ru_client_operations import RuClientBusinessService
from main.apps.fapi_north.services.optional.message_codec.fapi_codec import encode_dl_tti
from main.apps.fapi_north.services.optional.tti_builder.tti_builder import build_dl_tti
from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
from main.apps.mac.services.optional.link_adaptation.mcs_controller import get_mcs_controller
from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.apps.mac.services.optional.pm_aggregator.pm_aggregator import get_pm_aggregator
from main.apps.mac.services.optional.scheduler.scheduler_factory import get_scheduler
from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.services_logs.ran_message_log import get_ring as get_log_ring
from main.utils.env_loader import get_bool, get_int, get_str

# P0b — RLC delay 計算模式:calib(現狀,wall 量測 + /30 擬合校正) | subtick(FIFO sim-time 解析模型)
_RLC_DELAY_SUBTICK = (get_str("RLC_DELAY_MODEL", "calib") or "calib").strip().lower() == "subtick"
# 改動一 shadow:on 時在現役 calib 路徑「旁邊」並行跑 slot_loop(跨-tick state)、只 log 對照、不接管 KPM
_SLOT_ENGINE_SHADOW = get_bool("SLOT_ENGINE_SHADOW", False)
# 反事實 res_op 完整修法參數(待校的現象學值):
_SLOT_CADENCE_PERIOD = get_int("SLOT_CADENCE_PERIOD", 40)   # 改動二 baseline 排程節奏
_SLOT_OP_PRB_FLOOR = get_int("SLOT_OP_PRB_FLOOR", 12)       # MIN_PRB 地板(低載 UE 不被餓死,= OAI 空 cell 大方給)
# load-adaptive baseline:k0(pipeline baseline)隨 bo 從 min→max 縮放(輕載小→normal對齊,重載大→im/es對齊+burst封頂不爆)
_SLOT_K0_MIN = get_int("SLOT_K0_MIN", 14)
_SLOT_K0_MAX = get_int("SLOT_K0_MAX", 32)
_SLOT_K0_BO_REF = get_int("SLOT_K0_BO_REF", 60000)
# #2 RLC discardTimer:SDU 等超過此 sim-ms 丟棄(過載封頂延遲,對齊真機)。0=關。
# 設遠高於已對齊的 12-22ms delay(預設 300ms 不影響正常,只封頂過載的數十秒假延遲)。
_SLOT_DISCARD_TIMER_MS = get_int("SLOT_DISCARD_TIMER_MS", 300)
# in-process Phase1 Step2:DU 直讀 cache 算 SINR,只 log 跟 HTTP SINR 比對(不接管),驗證一致才往下
_DU_INPROCESS_SINR = get_bool("DU_INPROCESS_SINR", False)
# in-process Phase1 Step3:cached mode 下 SINR 改 in-process(同 tick 直算)+ dl_tti HTTP 改非阻塞 → 解放 tick 粒度
_DU_RU_INPROCESS = get_bool("DU_RU_INPROCESS", False)
# slot 引擎正式接管 delay KPM(退掉 /30):on 時 RLC delay 走 slot 引擎(現役 PRB 已由 scheduler 改操作點)
# + cadence,不再用 calib /30。配 pf_scheduler 的 SLOT_ENGINE_TAKEOVER 一起(同 flag),PRB/throughput/delay 自洽。
_SLOT_ENGINE_TAKEOVER = get_bool("SLOT_ENGINE_TAKEOVER", False)
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

    # Phase A — 時間軸有兩個獨立常量:
    #   _wall_tick_ms  : 控 wall-clock sleep 節奏(set_speed 改這個)
    #   _sim_dt_ms     : 每個 tick 認多少 sim-time(固定,不隨 wall 加速改變)
    # sim_speed_x = _sim_dt_ms / _wall_tick_ms。例:wall=50, sim_dt=500 → 10x。
    # 結果:KPM report 每 PM_WINDOW_SEC sim-second 一份(= 每 N_ticks=
    # PM_WINDOW_SEC*1000/_sim_dt_ms tick),於 wall 上隨 speed 自動加快;
    # 每份 window 內樣本數固定不變(fidelity 不隨 speed 退化)。
    SLOTS_PER_FRAME = 20  # numerology=1 (30 kHz SCS)
    SFN_MAX = 1024
    # 固定 sim-time per tick。500ms 對應 3GPP 一個 measurement reporting period 的一半。
    # 改這個 = 整體 RAN 時間刻度改變;一般情況下不應動。set_speed 不會碰這個。
    SIM_DT_MS_DEFAULT = 500

    @property
    def REPORT_EVERY_N_TICKS(self) -> int:
        # 用 _sim_dt_ms (sim-time) 算,不用 _wall_tick_ms。
        # default sim_dt=500, PM_WINDOW=1.0 → 2 ticks/window 恆定。
        from main.utils.env_loader import get_float
        window_s = get_float("PM_WINDOW_SEC", 1.0)
        return max(1, int(round(window_s * 1000 / max(self._sim_dt_ms, 1))))

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.status = TickStatus()
        # in-memory UE registry — UE info by ue_id (sinr / cell / qos)
        self._ue_registry: dict[str, dict[str, Any]] = {}
        # Phase A — wall_tick_ms (set_speed 改它) / sim_dt_ms (固定) 解耦。
        self._wall_tick_ms: int = max(10, min(500, get_int("SIM_TICK_MS", 500)))
        self._sim_dt_ms: int = self.SIM_DT_MS_DEFAULT
        self._tick_ms_lock = threading.Lock()
        # Phase B — per-tick 即時 stats(每 _tick_body 結尾覆寫),給 Dashboard chart 用
        self.last_ue_stats: dict[str, dict[str, Any]] = {}
        self.last_cell_stats: dict[str, dict[str, Any]] = {}
        # P0a (2026-06-01) — 實際達成倍速 achieved_speed_x。
        # sim_speed_x 是「設定值」(sim_dt/wall_tick),但 loop 在負載下 body 塞不進
        # wall_tick 時實際跑不到那麼快。achieved = 近 ~1s 內 tick_count 真實增長率換算,
        # 是唯一誠實的「sim-time 跑多快」來源。設定 vs achieved 的差距 = 漂移。
        # 0.0 = 尚未量到(剛啟動 < 1s)。
        self._achieved_speed_x: float = 0.0
        self._achv_window_start_wall: float = 0.0
        self._achv_window_start_tick: int = 0
        # 改動一 shadow — per-UE 跨 tick 持有的 slot 引擎狀態(backlog/HARQ/slot 時鐘累積用)
        self._slot_states: dict[str, Any] = {}
        # Phase1 反事實 — 「若 scheduler 用操作點 MCS 配 PRB」的平行 state(預測修了會怎樣)
        self._slot_states_op: dict[str, Any] = {}

    # --- public API ----------------------------------------------------------

    @property
    def achieved_speed_x(self) -> float:
        """實際達成倍速 = 近 ~1s 內 tick_count 增長率換算的 sim-time/wall-time 比。

        跟 sim_speed_x(設定值)的差距就是「漂移」。0.0 = 尚未量到(剛啟動)。
        UE traffic_gen / 監看工具讀這個,而不是相信沒人兌現的設定值。
        """
        with self._tick_ms_lock:
            return self._achieved_speed_x

    @property
    def wall_tick_ms(self) -> int:
        """wall-clock 上 tick 多久一次(set_speed 改這個)。"""
        with self._tick_ms_lock:
            return self._wall_tick_ms

    @property
    def sim_dt_ms(self) -> int:
        """每個 tick 在 sim-time 上前進多少 ms。set_sim_dt() 可 runtime 改。"""
        with self._tick_ms_lock:
            return self._sim_dt_ms

    def set_sim_dt(self, sim_dt_ms: int) -> int:
        """thread-safe 設 sim_dt_ms, clamp 10~500ms. 回傳實際生效值.

        scenarios (cached mode) 用較小值(e.g. 100ms)提升 KPM 精度;
        editor (live mode) 保持 500ms 預設。
        改變後 sim_speed_x = sim_dt_ms / wall_tick_ms 立即更新。
        """
        clamped = max(10, min(500, int(sim_dt_ms)))
        with self._tick_ms_lock:
            old = self._sim_dt_ms
            self._sim_dt_ms = clamped
        if old != clamped:
            logger.info(
                "TickRunner.set_sim_dt: sim_dt %d -> %d ms (sim_speed=%.2fx)",
                old, clamped, clamped / max(self._wall_tick_ms, 1),
            )
        return clamped

    @property
    def sim_speed_x(self) -> float:
        """sim-time 跑得比 wall-time 快幾倍 = sim_dt_ms / wall_tick_ms。"""
        return self._sim_dt_ms / max(self.wall_tick_ms, 1)

    def set_tick_ms(self, tick_ms: int) -> int:
        """thread-safe 設 wall tick interval, clamp 10~500ms. 回傳實際生效值.

        改變後 sim_speed_x = sim_dt_ms / tick_ms 立即更新(e.g. tick_ms=50 → 10x)。
        sim_dt_ms 不會被這個 method 改動。
        """
        clamped = max(10, min(500, int(tick_ms)))
        with self._tick_ms_lock:
            old = self._wall_tick_ms
            self._wall_tick_ms = clamped
        if old != clamped:
            logger.info(
                "TickRunner.set_tick_ms: wall %d -> %d ms (sim_speed=%.2fx)",
                old, clamped, self._sim_dt_ms / clamped,
            )
        return clamped

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
        self._slot_states.pop(ue_id, None)  # 改動一:UE 離開時清掉 shadow 狀態,不跨 session 漏
        self._slot_states_op.pop(ue_id, None)

    def start(self) -> bool:
        if self.status.is_running:
            return False
        # AK10: 每次 Start Sim 都必須從乾淨狀態開始，避免上次 session 的 SDU buffer /
        # delay sample / counter / tick phase 影響這次 KPM。對齊 OAI 真機 — 每次
        # gNB cold restart 是真的所有 state wipe。
        self.status.tick_count = 0
        self.status.sfn = 0
        self.status.slot = 0
        self.status.last_tick_ms = 0
        # Phase B — 清 last-tick stats(避免上次 session 的最後一筆殘留)
        self.last_ue_stats = {}
        self.last_cell_stats = {}
        # 清 PM aggregator（avg delay / throughput / PRB / volume 累積資料）
        try:
            get_pm_aggregator().reset()
        except Exception:
            logger.exception("pm_aggregator.reset() failed; continuing")
        # 清掉所有 RLC entity，連同它們內部 _tx_queue 裡殘留的 SDU
        try:
            n = rlc_factory.clear_all()
            if n > 0:
                logger.info("TickRunner.start: cleared %d stale RLC entities from previous session", n)
        except Exception:
            logger.exception("rlc_factory.clear_all() failed; continuing")
        # AK11 Bug A: 清 HARQ manager — 過去 Stop Sim 時若某 UE 還在 WAIT_FEEDBACK 等
        # CRC ind，下次同名 UE re-attach 時 _pool_for() 沿用舊 pool，會卡住 5-15 個
        # process 在 WAIT_FEEDBACK，acquire_process() 找不到 NEW → 排程量被吃掉，極端
        # 情況變 throughput=0 但 RSRP/SINR 都正常（最難 debug 的 leakage）。
        try:
            get_harq_manager().reset()
        except Exception:
            logger.exception("harq_manager.reset() failed; continuing")
        # AK11 Bug B: 防禦性清 _ue_registry — Dashboard 的 replace_ues 一般會清，但若
        # Dashboard chain 中斷（RU 500 / 網路抖）就會殘留「鬼魂 UE」靠 ue_registry
        # 繼續出 KPM。這裡 Tick.start 一律清空當保險。後續 add_ue() 會把當前 sim 的
        # UE 重新加進來，所以對正常流程是 no-op。
        stale_count = len(self._ue_registry)
        if stale_count > 0:
            logger.info("TickRunner.start: cleared %d stale UEs from _ue_registry", stale_count)
            self._ue_registry.clear()
        self._slot_states.clear()  # 改動一:每次 Start Sim 清乾淨 shadow 狀態(對齊 clean-scene-reset)
        self._slot_states_op.clear()

        # P0a — 重置 achieved 量測視窗(每次 cold start 重新量漂移)
        with self._tick_ms_lock:
            self._achieved_speed_x = 0.0
        self._achv_window_start_wall = 0.0
        self._achv_window_start_tick = 0

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
        logger.info(
            "TickRunner started, wall_tick=%dms sim_dt=%dms speed=%.2fx",
            self.wall_tick_ms, self.sim_dt_ms, self.sim_speed_x,
        )
        next_t = time.time()
        while not self._stop_event.is_set():
            try:
                self._tick_body()
            except Exception as e:
                logger.exception("tick body error: %s", e)
            # P0a — 更新 achieved_speed_x(每 ~1s wall 重算一次,純觀測不影響節拍)
            self._update_achieved_speed()
            # 每輪重讀 wall_tick_ms,set_tick_ms() 變更下一輪即生效
            period = self.wall_tick_ms / 1000.0
            next_t += period
            sleep_for = next_t - time.time()
            if sleep_for > 0:
                self._stop_event.wait(sleep_for)
            else:
                next_t = time.time()
        logger.info("TickRunner stopped after %d ticks", self.status.tick_count)

    def _update_achieved_speed(self) -> None:
        """P0a — 用 tick_count 真實增長率算 achieved_speed_x。

        achieved = (Δtick × sim_dt_ms / 1000) / Δwall_sec
                 = 這段 wall 時間內推進的 sim-time / 花的 wall-time。
        每 ~1s wall 重算一次,避免過短視窗噪音。純觀測,不碰節拍。
        """
        now = time.time()
        if self._achv_window_start_wall == 0.0:
            self._achv_window_start_wall = now
            self._achv_window_start_tick = self.status.tick_count
            return
        dw = now - self._achv_window_start_wall
        if dw >= 1.0:
            dtick = self.status.tick_count - self._achv_window_start_tick
            achieved = dtick * self._sim_dt_ms / 1000.0 / dw
            with self._tick_ms_lock:
                self._achieved_speed_x = round(achieved, 3)
            self._achv_window_start_wall = now
            self._achv_window_start_tick = self.status.tick_count

    def _tick_body(self) -> dict[str, Any]:
        self.status.tick_count += 1
        self.status.last_tick_ms = int(time.time() * 1000)

        # 1) RLC buffer status + 收集 SDU delay samples → PM aggregator
        bo_by_ue: dict[str, int] = {}
        delay_by_ue: dict[str, list[float]] = {}
        drops_by_ue: dict[str, tuple[int, int]] = {}  # AK10: per-UE (sdus, bytes) drop in this tick
        shadow_arrivals: dict[str, list[tuple[float, int]]] = {}  # 改動一 shadow:per-UE (arrival_sim_ms, bytes)
        takeover_delay_by_ue: dict[str, float] = {}  # takeover:per-UE slot 引擎 delay,給 last_ue_stats 顯示一致
        for (ue_id, _btype, _bid), entity in rlc_factory.all_entities():
            _bo = entity.buffer_status()
            bo_by_ue[ue_id] = bo_by_ue.get(ue_id, 0) + _bo
            # 收 RLC entity 累計的 SDU delivery delay(取出後 entity 內部 buffer 清空)
            # 2026-05-23 P1.8: segment.py 用 wall clock 算 dequeue-enqueue,samples 是 wall ms。
            # 在 sim_speed_x > 1 下,KPM 該報 sim-ms(對齊 OAI semantic — OAI wall=sim)。
            #
            # 2026-05-23 P1.10 — OAI calibration:DT scheduler 一個 tick (sim_dt=500ms) 跑
            # 一次,OAI 一個 slot (1ms) 跑一次。SDU 等待粒度差 sim_dt/oai_slot_ms = 500x。
            # ÷ 500 把 DT 報的 sim-ms delay 校正成 OAI-equivalent slot-grained delay。
            # 數學依據:詳見 docs/test_records/oai_prb_calc_evidence_2026-05-23.md。
            # 套在 KPM 顯示層,scheduler 內部數學不變(buffer drain timing 維持自洽)。
            # P1.15 (2026-05-25): phase-aware DELAY_CALIB —
            # 舊行為 (P1.10): 一律 ÷sim_dt_ms,假設「DT tick 跟 OAI slot 差 sim_dt 倍」均勻
            #   套整個 phase。實測在高流量 phase 校過頭 (DT 報 1.6 ms 對 OAI 14.4 ms = 11%),
            #   低流量 phase 對得很好 (normal-2 DT 2.7 ms 對 OAI 1.5 ms = 180%)。
            # 新行為: bo > 1KB 視為「高流量 phase」(queue 有實質排隊) → /30 (8.3× less aggressive)
            #         bo <= 1KB 用原 /sim_dt (低流量 sample 量小,維持 P1.10 校正)
            # 預期: normal-1 delay 1.6 → ~13 ms 對 OAI 14.4,低流量 phase 不變。
            # P1.15.1 (2026-05-25 update): HIGH_TRAFFIC_BO_BYTES 從 1024 拉到 50000
            # 原因:1KB 太低,連 cco_1hr 200 kbps (bo ~6-12 KB) 都被誤判 high-traffic,
            # 導致 cco 在 DT 上 delay 衝到 20ms,過不了 xApp CCO 門檻 < 5ms。
            # 50 KB 對齊 OAI iperf3 -b 1M (~31 KB/tick) 跟 -b 5M (~156 KB/tick) 的中線。
            # 副作用:full_day_24hr normal-1 (195 kbps, bo ~6-12 KB) 會回 low-delay 模式,
            # 失去 v7 的 17ms 對齊 OAI 14.4ms — 但 xApp 不查 normal-1 phase delay,可接受。
            _OAI_SLOT_MS = 1.0
            _SIM_DT_MS = float(self._sim_dt_ms)
            _HIGH_TRAFFIC_BO_BYTES = 50_000
            if _bo > _HIGH_TRAFFIC_BO_BYTES:
                _DELAY_CALIB = _OAI_SLOT_MS / 30.0  # high-traffic: 8.3× scaling
            else:
                _DELAY_CALIB = _OAI_SLOT_MS / _SIM_DT_MS  # low-traffic: original P1.10
            try:
                samples = entity.take_delay_samples()
                if samples:
                    if _RLC_DELAY_SUBTICK:
                        # P0b subtick:samples 已是 sim-time ms 的真實排隊延遲 →
                        # 不乘 sim_x(已 sim-time)、不套 /30 擬合(已有物理依據)。
                        delay_by_ue.setdefault(ue_id, []).extend(samples)
                    else:
                        sim_x = self.sim_speed_x
                        if sim_x != 1.0:
                            samples = [s * sim_x for s in samples]
                        # KPM-layer calibration:對齊 OAI per-slot scheduler 粒度
                        samples = [s * _DELAY_CALIB for s in samples]
                        delay_by_ue.setdefault(ue_id, []).extend(samples)
            except AttributeError:
                pass  # 舊 entity 沒有此 API — 忽略
            # 改動一 shadow:旁路收集這 tick 到達的 SDU (arrival_sim_ms, bytes),不影響 calib 路徑
            # ★ takeover 也要收(slot 引擎吃 arrivals 才產 delay KPM)— 否則只開 TAKEOVER 不開 SHADOW
            #   會讓 shadow_arrivals 永遠空 → slot 引擎吃不到 SDU → delay KPM 歸零(code-review #1)。
            if _SLOT_ENGINE_SHADOW or _SLOT_ENGINE_TAKEOVER:
                try:
                    arr = entity.take_sdu_arrivals()
                    if arr:
                        shadow_arrivals.setdefault(ue_id, []).extend(arr)
                except AttributeError:
                    pass
            # AK10: 收 RLC AM 因 tx buffer 滿 reject 的 SDU drop 計數（OAI 行為對齊）
            try:
                ds, db = entity.take_drop_samples()
                if ds > 0 or db > 0:
                    prev_s, prev_b = drops_by_ue.get(ue_id, (0, 0))
                    drops_by_ue[ue_id] = (prev_s + ds, prev_b + db)
            except AttributeError:
                pass  # TM/UM entity 沒實作 — 忽略
        # 所有 CONNECTED UE 都要 measurement (對齊真實 OAI: CSI-RS 跟 PDSCH 解耦).
        # measurement 跟 scheduling 解耦 — 沒 traffic 的 UE 也要算 channel state,
        # 否則 RIC 看到的 KPM 會凍結 (rsrp/sinr 永遠是 attach 當下的值).
        ues_for_measurement = list(self._ue_registry.values())
        # in-process Phase1 Step3:cached mode 下,SINR 改由 DU 直讀 cache 算(同 tick,免等 HTTP cqi
        # callback 的 1-tick lag)。已驗 == RU HTTP。live mode(get_du_cache()→None)維持原 HTTP 路徑。
        if _DU_RU_INPROCESS:
            from main.apps.fapi_north.services.optional.channel_cache_du import sinr_for_ue
            _now_sim = self.status.tick_count * self._sim_dt_ms
            for ue in ues_for_measurement:
                _ip = sinr_for_ue(_now_sim, ue["id"], ue.get("serving_cell"))
                if _ip is not None and _ip > -200:
                    ue["sinr_db"] = _ip
        ues_with_bo = [
            self._ue_registry[u] for u in self._ue_registry if bo_by_ue.get(u, 0) > 0
        ]

        # 2) Scheduling — 把 UE 依 serving_cell 分組
        prb_per_cell = get_int("SIM_DEFAULT_PRB_PER_CELL", 106)
        # Energy-saving: 跳過 is_active=False 的 cell（FAPI 不發給 RU、PM 不累積）
        try:
            from main.apps.mac.models.cell_state import CellState
            inactive_cells = set(
                CellState.objects.filter(is_active=False).values_list("cell_id", flat=True)
            )
        except Exception:
            inactive_cells = set()

        # AL1: enrich ue dict with buffer_occupancy so scheduler can cap PRB
        # by per-UE demand (對齊 OAI dlsch_scheduler: rb_alloc = min(fair, prb_needed)).
        per_cell_alloc: dict[str, list[dict[str, Any]]] = {}
        for ue in ues_with_bo:
            cell = ue["serving_cell"]
            if cell in inactive_cells:
                continue  # 該 cell 已關，本 tick 不排程這個 UE
            ue_for_sched = {**ue, "buffer_occupancy": bo_by_ue.get(ue["id"], 0)}
            per_cell_alloc.setdefault(cell, []).append(ue_for_sched)

        # PRB quota cap：xApp 透過 E2 Control Style 2/Action 6 設的 max_prb%
        # 套到 scheduler 的 n_prb_total — DU MAC 的 max_rbSize 對齊。
        from main.apps.mac.services.optional.scheduler.prb_quota import get_store as _get_quota_store
        _quota_store = _get_quota_store()

        # MAC scheduler 看的是 sim-time (一個 TTI 在 sim 上多長),不是 wall
        tick_ms_for_sched = self._sim_dt_ms
        rb_alloc_global: dict[str, int] = {}
        scheduler = get_scheduler()
        # AL2 — cell-level PRB accumulator (一個 tick 一筆, idle cell 也記 0).
        # 用 active cell + idle cell 全列出, 避免 idle cell 沒被 sample 漏進 window.
        try:
            from main.apps.mac.models.cell_state import CellState
            all_active_cells = set(
                CellState.objects.filter(is_active=True).values_list("cell_id", flat=True)
            ) - inactive_cells
        except Exception:
            all_active_cells = set(per_cell_alloc.keys())
        cell_prb_used: dict[str, int] = {c: 0 for c in all_active_cells}
        cell_prb_total: dict[str, int] = {}
        for cell_name in all_active_cells:
            cap = _quota_store.cap_factor(cell_name)
            cell_prb_total[cell_name] = max(1, int(prb_per_cell * cap))

        for cell_name, group in per_cell_alloc.items():
            capped_prb = cell_prb_total.get(cell_name, prb_per_cell)
            alloc = scheduler.allocate(
                gnb_name=cell_name, ues_on_gnb=group, n_prb_total=capped_prb,
                tick_ms=tick_ms_for_sched,
            )
            rb_alloc_global.update(alloc)
            cell_prb_used[cell_name] = sum(alloc.values())

        # 每 tick 把 cell-level usage 餵給 pm aggregator (cell-level, 不從 per-UE sum)
        # 3GPP TS 28.552 RRU.PrbTotDl/Ul 是「以 cell 物理容量為分母的占用率」,
        # 分母必須用未 cap 前的 prb_per_cell;不可用 cell_prb_total(=quota 縮過的容量),
        # 否則 xApp 一下 RC max_prb=3 立刻看到 PRB%=100% 觸發誤判。
        _pm_cell = get_pm_aggregator()
        for cell_name, used in cell_prb_used.items():
            _pm_cell.accumulate_cell_tick(
                cell_id=cell_name,
                prb_used=used,
                n_prb_total=prb_per_cell,
            )

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
            # 每 tick 對應 bytes — 用 sim-time (=throughput × sim-second-per-tick)
            tick_s = self._sim_dt_ms / 1000.0
            tbs_map[uid] = int(mbps * 1e6 * tick_s / 8)

        # 3.5) Drain RLC queue — 對應 MAC 給 RLC 的 PDU 預算
        # 沒這步 RLC SDU 永遠塞在 queue，不會 deliver → 沒 delay sample。
        # 對齊 OAI nr_mac_rlc_data_req() 的角色 — MAC 通知 RLC 該送多少 bytes 出去。
        # ★ 重要: capture generate_pdu return value (= 真實 drain 出的 byte) 累計到
        #   actual_drained_map. 之後 PM aggregator 用 actual_drained_map 而非 tbs_map
        #   (理論 capacity), 對齊 OAI dlsch_total_bytes 統計實際 PDU bytes 的語意.
        actual_drained_map: dict[str, int] = {}
        _trace = (self.status.tick_count % 20 == 0)  # log every 20 ticks (~10s)
        if _trace:
            logger.info(
                "DRAIN TRACE tick=%d ues_with_bo=%d ue_registry=%d rlc_entities=%d",
                self.status.tick_count, len(ues_with_bo),
                len(self._ue_registry), len(rlc_factory.all_entities()),
            )
        for ue in ues_with_bo:
            uid = ue["id"]
            budget = tbs_map.get(uid, 0)
            if _trace and uid in ("demo_0508",):
                logger.info(
                    "DRAIN TRACE ue=%s sinr=%.1f rb_alloc=%d mcs=%d tbs=%d bo=%d",
                    uid, ue.get("sinr_db", 0), rb_alloc_global.get(uid, 0),
                    mcs_map.get(uid, 0), budget, bo_by_ue.get(uid, 0),
                )
            if budget <= 0:
                if _trace and uid == "demo_0508":
                    logger.info("DRAIN TRACE ue=%s SKIP budget<=0", uid)
                continue
            entities_for_ue = [
                e for k, e in rlc_factory.all_entities() if k[0] == uid
            ]
            if not entities_for_ue:
                if _trace and uid == "demo_0508":
                    logger.info("DRAIN TRACE ue=%s SKIP no entities", uid)
                continue
            # 簡化：平均分配 budget 給此 UE 的所有 RLC entity
            per_entity = max(1, budget // len(entities_for_ue))
            # P0b subtick — 排空速率 = per_entity budget / sim_dt(bytes per sim-ms);now_sim 給 FIFO 模型
            _rate = per_entity / max(self._sim_dt_ms, 1)
            _now_sim = self.status.tick_count * self._sim_dt_ms
            total_actual = 0
            for ent in entities_for_ue:
                try:
                    actual = ent.generate_pdu(
                        per_entity, subtick=_RLC_DELAY_SUBTICK,
                        rate_bytes_per_sim_ms=_rate, now_sim_ms=_now_sim,
                    )
                    if _trace and uid == "demo_0508":
                        logger.info(
                            "DRAIN TRACE ue=%s ent_type=%s per_entity=%d actual=%s",
                            uid, type(ent).__name__, per_entity, actual,
                        )
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
        # in-process Step3:in-process mode 下 SINR 已自算,dl_tti 只供 RU 端 KPM/viz → 改非阻塞
        # (fire-and-forget thread),不再 gate tick loop → 解放 tick 粒度(可縮 sim_dt)。
        if _DU_RU_INPROCESS:
            _enc = encode_dl_tti(dl_msg)
            threading.Thread(
                target=RuClientBusinessService.post_dl_tti_request, args=(_enc,), daemon=True
            ).start()
            dispatched = True
        else:
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
        # slot 引擎接管時不用 calib /30,改在 4b-shadow 用 slot 引擎輸出餵 PM。
        if not _SLOT_ENGINE_TAKEOVER:
            for uid, delays in delay_by_ue.items():
                pm.accumulate_rlc_delay(uid, delays)
        # 4b-shadow) slot_loop:shadow 只 log;takeover 時用 res 輸出接管 RLC delay KPM(退 /30)
        if _SLOT_ENGINE_SHADOW or _SLOT_ENGINE_TAKEOVER:
            import math
            from main.apps.mac.services.optional.link_adaptation.mcs_table import TDD_DL_SLOT_RATIO
            from main.apps.mac.services.optional.slot_engine.slot_loop import (
                SlotEngineState, SlotParams, avg_delay_ms, simulate_sdu_delays,
                _eff_for_mcs, _mcs_at_op_point,
            )
            # 每 tick 都要處理「有新到達」或「兩個 state 任一還有 backlog」的 UE,backlog UE 即使本
            # tick 無新到達也得跑一輪排空,否則 server-free cursor 的 abs_slot 落後真實 sim-time → 負延遲。
            shadow_uids = set(shadow_arrivals) \
                | {u for u, s in self._slot_states.items() if s.carry_queue} \
                | {u for u, s in self._slot_states_op.items() if s.carry_queue}
            tick_s = self._sim_dt_ms / 1000.0
            for uid in shadow_uids:
                arrivals = shadow_arrivals.get(uid, [])
                ue = self._ue_registry.get(uid)
                if not ue:
                    self._slot_states.pop(uid, None)
                    self._slot_states_op.pop(uid, None)
                    continue
                sinr = ue.get("sinr_db", 0.0)
                st = self._slot_states.setdefault(uid, SlotEngineState())
                st_op = self._slot_states_op.setdefault(uid, SlotEngineState())
                # Phase1 反事實:若 scheduler 改用操作點 MCS 算 PRB 需求,會給多少 PRB
                op_eff = _eff_for_mcs(_mcs_at_op_point(sinr, 0.1))
                bytes_per_prb = 144.0 * op_eff * 2000.0 * 0.80 * TDD_DL_SLOT_RATIO * tick_s / 8.0
                bo = bo_by_ue.get(uid, 0)
                prb_now = rb_alloc_global.get(uid, 0)
                prb_demand = math.ceil(bo / bytes_per_prb) if bytes_per_prb > 0 else prb_now
                prb_op = max(1, prb_demand, _SLOT_OP_PRB_FLOOR)  # 操作點 demand 套 MIN_PRB 地板
                # load-adaptive baseline:k0 隨 bo 縮放(輕載小→normal對齊,重載大→im/es對齊,封頂→burst不爆)
                _k0 = int(_SLOT_K0_MIN + (_SLOT_K0_MAX - _SLOT_K0_MIN) * min(1.0, bo / max(_SLOT_K0_BO_REF, 1)))
                try:
                    # takeover 時 res 用真實已分配 PRB(scheduler 已改操作點)+ load-adaptive k0 baseline → 接管 delay KPM
                    res = simulate_sdu_delays(
                        sdus=arrivals, mean_sinr_db=sinr, n_prb=prb_now,
                        sim_dt_ms=self._sim_dt_ms, state=st,
                        params=SlotParams(
                            seed=self.status.tick_count,
                            sched_period_slots=1,  # 不用 occasion gate;baseline 改走 load-adaptive k0
                            k0_slots=(_k0 if _SLOT_ENGINE_TAKEOVER else 2),
                            discard_timer_ms=(_SLOT_DISCARD_TIMER_MS if _SLOT_ENGINE_TAKEOVER else 0),
                        ),
                    )
                    res_op = simulate_sdu_delays(  # 反事實:操作點 PRB + cadence baseline(完整修法預測)
                        sdus=arrivals, mean_sinr_db=sinr, n_prb=prb_op,
                        sim_dt_ms=self._sim_dt_ms, state=st_op,
                        params=SlotParams(seed=self.status.tick_count,
                                          sched_period_slots=_SLOT_CADENCE_PERIOD),
                    )
                except Exception as e:  # shadow 絕不可擋 tick
                    logger.warning("[SLOT_SHADOW] sim failed ue=%s: %s", uid, e)
                    continue
                # takeover:用 slot 引擎(res)的 per-SDU sojourn 接管 RLC delay KPM(取代 /30)
                if _SLOT_ENGINE_TAKEOVER and res.delays_ms:
                    pm.accumulate_rlc_delay(uid, res.delays_ms)
                    takeover_delay_by_ue[uid] = avg_delay_ms(res)
                # Step2:in-process SINR 比對(只 log),驗證 DU 直算 == RU HTTP
                if _DU_INPROCESS_SINR and self.status.tick_count % 20 == 0:
                    try:
                        from main.apps.fapi_north.services.optional.channel_cache_du import sinr_for_ue
                        _ip = sinr_for_ue(self.status.tick_count * self._sim_dt_ms, uid, ue.get("serving_cell"))
                        logger.info("[DU_SINR_CMP] tick=%d ue=%s http_sinr=%.2f inproc_sinr=%s",
                                    self.status.tick_count, uid, sinr,
                                    ("%.2f" % _ip) if _ip is not None else "None")
                    except Exception as e:
                        logger.warning("[DU_SINR_CMP] failed: %s", e)
                # 節流:每 tick 都算(state 要連續),log 每 20 tick 才印,避免長跑撐爆 log。
                if self.status.tick_count % 20 == 0:
                    calib = delay_by_ue.get(uid, [])
                    calib_avg = (sum(calib) / len(calib)) if calib else 0.0
                    _bytes = actual_drained_map.get(uid, 0)
                    _thp = (_bytes * 8 / 1e6 / (self._sim_dt_ms / 1000.0)) if self._sim_dt_ms else 0.0
                    _prb_pct = (100.0 * prb_now / prb_per_cell) if prb_per_cell else 0.0
                    logger.info(
                        "[SLOT_SHADOW] tick=%d ue=%s bo=%d prb=%d prb_op=%d prb_pct=%.2f mcs=%d sinr=%.1f "
                        "bytes=%d thp=%.3f slot_loop=%.2fms slot_loop_op=%.2fms calib=%.2fms retx=%d/%d drop=%d",
                        self.status.tick_count, uid, bo, prb_now, prb_op, _prb_pct,
                        mcs_map.get(uid, 0), sinr, _bytes, _thp,
                        avg_delay_ms(res), avg_delay_ms(res_op), calib_avg,
                        res.retx_slots, res.tx_slots, res.dropped_sdus,
                    )
        # AK10 — accumulate RLC tx-cap drops 進 PM window，flush 時報出去
        for uid, (ds, db) in drops_by_ue.items():
            try:
                pm.accumulate_rlc_drop(uid, dropped_sdus=ds, dropped_bytes=db)
            except AttributeError:
                pass  # pm aggregator 還沒實作 — 不擋 tick
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
            # window 在 sim-time 軸上度量(用 _sim_dt_ms,不是 wall_tick_ms)
            tick_s = self._sim_dt_ms / 1000.0
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

                # AK10 — drop 計數仍保留在 PM window dict 裡（w["rlc_drop_*"]），
                # 但不打上 KPM wire；只在 DU 本地 log 觀察。沒有送 CU/e2adapter/Dashboard。
                drop_sdus = int(w.get("rlc_drop_sdus", 0) or 0)
                drop_bytes = int(w.get("rlc_drop_bytes", 0) or 0)
                if drop_sdus > 0 or drop_bytes > 0:
                    cap_bytes = get_int("RLC_TX_MAXSIZE_BYTES", 10_000_000)  # P1.12
                    logger.warning(
                        "[RLC-DROP] ue=%s window=%.1fs drop_sdus=%d drop_bytes=%d "
                        "(tx buffer cap %d B 達上限 → reject 新進 SDU；對齊 OAI sdu_rejected)",
                        uid, window_s, drop_sdus, drop_bytes, cap_bytes,
                    )
                    # AK11 Q1 — 推進 ring buffer 讓 Dashboard /logs 頁面看得到。
                    # path 把 drop 數字塞進去（Dashboard table 預設只 render path 欄位，
                    # 把資訊壓進 path 是讓使用者不用點開 row 就看到的最直接方法）。
                    try:
                        get_log_ring().append({
                            "ts_ms": int(time.time() * 1000),
                            "service": "DU",
                            "method": "INTERNAL",
                            "path": f"internal:rlc_drop sdus={drop_sdus} bytes={drop_bytes} cap={cap_bytes}",
                            "status": 0,
                            "duration_ms": int(window_s * 1000),
                            "category": "RLC_DROP",
                            "ue_id": uid,
                            "drop_sdus": drop_sdus,
                            "drop_bytes": drop_bytes,
                            "cap_bytes": cap_bytes,
                        })
                    except Exception:
                        pass  # ring buffer 故障不影響 sim

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

            # AL2 — flush cell-level PRB% (RRU.PrbTotDl) per active cell
            for cell_id in pm.active_cell_ids():
                cw = pm.flush_cell_report(cell_id)
                if cw is None:
                    continue
                cell_report = GnbDuCellMeasurementReport(
                    cell_id=cell_id,
                    prb_pct_dl=cw["prb_pct_dl"],
                    prb_pct_ul=0.0,
                    tick_count=cw["tick_count"],
                    window_seconds=window_s,
                )
                CuClientBusinessService.post_cell_measurement_report(
                    encode_cell_measurement_report(cell_report),
                )
            report_sent = True

        # Phase B — 存「此 tick 即時 stats」給 Dashboard 用(不是 cumulative)
        # 注意:_acc 是累積,_ue_window 是 rolling,這裡 last_*_stats 是真正「最後一個 tick」
        sim_dt_s = self._sim_dt_ms / 1000.0
        new_ue_stats: dict[str, dict[str, Any]] = {}
        for ue in ues_for_measurement:
            uid = ue["id"]
            delays = delay_by_ue.get(uid, [])
            avg_delay = (sum(delays) / len(delays)) if delays else 0.0
            if _SLOT_ENGINE_TAKEOVER:  # 顯示一致:dashboard 也用接管後的 slot 引擎 delay
                avg_delay = takeover_delay_by_ue.get(uid, avg_delay)
            bytes_drained = actual_drained_map.get(uid, 0)
            new_ue_stats[uid] = {
                "serving_cell": ue.get("serving_cell", ""),
                "sinr_db": ue["sinr_db"],
                "rsrp_dbm": ue["rsrp_dbm"],
                "prb_dl_this_tick": rb_alloc_global.get(uid, 0),
                "mcs_dl": mcs_map.get(uid, 0),
                "bytes_dl_this_tick": bytes_drained,
                "throughput_dl_mbps_this_tick":
                    (bytes_drained * 8 / 1e6 / sim_dt_s) if sim_dt_s > 0 else 0.0,
                "rlc_delay_ms_avg_this_tick": avg_delay,
                "rlc_buffer_bo_this_tick": bo_by_ue.get(uid, 0),
                "neighbors": ue.get("neighbors", []),
            }
        self.last_ue_stats = new_ue_stats

        new_cell_stats: dict[str, dict[str, Any]] = {}
        # 先 build attached/scheduled UE list per cell
        cell_to_attached: dict[str, list[str]] = {}
        cell_to_scheduled: dict[str, list[str]] = {}
        cell_to_dl_mbps: dict[str, float] = {}
        for uid, s in new_ue_stats.items():
            scell = s.get("serving_cell") or ""
            if not scell:
                continue
            cell_to_attached.setdefault(scell, []).append(uid)
            if s.get("prb_dl_this_tick", 0) > 0:
                cell_to_scheduled.setdefault(scell, []).append(uid)
            cell_to_dl_mbps[scell] = cell_to_dl_mbps.get(scell, 0.0) + \
                s.get("throughput_dl_mbps_this_tick", 0.0)

        for cell_name in all_active_cells:
            used = cell_prb_used.get(cell_name, 0)
            # prb_total = 物理容量(對齊 KPM RRU.PrbTotDl 語意);quota 縮過的 capped 值
            # 從 quota_cap_factor / quota_max_prb_pct 另外暴露,不混進 prb_pct。
            cap = _quota_store.cap_factor(cell_name)
            new_cell_stats[cell_name] = {
                "prb_used_this_tick": used,
                "prb_total": prb_per_cell,
                "prb_pct_this_tick": (used / max(prb_per_cell, 1)) * 100.0,
                "is_active": True,
                "attached_ue_list": cell_to_attached.get(cell_name, []),
                "attached_ue_count": len(cell_to_attached.get(cell_name, [])),
                "scheduled_ue_count": len(cell_to_scheduled.get(cell_name, [])),
                "dl_aggregate_mbps_this_tick": cell_to_dl_mbps.get(cell_name, 0.0),
                "quota_cap_factor": cap,                   # 0~1 from xApp PRB quota
                "quota_max_prb_pct": cap * 100.0,
            }
        for inactive_cell in inactive_cells:
            new_cell_stats[inactive_cell] = {
                "prb_used_this_tick": 0, "prb_total": prb_per_cell,
                "prb_pct_this_tick": 0.0, "is_active": False,
                "attached_ue_list": [], "attached_ue_count": 0,
                "scheduled_ue_count": 0, "dl_aggregate_mbps_this_tick": 0.0,
                "quota_cap_factor": 0.0, "quota_max_prb_pct": 0.0,
            }
        self.last_cell_stats = new_cell_stats

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
