"""RrcEventTracker — 從 UE 出現/消失/換 serving 推 RRC 信令事件計數器。

對應 OAI RRC 的事件計數（OAI 實作位於 openair2/RRC/NR/）。我們沒有真 RRC
狀態機，用跨 tick 的 serving_gnb 變化和 UE presence 變化近似。

追蹤事件（對齊 E2.md pm 欄位）：
  RRC.ConnEstabAtt / ConnEstabSucc         — UE 首次出現
  RRC.ConnMax / ConnMean                   — 當下連線 UE 數統計
  MM.HoExeIntraFreqReq / HoExeIntraFreqSucc — 真 A3 TTT 觸發後的 HO
  MM.HoPrepIntraReq / HoPrepIntraSucc       — 同上
  gnb.MR.Event.A3                           — A3 事件實際觸發次數
  SM.PDUSessionSetupReq / Succ              — UE 首次出現 → 1 session
  UECNTX.Release.5GCinit.sum                — UE 消失
  DRB.EstabAtt / EstabSucc                  — 假設每 UE 建 1 DRB

HO 判定 — 對齊 3GPP TS 38.331 §5.5.4.4 Event A3：
  觸發條件：Mn + Ofn + Ocn − Hys > Mp + Ofp + Ocp + Off
           簡化：neighbor_rsrp − hys > serving_rsrp + offset
  持續時間：必須持續 timeToTrigger (TTT, 預設 160 ms) 才觸發

狀態機（per UE, per neighbor）：
  idle → (condition met) → pending (t=0)
  pending → (still met, t < TTT) → pending (t += tick_ms)
  pending → (still met, t >= TTT) → TRIGGERED + 轉 idle
  pending → (not met) → idle
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_float, get_int
from main.utils.logger import get_logger


logger = get_logger(__name__)


# 3GPP A3 預設值（TS 38.331 §6.3.2 ReportConfigNR > eventA3）
HO_A3_OFFSET_DB = 3.0      # offset (a3-Offset)
HO_A3_HYSTERESIS_DB = 1.0  # hysteresis (hysteresis)
HO_TTT_MS = 160             # timeToTrigger (timeToTrigger)
HO_SUCC_SINR_THRESH = 3.0  # HO 執行後 SINR > 3 dB 視為 Succ


@dataclass
class _A3PendingState:
    """per (UE, neighbor_gnb) 的 A3 觸發計時。"""
    neighbor_name: str
    first_met_ms: int    # 條件首次滿足時間戳
    # 若條件中斷就 pop 這個 entry


@dataclass
class _UeHoState:
    """per UE 的 HO 追蹤狀態。"""
    serving: str | None = None
    # 每個正在 pending 的 (neighbor) 有一個計時器
    pending_a3: dict[str, _A3PendingState] = field(default_factory=dict)


class RrcEventTracker:
    """stateful per-service singleton。加入 A3 TTT 真實 handover 判定。"""

    def __init__(self) -> None:
        self._ever_seen: set[str] = set()
        self._counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._conn_count_ewma: dict[str, float] = defaultdict(float)
        self._conn_max: dict[str, int] = defaultdict(int)

        # 新增 A3 狀態機 per UE
        self._ue_ho_state: dict[str, _UeHoState] = {}

        # 允許 env 覆蓋預設
        self._a3_offset_db = get_float("HO_A3_OFFSET_DB", default=HO_A3_OFFSET_DB)
        self._a3_hys_db = get_float("HO_A3_HYSTERESIS_DB", default=HO_A3_HYSTERESIS_DB)
        self._ttt_ms = get_int("HO_TTT_MS", default=HO_TTT_MS)

    def reset(self) -> None:
        self._ever_seen.clear()
        self._counters.clear()
        self._conn_count_ewma.clear()
        self._conn_max.clear()
        self._ue_ho_state.clear()

    def on_tick(self, ue_status_list: list[dict[str, Any]]) -> None:
        """每 tick 呼叫。輸入 compute_result 的 ue_status[] list。"""
        now_ms = TimestampService.now_ms()

        current_ues_per_gnb: dict[str, set[str]] = defaultdict(set)
        current_ue_ids: set[str] = set()

        for ue in ue_status_list:
            uid = ue["ue_id"]
            serving = ue["serving_gnb"]
            sinr = ue.get("sinr_db", 0.0)
            rsrp_serving = ue.get("rsrp_dbm", -999)
            all_rsrp = ue.get("all_rsrp", {})
            current_ue_ids.add(uid)
            current_ues_per_gnb[serving].add(uid)

            # RRC.ConnEstab — 首次看到
            if uid not in self._ever_seen:
                self._counters[serving]["RRC.ConnEstabAtt.sum"] += 1
                self._counters[serving]["RRC.ConnEstabAtt.mo-Data"] += 1
                self._counters[serving]["RRC.ConnEstabSucc.sum"] += 1
                self._counters[serving]["RRC.ConnEstabSucc.mo-Data"] += 1
                self._counters[serving]["SM.PDUSessionSetupReq"] += 1
                self._counters[serving]["SM.PDUSessionSetupSucc"] += 1
                self._counters[serving]["DRB.EstabAtt.sum"] += 1
                self._counters[serving]["DRB.EstabAtt.5QI9"] += 1
                self._counters[serving]["DRB.EstabSucc.sum"] += 1
                self._counters[serving]["DRB.EstabSucc.5QI9"] += 1
                self._ever_seen.add(uid)
                logger.debug("UE %s registered to %s", uid, serving)

            # 取 / 建 UE 的 HO state
            ho_state = self._ue_ho_state.setdefault(uid, _UeHoState())
            # 若 serving 在別處被強制換（例：UE 原本在 gNB_A，突然出現在 gNB_B）
            # 這不是 A3 TTT 觸發，而是物理 argmax(RSRP) 本身跳了；算直接切換
            serving_changed_externally = (
                ho_state.serving is not None and ho_state.serving != serving
            )

            # ── A3 TTT 狀態機更新 ─────────────────────────────
            # 條件：neighbor_rsrp − hys > serving_rsrp + offset
            triggered_neighbor: str | None = None
            for nb_name, nb_rsrp in all_rsrp.items():
                if nb_name == serving:
                    continue
                condition_met = (nb_rsrp - self._a3_hys_db) > (rsrp_serving + self._a3_offset_db)

                pending = ho_state.pending_a3.get(nb_name)
                if condition_met:
                    if pending is None:
                        # 首次滿足 → 開始計時
                        ho_state.pending_a3[nb_name] = _A3PendingState(
                            neighbor_name=nb_name, first_met_ms=now_ms,
                        )
                    else:
                        # 持續滿足 → 檢查是否到 TTT
                        elapsed = now_ms - pending.first_met_ms
                        if elapsed >= self._ttt_ms:
                            # 觸發！
                            triggered_neighbor = nb_name
                            self._counters[serving]["gnb.MR.Event.A3"] += 1
                            self._counters[serving]["MM.HoPrepIntraReq"] += 1
                            self._counters[serving]["MM.HoPrepIntraSucc"] += 1
                            # 計數 HO 執行
                            self._counters[serving]["MM.HoExeIntraFreqReq"] += 1
                            self._counters[serving]["MM.HoExeIntraReq"] += 1
                            if sinr > HO_SUCC_SINR_THRESH:
                                self._counters[serving]["MM.HoExeIntraFreqSucc"] += 1
                                self._counters[serving]["MM.HoExeIntraSucc"] += 1
                            logger.info(
                                "A3 TTT triggered: UE %s %s→%s (sinr=%.1f, elapsed=%dms)",
                                uid, serving, nb_name, sinr, elapsed,
                            )
                            # 清掉這個 UE 所有 pending（HO 完成）
                            ho_state.pending_a3.clear()
                            break
                else:
                    # 條件中斷 → 清除 pending
                    if pending is not None:
                        ho_state.pending_a3.pop(nb_name, None)

            # ── 外部 serving 切換：直接算 HO（不經 TTT）─────────
            # 這情境是：UE 瞬間換 serving cell 但不是我們觸發的
            # 通常發生在 UE 位置突變 / reload 後
            if serving_changed_externally and triggered_neighbor is None:
                prev = ho_state.serving
                assert prev is not None
                self._counters[prev]["MM.HoExeIntraFreqReq"] += 1
                self._counters[prev]["MM.HoExeIntraReq"] += 1
                if sinr > HO_SUCC_SINR_THRESH:
                    self._counters[prev]["MM.HoExeIntraFreqSucc"] += 1
                    self._counters[prev]["MM.HoExeIntraSucc"] += 1
                logger.info("External HO: UE %s %s→%s", uid, prev, serving)
                ho_state.pending_a3.clear()

            ho_state.serving = serving

        # 偵測離線 UE
        gone = set(self._ue_ho_state) - current_ue_ids
        for uid in gone:
            st = self._ue_ho_state.pop(uid)
            if st.serving:
                self._counters[st.serving]["UECNTX.Release.5GCinit.sum"] += 1

        # 更新每 gNB 的 ConnMax / ConnMean
        for gnb_name, ues in current_ues_per_gnb.items():
            n = len(ues)
            if n > self._conn_max[gnb_name]:
                self._conn_max[gnb_name] = n
            prev_ewma = self._conn_count_ewma[gnb_name]
            self._conn_count_ewma[gnb_name] = 0.9 * prev_ewma + 0.1 * n

        # 把 ConnMax / ConnMean 寫進 counters
        for gnb_name in set(list(self._conn_max.keys()) + list(self._counters.keys())):
            self._counters[gnb_name]["RRC.ConnMax"] = self._conn_max[gnb_name]
            self._counters[gnb_name]["RRC.ConnMean"] = int(round(self._conn_count_ewma[gnb_name]))

    def snapshot(self) -> dict[str, dict[str, int]]:
        """回傳目前所有 gNB 的計數器 snapshot（deep copy）。"""
        return {name: dict(counters) for name, counters in self._counters.items()}
